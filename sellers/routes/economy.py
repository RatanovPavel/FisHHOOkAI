# routes/economy.py
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session
# Поднимаемся на уровень выше, чтобы найти database
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal 
from core.models import User, UserAction
from core.economy import EconomyManager

# 1. Создаем роутер. Префикс /api/economy уже включен!
router = APIRouter(prefix="/api/economy", tags=["Economy"])

# Функция получения сессии БД для этого роутера
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# routes/economy.py

@router.post("/check_daily") 
async def check_daily(email: str = Form(...), db: Session = Depends(get_db)):
    print(f"📡 [ECONOMY]: Запрос ежедневного бонуса для {email}")
    
    # 1. Поиск юзера (email уже приведен к нижнему регистру и очищен)
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    
    if not user:
        print(f"❌ [ECONOMY]: Юзер {email} не найден.")
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    
    # 2. Вызываем логику начисления (Внутри неё должна быть проверка даты!)
    # Функция должна возвращать True/False (начислено или нет) и сумму награды
    try:
        rewarded, amount = EconomyManager.process_daily_bonus(db, user)
        
        # Сохраняем изменения, если они были произведены внутри EconomyManager
        if rewarded:
            db.commit()
            db.refresh(user)
            print(f"✅ [ECONOMY]: Бонус выдан: +{amount} 🦴 юзеру {user.email}")
        else:
            print(f"⏳ [ECONOMY]: Юзер {user.email} уже забирал бонус сегодня.")

    except Exception as e:
        db.rollback()
        print(f"❌ [ECONOMY_ERROR]: Ошибка при начислении: {e}")
        rewarded, amount = False, 0

    # 3. Возвращаем актуальный баланс фронтенду
    return {
        "status": "success",
        "bones": user.bones,
        "skulls": user.skulls,
        "rewarded": rewarded, # Фронт увидит, была ли награда
        "amount": amount      # И сколько именно капнуло
    }



@router.post("/use_promo")
async def use_promo(email: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    
    # Вызываем логику промокодов
    success, message = EconomyManager.claim_promo(db, user, code)
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {
        "status": "success", 
        "bones": user.bones, 
        "skulls": user.skulls,
        "message": message
    }


# =====================================================================
# 📡 СИСТЕМА УМНЫХ АКЦИЙ И ОПРОСОВ СКАЛЛА (2026)
# =====================================================================

@router.post("/check_active_action")
async def check_active_action(email: str = Form(...), db: Session = Depends(get_db)):
    """
    Проверяет, прошел ли селлер текущую активную акцию.
    Если не прошел — бэкенд возвращает полный конфиг честного окна бета-теста!
    """
    user_db = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
        
    # НАСТРОЙКА: Текущая активная акция на платформе Skulla
    CURRENT_ACTION = "beta_test_2026"
    
    # Ищем, отвечал ли уже юзер на эту акцию
    action_record = db.query(UserAction).filter(
        UserAction.user_id == user_db.id,
        UserAction.action_key == CURRENT_ACTION
    ).first()
    
    # Если запись есть, значит оффер уже обработан — ничего не показываем
    if action_record:
        return {"show_popup": False}
        
    # 🎯 БУНКЕРНЫЙ ХАК: Возвращаем фронтенду ЧЕСТНЫЙ ДИНАМИЧЕСКИЙ конфиг бета-теста конструктора!
    return {
        "show_popup": True,
        "action_key": CURRENT_ACTION,
        "type": "offer", # Режим первичного предложения
        "title": "ВЫ В ЗАКРЫТОМ БЕТА-ТЕСТЕ SKULLA",
        "text": "Мы открываем ранний доступ к нашему конструктору инфографики. Сервис сейчас активно дорабатывается, и вы одними из первых сможете собирать карточки бесплатно.",
        "sub_title": "Что взамен:",
        "sub_text": "Нам очень важен ваш опыт. Пожалуйста, ответьте на пару коротких вопросов при входе, чтобы мы сделали редактор идеальным для вашей работы.",
        "bonus_amount": 10000, # Наша внутренняя валюта (хватит на 1000 выгрузок хайрезов)
        "btn_accept": "ЗАБРАТЬ 1000 ГЕНЕРАЦИЙ И НАЧАТЬ ТЕСТ",
        "btn_decline": "Я пасс, мне не нужен бесплатный доступ"
    }



@router.post("/submit_action_decision")
async def submit_action_decision(
    email: str = Form(...), 
    action_key: str = Form(...), 
    decision: str = Form(...), # "accepted" или "declined"
    db: Session = Depends(get_db)
):
    """
    Записывает решение селлера в базу и мгновенно начисляет кости!
    """
    user_db = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    # Проверяем на дубликат запроса, чтобы селлер не набагал себе миллион бонов кликами
    already_done = db.query(UserAction).filter(
        UserAction.user_id == user_db.id, 
        UserAction.action_key == action_key
    ).first()
    
    if already_done:
        return {"status": "success", "bones": user_db.bones, "skulls": user_db.skulls}

    # Настройка награды (тянем из нашей конфигурации)
    BONUS_REWARD = 10000 if action_key == "beta_test_2026" else 0

    # 1. Фиксируем решение в бд
    new_action = UserAction(
        user_id=user_db.id,
        action_key=action_key,
        status=decision
    )
    db.add(new_action)

    # 2. 🔥 НАЧИСЛЯЕМ БОНЫ НА ЛЕТУ, ЕСЛИ СЕЛЛЕР СОГЛАСИЛСЯ!
    if decision == "accepted" and BONUS_REWARD > 0:
        user_db.bones = (user_db.bones or 0) + BONUS_REWARD
        print(f"💰 [ECONOMY]: Селлер {user_db.email} принял акцию {action_key}. Начислено +{BONUS_REWARD} костей!", flush=True)

    db.commit()
    db.refresh(user_db)

    return {
        "status": "success",
        "bones": user_db.bones,
        "skulls": user_db.skulls,
        "reward_applied": decision == "accepted"
    }
