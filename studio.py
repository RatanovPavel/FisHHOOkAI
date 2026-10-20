import os
import json
import io
import uuid
import shutil
import glob
import asyncio

from datetime import datetime

# FastAPI и SQLAlchemy
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image

# Твоё ядро (Бизнес-логика)
from database import get_db, SessionLocal
from core.models import User
from core.auth import get_current_user
from core.analytics import AnalyticsManager
from core.processor import ImageProcessor
from core.session_manager import SessionManager
from core.vision import SkullaVision  # Добавил на всякий случай, если нужен меш напрямую
from config import UPLOAD_DIR
from effects import EFFECTS_DATA
from typing import Optional

router = APIRouter(prefix="/api/studio", tags=["Studio"])


# routes/studio.py

import os
import io
import base64
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw, ImageFont

@router.post("/font-previews")
async def def_font_previews(
    text: str = Form("ЗАГОЛОВОК"),
    color: str = Form("#FFFFFF"),
    bg_color: str = Form("#0F172A")
):
    # --- НИШЕВОЙ МУЛЬТИРЕНДЕР ШЕФА В ИСПРАВЛЕННОЙ МАТЕМАТИКЕ PILLOW ---
    # Физически вычисляет ширину и высоту через индексы кортежа bbox, полностью исключая TypeError!
    
    def hex_to_rgba(hex_str, default=(255, 255, 255, 255)):
        try:
            h = hex_str.lstrip('#')
            if len(h) == 6:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (255,)
            elif len(h) == 8:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4, 6))
        except Exception:
            pass
        return default

    text_color = hex_to_rgba(color, (255, 255, 255, 255))
    canvas_bg_color = hex_to_rgba(bg_color, (15, 23, 42, 255))

    current_file_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 🎯 МОНОЛИТНЫЙ ПУТЬ: Смотрим строго в общую папку assets/fonts вне зависимости от категорий
    assets_fonts_dir = os.path.normpath(os.path.join(current_file_dir, "assets", "fonts"))
    
    previews = []

    if os.path.exists(assets_fonts_dir) and os.path.isdir(assets_fonts_dir):
        font_files = [f for f in os.listdir(assets_fonts_dir) if f.lower().endswith(('.ttf', '.otf'))]
        
        display_text = text.strip() if text.strip() else "ЗАГОЛОВОК"
        if len(display_text) > 20:
            display_text = display_text[:20] + "..."
            
        for font_file in font_files:
            try:
                img = Image.new("RGBA", (400, 90), canvas_bg_color)
                draw = ImageDraw.Draw(img)
                
                font_path = os.path.join(assets_fonts_dir, font_file)
                font = ImageFont.truetype(font_path, 32)
                
                # 🎯 АБСОЛЮТНЫЙ МАТЕМАТИЧЕСКИЙ ФИКС ШЕФА: Считаем габариты строго по индексам b[2]-b[0] и b[3]-b[1]!
                bbox = draw.textbbox((0, 0), display_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                x = (400 - text_w) // 2
                y = (90 - text_h) // 2 - 4
                
                draw.text((x, y), display_text, font=font, fill=text_color)
                
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                
                previews.append({
                    "font_name": font_file,
                    "base64": f"data:image/png;base64,{img_str}"
                })
            except Exception as e:
                print(f"⚠️ Ошибка рендера шрифта {font_file}: {e}", flush=True)

    return JSONResponse(content={"status": "success", "previews": previews})




@router.get("/preview/{session_id}/{file_type}")
async def get_preview(session_id: str, file_type: str):
    """Безопасный шлюз для шторки (с жестким и честным MIME-типом для MP4 веба)"""
    if file_type not in ["before", "after"]:
        raise HTTPException(status_code=403, detail="Доступ к оригиналу запрещен")
        
    session_path = os.path.join(UPLOAD_DIR, session_id)
    
    if file_type == "before":
        for name in ["original.png", "before.png"]:
            path = os.path.join(session_path, name)
            if os.path.exists(path): 
                return FileResponse(path, media_type="image/png")
        raise HTTPException(status_code=404, detail="Исходник не найден")

    if file_type == "after":
        video_path = os.path.join(session_path, "result.mp4")
        if os.path.exists(video_path):
            # 🎯 ФИНАЛЬНЫЙ СУПЕР-ФИКС: Передаем strictly "video/mp4",
            # чтобы Chrome понял, что это видеопоток H.264, а не PNG-картинка!
            return FileResponse(
                video_path, 
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Type": "video/mp4" # Дублируем для пуленепробиваемости
                }
            )
                
        img_path = os.path.join(session_path, "after.png")
        if os.path.exists(img_path): 
            return FileResponse(img_path, media_type="image/png")
            
    raise HTTPException(status_code=404, detail="Файл превью не найден")


@router.post("/apply")
async def apply_effect(
    session_id: str = Form(...), 
    style_id: str = Form(...), 
    params: str = Form(...), 
    user: Optional[User] = Depends(get_current_user), # Заменил на Optional, чтобы анонимов пускало
    db: Session = Depends(get_db)
):
    session_path = os.path.join(UPLOAD_DIR, session_id)
    if not os.path.exists(session_path):
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    # Распаковка параметров
    try:
        dict_params = json.loads(params)
    except:
        dict_params = {}
    
    dict_params["session_id"] = session_id 

    # 2. ЛОГИРУЕМ ИСПОЛЬЗОВАНИЕ ДЛЯ СТАТИСТИКИ
    try:
        AnalyticsManager.log_usage(db, style_id)
    except Exception as e:
        print(f"⚠️ [ANALYTICS_ERROR]: {e}")

    try:
        # 🎯 ВЫТАСКИВАЕМ ФЛАГ premium_only ИЗ КОНФИГА ЭФФЕКТА ДО ВЫЗОВА ОТВЕТОВ
        effect_config = EFFECTS_DATA.get(style_id, {})
        econ_cfg = effect_config.get("economy", {})
        premium_only = econ_cfg.get("premium_only", False) # Читаем True/False из твоего конфига эффекта
        fixed_skulls = econ_cfg.get("full_access_skulls", 0)

        # 3. ВЫЗЫВАЕМ ПРОЦЕССОР
        raw_result = ImageProcessor.apply_style(
            session_path, 
            style_id, 
            dict_params, 
            is_pro=False
        )

        # 🎯 ТВОЯ ЛОГИКА БАЛАНСА (Строго без изменений)
        if user:
            # Авторизован — шлем реальные цифры
            balance = {
                "bones": user.bones,
                "skulls": user.skulls
            }
        else:
            # Аноним — шлем нули
            balance = {
                "bones": 0,
                "skulls": 0
            }

        # 🎯 УМНЫЙ РАЗВОРОТ: Если процессор вернул словарь (наш видеоэффект)
        if isinstance(raw_result, dict):
            # Если в конфиге full_access_skulls > 0, берем его, иначе динамический ценник
            final_price = fixed_skulls if fixed_skulls > 0 else raw_result.get("price_skulls", 15)
            duration = raw_result.get("duration", 0)
            
            return {
                "status": "success",
                "before": f"/uploads/{session_id}/before.png",
                "processed": f"/uploads/{session_id}/result.mp4", # Ссылка на mp4 для плеера
                "new_balance": balance,
                "is_video": True,
                "premium_only": premium_only,  # 🎯 ПУШИМ СИГНАЛ ФРОНТЕНДУ, ЧТОБЫ СКРЫТЬ БОНЫ!
                "price_skulls": final_price,
                "duration": duration
            }
        else:
            # 🎯 ДЛЯ СТАРЫХ КАРТИНОК: Безопасно распаковываем оригинальный рабочий кортеж
            before_name, after_name = raw_result
            return {
                "status": "success",
                "before": f"/uploads/{session_id}/{before_name}",
                "processed": f"/uploads/{session_id}/{after_name}",
                "new_balance": balance,
                "premium_only": premium_only,  # Картинки тоже могут быть premium_only
                "is_video": False
            }

    except Exception as e:
        print(f"❌ [STUDIO_APPLY_ERROR]: {e}")
        raise HTTPException(status_code=500, detail=str(e))




