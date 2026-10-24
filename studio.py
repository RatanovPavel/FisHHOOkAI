# ==============================================================================
# 🔥 FISHHOOK AI v2.1.2 — ПОЛНАЯ ВЕРСИЯ
# ==============================================================================
# Версия: 2.1.2 (с исправлениями seed, перевода и длины промпта)
# ==============================================================================

import os
import time
import json
import hashlib
import asyncio
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
# 📋 PYDANTIC-СХЕМЫ
# ==============================================================================

class FishHookTaskRequest(BaseModel):
    user_login: str
    session_id: str
    prompt_style: str


class VoiceChatRequest(BaseModel):
    user_login: str
    role: Optional[str] = "assistant"
    gender: Optional[str] = "male"
    character: Optional[str] = "anna"
    scene: Optional[str] = "nature"
    text_message: Optional[str] = ""
    generate_image: Optional[bool] = False
    image_prompt: Optional[str] = ""
    nsfw: Optional[bool] = False


# ==============================================================================
# 🔥 FISHHOOK AI ENDPOINTS
# ==============================================================================

# --- 1. СТАТУС ВОКЕРА ---
@router.get("/fishhook/status/{user_login}")
async def get_worker_status(user_login: str):
    clean_login = user_login.lower().strip()
    last_ping = WORKER_ONLINE.get(clean_login, 0)
    is_online = (time.time() - last_ping) < 15.0
    return {"online": is_online}


# --- 2. СОЗДАНИЕ ЗАДАЧИ ---
@router.post("/fishhook/create_task")
async def create_fishhook_task(payload: FishHookTaskRequest):
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


# --- 3. ОПРОС ГОТОВНОСТИ ---
@router.get("/fishhook/check_task/{user_login}/{task_id}")
async def check_task_readiness(user_login: str, task_id: str):
    clean_login = user_login.lower().strip()
    
    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        return {"status": "not_found"}
        
    if task["status"] == "completed":
        response = {
            "status": "completed",
            "bot_text": task.get("bot_text", ""),
            "user_text": task.get("user_text", ""),
            "audio_url": task.get("audio_url"),
            "image_url": task.get("image_url")
        }
        return response
        
    return {"status": task["status"]}


# --- 4. LONG POLLING ДЛЯ ВОКЕРА ---
@router.get("/fishhook/get_task/{user_login}")
async def get_task_for_colab(user_login: str):
    clean_login = user_login.lower().strip()
    WORKER_ONLINE[clean_login] = time.time()

    max_wait_time = 4
    check_interval = 2
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        task = FISHHOOK_TASKS.get(clean_login)
        
        if task and task.get("status") == "pending":
            task["status"] = "processing"
            
            response_data = {
                "task_id": task["task_id"],
                "session_id": task["session_id"],
                "user_login": task["user_login"],
                "prompt_style": task["prompt_style"]
            }
            
            if "voice_role" in task:
                response_data["voice_role"] = task["voice_role"]
            if "voice_gender" in task:
                response_data["voice_gender"] = task["voice_gender"]
            if "character" in task:
                response_data["character"] = task["character"]
            if "scene" in task:
                response_data["scene"] = task["scene"]
            if "text_message" in task:
                response_data["text_message"] = task["text_message"]
            if "generate_image" in task:
                response_data["generate_image"] = task["generate_image"]
            if "image_prompt" in task:
                response_data["image_prompt"] = task["image_prompt"]
            if "nsfw" in task:
                response_data["nsfw"] = task["nsfw"]
            
            return {
                "status": "success",
                "task_data": response_data
            }

        await asyncio.sleep(check_interval)
        elapsed_time += check_interval

    return {"status": "no_tasks"}


# --- 5. СКАЧИВАНИЕ ФАЙЛА ИЗ СЕССИИ ---
@router.get("/fishhook/download_source/{session_id}")
async def download_source_from_session(session_id: str, filename: str = "user_voice.wav"):
    file_path = f"./uploads/{session_id}/{filename}"
    if os.path.exists(file_path):
        if filename.endswith('.wav'):
            media_type = "audio/wav"
        elif filename.endswith('.png'):
            media_type = "image/png"
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            media_type = "image/jpeg"
        else:
            media_type = "application/octet-stream"
            
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail=f"Файл {filename} не найден")


