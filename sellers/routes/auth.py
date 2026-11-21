# routes/auth.py
import random
import os
from datetime import datetime
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import uuid
from fastapi.responses import JSONResponse
# Импорты твоего проекта
from database import SessionLocal
from core.models import User
from core.economy import EconomyManager
import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from config import MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM, MAIL_FROM_NAME, VERIFICATION_REWARD

# Инициализация роутера
router = APIRouter(prefix="/api/auth", tags=["Auth"])

def send_verification_email(target_email, code, mode="register"):
    # Выбираем тему и текст в зависимости от режима
    if mode == "reset":
        subject = "Восстановление доступа SKULLA"
        header_text = "RECOVERY_MODE"
        action_text = "для сброса вашего пароля в системе"
    else:
        subject = "Код активации терминала SKULLA"
        header_text = "SYSTEM_NOTIFICATION"
        action_text = "для активации вашего профиля и получения 100🦴"

    body = f"""
    [ {header_text} ]
    
    Ваш персональный код {action_text}:
    
    >>> {code} <<<
    
    Если вы не запрашивал этот код, просто проигнорируйте это письмо.
    
    --------------------------------------------------
    SKULLA Laboratory | Neural Effects System
    """
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg['To'] = target_email

    try:
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as server:
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
        print(f"📧 [MAIL_SYSTEM]: Код {code} ({mode}) отправлен на {target_email}")
        return True
    except Exception as e:
        print(f"❌ [MAIL_ERROR]: {e}")
        return False

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
async def register(
    email: str = Form(...), 
    password: str = Form(...), 
    ref_from_url: str = Form(None), # <--- 🔥 ЛОВИМ ЛОГИН БЛОГЕРА ИЗ FORM-DATA
    db: Session = Depends(get_db)
):

    if not password or len(password) < 6:
        print(f"⚠️ [LOGIN_VALIDATION]: Отклонено! Пароль слишком короткий для {email_clean}", flush=True)
        raise HTTPException(status_code=400, detail="INVALID_CREDENTIALS")
        
    email_clean = email.lower().strip()
    print(f"📡 [REG_START]: Тихое создание аккаунта для {email_clean}")

    # 1. Проверка существования
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        print(f"⚠️ [REG_WARN]: Email {email_clean} уже занят")
        raise HTTPException(status_code=409, detail="EMAIL_TAKEN")
    
    # Генерируем код (он просто лежит в базе до востребования)
    v_code = str(random.randint(100000, 999999))
    
    # === ПРОВЕРКА РЕФЕРАЛЬНОЙ СВЯЗКИ ===
    inviter_login = None
    if ref_from_url:
        clean_inviter = ref_from_url.lower().strip()
        # Ищем блогера в нашей же таблице User по полю email (так как ты используешь email как логин)
        blogger = db.query(User).filter(User.email == clean_inviter).first()
        if blogger:
            inviter_login = blogger.email
            print(f"💸 [РЕФЕРАЛКА]: Селлер {email_clean} успешно привязался к блогеру {inviter_login}")
        else:
            print(f"⚠️ [РЕФЕРАЛКА]: Попытка регистрации от '{clean_inviter}', но такого блогера нет в базе.")


    new_user = User(
        email=email_clean, 
        hashed_password=pwd_context.hash(password[:72]),
        verification_code=v_code,
        is_verified=False,
        bones=0, 
        skulls=0,
        created_at=datetime.utcnow(),
        referred_by=inviter_login,
        partner_balance=0.0,        
    )


    
    try:
        # # 2. Сохранение в базу
        db.add(new_user)
        db.commit()
        print(f"📋 ✅ [REG_DB]: Юзер {email_clean} создан. Письмо НЕ отправлялось (по плану).")

        # 🚀 МГНОВЕННЫЙ АВТО-ВХОД: Сразу генерируем токен сессии для нового селлера!
        import uuid
        new_token = str(uuid.uuid4())
        new_user.session_token = new_token
        db.commit()

        # 🎯 ЗЕРКАЛЬНЫЙ ОТВЕТ: Копируем структуру твоего рабочего логина!
        from fastapi.responses import JSONResponse
        response = JSONResponse(content={
            "status": "success",
            "message": "USER_CREATED",
            "user": {
                "email": str(new_user.email),
                "bones": int(new_user.bones if new_user.bones is not None else 0),
                "skulls": int(new_user.skulls if new_user.skulls is not None else 0),
                "is_verified": bool(new_user.is_verified),
                "token": str(new_token)
            }
        }, status_code=201)

        # Накатываем точно такую же куку сессии, как в твоем логине
        response.set_cookie(
            key="skulla_token",
            value=new_token,
            httponly=True,
            max_age=31536000,  # 1 год
            samesite="lax",
            secure=True        # Обязательно для работы по HTTPS на домене skulla.ru
        )
        return response

    except Exception as e:
        db.rollback()
        print(f"🚨 🔻 * [REG_CRITICAL]: Ошибка при регистрации: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


import uuid
from fastapi.responses import JSONResponse

# --- 2. ВХОД (LOGIN) ---
@router.post("/login")
async def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):

    if not password or len(password) < 6:
        print(f"⚠️ [LOGIN_VALIDATION]: Отклонено! Пароль слишком короткий для {email_clean}", flush=True)
        raise HTTPException(status_code=400, detail="INVALID_CREDENTIALS")
    
    email_clean = email.lower().strip()
    user_db = db.query(User).filter(User.email == email_clean).first()
    
    if not user_db or not pwd_context.verify(password, user_db.hashed_password):
        raise HTTPException(status_code=400, detail="INVALID_CREDENTIALS")
    
    # 1. ГЕНЕРИРУЕМ ПАСПОРТ (Токен сессии)
    new_token = str(uuid.uuid4())
    user_db.session_token = new_token # Записываем в БД
    
    # 2. ПРОВЕРКА ЕЖЕДНЕВНОГО БОНУСА (1-2-3 Bones)
    EconomyManager.process_daily_bonus(db, user_db)
    
    user_db.last_login = datetime.utcnow()
    db.commit()

    # 3. ОТДАЕМ ОТВЕТ С КУКОЙ (чтобы Редактор видел токен автоматически)
    response = JSONResponse(content={
        "status": "success", 
        "user": {
            "email": user_db.email, 
            "bones": user_db.bones,
            "skulls": user_db.skulls,
            "is_verified": user_db.is_verified,
            "token": new_token # 🎯 Токен теперь здесь
        }
    })
    
    # Ставим куку для работы редактора и других скриптов
    response.set_cookie(
        key="skulla_token", 
        value=new_token, 
        httponly=True, 
        max_age=31536000, 
        samesite="lax"
    )
    return response

