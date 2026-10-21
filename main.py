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

# ============================================================
# 📦 АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================
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
    }

    for pip_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✅ {pip_name} уже установлен.")
        except ImportError:
            print(f"📦 Устанавливаю {pip_name}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-q", pip_name
            ])

    if not shutil.which("ffmpeg"):
        print("📦 Устанавливаю ffmpeg...")
        os.system("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null 2>&1")

install_dependencies()

import speech_recognition as sr
from transformers import AutoTokenizer, AutoModelForCausalLM

# ============================================================
# ⚙️ КОНФИГУРАЦИЯ
# ============================================================
USER_LOGIN = "RATANOV_PAVEL"
SERVER_URL = "https://skulla.ru"
DEMO_MODE  = False
NSFW_ENABLED = True  # Включить режим 18+

# ============================================================
# 👥 СИСТЕМА ПЕРСОНАЖЕЙ С ДЕТАЛЬНЫМ ОПИСАНИЕМ ВНЕШНОСТИ
# ============================================================
CHARACTERS = {
    "anna": {
        "name": "Анна",
        "personality": "Ты — Анна, 25 лет. Нежная, романтичная девушка с чувством юмора. Любишь искусство, музыку и долгие прогулки. Говоришь мягко, с лёгкой иронией.",
        "voice_sample": "voices/anna.wav",
        "appearance": {
            "en": "25 year old beautiful woman, long wavy chestnut brown hair, bright green eyes, oval face, soft delicate features, light porcelain skin, slender elegant figure, natural makeup, gentle smile",
            "negative": "ugly, deformed, disfigured, bad anatomy, bad hands, extra fingers, missing fingers, cropped, worst quality, low quality"
        },
        "seed": 42,
        "style": "romantic"
    },
    "kate": {
        "name": "Катя",
        "personality": "Ты — Катя, 23 года. Дерзкая, уверенная в себе, любишь флиртовать и подкалывать. Говоришь прямо, иногда грубовато, но с обаянием.",
        "voice_sample": "voices/kate.wav",
        "appearance": {
            "en": "23 year old stunning woman, short platinum blonde bob hair, piercing blue eyes, heart-shaped face, sharp confident features, fair skin with light freckles, athletic toned figure, bold red lipstick, smoky eyes",
            "negative": "ugly, deformed, disfigured, bad anatomy, bad hands, extra fingers, missing fingers, cropped, worst quality, low quality"
        },
        "seed": 123,
        "style": "bold"
    },
    "maria": {
        "name": "Мария",
        "personality": "Ты — Мария, 28 лет. Интеллектуалка, любишь философию и глубокие разговоры. Говоришь спокойно, вдумчиво, с академическим уклоном.",
        "voice_sample": "voices/maria.wav",
        "appearance": {
            "en": "28 year old elegant woman, long straight dark brown hair with subtle highlights, deep brown intelligent eyes, refined oval face, sophisticated features, olive skin, graceful slender figure, minimal natural makeup, glasses optional",
            "negative": "ugly, deformed, disfigured, bad anatomy, bad hands, extra fingers, missing fingers, cropped, worst quality, low quality"
        },
        "seed": 456,
        "style": "intellectual"
    },
    "lisa": {
        "name": "Лиза",
        "personality": "Ты — Лиза, 22 года. Весёлая, энергичная, обожаешь тусовки и приключения. Говоришь быстро, эмоционально, много смеёшься.",
        "voice_sample": "voices/lisa.wav",
        "appearance": {
            "en": "22 year old gorgeous woman, long straight bright red hair with bangs, sparkling hazel eyes, round youthful face, cute playful features, fair skin with rosy cheeks, slim fit figure, colorful makeup, energetic expression",
            "negative": "ugly, deformed, disfigured, bad anatomy, bad hands, extra fingers, missing fingers, cropped, worst quality, low quality"
        },
        "seed": 789,
        "style": "energetic"
    }
}

ACTIVE_CHARACTER = "anna"

