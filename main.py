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
        "transformers":             "transformers",
        "accelerate":               "accelerate",
        "bitsandbytes":             "bitsandbytes",
        "optimum":                  "optimum",
        "coqui-tts":                "TTS",
        "diffusers":                "diffusers",
        "openai-whisper":           "whisper",
        "SpeechRecognition":        "speech_recognition",
        "gtts":                     "gtts",
        "pydub":                    "pydub",
        "websockets":               "websockets",
        "insightface":              "insightface",
        "onnxruntime-gpu":          "onnxruntime",
        "opencv-python-headless":   "cv2"
    }
    
    for pip_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✅ {pip_name} уже установлен")
        except ImportError:
            print(f"📦 Устанавливаю {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pip_name])

    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "torchao"], capture_output=True, text=True)

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
        files = ["config.json", "main.jpg", "voice.wav"]
        for filename in files:
            file_resp = requests.get(f"{base_url}/characters/{character_key}/{filename}", timeout=60)
            if file_resp.status_code == 200:
                with open(os.path.join(char_dir, filename), "wb") as f:
                    f.write(file_resp.content)
                print(f"  📥 Скачан: {character_key}/{filename}")
            else:
                print(f"  ⚠ Ошибка скачивания {filename}: HTTP {file_resp.status_code}")


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
        config["main_photo"] = os.path.join(char_path, "main.jpg")
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
ANIME_MODEL = None
FACE_APP = None
FACE_EMBEDS_CACHE = {}
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

def translate_to_english(russian_text, subject="woman"):
    """Переводит промпт с русского на английский"""
    global VOICE_MODEL, VOICE_TOKENIZER
    
    if VOICE_MODEL is None or VOICE_TOKENIZER is None:
        return russian_text
    
    try:
        msgs = [{"role": "system", "content": f"Convert Russian action prompt for a {subject} into detailed English Stable Diffusion tags (10-18 words) describing exact body pose, hands, and objects. Always use '{subject}', never use opposite gender. Output ONLY English tags."}, {"role": "user", "content": russian_text}]
        prompt = VOICE_TOKENIZER.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad(): outputs = VOICE_MODEL.generate(**inputs, max_new_tokens=30, do_sample=False)

        translation = VOICE_TOKENIZER.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        translation = re.sub(r'^["\']|["\']$', '', translation).split('\n')[0].strip()
        print(f"🌐 Перевод: {translation}")
        return translation or russian_text

    except Exception as e:
        print(f"⚠️ Ошибка перевода: {e}")
        return russian_text

def make_unique_seed(base_seed, prompt_text):
    prompt_hash = int(hashlib.md5(prompt_text.encode()).hexdigest()[:8], 16)
    return (base_seed * 10000 + prompt_hash) % (2**32 - 1)