import os
import uuid
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
# Предполагаем, что у тебя есть функция получения конфига
from core.processor import EFFECTS_DATA
from core.processor import ImageProcessor

import uuid
import shutil

import os
import json
import uuid
import shutil
from fastapi import Form, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
from sqlalchemy.orm import Session
from PIL import Image

from fastapi import Body
from core.seo_generator import SkullaSEOGenerator

@router.post("/seo-generate")
async def generate_product_seo(data: dict = Body(...)):
    """
    Эндпоинт скоростной генерации SEO-описания карточки товара без ЛЛМ
    с автоматическим сохранением текстового файла в сессию.
    """
    platform = data.get("marketplace_type", "wildberries")
    product_name = data.get("main_title", "Универсальный Товар")
    brand_name = data.get("brand_name", "Skulla Brand")
    feature_1 = data.get("badge_1", "")
    feature_2 = data.get("badge_2", "")
    promo_tag = data.get("promo_tag", "")
    
    # Пытаемся вытащить путь к текущей сессии из входящих данных
    # Если на фронте ключ называется по-другому, подставь нужный (например session_id)
    session_id = data.get("session_id")
    s_path = data.get("session_path", ".")
    
    # Если прилетел чистый session_id, конструируем путь к папке uploads
    if session_id and s_path == ".":
        s_path = os.path.join("uploads", str(session_id))

    # Запускаем наше быстрое алгоритмическое ядро
    seo_result = SkullaSEOGenerator.generate_description(
        product_name=product_name,
        brand_name=brand_name,
        feature_1=feature_1,
        feature_2=feature_2,
        promo_tag=promo_tag,
        platform=platform
    )
    
    # 🎯 АВТОМАТИЧЕСКАЯ ЗАПИСЬ ТЕКСТА В СЕССИЮ СЕЛЛЕРА
    if os.path.exists(s_path):
        try:
            txt_path = os.path.join(s_path, "seo_description.txt")
            with open(txt_path, "w", encoding="utf-8") as f_txt:
                f_txt.write(seo_result["description"])
            print(f"📝 [SEO COMPILER SUCCESS]: Файл seo_description.txt сохранен в сессию: {txt_path}")
        except Exception as txt_err:
            print(f"⚠️ [SEO SAVE ERROR]: Не удалось записать файл на диск: {txt_err}")
            
    return seo_result

@router.post("/export")
async def export_result(
    data: dict, 
    db: Session = Depends(get_db), 
    user: Optional[User] = Depends(get_current_user)  # Анонимы разрешены для MVP промо-тестов
):
    try:
        # 1. ЛОГИКА АНОНИМА (Сохраняем твой каноничный шлагбаум для локальных тестов)
        is_anon = user is None
        if is_anon:
            from dataclasses import dataclass
            @dataclass
            class AnonUser:
                id: int = 0
                bones: int = 100
                skulls: int = 100
            user = AnonUser()
            # Нейтрализуем старые чекбоксы во входящем словаре анонима
            data["opt_no_watermark"] = True
            data["opt_high_res"] = True

        session_id = data.get("session_id")
        style_id = data.get("style_id")
        payment_type = data.get("payment_type")  # Получаем "bones" или "skulls" от нового JS

        session_path = os.path.join(UPLOAD_DIR, session_id)

        if not session_id or not style_id or not payment_type:
            raise HTTPException(400, "Отсутствует Session ID, Style ID или Тип оплаты")

        # Получаем конфиг текущего эффекта карточки маркетплейса
        effect_config = EFFECTS_DATA.get(style_id)
        if not effect_config:
            raise HTTPException(404, f"Конфиг эффекта '{style_id}' не найден")
        
        # Вытаскиваем наши новые плоские B2B промо-цены из CONFIG
        econ = effect_config.get("economy", {"price_bones": 10, "price_skulls": 5})
        is_video_effect = "video" in effect_config.get("tags", [])
        final_cost = 0

        # ==============================================================================
        # 🟢 ВЕТКА 1: ХИРУРГИЧЕСКИЙ ВЫБОР И ИЗОЛЯЦИЯ МЕДИАПОТОКОВ (ВИДЕО)
        # ==============================================================================
        if is_video_effect:
            # Распаковываем параметры текста переписки, прилетевшие из JS
            try:
                if isinstance(data.get("params"), dict):
                    dict_params = data.get("params")
                else:
                    import json
                    dict_params = json.loads(data.get("params", "{}"))
            except:
                dict_params = {}
                
            dict_params["session_id"] = session_id
            dict_params["session_path"] = session_path

            # Запускаем боевой рендер видео. Высокое качество (is_pro=True) насаждаем по умолчанию
            video_result = ImageProcessor.apply_style(session_path, style_id, dict_params, is_pro=True)
            
            if not isinstance(video_result, dict) or "price_skulls" not in video_result:
                raise HTTPException(500, "Ошибка генерации оригинального видео-файла")
                
            # Если юзер платит Скаллами, фиксируем динамическую цену из ИИ-видеодвижка
            if payment_type == "skulls":
                final_cost = video_result["price_skulls"]
                if not is_anon:
                    db.refresh(user)
                if user.skulls < final_cost:
                    raise HTTPException(402, "INSUFFICIENT_SKULLS")
            else:
                final_cost = econ.get("price_bones", 10)
                if user.bones < final_cost:
                    raise HTTPException(402, "INSUFFICIENT_BONES")

            source_path = os.path.join(session_path, "result.mp4")
            if not os.path.exists(source_path):
                raise HTTPException(404, "Финальный видео-файл не найден")

            # МОМЕНТ СПИСАНИЯ ДЛЯ ВИДЕО С БАЗЫ ДАННЫХ
            if not is_anon and final_cost > 0:
                if payment_type == "bones":
                    user.bones -= final_cost
                    print(f"🦴 [B2B ECONOMY]: Списано {final_cost} Бонов за видео-экспорт у юзера {user.id}")
                else:
                    user.skulls -= final_cost
                    print(f"🪙 [B2B ECONOMY]: Списано {final_cost} Скаллов за видео-экспорт у юзера {user.id}")
                db.commit()
                db.refresh(user)

            final_name = f"skulla_{uuid.uuid4().hex[:12]}.mp4"
            target_path = os.path.join("static", "results", final_name)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copyfile(source_path, target_path)

            return {
                "status": "success",
                "payment_type": payment_type,
                "download_url": f"/static/results/{final_name}",
                "new_balance": {"bones": user.bones, "skulls": user.skulls}
            }

        # ==============================================================================
        # 🔵 ВЕТКА 2: ЧИСТАЯ B2B ЛОГИКА ДЛЯ НАШИХ КАРТИНОК 900x1200 ПОД МАРКЕТПЛЕЙСЫ
        # ==============================================================================
        else:
            if payment_type == "skulls":
                final_cost = econ.get("price_skulls", 5)
                if user.skulls < final_cost:
                    raise HTTPException(402, "INSUFFICIENT_SKULLS")
            elif payment_type == "bones":
                final_cost = econ.get("price_bones", 10)
                if user.bones < final_cost:
                    raise HTTPException(402, "INSUFFICIENT_BONES")

            # Извлекаем параметры картинок
            try:
                if isinstance(data.get("params"), dict):
                    dict_params = data.get("params")
                else:
                    import json
                    dict_params = json.loads(data.get("params", "{}"))
            except:
                dict_params = {}

            # Насаждаем единый B2B лимит разрешения 1200px
            dict_params["session_path"] = session_path
            dict_params["resolution_limit"] = 1200

            # Запускаем процессор Pillow-генерации. Он запишет processed_hd.png
            ImageProcessor.apply_style(session_path, style_id, dict_params, is_pro=True)

            # Обе кнопки (и Боны, и Скаллы) забирают чистый, оригинальный processed_export.png
            target_file = "processed_export.png"
            source_path = os.path.join(session_path, target_file)

            if not os.path.exists(source_path):
                print(f"❌ [EXPORT_FAIL]: Файл {target_file} не найден на диске!")
                raise HTTPException(404, "Результат рендеринга инфографики не найден")

            try:
                # Открываем готовый PNG маркетплейса и сохраняем в статику
                with Image.open(source_path) as img:
                    # 🎯 СКАЛЛА-ФИКС №1: Спасаем альфа-канал прозрачности для утилиты вырезки!
                    # Если селлер экспортирует чистый cutout — мы КАТЕГОРИЧЕСКИ запрещаем конвертировать его в RGB!
                    # Картинка сохранит режим RGBA и улетит на фронтенд Павла кристально прозрачной!
                    if style_id == "skulla_tool_pure_cutout":
                        img = img.convert('RGBA')
                    else:
                        # Для обычных шаблонов инфографики сохраняем твой родной RGB-фолбэк
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                    
                    # # МОМЕНТ СПИСАНИЯ ДЛЯ КАРТИНОК С БАЗЫ ДАННЫХ В СЕССИИ ORM
                    if not is_anon and final_cost > 0:
                        if payment_type == "bones":
                            user.bones -= final_cost
                            print(f"🍏 [⚡ B2B ECONOMY]: Списано {final_cost} Бонов за инфографику у юзера {user.id}")
                        else:
                            user.skulls -= final_cost
                            print(f"🍏 [⚡ B2B ECONOMY]: Списано {final_cost} Скаллов за инфографику у юзера {user.id}")
                        db.commit()
                        db.refresh(user)
                        
                    final_name = f"skulla_infographic_{uuid.uuid4().hex[:12]}.png"
                    target_path = os.path.join("static", "results", final_name)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # 🔥 СКАЛЛА-ФИКС №2: Сохраняем с поддержкой альфа-канала, если это вырезка!
                    if style_id == "skulla_tool_pure_cutout":
                        img.save(target_path, "PNG", optimize=True)
                    else:
                        img.save(target_path, "PNG")


                return {
                    "status": "success",
                    "payment_type": payment_type,
                    "download_url": f"/static/results/{final_name}",
                    "new_balance": {"bones": user.bones, "skulls": user.skulls}
                }

            except Exception as e:
                if not is_anon: db.rollback()
                print(f"❌ [EXPORT_IMAGE_ERROR]: {str(e)}")
                raise HTTPException(500, f"Ошибка при подготовке графического файла: {e}")

    except HTTPException as http_ex:
        raise http_ex
    except Exception as general_err:
        print(f"❌ [GLOBAL EXPORT CRASH]: {general_err}")
        raise HTTPException(500, f"Критический сбой транзакции экспорта: {general_err}")




