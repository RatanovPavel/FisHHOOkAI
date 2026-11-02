# core/auth.py или core/session_manager.py
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
from core.models import User

from typing import Optional # Не забудь добавить в импорты наверху!

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    # 1. Ищем в заголовке Authorization
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        try:
            # 🎯 ФИКС: Добавили [1], чтобы взять именно токен, а не список из двух элементов!
            token = auth_header.split(" ")[1]
        except IndexError:
            token = None
    
    # 2. Если в заголовке нет, ищем в куках
    if not token:
        token = request.cookies.get("skulla_token")

    # Если токена нет вообще — возвращаем None
    if not token:
        return None
    
    # 3. Ищем в базе
    user = db.query(User).filter(User.session_token == token).first()
    
    # If user is not found — возвращаем None
    if not user:
        return None
    
    return user



