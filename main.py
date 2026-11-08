# ==============================================================================
# 🔥 FISHHOOK AI v4.0 — WebSocket архитектура
# ==============================================================================
# Множество пользователей, каждый со своим воркером
# Сервер выступает как маршрутизатор между фронтендом и воркером
# ==============================================================================

import os
import time
import json
import asyncio
import hashlib
from typing import Dict, Optional, Set
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Form, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==============================================================================
# 🚀 ИНИЦИАЛИЗАЦИЯ
# ==============================================================================

app = FastAPI(title="FishHook AI WebSocket Server", version="4.0")

# CORS для браузеров
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 📦 ХРАНИЛИЩА СОЕДИНЕНИЙ
# ==============================================================================

# Маппинг: user_id → WebSocket соединение с воркером
worker_connections: Dict[str, WebSocket] = {}

# Маппинг: user_id → WebSocket соединение с браузером
browser_connections: Dict[str, WebSocket] = {}

# Маппинг: user_id → информация о воркере
worker_info: Dict[str, dict] = {}

# Маппинг: user_id → текущая задача
active_tasks: Dict[str, dict] = {}

# Статистика
stats = {
    "total_connections": 0,
    "active_workers": 0,
    "active_browsers": 0,
    "tasks_processed": 0,
    "start_time": datetime.now().isoformat()
}

# ==============================================================================
# 🔐 АВТОРИЗАЦИЯ (упрощённая - через токен в URL)
# ==============================================================================

def generate_token(user_id: str) -> str:
    """Генерирует токен для подключения"""
    secret = "skulla_secret_key_2024"
    return hashlib.sha256(f"{user_id}:{secret}".encode()).hexdigest()[:16]

def verify_token(user_id: str, token: str) -> bool:
    """Проверяет токен"""
    expected = generate_token(user_id)
    return token == expected

# ==============================================================================
# 📡 WEBSOCKET: ПОДКЛЮЧЕНИЕ ВОРКЕРА
# ==============================================================================

@app.websocket("/ws/worker/{user_id}/{token}")
async def worker_websocket(websocket: WebSocket, user_id: str, token: str):
    """
    Воркер подключается к серверу через WebSocket.
    URL: wss://skulla.ru/ws/worker/{user_id}/{token}
    """
    
    # Проверка токена
    if not verify_token(user_id, token):
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    # Проверяем, не подключён ли уже воркер для этого пользователя
    if user_id in worker_connections:
        old_ws = worker_connections[user_id]
        try:
            await old_ws.close(code=4002, reason="Replaced by new connection")
        except:
            pass
    
    await websocket.accept()
    worker_connections[user_id] = websocket
    worker_info[user_id] = {
        "connected_at": datetime.now().isoformat(),
        "last_ping": time.time(),
        "status": "online",
        "gpu": "unknown"
    }
    
    stats["total_connections"] += 1
    stats["active_workers"] = len(worker_connections)
    
    print(f"\n🔌 [WORKER] Подключён: {user_id}")
    print(f"   Всего воркеров: {stats['active_workers']}")
    print(f"   Всего браузеров: {stats['active_browsers']}")
    
    # Отправляем приветствие воркеру
    await websocket.send_json({
        "type": "welcome",
        "user_id": user_id,
        "message": "Connected to FishHook AI server"
    })
    
    try:
        while True:
            # Получаем сообщения от воркера
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Обновляем last_ping
            worker_info[user_id]["last_ping"] = time.time()
            
            # --- Обработка разных типов сообщений ---
            
            if msg_type == "ping":
                # Ответ на ping
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
            
            elif msg_type == "status":
                # Воркер сообщает свой статус
                worker_info[user_id]["status"] = data.get("status", "online")
                worker_info[user_id]["gpu"] = data.get("gpu", "unknown")
                print(f"📊 [WORKER {user_id}] Статус: {data.get('status')}")
            
            elif msg_type == "task_result":
                # Воркер отправляет результат задачи
                print(f"📨 [WORKER {user_id}] Получен результат задачи")
                
                # Пересылаем результат в браузер пользователя
                if user_id in browser_connections:
                    browser_ws = browser_connections[user_id]
                    try:
                        await browser_ws.send_json({
                            "type": "task_result",
                            "task_id": data.get("task_id"),
                            "bot_text": data.get("bot_text", ""),
                            "user_text": data.get("user_text", ""),
                            "audio_url": data.get("audio_url"),
                            "image_url": data.get("image_url"),
                            "status": "completed"
                        })
                        stats["tasks_processed"] += 1
                        print(f"✅ [WORKER {user_id}] Результат переслан в браузер")
                    except Exception as e:
                        print(f"❌ [WORKER {user_id}] Ошибка пересылки: {e}")
                else:
                    print(f"⚠️ [WORKER {user_id}] Браузер не подключён")
            
            elif msg_type == "task_status":
                # Воркер отправляет промежуточный статус задачи
                if user_id in browser_connections:
                    try:
                        await browser_connections[user_id].send_json({
                            "type": "task_status",
                            "task_id": data.get("task_id"),
                            "status": data.get("status"),
                            "message": data.get("message", "")
                        })
                    except:
                        pass
            
            elif msg_type == "error":
                # Воркер сообщает об ошибке
                print(f"❌ [WORKER {user_id}] Ошибка: {data.get('message')}")
                if user_id in browser_connections:
                    try:
                        await browser_connections[user_id].send_json({
                            "type": "error",
                            "message": data.get("message", "Unknown error")
                        })
                    except:
                        pass
            
            else:
                print(f"⚠️ [WORKER {user_id}] Неизвестный тип сообщения: {msg_type}")
    
    except WebSocketDisconnect:
        print(f"\n🔌 [WORKER] Отключён: {user_id}")
    except Exception as e:
        print(f"\n❌ [WORKER {user_id}] Ошибка: {e}")
    finally:
        # Удаляем соединение
        if user_id in worker_connections:
            del worker_connections[user_id]
        if user_id in worker_info:
            del worker_info[user_id]
        stats["active_workers"] = len(worker_connections)
        print(f"   Осталось воркеров: {stats['active_workers']}")