@router.post("/resend_verify")
async def resend_verify(email: str = Form(...), db: Session = Depends(get_db)):
    email_clean = email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    
    # Генерируем новый код
    v_code = str(random.randint(100000, 999999))
    user.verification_code = v_code
    db.commit()

    # 🎯 ОТПРАВЛЯЕМ ПИСЬМО (mode="register" даст правильный текст)
    send_verification_email(email_clean, v_code, mode="register")
    
    print(f"🔄 [RESEND]: Код активации {v_code} отправлен на {email_clean}")
    return {"status": "success"}


# --- 3. ПОДТВЕРЖДЕНИЕ ПОЧТЫ ---
@router.post("/verify")
async def verify_email(
    email: str = Form(...), 
    code: str = Form(...), 
    db: Session = Depends(get_db)
):
    email_clean = email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user or user.verification_code != code:
        raise HTTPException(status_code=400, detail="INVALID_CODE")
        
    if not user.is_verified:
        user.is_verified = True
        
        # 🎯 Начисляем Боны (Bones), беря сумму из твоего конфига
        user.bones += VERIFICATION_REWARD 
        
        user.verification_code = None
        db.commit()
        print(f"🎁 Юзер {email_clean} верифицирован. Награда: {VERIFICATION_REWARD} Bones")

    return {
        "status": "success", 
        "bones": user.bones, 
        "skulls": user.skulls,
        "is_verified": True
    }


# --- 4. ЗАБЫЛИ ПАРОЛЬ (Генерация кода) ---
@router.post("/forgot_password")
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    print(f"🔥 [DEBUG]: Пытаемся сбросить пароль для {email}")
    email_clean = email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user:
        return {"status": "success", "message": "RECOVERY_CODE_SENT"}

    v_code = str(random.randint(100000, 999999))
    user.verification_code = v_code
    db.commit()

    # Вызови свою функцию отправки письма:
    send_verification_email(email_clean, v_code, mode="reset")
    
    return {"status": "success", "message": "RECOVERY_CODE_SENT"}