def load_server_memory(character_key):
    base_url = get_http_base_url()
    try:
        r = requests.get(f"{base_url}/api/memory/{USER_ID}/{character_key}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            mem = d.get("memory", {})
            mem["_account"] = d.get("account", {})
            return mem
    except Exception as e:
        print(f"⚠ Ошибка загрузки памяти: {e}")
    return {"user_name": "", "facts": [], "state": {}, "gifts": [], "history": [], "_account": {}}


def save_server_memory(character_key, mem):
    base_url = get_http_base_url()
    try:
        requests.post(f"{base_url}/api/memory/{USER_ID}/{character_key}", json=mem, timeout=10)
    except Exception as e:
        print(f"⚠ Ошибка сохранения памяти: {e}")

def extract_user_memory(user_text, mem):
    
    m = re.search(r'(?:меня зовут|мо[её] имя|я\s+—?\s*)([А-ЯЁ][а-яё]{2,15})', user_text, re.IGNORECASE)
    if m and m.group(1).lower() not in ["привет", "хорошо", "сегодня", "очень", "просто", "тоже"]:
        mem["user_name"] = m.group(1)
    low = user_text.lower()
    if "на ты" in low:
        mem["facts"] = [f for f in mem.get("facts", []) if "обращаться на" not in f] + ["Общаться с пользователем на 'ты'"]
    elif any(w in low for w in ["работаю", "увлекаюсь", "люблю", "живу в", "мне ", "мой город", "моя работа"]):
        fact = user_text.strip()[:90]
        if fact not in mem.get("facts", []):
            mem.setdefault("facts", []).append(fact)

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

def generate_personality_prompt(character_key, state, mem=None):

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
    
    if mem:
        if mem.get("user_name"):
            prompt_parts.append(f"Собеседника зовут {mem['user_name']}, обращайся к нему по имени.")
        if mem.get("facts"):
            prompt_parts.append("Что ты помнишь о собеседнике: " + "; ".join(mem["facts"][-8:]) + ".")
        if mem.get("gifts"):
            gifts_str = ", ".join(g["name"] for g in mem["gifts"][-5:])
            prompt_parts.append(f"Собеседник дарил тебе подарки: {gifts_str}. Ты ценишь это и помнишь о них.")

        is_prem = mem.get("_account", {}).get("is_premium", False)
        if is_prem:
            prompt_parts.append("У собеседника статус PREMIUM: ты можешь открыто флиртовать и поддерживать взрослые интимные темы (18+).")
        else:
            prompt_parts.append("У собеседника базовый статус (не PREMIUM): избегай откровенного сексуального контента (18+), мягко и с юмором переводи тему.")

    prompt_parts.append("Ты МОЖЕШЬ и умеешь отправлять свои фотографии и записывать голосовые сообщения прямо в этом чате: если собеседник просит фото или голос, отвечай кокетливо и с радостью (например: 'Лови моё фото!' или 'Записываю для тебя голосовое!'), НИКОГДА не отказывайся и не говори, что не умеешь отправлять медиа.")

    from datetime import datetime
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    now = datetime.now()
    prompt_parts.append(f"Сегодня {now.day} {months[now.month - 1]} {now.year} года, {days[now.weekday()]}. Общайся как живой человек в переписке (2-4 предложения), без нумерованных списков и канцелярита, строго на русском языке.")

    
    return " ".join(prompt_parts)

# ============================================================================
# 🚀 ЗАГРУЗЧИК МОДЕЛЕЙ
# ============================================================================

def init_models():
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, IMAGE_MODEL, ANIME_MODEL, FACE_APP, WHISPER_MODEL



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

    
    # Модель генерации изображений (DreamShaper + FaceID)
    print("\n⏳ Загрузка DreamShaper + FaceID...")
    try:
        from diffusers import StableDiffusionPipeline, AutoencoderKL, DDIMScheduler
        vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=torch.float16)
        IMAGE_MODEL = StableDiffusionPipeline.from_pretrained("Lykon/DreamShaper", vae=vae, torch_dtype=torch.float16, safety_checker=None).to("cuda")
        IMAGE_MODEL.scheduler = DDIMScheduler.from_config(IMAGE_MODEL.scheduler.config)
        IMAGE_MODEL.load_ip_adapter("h94/IP-Adapter-FaceID", subfolder="", weight_name="ip-adapter-faceid_sd15.bin", image_encoder_folder=None)
        IMAGE_MODEL.load_lora_weights("h94/IP-Adapter-FaceID", weight_name="ip-adapter-faceid_sd15_lora.safetensors", adapter_name="faceid")
        IMAGE_MODEL.load_textual_inversion("yesyeahvh/bad-hands-5", weight_name="bad-hands-5.pt", token="bad-hands-5")
        print("✅ DreamShaper + FaceID загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки DreamShaper: {e}")
    # Аниме-модель (Anything V3.1)
    print("\n⏳ Загрузка Anything V3.1 (аниме)...")
    try:
        from diffusers import StableDiffusionPipeline
        ANIME_MODEL = StableDiffusionPipeline.from_pretrained("Linaqruf/anything-v3-1", torch_dtype=torch.float16, safety_checker=None).to("cuda")
        ANIME_MODEL.enable_attention_slicing()
        ANIME_MODEL.load_textual_inversion("EvilEngine/easynegative", weight_name="easynegative.safetensors", token="EasyNegative")
        print("✅ Anything V3.1 загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки Anything V3.1: {e}")
    # Детектор FaceID
    try:
        import insightface
        FACE_APP = insightface.app.FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        FACE_APP.prepare(ctx_id=0, det_size=(320, 320))
        print("✅ Детектор FaceID загружен!")
    except Exception as e:
        print(f"⚠ Детектор FaceID не загружен: {e}")


    gc.collect()
    torch.cuda.empty_cache()
    return VOICE_MODEL is not None