# ==============================================================================
# 📡 WEBSOCKET: ПОДКЛЮЧЕНИЕ БРАУЗЕРА
# ==============================================================================

@app.websocket("/ws/browser/{user_id}/{token}")
async def browser_websocket(websocket: WebSocket, user_id: str, token: str):
    """
    Браузер подключается к серверу через WebSocket.
    URL: wss://skulla.ru/ws/browser/{user_id}/{token}
    """
    
    # Проверка токена
    if not verify_token(user_id, token):
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await websocket.accept()
    browser_connections[user_id] = websocket
    
    stats["total_connections"] += 1
    stats["active_browsers"] = len(browser_connections)
    
    print(f"\n🌐 [BROWSER] Подключён: {user_id}")
    print(f"   Всего воркеров: {stats['active_workers']}")
    print(f"   Всего браузеров: {stats['active_browsers']}")
    
    # Отправляем приветствие браузеру
    has_worker = user_id in worker_connections
    await websocket.send_json({
        "type": "welcome",
        "user_id": user_id,
        "worker_connected": has_worker,
        "message": "Connected to FishHook AI server"
    })
    
    try:
        while True:
            # Получаем сообщения от браузера
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # --- Обработка разных типов сообщений ---
            
            if msg_type == "task":
                # Браузер отправляет задачу
                print(f"📨 [BROWSER {user_id}] Получена задача")
                
                # Проверяем, подключён ли воркер
                if user_id not in worker_connections:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Воркер не подключён. Запустите main.py в Colab."
                    })
                    continue
                
                # Пересылаем задачу воркеру
                try:
                    task_id = f"task_{int(time.time())}_{user_id[:8]}"
                    
                    # Сохраняем задачу
                    active_tasks[user_id] = {
                        "task_id": task_id,
                        "data": data,
                        "created_at": datetime.now().isoformat(),
                        "status": "processing"
                    }
                    
                    # Пересылаем воркеру
                    await worker_connections[user_id].send_json({
                        "type": "task",
                        "task_id": task_id,
                        "task_data": data.get("task_data", {})
                    })
                    
                    # Подтверждаем браузеру
                    await websocket.send_json({
                        "type": "task_accepted",
                        "task_id": task_id,
                        "message": "Задача отправлена воркеру"
                    })
                    
                    print(f"✅ [BROWSER {user_id}] Задача {task_id} переслана воркеру")
                    
                except Exception as e:
                    print(f"❌ [BROWSER {user_id}] Ошибка пересылки: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Ошибка отправки задачи: {str(e)}"
                    })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
            
            elif msg_type == "check_worker":
                # Браузер проверяет, подключён ли воркер
                has_worker = user_id in worker_connections
                worker_status = worker_info.get(user_id, {}).get("status", "offline")
                await websocket.send_json({
                    "type": "worker_status",
                    "connected": has_worker,
                    "status": worker_status,
                    "gpu": worker_info.get(user_id, {}).get("gpu", "unknown")
                })
            
            else:
                print(f"⚠️ [BROWSER {user_id}] Неизвестный тип: {msg_type}")
    
    except WebSocketDisconnect:
        print(f"\n🌐 [BROWSER] Отключён: {user_id}")
    except Exception as e:
        print(f"\n❌ [BROWSER {user_id}] Ошибка: {e}")
    finally:
        if user_id in browser_connections:
            del browser_connections[user_id]
        stats["active_browsers"] = len(browser_connections)
        print(f"   Осталось браузеров: {stats['active_browsers']}")