from fastapi import HTTPException, UploadFile, File, Form
import io
import os
from PIL import Image

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 Мегабайт
async def check_file_size(file: UploadFile):
    file_size = getattr(file, "size", None)
    if file_size is None:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        # Шлем технический код
        raise HTTPException(
            status_code=413, 
            detail="ERROR_FILE_TOO_LARGE" 
        )



import os
import shutil
from core.vision import detect_product_name_local, generate_auto_marketing_utp

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.vision import choose_category, auto_select_best_background, analyze_product_color_hsv

import os
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
# Убедись, что твои функции импортированы корректно:
from core.vision import (
    detect_product_name_local, 
    generate_ai_title_json, 
    generate_ai_utp_list_json, 
    generate_ai_short_desc_json,
    translate_via_qwen
)

@router.post("/upload")
async def upload_user_image(
    file: UploadFile = File(...),
    style_id: str = Form(None),
    old_session_id: str = Form(None),
    requested_fields: str = Form(None)  # 🎯 ЛОВИМ НАШУ СТРОКУ С ПОЛЯМИ С ФРОНТА
):
    # 🧼 ШАГ 1: КВАНТОВЫЙ АВТО-КЛИНИНГ МУСОРА ОТ ШЕФА
    if old_session_id:
        # Хирургически чистим строку от попыток хакеров выйти из папки (удаляем точки и слэши)
        clean_old_id = "".join(c for c in old_session_id if c.isalnum() or c in "-_")
        if clean_old_id:
            # Строим абсолютный путь к старой папке на сервере
            # (Если UPLOAD_DIR не импортирован, можно вытащить его динамически или использовать твою константу)
            old_path = os.path.join("uploads", clean_old_id) 
            if os.path.exists(old_path) and os.path.isdir(old_path):
                try:
                    shutil.rmtree(old_path)
                    print(f"🧼 [GARBAGE COLLECTOR]: Старая мусорная сессия '{clean_old_id}' успешно стерта с диска VDS!", flush=True)
                except Exception as e:
                    print(f"⚠️ [GARBAGE_ERROR]: Не удалось удалить сессию {clean_old_id}: {e}", flush=True)

    # 1. Проверяем размер перед чтением
    await check_file_size(file)

    # 🚀 ШАГ 2: ДАЛЬШЕ ТВОЙ ИДЕАЛЬНЫЙ РОДНОЙ КОНВЕЙЕР ИНИЦИАЛИЗАЦИИ
    session_id, session_path = SessionManager.create_session()

    # === НАЧАЛО ТОЧЕЧНОЙ ЗАМЕНЫ ШЕФА (СТРОКИ 544-604) ===
    # 1. Считываем сырой файл (ТВОЙ РОДНОЙ КОД)
    img_data = await file.read()
    img = Image.open(io.BytesIO(img_data))

    # 2. ТВОЙ РОДНОЙ КОД — Процессор полностью вырезает фон и сохраняет no_bg.png!
    effect_cfg = EFFECTS_DATA.get(style_id, {})
    requirements = effect_cfg.get("user_pre", [])
    if "no_bg" not in requirements:
        requirements.append("no_bg") 

    success, error_msg = ImageProcessor.prepare_layer(img, session_path, "original.png", requirements)

    auto_payload = None  # Вызов генератора на "Товар" УДАЛЕН К ЧЕРТЯМ!
    detected_product = "product"
    category_key = "unknown"
    product_name_ru = detected_product
    utp_data = {}
    
    # Если фон успешно вырезан — берем на ИИ-анализ кристальный no_bg.png!
    if success:
        try:
            clean_img_path = os.path.join(session_path, "no_bg.png")
            
            if os.path.exists(clean_img_path):
                # Наживую считываем байты силуэта товара без визуального мусора фона
                with open(clean_img_path, "rb") as clean_f:
                    clean_bytes = clean_f.read()

                # Скармливаем локальному ИИ MobileNet чистый силуэт без фона
                # # Скармливаем локальному ИИ чистый силуэт без фона
                if requested_fields is None:
                    requested_fields = ""
                fields_list = [f.strip() for f in requested_fields.split(",")] 
                text_triggers = ["title", "short_desc", "utp", "descriptions_1", "badges_list"]
                need_qwen = any(t in "".join(fields_list).lower() for t in text_triggers)
                
                if need_qwen:
                    print("📡 [SKULLA INFERENCE]: Запрос содержит тексты. Запускаем Квен...", flush=True)
                    detected_product = detect_product_name_local(clean_bytes)
                    category_key = choose_category(detected_product)
                    utp_data = generate_ai_utp_list_json(detected_product)
                    product_name_ru = translate_via_qwen(detected_product)

                else:
                    print("🍏 [SKULLA BYPASS SUCCESS]: Чистая графика или улучшение фото. Квен успешно заблокирован!", flush=True)
                    # Вытаскиваем уже определенные данные из сессии Павла, Квен отдыхает


                import json
                try:

                    # 2. Инициализируем пустой финальный JSON-словарь под data-ai-field на фронте
                    auto_payload = {}

                    # 3. Собираем ответ, поочередно вызывая изолированные функции и склеивая их словари через .update()
                    if "title" in fields_list:
                        title_json = {"title": product_name_ru} #generate_ai_title_json(detected_product)  # Вернет {"title": "..."}
                        auto_payload.update(title_json)
                        
                    if "utp_list" in fields_list:
                        auto_payload.update(utp_data)
                        
                    if any(f in fields_list for f in ["template2_descriptions_1", "template2_descriptions_2", "template2_descriptions_3"]):
                        try:
                            from core.vision import generate_template2_short_descriptions_local
                            
                            # 1. Забираем сырую строку преимуществ из нашего глобального донора данных
                            raw_utp_string = utp_data.get("utp_list", "Хит продаж\nВысокое качество\nРекомендуем")
                            
                            # Идеально пилим текст по \n на чистый массив для падежного генератора
                            utp_array = [u.strip() for u in raw_utp_string.split("\n") if u.strip()]
                            while len(utp_array) < 3:
                                utp_array.append("высокое качество")
                            
                            # 2. Вызываем короткий генератор: получаем готовый словарь трех описаний
                            # 🎯 СКАЛЛА-ФИКС СИГНАТУРЫ ИМЕН: Сносим utp_list и передаем utp1, utp2, utp3!
                            # Раскладываем массив по трем одиночным индексам, навсегда выжигая квадратные скобки и этот TypeError!
                            t2_short_dict = generate_template2_short_descriptions_local(
                                product_name_en=product_name_ru,
                                category_key=category_key,
                                utp1=utp_array[0],
                                utp2=utp_array[1],
                                utp3=utp_array[2]
                            )

                            
                            # Нативно зашиваем 3 коротких описания в полезную нагрузку
                            auto_payload.update(t2_short_dict)

                            # =====================================================================
                            # 🎯 СКАЛЛА-РАЗГОН: СКВОЗНОЕ НАСЛЕДОВАНИЕ СТИЛЕЙ ЦВЕТА И ШРИФТОВ ДЛЯ Т3!
                            # =====================================================================
                            # Вытаскиваем дизайнерские параметры из utp_data (твоей базы категорий)
                            # Если в какой-то категории их нет — подставляем безопасный e-commerce дефолт
                            text_color = utp_data.get("text_color", "#ffffff")
                            bg_color = utp_data.get("bg_color", "#000000")
                            font_family = utp_data.get("font_family", "Arial")
                            font_size = utp_data.get("font_size", "14") # Твой дефолтный размер для описаний

                            # Динамически упаковываем стили в auto_payload с суффиксами 1, 2, 3!
                            # Имена ключей должны микрон в микрон совпадать с "ai_field" из твоего HTML-конфига!
                            auto_payload.update({
                                # Стили для текстовой области Feature_1
                                "template2_descriptions_1_text_color": text_color,
                                "template2_descriptions_1_bg_color": bg_color,
                                "template2_descriptions_1_font_family": font_family,
                                "template2_descriptions_1_font_size": font_size,
                                
                                # Стили для текстовой области Feature_2
                                "template2_descriptions_2_text_color": text_color,
                                "template2_descriptions_2_bg_color": bg_color,
                                "template2_descriptions_2_font_family": font_family,
                                "template2_descriptions_2_font_size": font_size,
                                
                                # Стили для текстовой области Feature_3
                                "template2_descriptions_3_text_color": text_color,
                                "template2_descriptions_3_bg_color": bg_color,
                                "template2_descriptions_3_font_family": font_family,
                                "template2_descriptions_3_font_size": font_size,
                            })
                            
                            print(f"超 [SKULLA DESIGN ENGINE SUCCESS]: Цвета и шрифты полей Feature 1-3 успешно синхронизированы!", flush=True)
                            
                        except Exception as e:
                            print(f"🚨 [❌ WARN ROUTE T2]: Не удалось собрать короткие шаблоны и стили: {e}", flush=True)
                            auto_payload.update({
                                "template2_descriptions_1": f"Качественный {detected_product} премиального уровня.",
                                "template2_descriptions_2": f"Надежный {detected_product} для ежедневного использования.",
                                "template2_descriptions_3": f"Стильный {detected_product} по доступной цене."
                            })




                    # 🎯 ТИТАНОВЫЙ СКАЛЛА-МОСТ ПАВЛА (ОДИН ВХОДНОЙ ШЛЮЗ ДЛЯ КОНТЕНТА):
                    # Так как в JSON-конфиге третьего шаблона поле Showcase Text Block привязано к ai_field: "short_desc",
                    # мы силой заставляем этот блок генерировать одно длинное, богатое СЕО-описание!
                    if "short_desc" in fields_list:
                        try:
                            from core.vision import generate_template2_descriptions_local
                            
                            # Идеально пилим глобальную строку донора по \n на чистый Python-список
                            utp_array = [u.strip() for u in utp_data.get("utp_list", "").split("\n") if u.strip()]
                            while len(utp_array) < 3:
                                utp_array.append("высокое качество")
                            
                            # Вызываем нашу всемогущую функцию: она вернет СТРОГО ОДНУ длинную строку (str) для 21 категории!
                            long_description_str = generate_template2_descriptions_local(
                                product_name_en=product_name_ru,
                                category_key=category_key,
                                utp_list=utp_array
                            )
                            
                            # Зашиваем СЕО-текст строго в ключ "short_desc" микрон в микрон под твой JSON-конфиг!
                            auto_payload["short_desc"] = long_description_str
                            print(f"🍏 [SKULLA T3 MONOLITH SUCCESS]: Одно длинное СЕО-описание успешно зашито в шлюз 'short_desc'!", flush=True)
                            
                        except Exception as e:
                            print(f"🚨 [❌ WARN ROUTE T3]: Не удалось собрать длинный текст в short_desc: {e}", flush=True)
                            auto_payload["short_desc"] = f"Премиальный качественный {detected_product} для вашего удобства."


                        
                    # Шаг Б: Вытаскиваем сгенерированные строки для нашего автоподборщика фонов
                    ai_title_str = auto_payload.get("title", "Название товара")
                    ai_utp_str = auto_payload.get("utp_list", "Преимущество №1\nПреимущество №2")

                    # 1. 🧠 АНАЛИЗИРУЕМ СИЛУЭТ ТОВАРА БЕЗ ФОНА
                    # clean_bytes — это байты картинки товара, из которой уже вырезан фон!
                    product_color_meta = analyze_product_color_hsv(clean_bytes)
                    print(f"🎨 [SKULLA COLOR]: Анализ товара завершен. Hue: {product_color_meta['hue']}°, Ахроматичный: {product_color_meta['is_achromatic']}", flush=True)

                    # 2. ПОДБИРАЕМ ИДЕАЛЬНЫЙ ФОН НА ОСНОВЕ НАУЧНЫХ ПРАВИЛ ДИЗАЙНА
                    # Передаем четвертым аргументом product_color_meta!
                    designer_payload = auto_select_best_background(category_key, ai_title_str, ai_utp_str, product_color_meta)
                    auto_payload.update(designer_payload)


                    # 🎯 ФИКС ДЛЯ ФРОНТЕНДА: Сканируем папку прямо сейчас в Python!
                    preview_dir = os.path.join("static", "backgrounds_preview", category_key)
                    
                    if os.path.exists(preview_dir):
                        # Собираем чистые имена файлов без расширения .png
                        available_files = [os.path.splitext(f)[0] for f in os.listdir(preview_dir) if f.lower().endswith('.png')]
                    else:
                        available_files = [] # Дефолт
                        
                    # Кладем этот массив прямо в auto_payload под специальным ключом!
                    auto_payload["category_backgrounds_list"] = available_files                    
                    # Записываем все подобранные стили прямо в наш финальный auto_payload!
                    # Так как внутри auto_select_best_background ключи НАПРЯМУЮ переписаны под твои сквозные ID
                    # ('main_title', 'badges_list'), мы просто объединяем словари!
                    #auto_payload.update(designer_payload)

                    # Удаляем старые несквозные ключи ИИ, чтобы они не засоряли JSON
                    auto_payload.pop("title", None)
                    auto_payload.pop("utp_list", None)

                    """
                    # 🦾 СКАЛЛА-РАЗГОН: Вызываем английскую генерацию и пулей переводим на русский!
                    try:
                        from core.vision import generate_product_description_local, translate_via_qwen
                        
                        # 1. Забираем чистейший английский маркетинг от Квена (без тормозов и зацикливаний!)
                        ai_description_en = generate_product_description_local(detected_product)
                        
                        # 2. 🔥 ПРОГОНЯЕМ ЧЕРЕЗ ТВОЙ РОДНОЙ ПЕРЕВОДЧИК СЕРВЕРА SKULLA!
                        # Подставь сюда имя своей функции перевода строк, которая шуршит в твоем бэкенде
                        ai_description_text = translate_via_qwen(ai_description_en)
                        
                        print(f"🍏 [SKULLA TRANSLATOR SUCCESS]: Английский текст Квена успешно переведен на русский!", flush=True)
                    except Exception as e:
                        print(f"🚨 [❌ WARN DETECTOR]: Не удалось сгенерить/перевести текст: {e}", flush=True)
                        ai_description_text = "Качественный автомобильный видеорегистратор для вашей безопасности."
                    """


                except Exception as qwen_err:
                    print(f"❌ [QWEN FIELD GENERATION ERROR]: {qwen_err}", flush=True)
                    # Железный страховочный фолбек, чтобы фронтенд редактора не упал при сбое ИИ
                    auto_payload = {
                        "title": detected_product,
                        "utp_list": "Хит продаж\nВысокое качество\nБыстрая доставка",
                        "short_desc": "Отличный выбор по доступной цене."
                    }

        except Exception as ai_err:
            print(f"⚠️ [WARN AI NO_BG]: Ошибка ИИ-анализа по силуэту no_bg: {ai_err}", flush=True)


    return {
        "status": "success" if success else "warning",
        "message": error_msg,
        "session_id": session_id,
        "url": f"/uploads/{session_id}/original.png",
        "meta": {"requirements": requirements, "face_ok": "success"},
        "detected_item": detected_product,
        "category_key": category_key,
        "auto_fields": auto_payload
        #"ai_description": ai_description_text 
    }



