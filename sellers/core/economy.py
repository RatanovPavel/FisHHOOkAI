# core/economy.py
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from core.models import User, PromoCode

class EconomyManager:
    @staticmethod
    def process_daily_bonus(db: Session, user: User):
        """Логика начисления Bones: День 1 (+1) -> День 2 (+2) -> День 3 (+3) -> Сброс"""
        now = datetime.utcnow()
        today = now.date()
        last_bonus_date = user.last_bonus_date.date() if user.last_bonus_date else None

        # Если сегодня бонус еще не забирали
        if last_bonus_date != today:
            yesterday = today - timedelta(days=1)
            
            # Если заходил вчера — наращиваем серию (стрик)
            if last_bonus_date == yesterday:
                user.daily_streak = user.daily_streak + 1 if user.daily_streak < 3 else 1
            else:
                # Если пропустил день — сброс на 1
                user.daily_streak = 1
            
            reward = user.daily_streak

            reward=0

            user.bones += reward
            user.last_bonus_date = now
            db.commit()
            return True, reward
        
        return False, 0

    @staticmethod
    def claim_promo(db: Session, user: User, code_text: str):
        """Активация промокода (проверка на существование и использование)"""
        code_clean = code_text.strip().upper()
        promo = db.query(PromoCode).filter(
            PromoCode.code == code_clean, 
            PromoCode.is_active == True
        ).first()

        if not promo:
            return False, "PROMO_INVALID"

        # Начисляем награду из промокода
        user.skulls += promo.reward_skulls
        user.bones += promo.reward_bones
        
        # Делаем промокод неактивным (если он одноразовый)
        promo.is_active = False 
        db.commit()
        
        return True, "PROMO_ACTIVATED"

# core/economy.py

@staticmethod
def finalize_download(db, user, options: dict, is_pro_style=False):
    """
    options: {"no_ads": bool, "no_wm": bool, "hi_res": bool, "use_skulls": bool}
    """
    if options.get("use_skulls") or is_pro_style:
        # Вариант за 1 Skull (Всё включено)
        if user.skulls < 1: return False, "NOT_ENOUGH_SKULLS"
        user.skulls -= 1
        db.commit()
        return True, "PREMIUM_UNLOCKED"
    
    # Вариант за Bones (Конструктор)
    total_bones = 0
    if options.get("no_ads"): total_bones += 1
    if options.get("no_wm"): total_bones += 1
    if options.get("hi_res"): total_bones += 1
    
    if user.bones < total_bones: return False, "NOT_ENOUGH_BONES"
    
    user.bones -= total_bones
    db.commit()
    return True, f"SUCCESS_SPENT_{total_bones}_BONES"