# ==============================================================================
# 📡 WEBSOCKET: ПРЯМОЕ ПОДКЛЮЧЕНИЕ (без токена - для тестирования)
# ==============================================================================

@app.websocket("/ws/worker/{user_id}")
async def worker_websocket_simple(websocket: WebSocket, user_id: str):
    """Упрощённое подключение воркера (без токена)"""
    await websocket.accept()
    worker_connections[user_id] = websocket
    worker_info[user_id] = {
        "connected_at": datetime.now().isoformat(),
        "last_ping": time.time(),
        "status": "online",
        "gpu": "unknown"
    }
    stats["active_workers"] = len(worker_connections)
    print(f"\n🔌 [WORKER] Подключён (simple): {user_id}")
    
    await websocket.send_json({
        "type": "welcome",
        "user_id": user_id,
        "message": "Connected (simple mode)"
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            worker_info[user_id]["last_ping"] = time.time()
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "task_result":
                if user_id in browser_connections:
                    await browser_connections[user_id].send_json({
                        "type": "task_result",
                        **data
                    })
            elif msg_type == "task_status":
                if user_id in browser_connections:
                    await browser_connections[user_id].send_json({
                        "type": "task_status",
                        **data
                    })
            elif msg_type == "status":
                worker_info[user_id].update(data)
    except WebSocketDisconnect:
        pass
    finally:
        if user_id in worker_connections:
            del worker_connections[user_id]
        stats["active_workers"] = len(worker_connections)


@app.websocket("/ws/browser/{user_id}")
async def browser_websocket_simple(websocket: WebSocket, user_id: str):
    """Упрощённое подключение браузера (без токена)"""
    await websocket.accept()
    browser_connections[user_id] = websocket
    stats["active_browsers"] = len(browser_connections)
    print(f"\n🌐 [BROWSER] Подключён (simple): {user_id}")
    
    await websocket.send_json({
        "type": "welcome",
        "user_id": user_id,
        "worker_connected": user_id in worker_connections
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "task":
                if user_id not in worker_connections:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Воркер не подключён"
                    })
                    continue
                
                task_id = f"task_{int(time.time())}_{user_id[:8]}"
                await worker_connections[user_id].send_json({
                    "type": "task",
                    "task_id": task_id,
                    "task_data": data.get("task_data", {})
                })
                await websocket.send_json({
                    "type": "task_accepted",
                    "task_id": task_id
                })
            
            elif msg_type == "check_worker":
                await websocket.send_json({
                    "type": "worker_status",
                    "connected": user_id in worker_connections
                })
    except WebSocketDisconnect:
        pass
    finally:
        if user_id in browser_connections:
            del browser_connections[user_id]
        stats["active_browsers"] = len(browser_connections)


# ==============================================================================
# 📊 REST API: СТАТИСТИКА И УПРАВЛЕНИЕ
# ==============================================================================

@app.get("/ws/status")
async def get_status():
    """Получить статус сервера"""
    return {
        "status": "online",
        "stats": stats,
        "workers": list(worker_info.keys()),
        "browsers": list(browser_connections.keys()),
        "active_tasks": len(active_tasks)
    }

@app.get("/ws/worker/{user_id}/status")
async def get_worker_status(user_id: str):
    """Получить статус конкретного воркера"""
    if user_id not in worker_info:
        return {"status": "offline", "user_id": user_id}
    
    info = worker_info[user_id].copy()
    info["status"] = "online"
    info["user_id"] = user_id
    return info

@app.get("/ws/token/{user_id}")
async def get_token(user_id: str):
    """Получить токен для подключения"""
    token = generate_token(user_id)
    return {
        "user_id": user_id,
        "token": token,
        "worker_url": f"wss://skulla.ru/ws/worker/{user_id}/{token}",
        "browser_url": f"wss://skulla.ru/ws/browser/{user_id}/{token}"
    }

# ==============================================================================
# 📁 СТАТИЧЕСКИЕ ФАЙЛЫ (для совместимости)
# ==============================================================================

@app.get("/characters/{character_key}/{filename}")
async def get_character_file(character_key: str, filename: str):
    """Отдаёт файлы персонажей"""
    if ".." in character_key or ".." in filename:
        raise HTTPException(400, "Invalid path")
    
    if filename.startswith("gallery/"):
        file_path = f"./characters/{character_key}/{filename}"
    elif filename in ["main.jpg", "voice.wav", "voice_intro.wav", "config.json"]:
        file_path = f"./characters/{character_key}/{filename}"
    else:
        raise HTTPException(400, "Invalid filename")
    
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found")
    
    if filename.endswith('.wav'):
        media_type = "audio/wav"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        media_type = "image/jpeg"
    elif filename.endswith('.png'):
        media_type = "image/png"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type)

@app.get("/api/studio/fishhook/characters")
async def get_characters():
    """Список персонажей (для совместимости)"""
    characters = {}
    characters_dir = "./characters"
    
    if os.path.exists(characters_dir):
        for item in os.listdir(characters_dir):
            char_path = os.path.join(characters_dir, item)
            config_file = os.path.join(char_path, "config.json")
            
            if os.path.isdir(char_path) and os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    has_voice = os.path.exists(os.path.join(char_path, "voice.wav"))
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
                    print(f"⚠️ Ошибка загрузки {item}: {e}")
    
    return {
        "status": "success",
        "characters": characters,
        "default": list(characters.keys())[0] if characters else None,
        "total": len(characters)
    }

@app.get("/api/studio/fishhook/character/{character_key}/preview")
async def get_character_preview(character_key: str):
    """Превью персонажа (для совместимости)"""
    char_dir = f"./characters/{character_key}"
    config_file = os.path.join(char_dir, "config.json")
    
    if not os.path.exists(config_file):
        raise HTTPException(404, "Персонаж не найден")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    gallery_dir = os.path.join(char_dir, "gallery")
    gallery = []
    if os.path.exists(gallery_dir):
        gallery = [f"/characters/{character_key}/gallery/{f}" 
                  for f in sorted(os.listdir(gallery_dir)) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    has_voice = os.path.exists(os.path.join(char_dir, "voice.wav"))
    
    return {
        "status": "success",
        "preview": {
            "key": character_key,
            "name": config.get("name"),
            "age": config.get("age"),
            "gender": config.get("gender"),
            "style": config.get("style", "realistic"),
            "emoji": config.get("emoji"),
            "description": config.get("description", ""),
            "personality": config.get("personality", ""),
            "main_photo": f"/characters/{character_key}/main.jpg",
            "voice": f"/characters/{character_key}/voice.wav" if has_voice else None,
            "gallery": gallery,
            "traits": config.get("traits", {})
        }
    }

# ==============================================================================
# 🧹 ОЧИСТКА
# ==============================================================================

async def cleanup_inactive_connections():
    """Периодическая очистка неактивных соединений"""
    while True:
        await asyncio.sleep(60)
        
        current_time = time.time()
        inactive_workers = []
        
        for user_id, info in worker_info.items():
            if current_time - info.get("last_ping", 0) > 300:  # 5 минут
                inactive_workers.append(user_id)
        
        for user_id in inactive_workers:
            print(f"🧹 Удаляю неактивного воркера: {user_id}")
            if user_id in worker_connections:
                try:
                    await worker_connections[user_id].close()
                except:
                    pass
                del worker_connections[user_id]
            if user_id in worker_info:
                del worker_info[user_id]
        
        stats["active_workers"] = len(worker_connections)

@app.on_event("startup")
async def startup_event():
    """Запуск фоновых задач"""
    asyncio.create_task(cleanup_inactive_connections())
    print("\n" + "=" * 60)
    print("🚀 FISHHOOK AI WebSocket Server v4.0 ЗАПУЩЕН")
    print("=" * 60)
    print(f"   Workers endpoint:  /ws/worker/{{user_id}}")
    print(f"   Browsers endpoint: /ws/browser/{{user_id}}")
    print(f"   Status endpoint:   /ws/status")
    print("=" * 60 + "\n")

# ==============================================================================
# 🏁 ЗАПУСК
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, ws_ping_interval=30, ws_ping_timeout=60)