# ============================================================
# 🎬 СИСТЕМА СЦЕН (ОБСТАНОВОК)
# ============================================================
SCENES = {
    "nature": {
        "name": "🌿 Природа",
        "prompt_en": "outdoor nature scene, lush green forest, dappled sunlight through trees, wildflowers, soft bokeh background, golden hour lighting, serene atmosphere",
        "nsfw": False
    },
    "sea": {
        "name": "🌊 Море",
        "prompt_en": "beautiful beach scene, turquoise ocean waves, white sand, sunset golden hour, warm tropical lighting, palm trees in background, cinematic composition",
        "nsfw": False
    },
    "shower": {
        "name": "🚿 Душ",
        "prompt_en": "intimate bathroom scene, glass shower, water droplets on skin, steam, soft warm lighting, wet hair, sensual atmosphere, artistic composition",
        "nsfw": True
    },
    "pastel": {
        "name": "🌸 Пастель",
        "prompt_en": "cozy bedroom scene, soft pastel colors, pink and lavender tones, dreamy soft lighting, fluffy pillows, warm intimate atmosphere, fairy lights",
        "nsfw": False
    },
    "nsfw": {
        "name": "🔥 18+",
        "prompt_en": "intimate boudoir scene, sensual pose, artistic nude, soft dramatic lighting, tasteful composition, professional boudoir photography style",
        "nsfw": True
    },
    "cafe": {
        "name": "☕ Кафе",
        "prompt_en": "cozy cafe interior, warm ambient lighting, coffee cup on table, window with city view, relaxed atmosphere, lifestyle photography",
        "nsfw": False
    },
    "gym": {
        "name": "💪 Спортзал",
        "prompt_en": "modern gym interior, fitness equipment, athletic pose, dynamic lighting, energetic atmosphere, sportswear, motivational setting",
        "nsfw": False
    }
}

# ============================================================
# 🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# ============================================================
IMAGE_MODEL = None

VOICE_MODEL     = None
VOICE_TOKENIZER = None
TTS_ENGINE      = None

# ============================================================
# 🔧 УТИЛИТЫ
# ============================================================
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
    """Проверяет наличие кириллицы в тексте"""
    return bool(re.search('[а-яА-Я]', text))

def translate_to_english(russian_text):
    """Переводит промпт с русского на английский через Qwen"""
    global VOICE_MODEL, VOICE_TOKENIZER

    if VOICE_MODEL is None or VOICE_TOKENIZER is None:
        print("⚠️ Qwen не загружен, пропускаю перевод")
        return russian_text

    try:
        prompt = f"Translate the following Russian text to English for image generation prompt. Output ONLY the English translation, nothing else. Be concise and descriptive:\n\n{russian_text}"
        inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = VOICE_MODEL.generate(
                **inputs,
                max_new_tokens=100,
                temperature=0.3,
                do_sample=False
            )

        translation = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
        translation = translation.replace(prompt, "").strip()

        # Убираем возможные артефакты
        translation = re.sub(r'^["\']|["\']$', '', translation)

        print(f"🌐 Перевод: {translation[:50]}...")
        return translation
    except Exception as e:
        print(f"⚠️ Ошибка перевода: {e}")
        return russian_text

# ============================================================
# 🚀 ЗАГРУЗЧИК МОДЕЛЕЙ В VRAM
# ============================================================
def init_models():
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, IMAGE_MODEL

    if not check_gpu():
        print("⛔ Без GPU дальнейшая работа невозможна.")
        return False

    # --- Qwen-7B (LLM) ---
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

    # --- XTTS v2 (TTS) ---
    print("\n⏳ Загрузка XTTS v2...")
    try:
        from TTS.api import TTS
        os.environ["COQUI_TOS_AGREED"] = "1"
        TTS_ENGINE = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2"
        ).to("cuda")
        print("✅ XTTS v2 загружен в VRAM!")
    except Exception as e:
        print(f"❌ Ошибка загрузки XTTS v2: {e}")
        TTS_ENGINE = None

    # --- Realistic Vision V6.0 (фотореалистичная генерация) ---
    print("\n⏳ Загрузка Realistic Vision V6.0 (фотореализм)...")
    try:
        from diffusers import StableDiffusionPipeline

        model_id = "SG161222/Realistic_Vision_V6.0_B1_noVAE"
        IMAGE_MODEL = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            safety_checker=None,  # Отключаем цензуру
        ).to("cuda")

        # Улучшаем настройки для фотореализма
        IMAGE_MODEL.enable_attention_slicing()

        print("✅ Realistic Vision V6.0 загружен в VRAM!")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки Realistic Vision: {e}")
        print("   Пробую загрузить стандартную SD 1.5...")
        try:
            from diffusers import StableDiffusionPipeline
            IMAGE_MODEL = StableDiffusionPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16,
                safety_checker=None,
            ).to("cuda")
            print("✅ SD 1.5 загружен (fallback)")
        except Exception as e2:
            print(f"❌ Ошибка загрузки SD 1.5: {e2}")
            IMAGE_MODEL = None

    gc.collect()
    torch.cuda.empty_cache()

    return VOICE_MODEL is not None

