from sqlalchemy.orm import Session
from core.models import User, Transaction, TransactionType

def reward_referrer_on_payment(db: Session, buyer_user: User, payment_amount: float, percent: float = 0.10):
    """
    Автоматически начисляет процент от покупки блогеру (рефереру).
    """
    # 1. Если у покупателя нет пригласившего (поле пусток) — ничего не делаем
    if not buyer_user.referred_by:
        return {"status": "no_referrer"}

    # 2. Ищем блогера в базе по его email, указанному в профиле покупателя
    blogger = db.query(User).filter(User.email == buyer_user.referred_by).first()
    if not blogger:
        return {"status": "blogger_not_found"}

    # 3. Считаем сумму бонуса (например, 10% от платежа)
    bonus_amount = round(payment_amount * percent, 2)
    if bonus_amount <= 0:
        return {"status": "zero_bonus"}

    try:
        # 4. Обновляем баланс в таблице User
        if blogger.partner_balance is None:
            blogger.partner_balance = 0.0
        blogger.partner_balance += bonus_amount

        # 5. Создаем финансовую запись в новую таблицу транзакций
        new_transaction = Transaction(
            user_id=blogger.id,
            amount=bonus_amount,
            type=TransactionType.REFERRAL_BONUS,
            description=f"Бонус {int(percent*100)}% за оплату пользователя {buyer_user.email}"
        )
        db.add(new_transaction)

        # 6. Сохраняем всё одним махом
        db.commit()
        db.refresh(blogger)
        return {"status": "success", "bonus_amount": bonus_amount}

    except Exception as e:
        db.rollback()  # Обязательно откатываем, если база «чихнула»
        return {"status": "error", "message": str(e)}