# --- 5.1. ПОЛУЧЕНИЕ АУДИО ---
@router.get("/fishhook/get_audio/{session_id}")
async def get_audio_response(session_id: str):
    file_path = f"./uploads/{session_id}/bot_response.wav"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="Аудио ответ не найден")


# --- 5.2. ПОЛУЧЕНИЕ ИЗОБРАЖЕНИЯ ---
@router.get("/fishhook/get_image/{session_id}")
async def get_generated_image(session_id: str):
    file_path = f"./uploads/{session_id}/generated_image.jpg"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Изображение не найдено")


# --- 6. ПРИЁМ РЕЗУЛЬТАТА ОТ ВОКЕРА ---
@router.post("/fishhook/submit_result")
async def submit_result_from_colab(
    task_id: str = Form(...),
    user_login: str = Form(...),
    user_text: Optional[str] = Form(""),
    bot_text: Optional[str] = Form(""),
    audio: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None)
):
    clean_login = user_login.lower().strip()
    
    task = FISHHOOK_TASKS.get(clean_login)
    if not task or task["task_id"] != task_id:
        raise HTTPException(status_code=400, detail="Задача устарела или не найдена")
        
    session_id = task["session_id"]
    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    if bot_text:
        try:
            text_path = os.path.join(session_dir, "bot_response.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(bot_text)
            print(f"📝 [TEXT SAVED]: {text_path}")
        except Exception as e:
            print(f"⚠️ [TEXT SAVE ERROR]: {e}")
    
    audio_url = None
    if audio:
        try:
            audio_path = os.path.join(session_dir, "bot_response.wav")
            contents = await audio.read()
            with open(audio_path, "wb") as f:
                f.write(contents)
            audio_url = f"/api/studio/fishhook/get_audio/{session_id}"
            print(f"🔊 [AUDIO SAVED]: {audio_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось записать аудио: {e}")
    
    image_url = None
    if image:
        try:
            image_path = os.path.join(session_dir, "generated_image.jpg")
            contents = await image.read()
            with open(image_path, "wb") as f:
                f.write(contents)
            image_url = f"/api/studio/fishhook/get_image/{session_id}"
            print(f"🖼️ [IMAGE SAVED]: {image_path}")
        except Exception as e:
            print(f"⚠️ [IMAGE SAVE ERROR]: {e}")
    
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


# --- 7. ГОЛОСОВОЙ ЧАТ С ПЕРСОНАЖАМИ И СЦЕНАМИ ---
@router.post("/fishhook/voice_chat")
async def voice_chat_endpoint(
    user_login: str = Form(...),
    character: str = Form("anna"),
    scene: str = Form("nature"),
    text_message: Optional[str] = Form(""),
    generate_image: Optional[bool] = Form(False),
    image_prompt: Optional[str] = Form(""),
    nsfw: Optional[bool] = Form(False),
    audio_file: Optional[UploadFile] = File(None),
    role: Optional[str] = Form("assistant"),
    gender: Optional[str] = Form("male")
):
    clean_login = user_login.lower().strip()
    
    voice_task_id = f"voice_{int(time.time())}"
    session_id = f"v_sess_{clean_login}"
    
    session_dir = f"./uploads/{session_id}"
    os.makedirs(session_dir, exist_ok=True)
    
    if audio_file:
        input_audio_path = os.path.join(session_dir, "user_voice.wav")
        try:
            contents = await audio_file.read()
            with open(input_audio_path, "wb") as f:
                f.write(contents)
            print(f"🎙️ [AUDIO SAVED]: {input_audio_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Не удалось записать аудио: {e}")
    
    task_data = {
        "status": "pending",
        "task_id": voice_task_id,
        "session_id": session_id,
        "user_login": clean_login,
        "prompt_style": "voice_chat",
        "voice_role": role,
        "voice_gender": gender,
        "character": character,
        "scene": scene,
        "text_message": text_message,
        "generate_image": generate_image,
        "image_prompt": image_prompt,
        "nsfw": nsfw
    }
    
    FISHHOOK_TASKS[clean_login] = task_data
    
    print(f"🎙️ [ОЧЕРЕДЬ]: Задача {voice_task_id} для '{character}', сцена '{scene}'")
    if generate_image:
        print(f"🖼️ [IMAGE GEN]: {image_prompt[:50]}... (сцена: {scene})")
    
    return {
        "status": "queued", 
        "task_id": voice_task_id,
        "character": character,
        "scene": scene,
        "generate_image": generate_image
    }


# --- 8. СПИСОК ПЕРСОНАЖЕЙ ---
@router.get("/fishhook/characters")
async def get_available_characters():
    characters = {
        # Женщины
        "anna": {"name": "Анна", "age": 25, "gender": "female", "personality": "Нежная, романтичная", "style": "romantic", "emoji": "💕"},
        "kate": {"name": "Катя", "age": 23, "gender": "female", "personality": "Дерзкая, уверенная", "style": "bold", "emoji": "🔥"},
        "maria": {"name": "Мария", "age": 28, "gender": "female", "personality": "Интеллектуалка", "style": "intellectual", "emoji": "📚"},
        "lisa": {"name": "Лиза", "age": 22, "gender": "female", "personality": "Весёлая, энергичная", "style": "energetic", "emoji": "⚡"},
        "sophie": {"name": "Софи", "age": 18, "gender": "female", "personality": "Мечтательная, наивная", "style": "dreamy", "emoji": "🌸"},
        "elena": {"name": "Елена", "age": 30, "gender": "female", "personality": "Бизнес-леди, властная", "style": "dominant", "emoji": "👑"},
        "olga": {"name": "Ольга", "age": 35, "gender": "female", "personality": "Заботливая, мудрая", "style": "caring", "emoji": "🤗"},
        "natasha": {"name": "Наташа", "age": 28, "gender": "female", "personality": "Спортивная, энергичная", "style": "athletic", "emoji": "💪"},
        "victoria": {"name": "Виктория", "age": 40, "gender": "female", "personality": "Строгая, интеллектуальная", "style": "strict", "emoji": "🎓"},
        "diana": {"name": "Диана", "age": 22, "gender": "female", "personality": "Гламурная, уверенная", "style": "glamorous", "emoji": "💎"},
        # Мужчины
        "alex": {"name": "Алекс", "age": 20, "gender": "male", "personality": "Романтичный, застенчивый", "style": "shy", "emoji": "🎵"},
        "maxim": {"name": "Максим", "age": 30, "gender": "male", "personality": "Уверенный, харизматичный", "style": "charismatic", "emoji": "💼"},
        "sergey": {"name": "Сергей", "age": 40, "gender": "male", "personality": "Спокойный, мудрый", "style": "wise", "emoji": "⚕️"}
    }
    return {"status": "success", "characters": characters, "default": "anna"}


# --- 9. ЗАГРУЗКА ГОЛОСА ---
@router.post("/fishhook/upload_voice_sample")
async def upload_voice_sample(
    character: str = Form(...),
    voice_file: UploadFile = File(...)
):
    valid_characters = [
        # Женщины
        "anna", "kate", "maria", "lisa", "sophie", "elena", "olga", "natasha", "victoria", "diana",
        # Мужчины
        "alex", "maxim", "sergey"
    ]
    if character not in valid_characters:
        raise HTTPException(status_code=400, detail=f"Неизвестный персонаж '{character}'. Доступные: {', '.join(valid_characters)}")
    
    voices_dir = "./voices"
    os.makedirs(voices_dir, exist_ok=True)
    
    voice_path = os.path.join(voices_dir, f"{character}.wav")
    try:
        contents = await voice_file.read()
        with open(voice_path, "wb") as f:
            f.write(contents)
        print(f"🎤 [VOICE SAVED]: {voice_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить голос: {e}")
    
    return {"status": "success", "character": character, "voice_path": voice_path}


# --- 10. ПОЛУЧЕНИЕ РЕЗУЛЬТАТА ---
@router.get("/fishhook/get_result/{session_id}")
async def get_chat_result(session_id: str):
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
    
    audio_path = os.path.join(session_dir, "bot_response.wav")
    if os.path.exists(audio_path):
        result["has_audio"] = True
        result["audio_url"] = f"/uploads/{session_id}/bot_response.wav"
    
    image_path = os.path.join(session_dir, "generated_image.jpg")
    if os.path.exists(image_path):
        result["has_image"] = True
        result["image_url"] = f"/uploads/{session_id}/generated_image.jpg"
    
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

MAX_FILE_SIZE = 10 * 1024 * 1024

async def check_file_size(file: UploadFile):
    file_size = getattr(file, "size", None)
    if file_size is None:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="ERROR_FILE_TOO_LARGE")