# --- 5. СБРОС ПАРОЛЯ (Установка нового по коду) ---
@router.post("/reset_password")
async def reset_password(
    email: str = Form(...), 
    code: str = Form(...), 
    new_password: str = Form(...), 
    db: Session = Depends(get_db)
):
    email_clean = email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user or user.verification_code != code:
        raise HTTPException(status_code=400, detail="INVALID_CODE")

    user.hashed_password = pwd_context.hash(new_password[:72])
    user.verification_code = None
    db.commit()
    
    return {"status": "success", "message": "PASSWORD_RESET_SUCCESS"}

# --- 6. ПРОВЕРКА СТАТУСА (Для синхронизации хедера) ---
@router.post("/check")
async def check_user(email: str = Form(...), db: Session = Depends(get_db)):
    user_db = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    
    # При каждой проверке пробуем начислить ежедневный бонус
    rewarded, amount = EconomyManager.process_daily_bonus(db, user_db)
    
    return {
        "status": "success",
        "user": {
            "email": user_db.email,
            "bones": user_db.bones,
            "skulls": user_db.skulls,
            "is_verified": user_db.is_verified,
            "daily_rewarded": rewarded,
            "reward_amount": amount
        }
    }

# --- ОБНОВЛЕНИЕ ПАРОЛЯ ИЗ КАБИНЕТА ---
@router.post("/update_password")
async def update_password(
    email: str = Form(...), 
    new_password: str = Form(...), 
    db: Session = Depends(get_db)
):
    email_clean = email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
        
    # Хешируем новый пароль
    user.hashed_password = pwd_context.hash(new_password[:72])
    db.commit()
    
    print(f"🔐 [CABINET]: Юзер {email_clean} обновил пароль.")
    return {"status": "success"}


import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

# 🌐 Официальные константы шлюзов Яндекса (СТРОГО БЕЗ КРИВЫХ yandex.ru)
YANDEX_OAUTH_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_INFO_URL = "https://login.yandex.ru/info"

# =====================================================================
# 🔑 ВПИСЫВАЙ СВОИ КЛЮЧИ ИЗ КАБИНЕТА РАЗРАБОТЧИКА СЮДА:
# =====================================================================
YANDEX_CLIENT_ID = "73bfd325031441eba8020ed41eccbbd0"  # Твой ID приложения
YANDEX_CLIENT_SECRET = "07b43a9bfb4a4cea8fcd30e3eef51419"  # Твой Secret Key
# =====================================================================


@router.get("/yandex")
async def yandex_login_redirect(request: Request):
    """
    1. РЕДИРЕКТ: Сюда ведет кнопка с фронтенда.
    Вычисляем домен (локалка/прод) и генерируем ссылку авторизации Яндекса.
    """
    base_url = str(request.base_url).rstrip("/")
    dynamic_redirect_uri = f"{base_url}/api/auth/yandex/callback"
    
    params = {
        "response_type": "code",
        "client_id": YANDEX_CLIENT_ID,
        "redirect_uri": dynamic_redirect_uri
    }
    
    # urlencode сам красиво соберет параметры через "?" и "&"
    final_url = f"{YANDEX_OAUTH_URL}?{urlencode(params)}"
    print(f"📡 [SKULLA OAUTH]: Редирект селлера на Яндекс -> {final_url}", flush=True)
    return RedirectResponse(url=final_url)


import uuid
import random
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

# Не забудь импортировать свою модель User и функцию get_db в начало файла routes/auth.py:
# from database import get_db
# from models import User