@router.post("/upload_layer")
async def upload_layer(
    layer_file: UploadFile = File(...), 
    session_id: str = Form(...), 
    layer_id: str = Form(...),
    style_id: str = Form(None)
):
    # 🎯 2. Проверяем размер слоя
    await check_file_size(layer_file)

    session_path = SessionManager.get_session_path(session_id)
    if not os.path.exists(session_path):
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    img_data = await layer_file.read()
    img = Image.open(io.BytesIO(img_data))
    
    effect_cfg = EFFECTS_DATA.get(style_id, {})
    requirements = effect_cfg.get("layer_pre", [])
    
    file_name = f"{layer_id}.png"
    success, error_msg = ImageProcessor.prepare_layer(img, session_path, file_name, requirements)
    
    return {
        "status": "success" if success else "warning",
        "message": error_msg,
        "filename": file_name,
        "url": f"/uploads/{session_id}/{file_name}",
        "face_ok": success
    }




# Если роутер еще не объявлен в этом файле, раскомментируй строку ниже:
# router = APIRouter(prefix="/api/ai", tags=["AI Test"])

# 1. Объявляем схему запроса от фронтенда
class CustomPromptRequest(BaseModel):
    prompt: str

# 2. Создаем сам эндпоинт
@router.post("/test-prompt")
async def api_test_custom_prompt(payload: CustomPromptRequest):
    """
    🚀 Временный эндпоинт для фронта: отправляешь prompt -> получаешь ответ ИИ
    """
    if not payload.prompt:
        raise HTTPException(status_code=400, detail="Промпт не может быть пустым")
        
    # Вызываем тяжелую логику генерации
    ai_response = ""#generate_custom_prompt_local(payload.prompt)
    
    return {
        "status": "success",
        "prompt": payload.prompt,
        "response": ai_response
    }

