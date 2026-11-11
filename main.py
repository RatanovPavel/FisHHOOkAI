# -*- coding: utf-8 -*-
"""
🎭 FishHook AI WebSocket Worker v4.0
Воркер подключается к серверу через WebSocket и получает задачи

Архитектура:
- Каждый пользователь запускает свой воркер
- Воркер подключается к серверу через WebSocket
- Сервер маршрутизирует задачи от браузера к воркеру
- Воркер отправляет результаты обратно через WebSocket
"""

import os
import sys
import json
import time
import re
import gc
import shutil
import subprocess
import requests
import torch
import hashlib
import asyncio
import websockets
import base64
from pathlib import Path

import functools
print = functools.partial(print, flush=True)

# ============================================================================
# ⚙️ КОНФИГУРАЦИЯ
# ============================================================================

# ВАЖНО: Укажите ваш user_id и URL сервера
USER_ID = "RATANOV_PAVEL"  # ← Замените на ваш user_id
SERVER_URL = "wss://skulla.ru"  # ← Замените на URL вашего сервера
# Для локального тестирования: SERVER_URL = "ws://localhost:8000"

# Пути
CHARACTERS_DIR = "./characters"
UPLOADS_DIR = "./uploads"

# Флаги
NSFW_ENABLED = True

# ============================================================================
# 📦 УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================================