# ============================================================
# 🖼️ ГЕНЕРАЦИЯ ФОТОРЕАЛИСТИЧНЫХ ИЗОБРАЖЕНИЙ
# ============================================================
def generate_photorealistic_image(user_prompt, character_key, scene_key, output_path, nsfw=False):
    """
    Генерирует фотореалистичное изображение с постоянством лица
    """
    global IMAGE_MODEL

    if IMAGE_MODEL is None:
        print("⚠️ Модель генерации изображений не загружена")
        return False

    try:
        character = CHARACTERS.get(character_key, CHARACTERS[ACTIVE_CHARACTER])
        scene = SCENES.get(scene_key, SCENES["nature"])

        # Переводим промпт на английский если есть кириллица
        if has_cyrillic(user_prompt):
            translated_prompt = translate_to_english(user_prompt)
        else:
            translated_prompt = user_prompt

        # Собираем полный промпт
        quality_tags = "photorealistic, masterpiece, best quality, ultra detailed, 8k uhd, high resolution, sharp focus, professional photography, dslr, cinematic lighting"
        character_desc = character["appearance"]["en"]
        scene_desc = scene["prompt_en"]

        full_prompt = f"{quality_tags}, {character_desc}, {translated_prompt}, {scene_desc}"

        # Negative prompt
        negative_prompt = f"{character['appearance']['negative']}, blurry, low quality, jpeg artifacts, watermark, text, signature, cartoon, anime, painting, drawing, illustration, 3d render, cgi, plastic, doll, mannequin"

        if not nsfw and not NSFW_ENABLED:
            negative_prompt += ", nude, naked, nsfw, explicit, lingerie, underwear"

        print(f"🎨 Генерация изображения...")
        print(f"   Персонаж: {character['name']}")
        print(f"   Сцена: {scene['name']}")
        print(f"   Промпт: {full_prompt[:80]}...")

        # Генерируем с seed для воспроизводимости
        generator = torch.Generator(device="cuda").manual_seed(character["seed"])

        with torch.inference_mode():
            image = IMAGE_MODEL(
                full_prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=35,
                guidance_scale=7.5,
                width=512,
                height=768,  # Портретная ориентация
                generator=generator,
            ).images[0]

        image.save(output_path, quality=95)
        print(f"✅ Изображение сохранено: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Ошибка генерации изображения: {e}")
        return False