# ============================================================================
# 🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# ============================================================================

def get_cached_faceid(character_key):
    if character_key in FACE_EMBEDS_CACHE:
        return FACE_EMBEDS_CACHE[character_key]
    main_path = os.path.join(CHARACTERS_DIR, character_key, "main.jpg")
    if FACE_APP is None or not os.path.exists(main_path):
        return None
    import cv2
    faces = FACE_APP.get(cv2.imread(main_path))
    if not faces:
        return None
    id_embeds = torch.from_numpy(faces[0].normed_embedding).unsqueeze(0).unsqueeze(0)
    id_embeds = torch.cat([torch.zeros_like(id_embeds), id_embeds], dim=0).to(device="cuda", dtype=torch.float16)
    FACE_EMBEDS_CACHE[character_key] = [id_embeds]
    return FACE_EMBEDS_CACHE[character_key]

def generate_photorealistic_image(user_prompt, character_key, scene_key, output_path, nsfw=False):
    character = CHARACTERS.get(character_key)
    if not character: return False
    is_anime = character.get("style") == "anime"
    model = ANIME_MODEL if is_anime else IMAGE_MODEL
    if model is None: return False
    try:
        scene = SCENES.get(scene_key, SCENES["nature"])
        subj = "woman" if character.get("gender") == "female" else "man"
        action = (translate_to_english(user_prompt, subj) if has_cyrillic(user_prompt) else user_prompt).strip()[:100]
        solo_tag = "solo, 1girl" if character.get("gender") == "female" else "solo, 1boy"
        full_prompt = f"({action}:1.35), anatomically correct, natural hands, {solo_tag}, {character.get('face_desc', 'person')}, {scene['prompt_en']}"[:320]
        neg = f"bad-hands-5, EasyNegative, {character.get('negative', '')}, extra hands, three hands, extra arms, three arms, mutated hands, poorly drawn hands, multiple people, two people, crowd, twins, clones, duplicate"

        if not nsfw and not NSFW_ENABLED: neg += ", nude, naked, nsfw"
        gen = torch.Generator(device="cuda").manual_seed(make_unique_seed(character.get("seed", 42), user_prompt + scene_key))
        face_data = None if is_anime else get_cached_faceid(character_key)
        with torch.inference_mode():
            if not is_anime and face_data is not None:
                model.set_adapters(["faceid"], adapter_weights=[0.55])
                model.set_ip_adapter_scale(0.5)
                img = model(full_prompt, negative_prompt=neg, ip_adapter_image_embeds=face_data, num_inference_steps=30, guidance_scale=7.0, width=576, height=768, generator=gen).images[0]
            else:
                if not is_anime and hasattr(model, "set_adapters"): model.set_adapters(["faceid"], adapter_weights=[0.0])
                img = model(full_prompt, negative_prompt=neg, num_inference_steps=30, guidance_scale=7.0, width=576, height=768, generator=gen).images[0]
        img.save(output_path, quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        return False


# ============================================================================
# 🎙️ ОБРАБОТКА ЗАДАЧИ
# ============================================================================

def classify_user_intent(user_text):
    if VOICE_MODEL is None or VOICE_TOKENIZER is None:
        return {"want_photo": False, "want_voice": False, "is_nsfw": False, "photo_prompt": user_text}
    try:
        sys_p = 'Analyze user message intent. Output ONLY valid JSON: {"want_photo": bool, "want_voice": bool, "is_nsfw": bool, "photo_prompt": "short english SD pose/scene"}. is_nsfw=true for any nudity, sex, erotic, explicit poses or intimate requests.'
        msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": user_text}]
        p = VOICE_TOKENIZER.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = VOICE_TOKENIZER(p, return_tensors="pt").to("cuda")
        with torch.no_grad(): out = VOICE_MODEL.generate(**inp, max_new_tokens=60, do_sample=False)
        raw = VOICE_TOKENIZER.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True)
        m = re.search(r'\{.*?\}', raw, re.S)
        return json.loads(m.group(0)) if m else {"want_photo": False, "want_voice": False, "is_nsfw": False, "photo_prompt": user_text}
    except Exception:
        return {"want_photo": False, "want_voice": False, "is_nsfw": False, "photo_prompt": user_text}