import os
from fastapi import APIRouter # или твой фреймворк

@router.get("/get_category_backgrounds/{category_id}")
async def get_category_backgrounds(category_id: str):
    # Путь к папке превьюшек на сервере, например: static/backgrounds_preview/cat_electronics
    preview_dir = os.path.join("static", "backgrounds_preview", category_id)
    
    if not os.path.exists(preview_dir):
        return {"status": "error", "backgrounds": []}
        
    # Сканируем папку на диске и забираем имена файлов БЕЗ расширения .png
    # os.path.splitext(f)[0] превратит "charcoal.png" в чистую строку "charcoal"
    files = [os.path.splitext(f)[0] for f in os.listdir(preview_dir) if f.lower().endswith('.png')]
    
    return {"status": "success", "backgrounds": files}


# ==============================================================================
# 🔥 СЕКЦИЯ СИСТЕМЫ СВОЕЙ GPU ГЕНЕРАЦИИ (FISHHOOK AI)
# ==============================================================================
import os
import time
from pydantic import BaseModel
from fastapi import UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

# Глобальные словари памяти модуля (инициализируются один раз при старте сервера)
FISHHOOK_TASKS = {}
WORKER_ONLINE = {}

# Pydantic-схема для валидации входящего JSON-запроса от фронтенда кнопки
class FishHookTaskRequest(BaseModel):
    user_login: str
    session_id: str
    prompt_style: str

# --- 1. ЭНДПОИНТ СТАТУСА (СВЕТОФОР) ---
# Автоматический префикс роутера /api/studio приклеится сам -> /api/studio/fishhook/status/{user_login}
@router.get("/fishhook/status/{user_login}")
async def get_worker_status(user_login: str):
    clean_login = user_login.lower().strip()
    
    last_ping = WORKER_ONLINE.get(clean_login, 0)
    # Если Колаб присылал пинг меньше 15 секунд назад — видеокарта онлайн
    is_online = (time.time() - last_ping) < 15.0
    return {"online": is_online}


# --- 2. ЭНДПОИНТ СОЗДАНИЯ ЗАДАЧИ (КНОПКА НА САЙТЕ) ---
# Итоговый адрес: POST /api/studio/fishhook/create_task
@router.post("/fishhook/create_task")
async def create_fishhook_task(payload: FishHookTaskRequest):
    task_id = f"task_{int(time.time())}"
    clean_login = payload.user_login.lower().strip()
    
    # Строим путь строго к файлу original.png внутри текущей папки сессии
    session_dir = f"./uploads/{payload.session_id}"
    source_file = os.path.join(session_dir, "original.png")
    
    # Жесткая проверка физического наличия исходника товара на сервере
    if not os.path.exists(source_file):
        raise HTTPException(
            status_code=404, 
            detail=f"Исходное изображение товара 'original.png' не найдено в сессии {payload.session_id}!"
        )

    # Пакуем изолированную задачу в память модуля
    FISHHOOK_TASKS[clean_login] = {
        "status": "pending",
        "task_id": task_id,
        "session_id": payload.session_id,
        "user_login": clean_login,
        "prompt_style": payload.prompt_style,
        "result_url": None
    }
    return {"status": "queued", "task_id": task_id}


# --- 3. ЭНДПОИНТ ОПРОСА ГОТОВНОСТИ (ЛОАДЕР НА САЙТЕ) ---
# Итоговый адрес: GET /api/studio/fishhook/check_task/{user_login}/{task_id}
@router.get("/fishhook/check_task/{user_login}/{task_id}")
async def check_task_readiness(user_login: str, task_id: str):
    clean_login = user_login.lower().strip()
    
    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        return {"status": "not_found"}
        
    if task["status"] == "completed":
        result_url = task["result_url"]
        # Тотально чистим задачу из оперативной памяти, так как результат успешно зафиксирован фронтом
        del FISHHOOK_TASKS[clean_login]
        return {"status": "completed", "result_url": result_url}
        
    return {"status": task["status"]}


# --- 4. ДЛЯ КОЛАБА: ЗАПРОС ЗАДАЧИ И ФИКСАЦИЯ ОНЛАЙНА (LONG POLLING) ---
# Итоговый адрес: GET /api/studio/fishhook/get_task/{user_login}
@router.get("/fishhook/get_task/{user_login}")
async def get_task_for_colab(user_login: str):
    clean_login = user_login.lower().strip()

    # Фиксируем время входящего пинга от воркера Колаба
    WORKER_ONLINE[clean_login] = time.time()

    max_wait_time = 4  # Сколько секунд максимум удерживать соединение с Колабом
    check_interval = 2  # Как часто заглядывать в словарь памяти (в секундах)
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        task = FISHHOOK_TASKS.get(clean_login)
        
        if task and task.get("status") == "pending":
            # Переводим статус в работу, чтобы предотвратить дублирующие перехваты
            task["status"] = "processing"
            return {
                "status": "success",
                "task_data": {
                    "task_id": task["task_id"],
                    "session_id": task["session_id"],
                    "user_login": task["user_login"],
                    "prompt_style": task["prompt_style"]
                }
            }

        # Если задачи нет — освобождаем поток сервера на 2 секунды.
        # В это окно сервер моментально и без лагов примет загрузку картинок!
        await asyncio.sleep(check_interval)
        elapsed_time += check_interval

    # Если за 20 секунд задача так и не появилась, возвращаем пустой статус
    return {"status": "no_tasks"}


