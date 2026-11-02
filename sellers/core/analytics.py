# core/analytics.py
from sqlalchemy.orm import Session
from core.models import EffectStats
from effects import EFFECTS_DATA

class AnalyticsManager:
    @staticmethod
    def init_stats(db: Session):
        """Проверяет наличие всех эффектов в базе при старте сервера"""
        try:
            for eid in EFFECTS_DATA.keys():
                exists = db.query(EffectStats).filter_by(style_id=eid).first()
                if not exists:
                    db.add(EffectStats(style_id=eid, usage_count=0, click_count=0))
                    print(f"📡 [ANALYTICS]: Инициализирован счетчик для {eid}")
            db.commit()
        except Exception as e:
            print(f"❌ [ANALYTICS_INIT_ERROR]: {e}")
            db.rollback()

    @staticmethod
    def log_usage(db: Session, style_id: str):
        """+1 к генерации (вызывать в /apply)"""
        stat = db.query(EffectStats).filter_by(style_id=style_id).first()
        if stat:
            stat.usage_count += 1
            db.commit()
            return stat.usage_count
        return 0

    @staticmethod
    def log_click(db: Session, style_id: str):
        """+1 к клику (вызывать в /stats/click)"""
        stat = db.query(EffectStats).filter_by(style_id=style_id).first()
        if stat:
            stat.click_count += 1
            db.commit()
