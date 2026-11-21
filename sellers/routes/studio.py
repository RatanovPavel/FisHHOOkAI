# ==============================================================================
# 🔥 FISHHOOK AI v2.1.2 — ПОЛНАЯ ВЕРСИЯ С ПРЕВЬЮ ПЕРСОНАЖЕЙ
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

router = APIRouter(prefix="/api/studio", tags=["Studio"])

# Отдельный роутер для статических файлов персонажей
static_router = APIRouter(tags=["Static"])

@static_router.get("/characters/{character_key}/{filename}")
async def get_character_static_file(character_key: str, filename: str):
    """Отдаёт статические файлы персонажей (main.jpg, voice_intro.wav, config.json)"""
    if ".." in character_key or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Разрешаем только основные файлы (без gallery/)
    if filename not in ["main.jpg", "voice.wav", "voice_intro.wav", "config.json"]:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = f"./characters/{character_key}/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Файл не найден: {filename}")
    
    if filename.endswith('.wav'):
        media_type = "audio/wav"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        media_type = "image/jpeg"
    elif filename.endswith('.png'):
        media_type = "image/png"
    elif filename.endswith('.json'):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type)


@static_router.get("/characters/{character_key}/gallery/{filename}")
async def get_character_gallery_file(character_key: str, filename: str):
    """Отдаёт файлы из галереи персонажа"""
    if ".." in character_key or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Разрешаем только изображения
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = f"./characters/{character_key}/gallery/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Файл галереи не найден: {filename}")
    
    if filename.lower().endswith('.png'):
        media_type = "image/png"
    elif filename.lower().endswith('.webp'):
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    
    return FileResponse(file_path, media_type=media_type)

# Глобальные словари
FISHHOOK_TASKS = {}
WORKER_ONLINE = {}
CHARACTERS = {}

# ==============================================================================
# 📋 СПИСОК ПЕРСОНАЖЕЙ
# ==============================================================================

@router.get("/fishhook/characters")
async def get_available_characters():
    """Загружает список персонажей из папки characters/"""
    characters = {}
    characters_dir = "./characters"
    
    if os.path.exists(characters_dir):
        for item in os.listdir(characters_dir):
            char_path = os.path.join(characters_dir, item)
            if os.path.isdir(char_path):
                config_file = os.path.join(char_path, "config.json")
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        has_voice = os.path.exists(os.path.join(char_path, "voice_intro.wav"))
                        has_main_photo = os.path.exists(os.path.join(char_path, "main.jpg"))
                        
                        characters[item] = {
                            "key": item,
                            "name": config.get("name", item),
                            "age": config.get("age", 0),
                            "gender": config.get("gender", "female"),
                            "style": config.get("style", "realistic"),
                            "personality": config.get("personality", ""),
                            "description": config.get("description", ""),
                            "emoji": config.get("emoji", "🎭"),
                            "has_voice": has_voice,
                            "has_main_photo": has_main_photo,
                            "main_photo_url": f"/characters/{item}/main.jpg" if has_main_photo else None,
                            "subscription_required": config.get("subscription_required", False),
                            "nsfw_allowed": config.get("nsfw_allowed", False),
                            "traits": config.get("traits", {})
                        }
                    except Exception as e:
                        print(f"⚠️ Ошибка загрузки персонажа {item}: {e}")
    
    default_character = list(characters.keys())[0] if characters else None
    
    return {
        "status": "success",
        "characters": characters,
        "default": default_character,
        "total": len(characters)
    }

# ==============================================================================
# 🎭 ПРЕВЬЮ ПЕРСОНАЖА (для модального окна)
# ==============================================================================

@router.get("/fishhook/character/{character_key}/preview")
async def get_character_preview(character_key: str):
    """Быстрое превью персонажа для модального окна с галереей и голосом"""
    char_dir = f"./characters/{character_key}"
    config_file = os.path.join(char_dir, "config.json")
    
    if not os.path.exists(config_file):
        raise HTTPException(status_code=404, detail=f"Персонаж '{character_key}' не найден")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Загружаем галерею
        gallery_dir = os.path.join(char_dir, "gallery")
        gallery = []
        if os.path.exists(gallery_dir):
            gallery = [f"/characters/{character_key}/gallery/{f}" 
                      for f in sorted(os.listdir(gallery_dir)) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        has_voice = os.path.exists(os.path.join(char_dir, "voice_intro.wav"))
        has_main_photo = os.path.exists(os.path.join(char_dir, "main.jpg"))
        
        return {
            "status": "success",
            "preview": {
                "key": character_key,
                "name": config.get("name", character_key),
                "age": config.get("age", 0),
                "gender": config.get("gender", "female"),
                "style": config.get("style", "realistic"),
                "emoji": config.get("emoji", "🎭"),
                "description": config.get("description", ""),
                "personality": config.get("personality", ""),
                "main_photo": f"/characters/{character_key}/main.jpg" if has_main_photo else None,
                "voice": f"/characters/{character_key}/voice_intro.wav" if has_voice else None,
                "gallery": gallery,
                "traits": config.get("traits", {})
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки превью: {e}")

# ==============================================================================
# 🎭 ПОЛНАЯ ИНФОРМАЦИЯ О ПЕРСОНАЖЕ
# ==============================================================================

@router.get("/fishhook/character/{character_key}")
async def get_character_info(character_key: str):
    """Получает полную информацию о персонаже"""
    char_dir = f"./characters/{character_key}"
    config_file = os.path.join(char_dir, "config.json")
    
    if not os.path.exists(config_file):
        raise HTTPException(status_code=404, detail=f"Персонаж '{character_key}' не найден")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        gallery_dir = os.path.join(char_dir, "gallery")
        gallery = []
        if os.path.exists(gallery_dir):
            gallery = [f"/characters/{character_key}/gallery/{f}" 
                      for f in sorted(os.listdir(gallery_dir)) 
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        has_voice = os.path.exists(os.path.join(char_dir, "voice_intro.wav"))
        has_main_photo = os.path.exists(os.path.join(char_dir, "main.jpg"))
        
        return {
            "status": "success",
            "character": {
                "key": character_key,
                "config": config,
                "has_voice": has_voice,
                "has_main_photo": has_main_photo,
                "gallery": gallery,
                "main_photo_url": f"/characters/{character_key}/main.jpg" if has_main_photo else None,
                "voice_url": f"/characters/{character_key}/voice_intro.wav" if has_voice else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки персонажа: {e}")