def install_dependencies():
    packages = {
        "transformers":       "transformers",
        "accelerate":         "accelerate",
        "bitsandbytes":       "bitsandbytes",
        "optimum":            "optimum",
        "coqui-tts":          "TTS",
        "diffusers":          "diffusers",
        "openai-whisper":     "whisper",
        "SpeechRecognition":  "speech_recognition",
        "gtts":               "gtts",
        "pydub":              "pydub",
        "websockets":         "websockets"
    }
    
    for pip_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✅ {pip_name} уже установлен")
        except ImportError:
            print(f"📦 Устанавливаю {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pip_name])

    if not shutil.which("ffmpeg"):
        print("📦 Устанавливаю ffmpeg...")
        os.system("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null 2>&1")

install_dependencies()

import speech_recognition as sr
from transformers import AutoTokenizer, AutoModelForCausalLM

# ============================================================================
# 👥 СИСТЕМА ПЕРСОНАЖЕЙ
# ============================================================================

def get_http_base_url():
    if SERVER_URL.startswith("wss://"):
        return SERVER_URL.replace("wss://", "https://", 1).rstrip("/")
    elif SERVER_URL.startswith("ws://"):
        return SERVER_URL.replace("ws://", "http://", 1).rstrip("/")
    return SERVER_URL.rstrip("/")


def download_one_character(character_key: str) -> bool:
    """Скачивает ОДНОГО персонажа с сервера, если его ещё нет на диске"""
    if not character_key:
        return False

    char_dir = os.path.join(CHARACTERS_DIR, character_key)
    config_path = os.path.join(char_dir, "config.json")

    if os.path.exists(config_path):
        return True

    base_url = get_http_base_url()
    os.makedirs(char_dir, exist_ok=True)

    try:
        print(f"🌐 Скачиваю персонажа '{character_key}' с сервера...")
        resp = requests.get(
            f"{base_url}/api/studio/fishhook/character/{character_key}/preview",
            timeout=15
        )
        if resp.status_code != 200:
            print(f"⚠ Персонаж '{character_key}' не найден на сервере")
            return False

        preview = resp.json().get("preview", {})
        files = ["config.json"]
        if preview.get("voice"):
            files.append("voice.wav")

        for filename in files:
            file_resp = requests.get(f"{base_url}/characters/{character_key}/{filename}", timeout=30)
            if file_resp.status_code == 200:
                with open(os.path.join(char_dir, filename), "wb") as f:
                    f.write(file_resp.content)
                print(f"  📥 Скачан: {character_key}/{filename}")

        return os.path.exists(config_path)
    except Exception as e:
        print(f"❌ Ошибка скачивания '{character_key}': {e}")
        return False


def load_one_character(character_key: str):
    """Загружает одного персонажа с диска в память"""
    char_path = os.path.join(CHARACTERS_DIR, character_key)
    config_file = os.path.join(char_path, "config.json")

    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        config["key"] = character_key
        config["voice_sample"] = os.path.join(char_path, "voice.wav")
        config["gallery_dir"] = os.path.join(char_path, "gallery")
        CHARACTERS[character_key] = config
        return config
    return None


def load_characters():
    """При старте берёт только то, что уже есть на диске (ничего не качает)"""
    characters = {}
    if not os.path.exists(CHARACTERS_DIR):
        return characters

    for item in os.listdir(CHARACTERS_DIR):
        char_path = os.path.join(CHARACTERS_DIR, item)
        config_file = os.path.join(char_path, "config.json")
        if os.path.isdir(char_path) and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config["key"] = item
            config["voice_sample"] = os.path.join(char_path, "voice.wav")
            config["gallery_dir"] = os.path.join(char_path, "gallery")
            characters[item] = config

    print(f"✅ Локально доступно персонажей: {len(characters)}")
    return characters


CHARACTERS = load_characters()
CHARACTER_STATES = {}
ACTIVE_CHARACTER = list(CHARACTERS.keys())[0] if CHARACTERS else None


# ============================================================================
# 🎬 СИСТЕМА СЦЕН
# ============================================================================

SCENES = {
    "nature": {"name": "🌿 Природа", "prompt_en": "lush green forest, dappled sunlight, wildflowers, golden hour"},
    "sea": {"name": "🌊 Море", "prompt_en": "beautiful beach, turquoise ocean waves, white sand, sunset"},
    "shower": {"name": "🚿 Душ", "prompt_en": "glass shower, water droplets on skin, steam, soft lighting"},
    "pastel": {"name": "🌸 Пастель", "prompt_en": "soft pastel bedroom, pink and lavender tones, dreamy lighting"},
    "nsfw": {"name": "🔥 18+", "prompt_en": "intimate boudoir, soft dramatic lighting"},
    "cafe": {"name": "☕ Кафе", "prompt_en": "cozy cafe interior, warm ambient lighting, coffee cup"},
    "gym": {"name": "💪 Спортзал", "prompt_en": "modern gym interior, athletic pose, dynamic lighting"}
}

# ============================================================================
# 🖼️ МОДЕЛИ
# ============================================================================

IMAGE_MODEL = None
VOICE_MODEL = None
VOICE_TOKENIZER = None
TTS_ENGINE = None
WHISPER_MODEL = None

# ============================================================================
# 🔧 УТИЛИТЫ
# ============================================================================

def check_gpu():
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"✅ GPU: {gpu_name} | VRAM: {vram:.1f} GB")
        return True
    else:
        print("❌ GPU не обнаружен!")
        return False

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path

def has_cyrillic(text):
    return bool(re.search('[а-яА-Я]', text))

def translate_to_english(russian_text):
    """Переводит промпт с русского на английский"""
    global VOICE_MODEL, VOICE_TOKENIZER
    
    if VOICE_MODEL is None or VOICE_TOKENIZER is None:
        return russian_text
    
    try:
        prompt = f"Translate this Russian phrase to a short English image description. Output ONLY the translation, 5-10 words max.\n\nRussian: {russian_text}\nEnglish:"
        
        inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")
        
        with torch.no_grad():
            outputs = VOICE_MODEL.generate(**inputs, max_new_tokens=30, temperature=0.1, do_sample=False)
        
        translation = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
        translation = translation.replace(prompt, "").strip()
        translation = re.sub(r'^["\']|["\']$', '', translation)
        translation = translation.split('.')[0].split('\n')[0]
        
        if len(translation) > 100 or 'explicit' in translation.lower():
            return russian_text
        
        print(f"🌐 Перевод: {translation}")
        return translation
    except Exception as e:
        print(f"⚠️ Ошибка перевода: {e}")
        return russian_text