@router.get("/yandex/callback")
async def yandex_callback(request: Request, code: str = None, token: str = None, db: Session = Depends(get_db)):
    """
    ЭНДПОИНТ: GET /api/auth/yandex/callback
    Принимает токен напрямую из параметров!
    """
    actual_token = token

    if not actual_token:
        # 🧠 ХАК ШЕФА: Если токена нет, отдаем фронтенду простую HTML-страничку, 
        # которая распарсит решётку '#' в браузере и перезапустит роут правильно!
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="""
            <script>
                // Распиливаем строку после решётки # и вытаскиваем access_token
                const hashParams = new URLSearchParams(window.location.hash.substring(1));
                const token = hashParams.get('access_token');
                if (token) {
                    // Перенаправляем страницу сами на этот же роут, превращая '#' в нормальный параметр '?token='
                    window.location.href = '/api/auth/yandex/callback?token=' + token;
                } else {
                    document.write("🚨 Ошибка перехвата токена Яндекса. Перезапустите вход.");
                }
            </script>
        """)

    # Сюда код долетит, когда сработает редирект скрипта с '?token='
    base_url = str(request.base_url).rstrip("/")

    async with httpx.AsyncClient() as client:
        print(f"📡 [SKULLA OAUTH]: Токен успешно пойман! Летим в Паспорт за Email...", flush=True)
        
        # 🔥 СНАЙПЕРСКИЙ ВЫСТРЕЛ: Сразу бьем полученным токеном в Яндекс Паспорт!
        user_info_response = await client.get(
            YANDEX_USER_INFO_URL, # Наша константа https://login.yandex.ru/info
            headers={"Authorization": f"OAuth {actual_token}"},
            params={"format": "json"}
        )
        
        if user_info_response.status_code != 200:
            print(f"🚨 [SKULLA ERROR]: Паспорт отклонил токен: {user_info_response.text}", flush=True)
            raise HTTPException(status_code=400, detail="Не удалось получить профиль из Яндекса")
            
        user_data = user_info_response.json()
        # ... твой код, который достает из Паспорта email и first_name ...
        email = user_data.get("default_email") or user_data.get("emails", [None])
        first_name = user_data.get("first_name", "Селлер")

    if not email:
        raise HTTPException(status_code=400, detail="Яндекс паспорт не передал Email пользователя")

    email_clean = email.lower().strip()

    # =====================================================================
    # 🎯 ИНТЕГРАЦИЯ С БАЗОЙ ДАННЫХ И СЕССИЕЙ SKULLA (СТРОГО ПО ТВОЕМУ КОДУ)
    # =====================================================================
    
    # Шаг 1. Ищем существующего селлера в БД
    user_db = db.query(User).filter(User.email == email_clean).first()

    if not user_db:
        print(f"🆕 [SKULLA OAUTH]: Юзер {email_clean} не найден в БД. Запускаем тихую регистрацию...", flush=True)
        
        # Создаем пустой хэш пароля для OAuth юзеров (чтобы колонка не пустовала)
        # Так как они заходят через Яндекс, пароль им не нужен
        random_pass = str(uuid.uuid4())
        
        # Полностью копируем твою структуру со строк 88-95 на скриншоте:
        user_db = User(
            email=email_clean,
            hashed_password=pwd_context.hash(random_pass),
            verification_code=str(random.randint(100000, 999999)),
            is_verified=True, # OAuth верифицирован Яндексом автоматически!
            bones=0,
            skulls=0,
            created_at=datetime.utcnow()
        )
        db.add(user_db)
        db.commit()
        db.refresh(user_db) # Перезапрашиваем юзера, чтобы получить его ID из БД
        print(f"✅ [SKULLA OAUTH]: Новый OAuth-юзер {email_clean} успешно создан в базе!", flush=True)
    else:
        print(f"🔑 [SKULLA OAUTH]: Юзер {email_clean} найден в БД. Авторизуем...", flush=True)

    # Шаг 2. Генерируем токен сессии (паспорт токена) строго по твоим строкам 124-126:
    new_token = str(uuid.uuid4())
    user_db.session_token = new_token
    
    # Процессим ежедневный бонус, если у тебя подключен этот класс (строки 128-129):
    try:
        EconomyManager.process_daily_bonus(db, user_db)
    except Exception as economy_err:
        print(f"⚠️ Ошибка начисления бонуса: {economy_err}", flush=True)

    # Обновляем таймштамп входа строго по строке 131:
    user_db.last_login = datetime.utcnow()
    db.commit()

    # === ЗДЕСЬ ЗАКАНЧИВАЕТСЯ ТВОЯ ЗАПИСЬ ЯНДЕКС-ЮЗЕРА В БАЗУ И db.commit() ===

    # -----------------------------------------------------------------
    # === ЗДЕСЬ ЗАКАНЧИВАЕТСЯ ТВОЯ ЗАПИСЬ ЯНДЕКС-ЮЗЕРА В БАЗУ И db.commit() ===

    # -----------------------------------------------------------------
    # 🔥 СКАЛЛА-ФИКС ЯНДЕКСА: БЕЗОПАСНАЯ ПЕРЕДАЧА ДАННЫХ ИЗ ПОП-АПА НА ФРОНТ
    # Инжектируем JSON как безопасную строку и шлем postMessage со звездочкой!
    # -----------------------------------------------------------------
    import json
    from fastapi.responses import HTMLResponse

    # Собираем чистый payload сессии один в один как для ВК
    user_data_payload = {
        "isLoggedIn": True,
        "email": str(user_db.email),
        "bones": int(user_db.bones if user_db.bones is not None else 0),
        "skulls": int(user_db.skulls if user_db.skulls is not None else 0),
        "is_verified": bool(user_db.is_verified),
        "token": str(new_token)
    }
    
    # Превращаем в чистую строку без синтаксических крашей для Хрома
    js_user_data = json.dumps(user_data_payload)

    # -----------------------------------------------------------------
    # 🔥 БУНКЕРНЫЙ ФИКС СКАЛЛЫ: ЗАЩИТА СТEЙТА ЧЕРЕЗ APPLICATION/JSON
    # Полностью исключает SyntaxError, так как Хром не компилирует строку!
    # -----------------------------------------------------------------
    html_content = f"""
    <!DOCTYPE HTML>
    <html>
    <head><title>Skulla Yandex Sync</title></head>
    <body>
        <script id="skulla-payload" type="application/json">{js_user_data}</script>

        <script>
            console.log("🍏 [SKULLA YANDEX]: Записываем сессию селлера Павла...");

            try {{
                // 1. Вытягиваем чистый JSON из безопасного тега и парсим его
                const rawJsonText = document.getElementById("skulla-payload").textContent;
                const userData = JSON.parse(rawJsonText);

                // 2. 🦾 ЖЕСТКАЯ ЗАПИСЬ: Записываем сессию прямо в общую память браузера!
                // Это автоматически стриггерит событие 'storage' на главном экране на заднем плане!
                window.user = userData;
                localStorage.setItem('skulla_user', JSON.stringify(userData));
                console.log("💾 Общая память LocalStorage успешно обновлена!");
            }} catch (jsonErr) {{
                console.error("🚨 Ошибка парсинга JSON:", jsonErr);
            }}

            // 3. Захлопываем поп-ап окно Яндекса к чертям, оно больше не нужно!
            window.close();
            if (window.top) window.top.close();
        </script>
    </body>
    </html>
    """



    response = HTMLResponse(content=html_content, status_code=200)

    # Накатываем куку сессии Skulla на 1 год
    response.set_cookie(
        key="skulla_token",
        value=new_token,
        httponly=True,
        max_age=31536000,
        samesite="lax",
        secure=True
    )

    print(f"🚀 [SKULLA YANDEX SUCCESS]: HTML-скрипт с postMessage успешно отправлен в поп-ап!", flush=True)
    return response