def generate_suggestions(character, user_text, bot_text):
    base = ["📸 Пришли фоточку", "🎤 Ответь голосом"]
    if VOICE_MODEL is None or VOICE_TOKENIZER is None:
        return ["💬 Расскажи о себе", "💬 Какие у тебя увлечения?"] + base
    try:
        msgs = [{"role": "system", "content": f"Придумай 2 РАЗНЫЕ короткие реплики (по 3-5 слов, каждая с новой строки) от лица пользователя для развития диалога. НЕ повторяй вопрос: '{user_text[:40]}'."}, {"role": "user", "content": f"{character['name']}: {bot_text}"}]
        p = VOICE_TOKENIZER.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = VOICE_TOKENIZER(p, return_tensors="pt").to("cuda")
        with torch.no_grad(): out = VOICE_MODEL.generate(**inp, max_new_tokens=45, temperature=0.85, do_sample=True)
        raw = re.sub(r'["\'\d.)\-•一-鿿！？，。]+', '', VOICE_TOKENIZER.decode(out[0][inp.input_ids.shape[1]:], skip_special_tokens=True))
        lines = [f"💬 {l.strip()[:42]}" for l in raw.split("\n") if len(l.strip()) > 3][:2]
        return (lines if lines else ["💬 А что тебе ещё нравится?"]) + base
    except Exception: return ["💬 Расскажи подробнее", "💬 А что ты любишь?"] + base


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
                audio_b64 = audio_b64.split(",", 1)[1]
            input_audio = os.path.join(session_dir, f"in_{task_id}.webm")
            with open(input_audio, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            asr_res = await asyncio.to_thread(WHISPER_MODEL.transcribe, input_audio, language="ru")
            user_text = asr_res.get("text", "").strip()
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
            mem = load_server_memory(character_key)
            if mem.get("state"):
                CHARACTER_STATES[character_key] = mem["state"]
            sentiment = analyze_message_sentiment(user_text)
            state = update_character_state(character_key, sentiment)
            mem["state"] = state
            extract_user_memory(user_text, mem)
            system_prompt = generate_personality_prompt(character_key, state, mem)
            chat_history = mem.get("history", [])

            is_prem = mem.get("_account", {}).get("is_premium", False)
            is_gift_msg = "подарил тебе:" in user_text.lower() or "🎁" in user_text
            intent = await asyncio.to_thread(classify_user_intent, user_text)
            want_voice = bool(audio_b64) or is_gift_msg or intent.get("want_voice", False)
            if intent.get("is_nsfw") and not is_prem:
                generate_img = False
                system_prompt += " ВАЖНО: собеседник просит контент 18+, но у него НЕТ подписки PREMIUM. Не читай мораль, а кокетливо скажи, что откровенные фото и темы доступны только с подпиской 👑 PREMIUM (кнопка в правом верхнем углу чата)."
            elif is_gift_msg or intent.get("want_photo") or generate_img:
                generate_img = True
                image_prompt = "happy smiling selfie holding a gift" if is_gift_msg else (intent.get("photo_prompt") or user_text)
                if intent.get("is_nsfw") and is_prem: nsfw, scene_key = True, "nsfw"


            if chat_history and chat_history[0]["role"] == "system":
                chat_history[0]["content"] = system_prompt
            else:
                chat_history.insert(0, {"role": "system", "content": system_prompt})
            
            chat_history.append({"role": "user", "content": user_text})
            
            if len(chat_history) > 17:
                chat_history = [chat_history[0]] + chat_history[-16:]

            
            prompt = VOICE_TOKENIZER.apply_chat_template(
                chat_history, tokenize=False, add_generation_prompt=True
            )
            inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")
            
            outputs = await asyncio.to_thread(
                lambda: VOICE_MODEL.generate(
                    **inputs, max_new_tokens=180, temperature=0.72,
                    do_sample=True, top_p=0.9, repetition_penalty=1.12
                )
            )
            
            full_output = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
            bot_text = full_output.replace(prompt, "").strip()
            
            if "assistant" in bot_text:
                bot_text = bot_text.split("assistant")[-1].strip()
            
            # Очистка от артефактов
            bot_text = re.sub(r'[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯！？，。、；：「」『』（）]+', '', bot_text)
            bot_text = re.sub(r'\s+', ' ', bot_text).strip()
            
            if len(bot_text) < 5:
                with torch.no_grad():
                    outputs = VOICE_MODEL.generate(
                        **inputs, max_new_tokens=180, temperature=0.7,
                        do_sample=True, top_p=0.85, repetition_penalty=1.2
                    )
                full_output = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
                bot_text = full_output.replace(prompt, "").strip()
                if "assistant" in bot_text:
                    bot_text = bot_text.split("assistant")[-1].strip()
                bot_text = re.sub(r'[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯！？，。、；：「」『』（）]+', '', bot_text)
                bot_text = re.sub(r'\s+', ' ', bot_text).strip()
            
            print(f"🤖 {character['name']}: {bot_text}")
            
            chat_history.append({"role": "assistant", "content": bot_text})
            mem["history"] = chat_history
            save_server_memory(character_key, mem)

    
    except Exception as e:
        print(f"❌ Сбой LLM: {e}")
        bot_text = "Произошла ошибка при генерации ответа."
    
    want_voice = bool(audio_b64) or ("🎁" in user_text) or any(w in user_text.lower() for w in ["голос", "озвуч", "скажи", "проговори", "послушать"])
    output_audio_name = os.path.join(session_dir, "bot_response.wav")
    if want_voice:
        await send_status(task_id, "speaking", "Синтез речи...")

    # ШАГ 3: Синтез речи (TTS)
    if want_voice:
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
                    
                    await asyncio.to_thread(
                        TTS_ENGINE.tts_to_file,
                        text=clean_text,
                        language="ru",
                        speaker_wav=speaker_name,
                        file_path=output_audio_name,
                        speed=1.1, temperature=0.65, repetition_penalty=2.5
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
                        await asyncio.to_thread(
                            TTS_ENGINE.tts_to_file,
                            text=clean_text,
                            language="ru",
                            speaker_wav=speaker_wav,
                            file_path=output_audio_name,
                            speed=1.1, temperature=0.65, repetition_penalty=2.5
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
    
    
    # ШАГ 4: Генерация изображения
    output_image_name = None
    if generate_img:
        await send_status(task_id, "generating", "Генерация изображения...")
        final_img_prompt = image_prompt.strip() or bot_text or user_text
        output_image_name = os.path.join(session_dir, "generated_image.jpg")
        success = await asyncio.to_thread(
            generate_photorealistic_image,
            final_img_prompt, character_key, scene_key, output_image_name, nsfw=nsfw
        )


        if not success:
            output_image_name = None
    
    await send_status(task_id, "uploading", "Отправка результатов...")
    
    # ШАГ 5: Отправка результатов через WebSocket
    # Вместо загрузки на сервер, отправляем файлы через WebSocket
    
    suggestions = await asyncio.to_thread(generate_suggestions, character, user_text, bot_text)
    result = {
        "type": "task_result",
        "task_id": task_id,
        "user_text": user_text,
        "bot_text": bot_text,
        "audio_url": None,
        "image_url": None,
        "suggestions": suggestions
    }
    
    # Отправляем аудио (сжимаем WAV -> MP3 для быстрой доставки)
    if os.path.exists(output_audio_name):
        try:
            from pydub import AudioSegment
            mp3_path = output_audio_name.replace(".wav", ".mp3")
            AudioSegment.from_file(output_audio_name).export(mp3_path, format="mp3", bitrate="64k")
            with open(mp3_path, "rb") as f:
                audio_data = f.read()
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            result["audio_url"] = f"data:audio/mp3;base64,{audio_b64}"
            print(f"✅ MP3 аудио подготовлено для отправки ({len(audio_data)} байт)")
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
        except Exception as e:
            print(f"❌ Ошибка сжатия/чтения аудио: {e}")

    
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