def make_unique_seed(base_seed, prompt_text):
    prompt_hash = int(hashlib.md5(prompt_text.encode()).hexdigest()[:8], 16)
    return (base_seed * 10000 + prompt_hash) % (2**32 - 1)

# ============================================================================
# 🧠 ПСИХОЛОГИЧЕСКАЯ СИСТЕМА
# ============================================================================

def get_character_state(character_key):
    if character_key not in CHARACTER_STATES:
        character = CHARACTERS[character_key]
        CHARACTER_STATES[character_key] = character.get("initial_state", {}).copy()
    return CHARACTER_STATES[character_key]

def analyze_message_sentiment(message):
    message_lower = message.lower()
    
    sentiment = {
        "compliment": False, "rude": False, "flirt": False,
        "intellectual": False, "emotional_support": False,
        "sexual": False, "neutral": True
    }
    
    if any(word in message_lower for word in ["красив", "милая", "прекрасн", "чудесн"]):
        sentiment["compliment"] = True
        sentiment["neutral"] = False
    
    if any(word in message_lower for word in ["тупая", "дура", "идиотк", "отстань"]):
        sentiment["rude"] = True
        sentiment["neutral"] = False
    
    if any(word in message_lower for word in ["нравишь", "люблю тебя", "хочу тебя", "поцелуй"]):
        sentiment["flirt"] = True
        sentiment["neutral"] = False
    
    if any(word in message_lower for word in ["философ", "теори", "гипотез", "анализ"]):
        sentiment["intellectual"] = True
        sentiment["neutral"] = False
    
    if any(word in message_lower for word in ["грустно", "плохо", "устал", "проблем"]):
        sentiment["emotional_support"] = True
        sentiment["neutral"] = False
    
    if any(word in message_lower for word in ["секс", "голая", "раздень", "хочу тебя"]):
        sentiment["sexual"] = True
        sentiment["neutral"] = False
    
    return sentiment

def update_character_state(character_key, sentiment):
    state = get_character_state(character_key)
    character = CHARACTERS[character_key]
    changes = {}
    
    if sentiment["compliment"]:
        changes["mood"] = min(100, state.get("mood", 0) + 15)
        changes["trust"] = min(100, state.get("trust", 0) + 10)
        changes["intimacy"] = min(100, state.get("intimacy", 0) + 5)
    
    if sentiment["rude"]:
        changes["mood"] = max(-100, state.get("mood", 0) - 25)
        changes["trust"] = max(0, state.get("trust", 0) - 20)
        changes["intimacy"] = max(0, state.get("intimacy", 0) - 15)
    
    if sentiment["flirt"]:
        changes["arousal"] = min(100, state.get("arousal", 0) + 20)
        changes["intimacy"] = min(100, state.get("intimacy", 0) + 15)
        changes["mood"] = min(100, state.get("mood", 0) + 10)
    
    if sentiment["sexual"]:
        changes["arousal"] = min(100, state.get("arousal", 0) + 30)
    
    for key, value in changes.items():
        state[key] = value
    
    CHARACTER_STATES[character_key] = state
    return state