# ============================================================
# 🎙️ КОНВЕЙЕР ГОЛОСОВОГО ЧАТА
# ============================================================
def process_voice_chat(task_data):
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, ACTIVE_CHARACTER

    actual_task = task_data.get("task_data", {})
    task_id     = actual_task.get("task_id", "test_001")
    session_id  = actual_task.get("session_id", "demo_session")
    user_login  = actual_task.get("user_login", USER_LOGIN)
    web_text    = actual_task.get("text_message", "")

    character_key = actual_task.get("character", ACTIVE_CHARACTER)
    character = CHARACTERS.get(character_key, CHARACTERS[ACTIVE_CHARACTER])

    generate_img = actual_task.get("generate_image", False)
    image_prompt = actual_task.get("image_prompt", "")
    scene_key = actual_task.get("scene", "nature")
    nsfw = actual_task.get("nsfw", False)

    print(f"\n🎙️ Обработка задачи {task_id} (персонаж: {character['name']}) ...")

    session_dir = ensure_dir(f"./uploads/{session_id}")
    local_input_audio = os.path.join(session_dir, "user_voice.wav")
    output_audio_name = os.path.join(session_dir, "bot_response.wav")

    # Скачиваем аудио
    if not DEMO_MODE:
        download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=user_voice.wav"
        try:
            res = requests.get(download_url, timeout=20)
            if res.status_code == 200:
                with open(local_input_audio, "wb") as f:
                    f.write(res.content)
                print("✅ Аудио скачано.")
        except Exception as e:
            print(f"⚠️ Не удалось скачать аудио: {e}")

    # ШАГ 1: Получение текста
    user_text = ""
    if web_text.strip():
        user_text = web_text.strip()
        print(f"✍️ Текстовый ввод: {user_text}")
    elif os.path.exists(local_input_audio) and os.path.getsize(local_input_audio) > 100:
        try:
            import whisper
            model_w = whisper.load_model("base")
            converted = os.path.join(session_dir, "clean_pcm.wav")
            os.system(f'ffmpeg -y -i "{local_input_audio}" -ar 16000 -ac 1 -c:a pcm_s16le "{converted}" > /dev/null 2>&1')
            if os.path.exists(converted):
                result = model_w.transcribe(converted, language="ru")
                user_text = result.get("text", "").strip()
                os.remove(converted)
            print(f"🗣️ Whisper распознал: {user_text}")
        except Exception as e:
            print(f"⚠️ Ошибка Whisper: {e}")
            user_text = "Звук не распознан."
    else:
        user_text = "Привет! Ответь мне на русском языке."

    if not user_text.strip():
        user_text = "Привет!"

    # ШАГ 2: Генерация ответа (LLM)
    bot_text = ""
    try:
        if VOICE_MODEL is None or VOICE_TOKENIZER is None:
            bot_text = "Мой LLM-модуль не был загружен."
        else:
            system_prompt = (
                f"{character['personality']} "
                "Отвечай кратко и по делу, строго на русском языке. "
                "Сохраняй свой характер во всех ответах."
            )

            history_file = f"chat_history_{session_id}.json"
            chat_history = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r", encoding="utf-8") as hf:
                        chat_history = json.load(hf)
                except Exception:
                    pass

            if not chat_history:
                chat_history.append({"role": "system", "content": system_prompt})

            chat_history.append({"role": "user", "content": user_text})

            if len(chat_history) > 5:
                chat_history = [chat_history[0]] + chat_history[-4:]

            prompt = VOICE_TOKENIZER.apply_chat_template(
                chat_history, tokenize=False, add_generation_prompt=True
            )
            inputs = VOICE_TOKENIZER(prompt, return_tensors="pt").to("cuda")

            with torch.no_grad():
                outputs = VOICE_MODEL.generate(
                    **inputs,
                    max_new_tokens=180,
                    temperature=0.85,
                    do_sample=True,
                    top_p=0.9,
                )

            full_output = VOICE_TOKENIZER.decode(outputs[0], skip_special_tokens=True)
            bot_text = full_output.replace(prompt, "").strip()

            if "assistant" in bot_text:
                bot_text = bot_text.split("assistant")[-1].strip()

            print(f"🤖 {character['name']} ответила: {bot_text}")

            chat_history.append({"role": "assistant", "content": bot_text})
            with open(history_file, "w", encoding="utf-8") as hf:
                json.dump(chat_history, hf, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"❌ Сбой LLM: {e}")
        bot_text = "Произошла ошибка при генерации ответа."

    # ШАГ 3: Синтез речи (TTS)
    clean_text = re.sub(r'\*.*?\*', '', bot_text).strip()
    try:
        if TTS_ENGINE is not None:
            voice_sample = character.get("voice_sample")
            speaker_wav = None

            if voice_sample and os.path.exists(voice_sample):
                speaker_wav = voice_sample
                print(f"🎤 Используем голос персонажа: {voice_sample}")
            elif os.path.exists(local_input_audio) and os.path.getsize(local_input_audio) > 100:
                speaker_wav = local_input_audio
                print("🎤 Клонируем голос из входящего аудио")

            if speaker_wav:
                TTS_ENGINE.tts_to_file(
                    text=clean_text,
                    language="ru",
                    speaker_wav=speaker_wav,
                    file_path=output_audio_name,
                )
                print("✅ XTTS v2: голос синтезирован!")
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
            print("✅ gTTS fallback: аудио создано.")
        except Exception as e2:
            print(f"❌ gTTS тоже упал: {e2}")
            with open(output_audio_name, "wb") as f:
                f.write(b"")

    # ШАГ 3.5: Генерация фотореалистичного изображения
    output_image_name = None
    if generate_img and image_prompt:
        output_image_name = os.path.join(session_dir, "generated_image.jpg")
        success = generate_photorealistic_image(
            image_prompt,
            character_key,
            scene_key,
            output_image_name,
            nsfw=nsfw
        )
        if not success:
            output_image_name = None

    # ШАГ 4: Отправка результата
    if not DEMO_MODE:
        try:
            upload_url = f"{SERVER_URL}/api/studio/fishhook/submit_result"

            data = {
                "task_id": task_id,
                "user_login": user_login,
                "user_text": user_text,
                "bot_text": bot_text
            }

            files = {}

            if os.path.exists(output_audio_name):
                files["audio"] = ("bot_response.wav", open(output_audio_name, "rb"), "audio/wav")

            if output_image_name and os.path.exists(output_image_name):
                files["image"] = ("generated_image.jpg", open(output_image_name, "rb"), "image/jpeg")

            response = requests.post(
                upload_url,
                data=data,
                files=files if files else None,
                timeout=60
            )

            if response.status_code == 200:
                if "image" in files:
                    print(f"🏁 Результат отправлен (аудио + изображение)!")
                else:
                    print(f"🏁 Результат отправлен (только аудио)!")
            else:
                print(f"❌ Ошибка отправки: HTTP {response.status_code}")

            for key, file_tuple in files.items():
                file_tuple[1].close()

        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
    else:
        print(f"🏁 [DEMO] Результат сохранён локально: {output_audio_name}")
        if output_image_name:
            print(f"🏁 [DEMO] Изображение сохранено: {output_image_name}")

    # Очистка
    for fp in [local_input_audio, output_audio_name, output_image_name]:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