# --- 5. ДЛЯ КОЛАБА: СКАЧИВАНИЕ ИСХОДНИКА ТОВАРА ИЗ ПАПКИ СЕССИИ ---
# Итоговый адрес: GET /api/studio/fishhook/download_source/{session_id}
@router.get("/fishhook/download_source/{session_id}")
async def download_source_from_session(session_id: str):
    """Колаб дергает этот роут, чтобы скачать original.png из нужной папки сессии"""
    file_path = f"./uploads/{session_id}/original.png"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Файл original.png физически отсутствует на диске сессии")


# --- 6. ДЛЯ КОЛАБА: ПРИЕМ ГОТОВОЙ КАРТИНКИ И ЗАПИСЬ В СЕССИЮ ---
# Итоговый адрес: POST /api/studio/fishhook/submit_result
@router.post("/fishhook/submit_result")
async def submit_result_from_colab(
    task_id: str = Form(...),
    user_login: str = Form(...),
    image: UploadFile = File(...)
):
    clean_login = user_login.lower().strip()
    
    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        raise HTTPException(status_code=400, detail="Задача устарела, была перехвачена или не найдена в памяти")
        
    session_id = task["session_id"]
    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    # Сохраняем ИИ-результат строго под системным именем after.png в папку текущей сессии селлера!
    file_path = os.path.join(session_dir, "after.png")
    
    try:
        contents = await image.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось записать готовый ИИ-файл в папку сессии: {e}")
        
    # Формируем относительный URL превью для фронтенда (один-в-один как на твоем оригинальном скриншоте!)
    result_url = f"/api/studio/preview/{session_id}/after"
    
    task["status"] = "completed"
    task["result_url"] = result_url
    
    return {"status": "received"}


import os
import time
import hashlib
from fastapi import UploadFile, File, Form, HTTPException

import time
import io
from PIL import Image
from fastapi import UploadFile, File, Form, HTTPException

@router.post("/upload_v2")
async def upload_photo_v2(
    file: UploadFile = File(...),
    user_login: str = Form(...)
):
    clean_login = user_login.lower().strip()
    task_id = f"task_{int(time.time())}"

    # 🚀 ШАГ 1: Твой родной конвейер инициализации сессии
    # Он сам создаст нужную структуру папок на сервере!
    session_id, session_path = SessionManager.create_session()

    try:
        # Проверяем размер файла перед чтением (как в твоем оригинальном коде)
        await check_file_size(file)

        # Считываем сырой файл
        img_data = await file.read()
        img = Image.open(io.BytesIO(img_data))

        # 🚀 ШАГ 2: Твой родной метод сохранения оригинальной картинки
        # Передаем пустой список требований [], чтобы сервер просто сохранил original.png,
        # без тяжелой процессорной вырезки фона (no_bg)! Это займет миллисекунды.
        success, error_msg = ImageProcessor.prepare_layer(img, session_path, "original.png", [])

        if not success:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {error_msg}")

    except Exception as e:
        print(f"❌ [UPLOAD_V2_ERROR]: Не удалось сохранить файл через ImageProcessor: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки файла на сервере")

    # 🚀 ШАГ 3: Мгновенно публикуем задачу в оперативную память для Колаба
    FISHHOOK_TASKS[clean_login] = {
        "status": "pending",
        "task_id": task_id,
        "session_id": session_id,
        "session_path": session_path,  # Запоминаем путь, который сгенерировал SessionManager
        "user_login": clean_login,
        "prompt_style": "high quality commercial clothing texture, fashion look"
    }

    print(f"📦 [UPLOAD_V2]: Файл сохранен через ImageProcessor. Задача {task_id} в памяти.")

    # 🚀 ШАГ 4: Моментальный ответ фронтенду (Запрос закроется за сотые доли секунды)
    return {
        "status": "processing_started",
        "task_id": task_id,
        "session_id": session_id
    }


import time
import io
from PIL import Image
from fastapi import UploadFile, File, Form, HTTPException

@router.post("/upload_tryon_v3")
async def upload_tryon_v3(
    file_person: UploadFile = File(...),   # Принимает ключ "file_person" с фронта
    file_garment: UploadFile = File(...),  # Принимает ключ "file_garment" с фронта
    user_login: str = Form(...)
):
    clean_login = user_login.lower().strip()
    task_id = f"task_{int(time.time())}"

    # 1. Твой родной конвейер инициализации сессии (создает одну общую папку для файлов)
    session_id, session_path = SessionManager.create_session()

    try:
        # Валидация размера файлов (твои оригинальные проверки)
        await check_file_size(file_person)
        await check_file_size(file_garment)

        # Читаем байты и открываем фото человека через PIL
        person_bytes = await file_person.read()
        img_person = Image.open(io.BytesIO(person_bytes))

        # 2. Твой родной prepare_layer сохраняет "person.png"
        # Передаем пустой список [], чтобы пропустить медленное удаление фона процессором сервера
        success_p, err_p = ImageProcessor.prepare_layer(img_person, session_path, "person.png", [])
        if not success_p:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения модели: {err_p}")

        # Читаем байты и открываем фото одежды через PIL
        garment_bytes = await file_garment.read()
        img_garment = Image.open(io.BytesIO(garment_bytes))

        # Твой родной prepare_layer сохраняет "garment.png"
        success_g, err_g = ImageProcessor.prepare_layer(img_garment, session_path, "garment.png", [])
        if not success_g:
            raise HTTPException(status_code=500, detail=f"Ошибка сохранения одежды: {err_g}")

    except Exception as e:
        print(f"❌ [UPLOAD_V3_ERROR]: Сбой при сохранении пары файлов через ImageProcessor: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки файлов на сервере")

    # 3. МГНОВЕННО ПУБЛИКУЕМ ЗАДАЧУ В ПАМЯТЬ ДЛЯ КОЛАБА
    # Сервер выполнил свою работу за сотые доли секунды и полностью свободен
    FISHHOOK_TASKS[clean_login] = {
        "status": "pending",
        "task_id": task_id,
        "session_id": session_id,
        "session_path": session_path,
        "user_login": clean_login,
        # Запоминаем точные имена файлов внутри сессии
        "person_filename": "person.png",
        "garment_filename": "garment.png",
        "prompt_style": "high quality commercial clothing texture, fashion look"
    }

    print(f"📦 [UPLOAD_V3]: Пара файлов успешно разложена в {session_id}. Задача {task_id} ждет Колаб.")

    # 4. Моментальный ответ фронтенду (Ноль лагов, Nginx не выдаст 504)
    return {
        "status": "processing_started",
        "task_id": task_id,
        "session_id": session_id
    }





