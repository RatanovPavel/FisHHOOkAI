# routes/shop.py
import uuid
import os
import sys
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session
from yookassa import Configuration, Payment

# Настройка путей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from core.models import User
from config import (
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, 
    LEGAL_INFO, VERIFICATION_REWARD, SKULLA_TIERS,
    RETURN_URL, DISCOUNT_PROMOS
)

# Инициализация роутера
router = APIRouter(prefix="/api/shop", tags=["Shop & Payments"])

# Конфигурация ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# Зависимость БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 1. КОНФИГ И ТАРИФЫ ---
@router.get("/config")
async def get_frontend_config():
    return {
        "verification_reward_bones": VERIFICATION_REWARD,
        "tiers": SKULLA_TIERS,
        "legal": LEGAL_INFO, 
        "currency": "RUB"
    }

@router.get("/tiers")
async def get_shop_tiers():
    return {"tiers": SKULLA_TIERS}

# --- 2. ПРОМОКОДЫ НА СКИДКУ ---
@router.post("/promo/check")
async def check_discount_promo(code: str = Form(...)):
    code_clean = code.upper().strip()
    if code_clean in DISCOUNT_PROMOS:
        return {
            "status": "success", 
            "discount_percent": DISCOUNT_PROMOS[code_clean]
        }
    raise HTTPException(status_code=404, detail="PROMO_NOT_FOUND")

# --- 3. СОЗДАНИЕ ПЛАТЕЖА ---
@router.post("/payments/create")
async def create_payment(
    tier_id: str = Form(...), 
    email: str = Form(...), 
    promo: str = Form(None)
):
    # Убеждаемся, что ключи подтянуты
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    
    tier = next((t for t in SKULLA_TIERS if t['id'] == tier_id), None)
    if not tier:
        print(f"❌ [SHOP_ERR]: Пакет {tier_id} не найден!")
        raise HTTPException(status_code=404, detail="TIER_NOT_FOUND")
    
    final_price = tier['price']
    
    if promo:
        promo_clean = promo.upper().strip()
        if promo_clean in DISCOUNT_PROMOS:
            discount = DISCOUNT_PROMOS[promo_clean]
            final_price = int(final_price * (1 - discount / 100))
            print(f"🎟 [PROMO]: Применен код {promo_clean}, цена снижена до {final_price}")
    
    idempotence_key = str(uuid.uuid4())
    user_email = email.lower().strip()
    
    try:
        # 🎯 СОЗДАЕМ ПЛАТЕЖ С ОБЯЗАТЕЛЬНЫМ ЧЕКОМ (ФЗ-54)
        payment = Payment.create({
            "amount": {
                "value": f"{final_price}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": RETURN_URL
            },
            "capture": True,
            "description": f"SKULLA: {tier['amount']} 💀 для {user_email}",
            "metadata": {
                "email": user_email,
                "skulls_amount": tier['amount']
            },
            # 🔥 ВОТ ЭТОТ БЛОК РЕШАЕТ ПРОБЛЕМУ
            "receipt": {
                "customer": {
                    "email": user_email
                },
                "items": [
                    {
                        "description": f"Пополнение баланса: {tier['amount']} Skulls",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{final_price}.00",
                            "currency": "RUB"
                        },
                        "vat_code": "1",  # 1 - Без НДС, 2 - 0%, 4 - 20%
                        "payment_mode": "full_payment",
                        "payment_subject": "service"
                    }
                ]
            }
        }, idempotence_key)

        print(f"💰 [SHOP]: Выставлен счет {payment.id} на {final_price} руб. ({tier['amount']} 💀)")
        
        return {
            "status": "success",
            "confirmation_url": payment.confirmation.confirmation_url
        }
    
    except Exception as e:
        print(f"❌ [PAYMENT_ERROR]: Ошибка ЮKassa: {e}")
        raise HTTPException(status_code=500, detail=str(e)) # Выводим ошибку для дебага



# --- 4. WEBHOOK (АВТО-НАЧИСЛЕНИЕ ПОСЛЕ ОПЛАТЫ) ---
from fastapi import Request

@router.post("/webhook")
async def yookassa_webhook(request: Request, db: Session = Depends(get_db)):
    # 1. Получаем данные от ЮKassa
    data = await request.json()
    
    # 2. Проверяем, что оплата реально прошла успешно
    if data.get('event') == 'payment.succeeded':
        payment_obj = data.get('object', {})
        metadata = payment_obj.get('metadata', {})
        
        email = metadata.get('email')
        # 🎯 Берем именно то количество, которое пробросили при создании платежа
        skulls_to_add = int(metadata.get('skulls_amount', 0))
        payment_id = payment_obj.get('id')

        if email and skulls_to_add > 0:
            user = db.query(User).filter(User.email == email.lower().strip()).first()
            if user:
                # Начисляем монеты
                user.skulls += skulls_to_add
                db.commit()
                print(f"💰 [WEBHOOK_SUCCESS]: Оплата {payment_id} принята. +{skulls_to_add} 💀 для {email}")
                return {"status": "ok"}
            else:
                print(f"⚠️ [WEBHOOK_ERROR]: Юзер {email} не найден в базе!")
                
    return {"status": "ignored"}


@router.post("/calculate_prices")
async def calculate_prices(promo: str = Form(None)):
    discount = 0
    if promo:
        # Приводим к верхнему регистру, чтобы промокоды типа "skulla" и "SKULLA" работали одинаково
        promo_clean = promo.upper().strip()
        discount = DISCOUNT_PROMOS.get(promo_clean, 0)
    
    result_tiers = []
    for tier in SKULLA_TIERS:
        old_price = tier['price']
        # Округляем до целых, чтобы не было 99.40 руб
        new_price = int(old_price * (1 - discount / 100))
        
        # 🎯 Добавляем все поля, которые ждет JS (amount, popular, id)
        result_tiers.append({
            "id": tier['id'],
            "amount": tier['amount'],           # Важно для JS (window.currentPrices.amount)
            "popular": tier.get('popular', False), # Подсветит нужную карточку
            "old_price": old_price if discount > 0 else None,
            "current_price": new_price,
            "discount_pct": discount
        })
    
    return {
        "status": "success", 
        "tiers": result_tiers, 
        "active_discount": discount
    }