# Заглушки
def process_video_animation(task_data):
    print("⚠️ process_video_animation() — ещё не реализована.")

def process_heavy_tryon_naked(task_data):
    print("⚠️ process_heavy_tryon_naked() — ещё не реализована.")

# ============================================================
# 🔄 ГЛАВНЫЙ ЦИКЛ
# ============================================================
def main_loop(login: str):
    clean_login = login.lower().strip()

    print("\n" + "=" * 60)
    print("🚀  FISHHOOK MULTIMODAL ENGINE v2.1 — ЗАПУСК")
    print("=" * 60)

    if not init_models():
        print("⛔ Модели не загружены. Выход.")
        return

    if DEMO_MODE:
        print("\n🧪 ДЕМО-РЕЖИМ: работаю без сервера.")
        print("   Введите текст (или 'quit' для выхода):\n")
        while True:
            user_input = input("👤 Вы: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 До свидания!")
                break
            if not user_input:
                continue
            fake_task = {
                "task_data": {
                    "task_id": "demo_001",
                    "session_id": "demo",
                    "user_login": clean_login,
                    "text_message": user_input,
                    "generate_image": True,
                    "image_prompt": "красивый портрет",
                    "scene": "nature"
                }
            }
            process_voice_chat(fake_task)
        return

    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{clean_login}"
    print(f"📡 Опрос сервера: {endpoint}")

    while True:
        try:
            res = requests.get(endpoint, timeout=10)
            if res.status_code == 200:
                task_data = res.json()
                status = task_data.get("status")

                if status == "success":
                    style = task_data.get("task_data", {}).get("prompt_style", "")
                    if style == "animate_video":
                        process_video_animation(task_data)
                    elif style == "voice_chat":
                        process_voice_chat(task_data)
                    else:
                        process_heavy_tryon_naked(task_data)
                elif status == "no_tasks":
                    print(".", end="", flush=True)
            elif res.status_code == 404:
                print(f"\n⚠️ 404: маршрут не найден.")
                time.sleep(5)
        except requests.ConnectionError:
            print("\n🔌 Нет связи с сервером. Пауза 10 сек...")
            time.sleep(10)
        except Exception as e:
            print(f"\n⚠️ Ошибка: {e}")
            time.sleep(3)

        time.sleep(1)

if __name__ == "__main__":
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--login", type=str, default=USER_LOGIN)
        args = parser.parse_args()
        login = args.login
    except SystemExit:
        login = USER_LOGIN

    main_loop(login)