@router.post("/fishhook/voice_chat")
async def voice_chat_endpoint(
    role: str = Form(...),
    gender: str = Form(...),
    user_login: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """
    СЕРВЕРНЫЙ МОСТ ГОЛОСА:
    Принимает аудио из браузера, кладёт на диск сессии и ставит задачу в очередь для Колаба!
    """
    clean_login = user_login.lower().strip()
    
    # 1. Генерируем уникальный ID для голосовой задачи
    voice_task_id = f"voice_{int(time.time())}"
    session_id = f"v_sess_{clean_login}" # Фиксированная папка сессии для голоса пользователя
    
    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    # Сохраняем исходный голос пользователя
    input_audio_path = os.path.join(session_dir, "user_voice.wav")
    try:
        contents = await audio_file.read()
        with open(input_audio_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось записать аудио на бэкенд: {e}")

    # 2. ПУБЛИКУЕМ ЗАДАЧУ В ОЧЕРЕДЬ FISHHOOK_TASKS (Её тут же прочитает Колаб!)
    FISHHOOK_TASKS[clean_login] = {
        "status": "pending",
        "task_id": voice_task_id,
        "session_id": session_id,
        "user_login": clean_login,
        "prompt_style": "voice_chat",  # Тег задачи, чтобы воркер понял, что нужно включить мозг и микрофон
        "voice_role": role,            # Передаем выбранную роль (пират, психолог)
        "voice_gender": gender         # Передаем пол голоса для озвучки
    }
    
    print(f"🎙️ [ОЧЕРЕДЬ СЕРВЕРА]: Создана голосовая задача {voice_task_id} для Колаба.")
    return {"status": "queued", "task_id": voice_task_id}


# ==============================================================================
# 🔥 FISHHOOK AI — ФИНАЛЬНАЯ ВЕРСИЯ С ПЕРСОНАЖАМИ И ГЕНЕРАЦИЕЙ ИЗОБРАЖЕНИЙ
# ==============================================================================
# ВЕРСИЯ: 2.1 (с исправлениями для фронтенда)
# ДАТА: 2024
# ==============================================================================

import os
import time
import json
import hashlib
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Твоё ядро (Бизнес-логика)
from database import get_db, SessionLocal
from core.models import User
from core.auth import get_current_user
from core.analytics import AnalyticsManager
from core.processor import ImageProcessor
from core.session_manager import SessionManager
from config import UPLOAD_DIR

router = APIRouter(prefix="/api/studio", tags=["Studio"])

# Глобальные словари памяти модуля
FISHHOOK_TASKS = {}
WORKER_ONLINE = {}


# ==============================================================================
# 📋 PYDANTIC-СХЕМЫ ДЛЯ ВАЛИДАЦИИ ЗАПРОСОВ
# ==============================================================================

class FishHookTaskRequest(BaseModel):
    """Базовая схема для создания задачи"""
    user_login: str
    session_id: str
    prompt_style: str


class VoiceChatRequest(BaseModel):
    """Схема для голосового чата с поддержкой персонажей и генерации изображений"""
    user_login: str
    role: Optional[str] = "assistant"
    gender: Optional[str] = "male"
    character: Optional[str] = "anna"
    text_message: Optional[str] = ""
    generate_image: Optional[bool] = False
    image_prompt: Optional[str] = ""


# ==============================================================================
# 🔥 СЕКЦИЯ СИСТЕМЫ GPU ГЕНЕРАЦИИ (FISHHOOK AI)
# ==============================================================================

# --- 1. ЭНДПОИНТ СТАТУСА (СВЕТОФОР) ---
@router.get("/fishhook/status/{user_login}")
async def get_worker_status(user_login: str):
    """Проверяет, онлайн ли воркер Colab/Kaggle"""
    clean_login = user_login.lower().strip()

    last_ping = WORKER_ONLINE.get(clean_login, 0)
    is_online = (time.time() - last_ping) < 15.0
    return {"online": is_online}


# --- 2. ЭНДПОИНТ СОЗДАНИЯ ЗАДАЧИ (КНОПКА НА САЙТЕ) ---
@router.post("/fishhook/create_task")
async def create_fishhook_task(payload: FishHookTaskRequest):
    """Создаёт задачу для обработки воркером"""
    task_id = f"task_{int(time.time())}"
    clean_login = payload.user_login.lower().strip()

    session_dir = f"./uploads/{payload.session_id}"
    source_file = os.path.join(session_dir, "original.png")

    if not os.path.exists(source_file):
        raise HTTPException(
            status_code=404,
            detail=f"Исходное изображение 'original.png' не найдено в сессии {payload.session_id}!"
        )

    FISHHOOK_TASKS[clean_login] = {
        "status": "pending",
        "task_id": task_id,
        "session_id": payload.session_id,
        "user_login": clean_login,
        "prompt_style": payload.prompt_style,
        "result_url": None
    }
    return {"status": "queued", "task_id": task_id}


# --- 3. ЭНДПОИНТ ОПРОСА ГОТОВНОСТИ (ЛОАДЕР НА САЙТЕ) ---
@router.get("/fishhook/check_task/{user_login}/{task_id}")
async def check_task_readiness(user_login: str, task_id: str):
    """Проверяет статус задачи и возвращает URL аудио/изображения"""
    clean_login = user_login.lower().strip()

    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        return {"status": "not_found"}

    if task["status"] == "completed":
        # Возвращаем все URL для фронтенда
        response = {
            "status": "completed",
            "bot_text": task.get("bot_text", ""),
            "user_text": task.get("user_text", ""),
            "audio_url": task.get("audio_url"),
            "image_url": task.get("image_url")
        }
        # НЕ удаляем задачу сразу - даём фронтенду время скачать файлы
        # del FISHHOOK_TASKS[clean_login]
        return response

    return {"status": task["status"]}


# --- 4. ДЛЯ КОЛАБА: ЗАПРОС ЗАДАЧИ И ФИКСАЦИЯ ОНЛАЙНА (LONG POLLING) ---
@router.get("/fishhook/get_task/{user_login}")
async def get_task_for_colab(user_login: str):
    """Воркер Colab/Kaggle опрашивает этот эндпоинт для получения задач"""
    clean_login = user_login.lower().strip()

    # Фиксируем время входящего пинга от воркера
    WORKER_ONLINE[clean_login] = time.time()

    max_wait_time = 4
    check_interval = 2
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        task = FISHHOOK_TASKS.get(clean_login)

        if task and task.get("status") == "pending":
            task["status"] = "processing"

            # Формируем ответ с ВСЕМИ параметрами задачи
            response_data = {
                "task_id": task["task_id"],
                "session_id": task["session_id"],
                "user_login": task["user_login"],
                "prompt_style": task["prompt_style"]
            }

            # Добавляем параметры голосового чата если есть
            if "voice_role" in task:
                response_data["voice_role"] = task["voice_role"]
            if "voice_gender" in task:
                response_data["voice_gender"] = task["voice_gender"]
            if "character" in task:
                response_data["character"] = task["character"]
            if "text_message" in task:
                response_data["text_message"] = task["text_message"]
            if "generate_image" in task:
                response_data["generate_image"] = task["generate_image"]
            if "image_prompt" in task:
                response_data["image_prompt"] = task["image_prompt"]

            return {
                "status": "success",
                "task_data": response_data
            }

        await asyncio.sleep(check_interval)
        elapsed_time += check_interval

    return {"status": "no_tasks"}


# --- 5. ДЛЯ КОЛАБА: СКАЧИВАНИЕ ИСХОДНИКА ИЗ ПАПКИ СЕССИИ ---
@router.get("/fishhook/download_source/{session_id}")
async def download_source_from_session(session_id: str, filename: str = "user_voice.wav"):
    """Колаб дергает этот роут, чтобы скачать файл из папки сессии"""
    file_path = f"./uploads/{session_id}/{filename}"
    if os.path.exists(file_path):
        # Определяем MIME-тип по расширению
        if filename.endswith('.wav'):
            media_type = "audio/wav"
        elif filename.endswith('.png'):
            media_type = "image/png"
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            media_type = "image/jpeg"
        else:
            media_type = "application/octet-stream"

        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail=f"Файл {filename} физически отсутствует на диске сессии")


# --- 5.1. ЭНДПОИНТ ПОЛУЧЕНИЯ АУДИО ОТВЕТА ДЛЯ ФРОНТЕНДА ---
@router.get("/fishhook/get_audio/{session_id}")
async def get_audio_response(session_id: str):
    """Фронтенд дергает этот роут, чтобы получить аудио ответ бота"""
    file_path = f"./uploads/{session_id}/bot_response.wav"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Аудио ответ не найден")


# --- 5.2. ЭНДПОИНТ ПОЛУЧЕНИЯ СГЕНЕРИРОВАННОГО ИЗОБРАЖЕНИЯ ДЛЯ ФРОНТЕНДА ---
@router.get("/fishhook/get_image/{session_id}")
async def get_generated_image(session_id: str):
    """Фронтенд дергает этот роут, чтобы получить сгенерированное изображение"""
    file_path = f"./uploads/{session_id}/generated_image.jpg"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Сгенерированное изображение не найдено")


# --- 6. ДЛЯ КОЛАБА: ПРИЕМ ГОТОВОГО РЕЗУЛЬТАТА ---
@router.post("/fishhook/submit_result")
async def submit_result_from_colab(
    task_id: str = Form(...),
    user_login: str = Form(...),
    user_text: Optional[str] = Form(""),
    bot_text: Optional[str] = Form(""),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Принимает результат от воркера:
    - audio: голосовой ответ (обязательно)
    - image: сгенерированное изображение (опционально)
    - user_text: текст пользователя
    - bot_text: текст ответа бота
    """
    clean_login = user_login.lower().strip()

    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        raise HTTPException(status_code=400, detail="Задача устарела, была перехвачена или не найдена")

    session_id = task["session_id"]
    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    # Сохраняем текст ответа
    if bot_text:
        try:
            text_path = os.path.join(session_dir, "bot_response.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(bot_text)
            print(f"📝 [TEXT SAVED]: Текст ответа сохранён в {text_path}")
        except Exception as e:
            print(f"⚠️ [TEXT SAVE ERROR]: {e}")

    # Сохраняем аудио
    audio_url = None
    if audio:
        try:
            audio_path = os.path.join(session_dir, "bot_response.wav")
            contents = await audio.read()
            with open(audio_path, "wb") as f:
                f.write(contents)
            audio_url = f"/api/studio/fishhook/get_audio/{session_id}"
            print(f"🔊 [AUDIO SAVED]: Аудио сохранено в {audio_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось записать аудио: {e}")

    # Сохраняем изображение (если есть)
    image_url = None
    if image:
        try:
            image_path = os.path.join(session_dir, "generated_image.jpg")
            contents = await image.read()
            with open(image_path, "wb") as f:
                f.write(contents)
            image_url = f"/api/studio/fishhook/get_image/{session_id}"
            print(f"🖼️ [IMAGE SAVED]: Изображение сохранено в {image_path}")
        except Exception as e:
            print(f"⚠️ [IMAGE SAVE ERROR]: Не удалось записать изображение: {e}")

    # Сохраняем URL в задачу для фронтенда
    task["status"] = "completed"
    task["bot_text"] = bot_text
    task["user_text"] = user_text
    task["audio_url"] = audio_url
    task["image_url"] = image_url

    return {
        "status": "received",
        "bot_text": bot_text,
        "audio_url": audio_url,
        "image_url": image_url
    }


# --- 7. НОВЫЙ ЭНДПОИНТ: ГОЛОСОВОЙ ЧАТ С ПЕРСОНАЖАМИ ---
@router.post("/fishhook/voice_chat")
async def voice_chat_endpoint(
    user_login: str = Form(...),
    character: str = Form("anna"),
    text_message: Optional[str] = Form(""),
    generate_image: Optional[bool] = Form(False),
    image_prompt: Optional[str] = Form(""),
    audio_file: Optional[UploadFile] = File(None),
    role: Optional[str] = Form("assistant"),
    gender: Optional[str] = Form("male")
):
    """
    УНИВЕРСАЛЬНЫЙ ЭНДПОИНТ ГОЛОСОВОГО/ТЕКСТОВОГО ЧАТА
    """
    clean_login = user_login.lower().strip()

    voice_task_id = f"voice_{int(time.time())}"
    session_id = f"v_sess_{clean_login}"

    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    # Сохраняем аудио если есть
    if audio_file:
        input_audio_path = os.path.join(session_dir, "user_voice.wav")
        try:
            contents = await audio_file.read()
            with open(input_audio_path, "wb") as f:
                f.write(contents)
            print(f"🎙️ [AUDIO SAVED]: Голос сохранён в {input_audio_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось записать аудио: {e}")

    # ПУБЛИКУЕМ ЗАДАЧУ В ОЧЕРЕДЬ
    task_data = {
        "status": "pending",
        "task_id": voice_task_id,
        "session_id": session_id,
        "user_login": clean_login,
        "prompt_style": "voice_chat",
        "voice_role": role,
        "voice_gender": gender,
        "character": character,
        "text_message": text_message,
        "generate_image": generate_image,
        "image_prompt": image_prompt
    }

    FISHHOOK_TASKS[clean_login] = task_data

    print(f"🎙️ [ОЧЕРЕДЬ]: Задача {voice_task_id} создана для персонажа '{character}'")
    if generate_image:
        print(f"🖼️ [IMAGE GEN]: Запрошена генерация изображения: {image_prompt[:50]}...")

    return {
        "status": "queued",
        "task_id": voice_task_id,
        "character": character,
        "generate_image": generate_image
    }


# --- 8. НОВЫЙ ЭНДПОИНТ: СПИСОК ДОСТУПНЫХ ПЕРСОНАЖЕЙ ---
@router.get("/fishhook/characters")
async def get_available_characters():
    """Возвращает список доступных персонажей"""
    characters = {
        "anna": {
            "name": "Анна",
            "age": 25,
            "personality": "Нежная, романтичная девушка с чувством юмора",
            "style": "romantic",
            "emoji": "💕"
        },
        "kate": {
            "name": "Катя",
            "age": 23,
            "personality": "Дерзкая, уверенная в себе, любит флиртовать",
            "style": "bold",
            "emoji": "🔥"
        },
        "maria": {
            "name": "Мария",
            "age": 28,
            "personality": "Интеллектуалка, любит философию и глубокие разговоры",
            "style": "intellectual",
            "emoji": "📚"
        },
        "lisa": {
            "name": "Лиза",
            "age": 22,
            "personality": "Весёлая, энергичная, обожает тусовки",
            "style": "energetic",
            "emoji": "⚡"
        }
    }

    return {
        "status": "success",
        "characters": characters,
        "default": "anna"
    }


# --- 9. НОВЫЙ ЭНДПОИНТ: ЗАГРУЗКА ГОЛОСОВОГО ОБРАЗЦА ПЕРСОНАЖА ---
@router.post("/fishhook/upload_voice_sample")
async def upload_voice_sample(
    character: str = Form(...),
    voice_file: UploadFile = File(...)
):
    """Загружает образец голоса для персонажа"""
    valid_characters = ["anna", "kate", "maria", "lisa"]
    if character not in valid_characters:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный персонаж '{character}'. Доступные: {', '.join(valid_characters)}"
        )

    voices_dir = "./voices"
    os.makedirs(voices_dir, exist_ok=True)

    voice_path = os.path.join(voices_dir, f"{character}.wav")
    try:
        contents = await voice_file.read()
        with open(voice_path, "wb") as f:
            f.write(contents)
        print(f"🎤 [VOICE SAVED]: Голос персонажа '{character}' сохранён в {voice_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить голос: {e}")

    return {
        "status": "success",
        "character": character,
        "voice_path": voice_path
    }


# --- 10. НОВЫЙ ЭНДПОИНТ: ПОЛУЧЕНИЕ РЕЗУЛЬТАТА С ИЗОБРАЖЕНИЕМ ---
@router.get("/fishhook/get_result/{session_id}")
async def get_chat_result(session_id: str):
    """Возвращает полный результат чата: текст, аудио, изображение"""
    session_dir = f"./uploads/{session_id}"

    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    result = {
        "status": "success",
        "session_id": session_id,
        "has_audio": False,
        "has_image": False,
        "has_text": False,
        "bot_text": ""
    }

    # Проверяем наличие аудио
    audio_path = os.path.join(session_dir, "bot_response.wav")
    if os.path.exists(audio_path):
        result["has_audio"] = True
        result["audio_url"] = f"/uploads/{session_id}/bot_response.wav"

    # Проверяем наличие изображения
    image_path = os.path.join(session_dir, "generated_image.jpg")
    if os.path.exists(image_path):
        result["has_image"] = True
        result["image_url"] = f"/uploads/{session_id}/generated_image.jpg"

    # Проверяем наличие текста
    text_path = os.path.join(session_dir, "bot_response.txt")
    if os.path.exists(text_path):
        result["has_text"] = True
        try:
            with open(text_path, "r", encoding="utf-8") as f:
                result["bot_text"] = f.read()
        except Exception as e:
            print(f"⚠️ [TEXT READ ERROR]: {e}")

    return result


# ==============================================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================

import asyncio

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

async def check_file_size(file: UploadFile):
    """Проверяет размер загружаемого файла"""
    file_size = getattr(file, "size", None)
    if file_size is None:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="ERROR_FILE_TOO_LARGE"
        )
