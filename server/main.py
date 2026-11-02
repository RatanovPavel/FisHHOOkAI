import os
import shutil
import json 
import uuid
from contextlib import asynccontextmanager

# 1. Библиотеки FastAPI
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 2. База данных и Модели
from sqlalchemy.orm import Session
from database import engine, SessionLocal, get_db
from core.models import Base, User, PromoCode, EffectStats 

# 3. Сервисы и Аналитика
from core.session_manager import SessionManager
from core.analytics import AnalyticsManager
from core.processor import ImageProcessor
from effects import get_catalog_data, get_effects_list

# 4. Безопасность и Оплата
from passlib.context import CryptContext
from yookassa import Configuration, Payment

# 5. Конфигурация
from config import (
    STATIC_DIR, UPLOAD_DIR, RESULT_DIR, 
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY,
    VERIFICATION_REWARD, SKULLA_TIERS,
    RETURN_URL, DISCOUNT_PROMOS, LEGAL_INFO
)
# main.py
from core.auth import get_current_user

# --- ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ ---

# Создаем таблицы (Base уже знает про все импортированные модели выше)
Base.metadata.create_all(bind=engine)

# Настройка безопасности и оплаты
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

# --- LIFESPAN (Запуск и Остановка) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [SYSTEM]: Запуск сервера SKULLA...")
    db = SessionLocal()
    try:
        # Синхронизируем базу с папкой effects/
        AnalyticsManager.init_stats(db)
        print("✅ [SYSTEM]: База аналитики синхронизирована с файлами эффектов.")
    except Exception as e:
        print(f"❌ [STARTUP_ERROR]: {e}")
    finally:
        db.close()
    
    yield # Здесь приложение живет
    
    print("🛑 [SYSTEM]: Сервер остановлен.")

# 🎯 АБСОЛЮТНЫЙ КИБЕР-ЗАДВИЖОК ШЕФА ДЛЯ ПРОДАКШЕНА:
# Сохраняем твой жизненный цикл lifespan, но наглухо выжигаем Swagger, ReDoc и openapi.json! [INDEX]
app = FastAPI(
    lifespan=lifespan,
    docs_url=None,      # Вырезает /docs [INDEX]
    redoc_url=None,     # Вырезает /redoc [INDEX]
    openapi_url=None    # Вырезает сырой /openapi.json JSON-паспорт [INDEX]
)


# Подключаем статику (убедись, что папка STATIC_DIR существует)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- ЭНДПОИНТЫ МОЖНО ПИСАТЬ НИЖЕ ---


# DEV_CODE = "SKULL_DEV_2024" # Твой секретный код

# @app.middleware("http")
# async def maintenance_mode(request: Request, call_next):
#     # Пропускаем запросы к API, статике и самому логину, чтобы система не самозаблокировалась
#     if any(request.url.path.startswith(p) for p in ["/api/", "/static/", "/dev-login"]):
#         return await call_next(request)

#     # Проверяем "печать" разработчика в куках
#     if request.cookies.get("skulla_access") != DEV_CODE:
#         return HTMLResponse(content=f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>SKULLA | RESTRICTED_AREA</title>
#             <style>
#                 @import url('https://fonts.googleapis.com');
#                 body {{ background: #020617; color: #f8fafc; font-family: 'Inter', sans-serif; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }}
#                 .terminal {{ position: relative; z-index: 10; text-align: center; background: rgba(15, 23, 42, 0.6); padding: 50px; border-radius: 40px; border: 1px solid rgba(34, 211, 238, 0.1); backdrop-filter: blur(20px); box-shadow: 0 0 50px rgba(0,0,0,0.5); }}
#                 .skull {{ font-size: 80px; margin-bottom: 20px; filter: drop-shadow(0 0 15px #22d3ee); animation: float 3s ease-in-out infinite; display: inline-block; }}
#                 @keyframes float {{ 0%, 100% {{ transform: translateY(0) rotate(-5deg); }} 50% {{ transform: translateY(-20px) rotate(5deg); }} }}
#                 h1 {{ font-size: 12px; letter-spacing: 0.5em; color: #22d3ee; margin-bottom: 30px; opacity: 0.8; }}
#                 input {{ background: #020617; border: 1px solid #1e293b; color: #22d3ee; padding: 15px 25px; border-radius: 15px; outline: none; text-align: center; font-weight: bold; width: 200px; transition: 0.3s; }}
#                 input:focus {{ border-color: #22d3ee; box-shadow: 0 0 15px rgba(34, 211, 238, 0.2); }}
#                 button {{ background: #0891b2; color: #020617; border: none; padding: 15px 30px; border-radius: 15px; cursor: pointer; font-weight: 900; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 20px; transition: 0.3s; }}
#                 button:hover {{ background: #22d3ee; transform: scale(1.05); }}
#                 .grid {{ position: fixed; inset: 0; background-image: linear-gradient(to right, rgba(34,211,238,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(34,211,238,0.05) 1px, transparent 1px); background-size: 50px 50px; z-index: 1; }}
#             </style>
#         </head>
#         <body>
#             <div class="grid"></div>
#             <div class="terminal">
#                 <div class="skull">💀</div>
#                 <h1>[ SYSTEM_ENCRYPTED ]</h1>
#                 <form action="/dev-login" method="post">
#                     <input type="password" name="password" placeholder="ENTER_ACCESS_KEY" required><br>
#                     <button type="submit">Decrypt_Access</button>
#                 </form>
#             </div>
#         </body>
#         </html>
#         """)
    