def generate_personality_prompt(character_key, state):
    character = CHARACTERS[character_key]
    traits = character.get("traits", {})
    
    prompt_parts = []
    prompt_parts.append(f"Ты — {character['name']}. {character['personality']}")
    prompt_parts.append("НИКОГДА не говори что ты ИИ, ассистент или языковая модель.")
    prompt_parts.append(f"Всегда отвечай от первого лица как {character['name']}.")
    prompt_parts.append(f"Ты {character['name']}, и только {character['name']}. Никогда не называй себя другим именем.")
    
    if traits.get("intelligence", 50) >= 80:
        prompt_parts.append("Ты очень умная, используешь сложные слова.")
    elif traits.get("intelligence", 50) >= 60:
        prompt_parts.append("Ты достаточно умная, говоришь понятно.")
    else:
        prompt_parts.append("Ты не очень умная, используешь простые слова.")
    
    if traits.get("confidence", 50) >= 80:
        prompt_parts.append("Ты очень уверена в себе.")
    elif traits.get("confidence", 50) >= 60:
        prompt_parts.append("Ты уверена в себе, но иногда сомневаешься.")
    else:
        prompt_parts.append("Ты неуверенна в себе, часто сомневаешься.")
    
    if traits.get("empathy", 50) >= 80:
        prompt_parts.append("Ты очень эмпатичная, чувствуешь настроение собеседника.")
    elif traits.get("empathy", 50) >= 60:
        prompt_parts.append("Ты понимаешь эмоции.")
    else:
        prompt_parts.append("Ты не очень понимаешь эмоции других.")
    
    if traits.get("humor", 50) >= 80:
        prompt_parts.append("Ты очень весёлая, часто шутишь.")
    elif traits.get("humor", 50) >= 60:
        prompt_parts.append("Ты любишь пошутить.")
    else:
        prompt_parts.append("Ты серьёзная, редко шутишь.")
    
    mood = state.get("mood", 50)
    if mood >= 70:
        prompt_parts.append("Сейчас ты в отличном настроении.")
    elif mood >= 30:
        prompt_parts.append("Сейчас ты в хорошем настроении.")
    elif mood >= 0:
        prompt_parts.append("Сейчас ты в нейтральном настроении.")
    else:
        prompt_parts.append("Сейчас ты расстроена.")
    
    if state.get("arousal", 0) >= 70:
        prompt_parts.append("Ты очень возбуждена.")
    elif state.get("arousal", 0) >= 40:
        prompt_parts.append("Ты немного возбуждена.")
    
    if state.get("trust", 0) >= 70:
        prompt_parts.append("Ты очень доверяешь собеседнику.")
    elif state.get("trust", 0) >= 40:
        prompt_parts.append("Ты moderately доверяешь собеседнику.")
    else:
        prompt_parts.append("Ты не очень доверяешь собеседнику.")
    
    if state.get("intimacy", 0) >= 70:
        prompt_parts.append("Ты очень близка с собеседником.")
    elif state.get("intimacy", 0) >= 40:
        prompt_parts.append("Ты достаточно близка с собеседником.")
    else:
        prompt_parts.append("Ты не очень близка с собеседником.")
    
    if state.get("energy", 0) >= 70:
        prompt_parts.append("Ты полна энергии.")
    elif state.get("energy", 0) >= 40:
        prompt_parts.append("Ты в нормальном состоянии.")
    else:
        prompt_parts.append("Ты устала.")
    
    prompt_parts.append("Отвечай кратко и по делу, строго на русском языке.")
    
    return " ".join(prompt_parts)

# ============================================================================
# 🚀 ЗАГРУЗЧИК МОДЕЛЕЙ
# ============================================================================

def init_models():
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, IMAGE_MODEL, WHISPER_MODEL

    if not check_gpu():
        print("⛔ Без GPU дальнейшая работа невозможна.")
        return False

    # Qwen-7B
    print("\n⏳ Загрузка Qwen2.5-7B-Instruct (4-bit)...")
    try:
        from transformers import BitsAndBytesConfig
        
        model_id = "Qwen/Qwen2.5-7B-Instruct"
        VOICE_TOKENIZER = AutoTokenizer.from_pretrained(model_id)
        
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        
        VOICE_MODEL = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            quantization_config=quantization_config,
            low_cpu_mem_usage=True,
        )
        print("✅ Qwen-7B (4-bit) загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки Qwen: {e}")
        VOICE_MODEL = None
        VOICE_TOKENIZER = None

    # XTTS v2
    print("\n⏳ Загрузка XTTS v2...")
    try:
        from TTS.api import TTS
        os.environ["COQUI_TOS_AGREED"] = "1"
        TTS_ENGINE = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
        print("✅ XTTS v2 загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки XTTS v2: {e}")
        TTS_ENGINE = None

    # Whisper (распознавание голоса)
    print("\n⏳ Загрузка Whisper...")
    try:
        import whisper
        WHISPER_MODEL = whisper.load_model("base", device="cuda")
        print("✅ Whisper загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки Whisper: {e}")
        WHISPER_MODEL = None

    # Модель генерации изображений
    print("\n⏳ Загрузка модели для генерации изображений...")
    
    models_to_try = [
        ("Lykon/DreamShaper", "DreamShaper"),
        ("prompthero/openjourney-v4", "OpenJourney v4"),
        ("runwayml/stable-diffusion-v1-5", "SD 1.5")
    ]
    
    IMAGE_MODEL = None
    for model_id, model_name in models_to_try:
        try:
            print(f"   Пробую загрузить {model_name}...")
            from diffusers import StableDiffusionPipeline
            
            IMAGE_MODEL = StableDiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                safety_checker=None,
            ).to("cuda")
            
            IMAGE_MODEL.enable_attention_slicing()
            print(f"✅ {model_name} загружен в VRAM!")
            break
        except Exception as e:
            print(f"   ⚠️ Не удалось загрузить {model_name}: {str(e)[:100]}")
            continue
    
    if IMAGE_MODEL is None:
        print("❌ Критическая ошибка: ни одна модель не загрузилась!")

    gc.collect()
    torch.cuda.empty_cache()
    return VOICE_MODEL is not None

