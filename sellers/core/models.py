import os
import sys
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Enum
from datetime import datetime

# --- БЛОК ГЛУБОКОЙ ОТЛАДКИ ---
print("\n--- 🔍 SKULLA DEBUG START ---")
print(f"📍 Текущий файл: {os.path.abspath(__file__)}")
print(f"📂 Рабочая директория (CWD): {os.getcwd()}")

# Ищем корень проекта (поднимаемся на уровень выше от папки core)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"🛠 Ожидаемый корень проекта: {PROJECT_ROOT}")

# Проверяем, есть ли там файл database.py
files_in_root = os.listdir(PROJECT_ROOT) if os.path.exists(PROJECT_ROOT) else []
print(f"📦 Файлы в корне: {files_in_root}")

if "database.py" in files_in_root:
    print("✅ database.py НАЙДЕН в корне!")
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
else:
    print("❌ database.py НЕ НАЙДЕН в корне! Проверь расположение файла.")

print("--- 🔍 SKULLA DEBUG END ---\n")

# Попытка импорта
try:
    from database import Base
except ImportError as e:
    print(f"💀 КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА: {e}")
    raise e



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
     # ПАСПОРТ СЕССИИ
    session_token = Column(String, unique=True, index=True, nullable=True)
    # ДАТА РЕГИСТРАЦИИ
    created_at = Column(DateTime, default=datetime.utcnow)
    # ВАЛЮТЫ (Скулы - донат, Боны - социалка)
    skulls = Column(Integer, default=0) 
    bones = Column(Integer, default=0)  
    
    # ДАТЫ И БОНУСЫ
    last_login = Column(DateTime, default=datetime.utcnow)
    last_bonus_date = Column(DateTime, nullable=True)
    daily_streak = Column(Integer, default=0) # 1-2-3
    
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)

    # === РЕФЕРАЛЬНАЯ СИСТЕМА ДЛЯ БЛОГЕРОВ (ПО ЛОГИНУ) ===
    # Логин блогера из этой же базы, который пригласил селлера (String, nullable)
    referred_by = Column(String, nullable=True)
    
    # Счётчик заработанных денег блогера в рублях, которые можно вывести
    partner_balance = Column(Float, default=0.0, server_default="0.0")
    # === РОЛЕВАЯ МОДЕЛЬ ДЛЯ УПРАВЛЕНИЯ ДОСТУПОМ ===
    # Может принимать значения: 'user', 'blogger', 'admin'
    role = Column(String, default="user", server_default="user")

class PromoCode(Base):
    __tablename__ = "promo_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True) # Например: "SKULLA2024"
    reward_skulls = Column(Integer, default=0)
    reward_bones = Column(Integer, default=0)
    uses_left = Column(Integer, default=1) # Сколько раз можно активировать
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)

class EffectStats(Base):
    __tablename__ = "effect_stats"
    
    style_id = Column(String, primary_key=True)
    usage_count = Column(Integer, default=0) 
    click_count = Column(Integer, default=0) 

class UserAction(Base):
    __tablename__ = "user_actions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action_key = Column(String(50), nullable=False)  # Например: "beta_test_2026"
    status = Column(String(20), nullable=False)      # "accepted", "declined", "completed"
    answers = Column(Text, nullable=True)            # Сюда в будущем будем сохранять JSON опросов!
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TransactionType(str, enum.Enum):
    REFERRAL_BONUS = "referral_bonus"  # Начисление за реферала
    WITHDRAWAL = "withdrawal"          # Вывод денег блогером
    MANUAL_ADJUST = "manual_adjust"    # Ручная корректировка админом

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Для денег ВСЕГДА лучше использовать Float/Numeric, а не строки
    amount = Column(Float, nullable=False)  # Например: 150.50 (плюс — начисление, минус — вывод)
    
    type = Column(Enum(TransactionType), nullable=False)  # Тип операции
    description = Column(String, nullable=True)           # Человеческое описание для истории
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Опционально: можно связать с заказом или покупателем, если нужно
    # buyer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