# 🌐 Официальные константы шлюзов ВКонтакте
VK_TOKEN_URL = "https://id.vk.ru/oauth2/auth"
VK_USER_INFO_URL = "https://id.vk.ru/oauth2/user_info"
# Ключи твоего приложения из кабинета разработчика VK ID
VK_CLIENT_ID = "54683991"
VK_CLIENT_SECRET = "SLKLC5uJGoCuik3FIHJG"  # Твой реальный секрет
VK_SERVICE_TOKEN = "ce272db8ce272db8ce272db89acd6544efcce27ce272db8a47b5fc0a7d06a9927630320"
DYNAMIC_REDIRECT_URI = "https://skulla.ru/api/auth/vk/callback"

@router.get("/vk/callback")
# 🦾 СИНХРОНИЗАЦИЯ СО СХЕМОЙ: Принимаем code, device_id и code_verifier с фронтенда!
async def vk_callback(request: Request, code: str = None, device_id: str = None, code_verifier: str = None, db: Session = Depends(get_db)):
    print(f"🚀 [SKULLA VK]: Начат PKCE-обмен по схеме ВК...", flush=True)
    if not code:
        raise HTTPException(status_code=400, detail="Код авторизации ВК не получен")
    if not device_id:
        raise HTTPException(status_code=400, detail="Параметр device_id не получен с фронтенда")
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Параметр code_verifier не получен с фронтенда")

    # Собираем payload строго под PKCE-контекст схемы ВК Паспорта
    payload = {
        "grant_type": "authorization_code",
        "client_id": VK_CLIENT_ID,
        "client_secret": VK_CLIENT_SECRET,
        "redirect_uri": DYNAMIC_REDIRECT_URI,
        "code": code,
        "device_id": device_id,
        "code_verifier": code_verifier,
        # 🔥 ФИНАЛЬНЫЙ ПОБЕДНЫЙ ВЫСТРЕЛ: Добавляем сервисный ключ в JSON, как просит ВК!
        "service_token": VK_SERVICE_TOKEN  
    }

    try:
        async with httpx.AsyncClient() as client:
            print(f"📡 [SKULLA VK]: Шлем JSON-пакет обмена на id.vk.ru/oauth2/auth ...", flush=True)
            
            token_response = await client.post(
                VK_TOKEN_URL,
                json=payload,
                timeout=10.0,
            )
            
            print(f"📡 [SKULLA VK]: Финальный статус ответа ВК (Этап 1): {token_response.status_code}", flush=True)
            
            raw_text = token_response.content.decode('utf-8', errors='ignore').strip()
            
            if token_response.status_code != 200:
                print(f"❌ [SKULLA VK ERROR]: Сбой обмена токена! Статус: {token_response.status_code}", flush=True)
                raise HTTPException(status_code=400, detail=f"Ошибка ВК: {raw_text}")

            vk_data = token_response.json()
            access_token = vk_data.get("access_token")
            vk_user_id = vk_data.get("user_id")

            print(f"📡 [SKULLA VK]: Токен получен! Запускаем Второй Этап по доке ВК...", flush=True)

            email = vk_data.get("email")

            # 🎯 СКАЛЛА-ФИКС СЕТКИ: Этот блок ТЕПЕРЬ СТОИТ ВНУТРИ ASYNC WITH (Сдвинут вправо на 4 пробела!)
            # Теперь httpx гарантированно отправит запрос, вычитает реальный Email и сотрет ошибку!
            if not email and access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                
                print(f"📡 [SKULLA VK]: Запрашиваем профиль на {VK_USER_INFO_URL} ...", flush=True)
                user_info_response = await client.get(
                    VK_USER_INFO_URL,
                    headers=headers,
                    params={"client_id": VK_CLIENT_ID},
                    timeout=10.0
                )
                
                print(f"📋 [SKULLA VK]: Ответ user_info. Статус: {user_info_response.status_code}", flush=True)
                print(f"📋 [SKULLA VK]: Данные профиля от ВК -> {user_info_response.text}", flush=True)
                
                if user_info_response.status_code == 200:
                    user_info_data = user_info_response.json()
                    email = user_info_data.get("email")
                    if not email and isinstance(user_info_data.get("user"), dict):
                        email = user_info_data.get("user", {}).get("email")

        # === КОНТЕКСТ ASYNC WITH ЗАКРЫЛСЯ (Выравниваем код БД обратно влево) ===
        # 🧠 ЖЕЛЕЗНЫЙ ФОЛБЭК: Оставляем только на самый крайний аварийный случай
        if not email and vk_user_id:
            email = f"vk_{vk_user_id}@skulla.ru"
            print(f"👤 [SKULLA VK]: Сгенерирован резервный email селлера -> {email}", flush=True)

        if not email:
            raise HTTPException(status_code=400, detail="ВКонтакте не предоставил идентификаторы пользователя")

        email_clean = email.lower().strip()


    except Exception as e:
        print(f"🚨 [SKULLA BACKEND CRASH]: Сбой httpx или парсинга! Ошибка -> {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=f"Внутренний сбой бэкенда при обмене: {str(e)}")

    if not email:
        print(f"❌ [SKULLA VK ERROR]: ВК не передал email селлера в ответе токена!", flush=True)
        raise HTTPException(status_code=400, detail="ВКонтакте не передал email пользователя")

    email_clean = email.lower().strip()

    # -----------------------------------------------------------------
    # СИНХРОНИЗАЦИЯ С БАЗОЙ ДАННЫХ SKULLA (ОДИН В ОДИН С ЯНДЕКСОМ)
    # -----------------------------------------------------------------
    user_db = db.query(User).filter(User.email == email_clean).first()

    if not user_db:
        print(f"👤 [SKULLA VK]: Юзер {email_clean} не найден в БД. Регистрируем...", flush=True)
        random_pass = str(uuid.uuid4())
        user_db = User(
            email=email_clean,
            hashed_password=pwd_context.hash(random_pass),
            verification_code=str(random.randint(100000, 999999)),
            is_verified=True,  # Верифицировано через ВК ID
            bones=0,
            skulls=0,
            created_at=datetime.utcnow()
        )
        db.add(user_db)
        db.commit()
        db.refresh(user_db)
    else:
        print(f"👤 [SKULLA VK]: Юзер {email_clean} найден в БД. Логиним...", flush=True)

    # 🦾 СКАЛЛА-ФИКС: Все строки ниже стоят строго на одном уровне с 'if' и 'else'!
    new_token = str(uuid.uuid4())
    user_db.session_token = new_token

    try:
        EconomyManager.process_daily_bonus(db, user_db)
    except Exception:
        pass

    user_db.last_login = datetime.utcnow()
    db.commit()

    # -----------------------------------------------------------------
    # 🔥 СКАЛЛА-ФИКС: ГЕНЕРИРУЕМ JS-СКРИПТ ДЛЯ ОБНОВЛЕНИЯ ФРОНТЕНДА!
    # Прописываем LocalStorage, убираем белый экран и силой обновляем шапку!
    # -----------------------------------------------------------------
    import json
    from fastapi.responses import HTMLResponse

    # Собираем чистый payload сессии, который ждет твой header.js и shop.js
    user_data_payload = {
        "isLoggedIn": True,
        "email": str(user_db.email),
        "bones": int(user_db.bones if user_db.bones is not None else 0),
        "skulls": int(user_db.skulls if user_db.skulls is not None else 0),
        "is_verified": bool(user_db.is_verified),
        "token": str(new_token)
    }
    js_user_data = json.dumps(user_data_payload)

    # Вместо голого JSON отдаем Хрому скрипт, который выполнит нативный редирект
    html_content = f"""
    <script>
        console.log("🍏 [SKULLA VK]: База Павла обновлена. Синхронизируем стейт фронтенда...");

        try {{
            // 1. Зашиваем данные напрямую в память браузера (LocalStorage) главной страницы
            const userData = {js_user_data};
            window.user = userData;
            localStorage.setItem('skulla_user', JSON.stringify(userData));
            console.log("💾 Данные селлера успешно записаны в LocalStorage!");
        }} catch (err) {{
            console.error("🚨 Ошибка записи стейта в Хроме:", err);
        }}

        // 2. 🔥 ГЛАВНЫЙ СНАЙПЕРСКИЙ ВЫСТРЕЛ ВЕКА: Возвращаем вкладку из белого экрана на главную!
        // Браузер обновит корень сайта, кука встанет на место, header.js нативно прочитает 
        // LocalStorage, надпись ВХОД испарится, зажжется PAVEL и твои 9212 бонов!
        window.location.href = "/";
    </script>
    """

    response = HTMLResponse(content=html_content, status_code=200)

    # Накатываем куку сессии Skulla на 1 год для фоновых AJAX-проверок бэкенда
    response.set_cookie(
        key="skulla_token",
        value=new_token,
        httponly=True,
        max_age=31536000, # 1 год в секундах
        samesite="lax",
        secure=True       # Обязательно для работы по HTTPS на skulla.ru
    )

    print(f"🚀 [SKULLA VK SUCCESS]: HTML-скрипт редиректа фронтенда успешно отправлен селлеру!", flush=True)
    return response

@router.post("/logout")
async def logout(response: JSONResponse):
    """
    ЭНДПОИНТ: Полное выжигание куки skulla_token на стороне сервера.
    """
    print("📡 [SKULLA LOGOUT]: Стираем сессионный токен из кук...", flush=True)
    response.delete_cookie(
        key="skulla_token",
        path="/",
        samesite="lax",
        secure=True  # Обязательно для HTTPS на skulla.ru
    )
    return {"status": "success", "message": "LOGGED_OUT"}