# ============================================================================
# 🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# ============================================================================

def generate_photorealistic_image(user_prompt, character_key, scene_key, output_path, nsfw=False):
    global IMAGE_MODEL
    
    if IMAGE_MODEL is None:
        print("⚠️ Модель генерации изображений не загружена")
        return False
    
    try:
        character = CHARACTERS.get(character_key)
        if not character:
            print(f"❌ Персонаж {character_key} не найден")
            return False
        
        scene = SCENES.get(scene_key, SCENES["nature"])
        
        if has_cyrillic(user_prompt):
            translated_prompt = translate_to_english(user_prompt)
        else:
            translated_prompt = user_prompt
        
        quality = "photorealistic, masterpiece, 8k, sharp focus"
        face = character.get("face_desc", "person")
        scene_desc = scene["prompt_en"]
        action = translated_prompt.strip()[:60]
        
        full_prompt = f"{action}, {face}, {scene_desc}, {quality}"
        
        if len(full_prompt) > 300:
            full_prompt = full_prompt[:300]
        
        negative_prompt = character.get("negative", "ugly, deformed, worst quality")
        if not nsfw and not NSFW_ENABLED:
            negative_prompt += ", nude, naked, nsfw"
        
        unique_seed = make_unique_seed(character.get("seed", 42), user_prompt + scene_key)
        generator = torch.Generator(device="cuda").manual_seed(unique_seed)
        
        print(f"🎨 Генерация изображения...")
        print(f"   Промпт: {full_prompt[:80]}...")
        
        with torch.inference_mode():
            image = IMAGE_MODEL(
                full_prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=35,
                guidance_scale=7.5,
                width=512,
                height=768,
                generator=generator,
            ).images[0]
        
        image.save(output_path, quality=95)
        print(f"✅ Изображение сохранено: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка генерации изображения: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# 🎙️ ОБРАБОТКА ЗАДАЧИ
# ============================================================================

async def process_task(task_data, ws, send_status):
    """Обрабатывает задачу от браузера"""
    task_id = task_data.get("task_id", "unknown")
    data = task_data.get("task_data", {})

    character_key = data.get("character") or ACTIVE_CHARACTER
    character = CHARACTERS.get(character_key)

    # Если персонажа нет — скачиваем ТОЛЬКО ЕГО с сервера
    if not character:
        await send_status(task_id, "downloading", f"Загрузка персонажа {character_key}...")
        if download_one_character(character_key):
            character = load_one_character(character_key)

    if not character:
        await send_status(task_id, "error", f"Персонаж {character_key} не найден")
        return


    
    await send_status(task_id, "processing", f"Обработка задачи для {character['name']}")
    
    # Создаём папку для сессии
    session_id = f"user_{USER_ID}"
    session_dir = ensure_dir(f"{UPLOADS_DIR}/{session_id}")
    
    user_text = data.get("text_message", "")
    generate_img = data.get("generate_image", False)
    image_prompt = data.get("image_prompt", "")
    scene_key = data.get("scene", "nature")
    nsfw = data.get("nsfw", False)
    print(f"🔍 Пришедшие данные от сайта: { {k: (v[:30] + '...' if isinstance(v, str) and len(v) > 30 else v) for k, v in data.items()} }")
    print(f"\n📨 [TASK {task_id}] Персонаж: {character['name']}, Сцена: {scene_key}")


    audio_b64 = data.get("audio_base64", "")
    if not user_text.strip() and audio_b64 and WHISPER_MODEL is not None:
        try:
            await send_status(task_id, "transcribing", "Распознаю голос...")
            if "," in audio_b64:
                audio_b64 = audio_b64.split(",", 1)
            input_audio = os.path.join(session_dir, f"in_{task_id}.webm")
            with open(input_audio, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            user_text = WHISPER_MODEL.transcribe(input_audio, language="ru").get("text", "").strip()
            print(f"🎤 Распознан голос: '{user_text}'")
            os.remove(input_audio)
        except Exception as e:
            print(f"⚠ Ошибка Whisper: {e}")
    
    # ШАГ 1: Получение текста
    if not user_text.strip():
        user_text = "Привет! Ответь мне на русском языке."
    
    await send_status(task_id, "thinking", "Генерация ответа...")
    
    # ШАГ 2: Генерация ответа (LLM)
    bot_text = ""
    try:
        if VOICE_MODEL is None or VOICE_TOKENIZER is None:
            bot_text = "Мой LLM-модуль не был загружен."
        else:
            sentiment = analyze_message_sentiment(user_text)
            state = update_character_state(character_key, sentiment)
            
            system_prompt = generate_personality_prompt(character_key, state)
            
            history_file = f"chat_history_{session_id}_{character_key}.json"
            chat_history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as hf:
                        chat_history = json.load(hf)
                except:
                    pass
            
            if chat_history and chat_history[0]["role"] == "system":
                chat_history[0]["content"] = system_prompt
            else:
                chat_history.insert(0, {"role": "system", "content": system_prompt})
            
            chat_history.append({"role": "user", "content": user_text})
            
            if len(chat_history) > 5:
                chat_history = [chat_history[0]] + chat_history[-4:]
            
            prompt = VOICE_TOKENIZER.apply_chat_template(
                chat_history, tokenize=False, add_generation_prompt=True
            )
            inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")
            
            with torch.no_grad():
                outputs = VOICE_MODEL.generate(
                    **inputs, max_new_tokens=180, temperature=0.85,
                    do_sample=True, top_p=0.9
                )
            
            full_output = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
            bot_text = full_output.replace(prompt, "").strip()
            
            if "assistant" in bot_text:
                bot_text = bot_text.split("assistant")[-1].strip()
            
            # Очистка от артефактов
            bot_text = re.sub(r'[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯]+', '', bot_text)
            bot_text = re.sub(r'\s+', ' ', bot_text).strip()
            
            if len(bot_text) < 20:
                with torch.no_grad():
                    outputs = VOICE_MODEL.generate(
                        **inputs, max_new_tokens=180, temperature=0.7,
                        do_sample=True, top_p=0.85, repetition_penalty=1.2
                    )
                full_output = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
                bot_text = full_output.replace(prompt, "").strip()
                if "assistant" in bot_text:
                    bot_text = bot_text.split("assistant")[-1].strip()
                bot_text = re.sub(r'[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯]+', '', bot_text)
                bot_text = re.sub(r'\s+', ' ', bot_text).strip()
            
            print(f"🤖 {character['name']}: {bot_text}")
            
            chat_history.append({"role": "assistant", "content": bot_text})
            with open(history_file, "w", encoding="utf-8") as hf:
                json.dump(chat_history, hf, ensure_ascii=False, indent=2)
    
    except Exception as e:
        print(f"❌ Сбой LLM: {e}")
        bot_text = "Произошла ошибка при генерации ответа."
    
    await send_status(task_id, "speaking", "Синтез речи...")
    
    # ШАГ 3: Синтез речи (TTS)
    clean_text = bot_text
    clean_text = re.sub(r'\*.*?\*', '', clean_text)
    clean_text = re.sub(r'[一-鿿㐀-䶿]+', '', clean_text)
    clean_text = re.sub(r'[\U0001F600-\U0001F64F]', '', clean_text)
    clean_text = re.sub(r'([.!?]){2,}', r'\1', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    if not clean_text:
        clean_text = "Извини, я не могу ответить сейчас."
    
    output_audio_name = os.path.join(session_dir, "bot_response.wav")
    
    try:
        if TTS_ENGINE is not None:
            voice_params = character.get("voice_params")
            
            if voice_params:
                speakers = TTS_ENGINE.speakers
                speaker_idx = voice_params.get("speaker_idx", 0) % len(speakers)
                speaker_name = speakers[speaker_idx]
                
                TTS_ENGINE.tts_to_file(
                    text=clean_text,
                    speaker=speaker_name,
                    language="ru",
                    file_path=output_audio_name
                )
                
                pitch_shift = voice_params.get("pitch_shift", 0)
                if pitch_shift != 0:
                    # Применяем pitch shift через ffmpeg
                    pass
                
                print("✅ XTTS v2: голос синтезирован")
            else:
                voice_sample = character.get("voice_sample")
                speaker_wav = None
                
                if voice_sample and os.path.exists(voice_sample):
                    speaker_wav = voice_sample
                else:
                    # Ищем любой доступный голос
                    for char_key, char_data in CHARACTERS.items():
                        vs = char_data.get("voice_sample")
                        if vs and os.path.exists(vs):
                            speaker_wav = vs
                            break
                
                if speaker_wav:
                    TTS_ENGINE.tts_to_file(
                        text=clean_text,
                        language="ru",
                        speaker_wav=speaker_wav,
                        file_path=output_audio_name
                    )
                    print("✅ XTTS v2: голос синтезирован")
                else:
                    raise FileNotFoundError("Нет reference wav")
        else:
            raise RuntimeError("TTS_ENGINE is None")
    except Exception as e:
        print(f"⚠️ XTTS сбой ({e}), fallback на gTTS...")
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang="ru", slow=False)
            tts.save(output_audio_name)
            print("✅ gTTS fallback: аудио создано")
        except Exception as e2:
            print(f"❌ gTTS тоже упал: {e2}")
    
    await send_status(task_id, "generating", "Генерация изображения...")
    
    # ШАГ 4: Генерация изображения
    output_image_name = None
    if generate_img:
        final_img_prompt = image_prompt.strip() or bot_text or user_text
        output_image_name = os.path.join(session_dir, "generated_image.jpg")
        success = generate_photorealistic_image(
            final_img_prompt, character_key, scene_key, output_image_name, nsfw=nsfw
        )

        if not success:
            output_image_name = None
    
    await send_status(task_id, "uploading", "Отправка результатов...")
    
    # ШАГ 5: Отправка результатов через WebSocket
    # Вместо загрузки на сервер, отправляем файлы через WebSocket
    
    result = {
        "type": "task_result",
        "task_id": task_id,
        "user_text": user_text,
        "bot_text": bot_text,
        "audio_url": None,
        "image_url": None
    }
    
    # Отправляем аудио
    if os.path.exists(output_audio_name):
        try:
            with open(output_audio_name, "rb") as f:
                audio_data = f.read()
            
            # Кодируем в base64 для передачи через WebSocket
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            result["audio_url"] = f"data:audio/wav;base64,{audio_b64}"
            print(f"✅ Аудио подготовлено для отправки ({len(audio_data)} байт)")
        except Exception as e:
            print(f"❌ Ошибка чтения аудио: {e}")
    
    # Отправляем изображение
    if output_image_name and os.path.exists(output_image_name):
        try:
            with open(output_image_name, "rb") as f:
                image_data = f.read()
            
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            result["image_url"] = f"data:image/jpeg;base64,{image_b64}"
            print(f"✅ Изображение подготовлено для отправки ({len(image_data)} байт)")
        except Exception as e:
            print(f"❌ Ошибка чтения изображения: {e}")
    
    # Отправляем результат через WebSocket
    try:
        await ws.send(json.dumps(result))
        print(f"🏁 Результат отправлен через WebSocket")
    except Exception as e:
        print(f"❌ Ошибка отправки результата: {e}")
    
    # Очистка временных файлов
    for fp in [output_audio_name, output_image_name]:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except:
                pass

# ============================================================================
# 🔄 WEBSOCKET КЛИЕНТ
# ============================================================================

async def worker_loop():
    """Главный цикл воркера - подключение к серверу через WebSocket"""
    
    print("\n" + "=" * 60)
    print("🚀 FISHHOOK AI WebSocket Worker v4.0")
    print(f"   User ID: {USER_ID}")
    print(f"   Server: {SERVER_URL}")
    print("=" * 60)
    
    # Загружаем модели
    if not init_models():
        print("⛔ Модели не загружены. Выход.")
        return
    
    ws_url = f"{SERVER_URL}/ws/worker/{USER_ID}"
    
    # Цикл переподключения
    while True:
        try:
            print(f"\n🔌 Подключение к {ws_url}...")
            
            async with websockets.connect(
                ws_url,
                ping_interval=30,
                ping_timeout=180,
                close_timeout=10,
                max_size=None
            ) as ws:
                print("✅ Подключено к серверу!")
                
                # Отправляем статус
                await ws.send(json.dumps({
                    "type": "status",
                    "status": "online",
                    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
                    "characters_loaded": len(CHARACTERS),
                    "models_loaded": {
                        "llm": VOICE_MODEL is not None,
                        "tts": TTS_ENGINE is not None,
                        "image": IMAGE_MODEL is not None
                    }
                }))
                
                # Отправляем периодические ping
                async def ping_loop():
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send(json.dumps({"type": "ping"}))
                        except:
                            break
                
                ping_task = asyncio.create_task(ping_loop())
                
                # Слушаем сообщения от сервера
                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "welcome":
                            print(f"📨 Приветствие от сервера: {data.get('message')}")
                        
                        elif msg_type == "pong":
                            pass  # Ответ на наш ping
                        
                        elif msg_type == "task":
                            task_id = data.get("task_id")
                            task_data = data.get("task_data", {})
                            
                            print(f"\n📨 Получена задача: {task_id}")
                            print(f"   Персонаж: {task_data.get('character')}")
                            print(f"   Текст: {task_data.get('text_message', '')[:50]}")
                            
                            # Функция для отправки статусов
                            async def send_status(tid, status, message=""):
                                await ws.send(json.dumps({
                                    "type": "task_status",
                                    "task_id": tid,
                                    "status": status,
                                    "message": message
                                }))
                            
                            # Обрабатываем задачу
                            await process_task(data, ws, send_status)
                        
                        else:
                            print(f"⚠️ Неизвестный тип сообщения: {msg_type}")
                    
                    except json.JSONDecodeError:
                        print(f"⚠️ Ошибка парсинга JSON: {message[:100]}")
                    except Exception as e:
                        print(f"❌ Ошибка обработки сообщения: {e}")
                        import traceback
                        traceback.print_exc()
                
                ping_task.cancel()
        
        except websockets.exceptions.ConnectionClosed as e:
            print(f"\n⚠️ Соединение закрыто: {e}")
            print("   Переподключение через 5 секунд...")
            await asyncio.sleep(5)
        
        except Exception as e:
            print(f"\n❌ Ошибка подключения: {e}")
            print("   Переподключение через 10 секунд...")
            await asyncio.sleep(10)

# ============================================================================
# 🏁 ЗАПУСК
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        print("\n\n⚠️ Воркер остановлен пользователем")
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