#     return await call_next(request)

# # Добавляем GET метод, чтобы не было 405 ошибки
# @app.get("/dev-login")
# async def dev_login_get():
#     return RedirectResponse(url="/", status_code=303)

# @app.post("/dev-login")
# async def dev_login(password: str = Form(...)):
#     if password == DEV_CODE:
#         response = RedirectResponse(url="/", status_code=303)
#         # Ставим куку на время сессии (до закрытия браузера) или на долгий срок
#         response.set_cookie(key="skulla_access", value=DEV_CODE, httponly=True)
#         return response
#     return RedirectResponse(url="/", status_code=303)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Разрешаем всем (для разработки — ок)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

import random

# main.py
# main.py
from routes import auth, economy, shop, admin, studio # Импортируем оба файла из папки routes


app.include_router(auth.router)    # Пути будут начинаться с /api/auth
app.include_router(economy.router) # Пути будут начинаться с /api/economy
app.include_router(shop.router)
app.include_router(admin.router) # Админка будет доступна по /skulla-admin   
app.include_router(studio.router)
app.include_router(studio.static_router)
# 1. Монтируем папки для доступа из браузера
#app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 2. Главная страница (Витрина)
# # 2. Главная страница (Витрина)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """
    Серверный шлюз Skulla. Отдает index.html только авторизованным юзерам
    или тем, кто нажал кнопку входа на лендинге!
    """
    session_token = request.cookies.get("skulla_token")
    
    # 🔥 ГЛАВНЫЙ ХАК: Проверяем, есть ли хэш или параметры логина в URL-строке запроса
    is_login_intent = "#login" in str(request.url) or "login" in str(request.url.query)

    # Пускаем к конструктору, если есть сессия ИЛИ если юзер нажал кнопку авторизации на лендинге!
    if session_token or is_login_intent:
        print("A️ [SKULLA ACCESS]: Доступ к index.html одобрен!", flush=True)
        with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
            return f.read()

    print("🔒 [SKULLA ACCESS]: Отдаем изолированный landing.html", flush=True)
    with open(os.path.join(STATIC_DIR, "landing3.html"), "r", encoding="utf-8") as f:
        return f.read()


from fastapi.responses import HTMLResponse
import os

@app.get("/voice_bot")
async def get_micro_editor():
    # Путь к файлу. Если закинули в корень, то просто "micro_editor.html".
    # Если лежит в папке templates, укажите "templates/micro_editor.html"
    file_path = os.path.join(STATIC_DIR, "voice_bot.html")

    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    
    return HTMLResponse(content="<h1>Файл voice_bot.html не найден на сервере!</h1>", status_code=404)

@app.get("/micro_editor")
async def get_micro_editor():
    # Путь к файлу. Если закинули в корень, то просто "micro_editor.html".
    # Если лежит в папке templates, укажите "templates/micro_editor.html"
    file_path = os.path.join(STATIC_DIR, "micro_editor.html")

    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    
    return HTMLResponse(content="<h1>Файл micro_editor.html не найден на сервере!</h1>", status_code=404)

# 3. Страница редактора
@app.get("/chat", response_class=HTMLResponse)
def chat_page():
    with open(os.path.join(STATIC_DIR, "chat.html"), "r", encoding="utf-8") as f:
        return f.read()
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    
    return HTMLResponse(content="<h1>Файл catalog-frame.html не найден на сервере!</h1>", status_code=404)

from fastapi.responses import JSONResponse

# 4. API для получения списка эффектов
@app.get("/api/effects")
def api_effects():
    # 🎯 Явно оборачиваем в JSONResponse
    effects = get_effects_list()
    return JSONResponse(content=effects)


from core.analytics import AnalyticsManager

@app.get("/api/catalog")
async def get_catalog(db: Session = Depends(get_db)):
    # 1. Собираем мапу из базы через твой новый менеджер или простым запросом
    stats = {s.style_id: s.usage_count for s in db.query(EffectStats).all()}
    
    # 2. Генерируем каталог (теперь он сам отсортирует ТОП)
    from effects import get_catalog_data
    return get_catalog_data(db_stats=stats)

if __name__ == "__main__":
    import uvicorn
    
    # 1. Создаем или обновляем таблицы (User, Promo, Stats)
    Base.metadata.create_all(bind=engine)
    
    # 2. Синхронизируем список эффектов с базой данных
    print("🚀 [SYSTEM]: Инициализация аналитики и проверка базы...")
    db = SessionLocal()
    try:
        # Теперь все новые эффекты из папки /effects попадут в БД автоматически
        AnalyticsManager.init_stats(db)
        print("✅ [SYSTEM]: База готова к работе.")
    except Exception as e:
        print(f"❌ [SYSTEM_ERROR]: Ошибка при старте: {e}")
    finally:
        db.close()
    
    # 3. Поехали! 
    uvicorn.run(app, host="0.0.0.0", port=8000)



# cd /opt/skulla

# пересборка докера при обновлении библиотек
# docker build --no-cache -t skulla-core .
# docker rm -f skulla_main
# docker run -d --name skulla_main -p 80:8000 -v /opt/skulla:/app --restart always skulla-core

# перезапуск сервера при обновлении py
# docker restart skulla_main
# docker logs --tail 20 skulla_main

# при изменении static перезапуск не нужен

# смотреть логи
# docker logs -f skulla_main

## docker compose up -d