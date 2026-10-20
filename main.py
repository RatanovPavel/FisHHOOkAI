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
# 📦 АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ (для Colab / Kaggle)
# ============================================================
def install_dependencies():
    """
    Устанавливает все необходимые пакеты, если их нет.
    Словарь: {pip-имя пакета : имя модуля для импорта}
    """
    packages = {
        "transformers":       "transformers",
        "accelerate":         "accelerate",
        "bitsandbytes":       "bitsandbytes",
        "optimum":            "optimum",
        "coqui-tts":          "TTS",  # ← Coqui TTS форк (поддерживает Python 3.12!)
        "diffusers":          "diffusers",  # ← Для генерации изображений
        "openai-whisper":     "whisper",
        "SpeechRecognition":  "speech_recognition",
        "gtts":               "gtts",
        "pydub":              "pydub",
    }

    # Устанавливаем пакеты
    for pip_name, import_name in packages.items():
        try:
            __import__(import_name)
            print(f"✅ {pip_name} уже установлен.")
        except ImportError:
            print(f"📦 Устанавливаю {pip_name}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-q", pip_name
            ])

    # FFmpeg — критичен для обработки аудио
    if not shutil.which("ffmpeg"):
        print("📦 Устанавливаю ffmpeg...")
        os.system("apt-get update -qq && apt-get install -y -qq ffmpeg > /dev/null 2>&1")

install_dependencies()

# ============================================================
# 📥 ДОПОЛНИТЕЛЬНЫЕ ИМПОРТЫ (после установки)
# ============================================================
import speech_recognition as sr
from transformers import AutoTokenizer, AutoModelForCausalLM

# ============================================================
# ⚙️ КОНФИГУРАЦИЯ — МЕНЯЙТЕ ЗДЕСЬ
# ============================================================
USER_LOGIN = "RATANOV_PAVEL"
SERVER_URL = "https://skulla.ru"
DEMO_MODE  = False

# ============================================================
# 👥 СИСТЕМА ПЕРСОНАЖЕЙ
# ============================================================
CHARACTERS = {
    "anna": {
        "name": "Анна",
        "personality": "Ты — Анна, 25 лет. Нежная, романтичная девушка с чувством юмора. Любишь искусство, музыку и долгие прогулки. Говоришь мягко, с лёгкой иронией.",
        "voice_sample": "voices/anna.wav",  # Путь к образцу голоса
        "style": "romantic"
    },
    "kate": {
        "name": "Катя",
        "personality": "Ты — Катя, 23 года. Дерзкая, уверенная в себе, любишь флиртовать и подкалывать. Говоришь прямо, иногда грубовато, но с обаянием.",
        "voice_sample": "voices/kate.wav",
        "style": "bold"
    },
    "maria": {
        "name": "Мария",
        "personality": "Ты — Мария, 28 лет. Интеллектуалка, любишь философию и глубокие разговоры. Говоришь спокойно, вдумчиво, с академическим уклоном.",
        "voice_sample": "voices/maria.wav",
        "style": "intellectual"
    },
    "lisa": {
        "name": "Лиза",
        "personality": "Ты — Лиза, 22 года. Весёлая, энергичная, обожаешь тусовки и приключения. Говоришь быстро, эмоционально, много смеёшься.",
        "voice_sample": "voices/lisa.wav",
        "style": "energetic"
    }
}

# Активный персонаж (можно менять динамически)
ACTIVE_CHARACTER = "anna"

# ============================================================
# 🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# ============================================================
IMAGE_MODEL = None

# Глобальные переменные для удержания ИИ-моделей в VRAM
VOICE_MODEL     = None
VOICE_TOKENIZER = None
TTS_ENGINE      = None

# ============================================================
# 🔧 УТИЛИТЫ
# ============================================================
def check_gpu():
    """Проверяет доступность GPU и выводит информацию."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"✅ GPU: {gpu_name} | VRAM: {vram:.1f} GB")
        return True
    else:
        print("❌ GPU не обнаружен! Код требует CUDA.")
        return False

def ensure_dir(path):
    """Создаёт директорию, если её нет."""
    os.makedirs(path, exist_ok=True)
    return path

# ============================================================
# 🚀 ЗАГРУЗЧИК МОДЕЛЕЙ В VRAM
# ============================================================
def init_models():
    """Загружает все ИИ-модели в видеопамять."""
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, IMAGE_MODEL

    if not check_gpu():
        print("⛔ Без GPU дальнейшая работа невозможна.")
        return False

    # --- Qwen-7B (LLM) с 4-bit квантованием через bitsandbytes ---
    # Используем 7B вместо 14B для экономии VRAM (влезет в Tesla T4 14.6 GB)
    print("\n⏳ Загрузка Qwen2.5-7B-Instruct (4-bit)...")
    try:
        from transformers import BitsAndBytesConfig

        model_id = "Qwen/Qwen2.5-7B-Instruct"
        VOICE_TOKENIZER = AutoTokenizer.from_pretrained(model_id)

        # Правильная конфигурация 4-bit квантования
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

    # --- XTTS v2 (TTS) через Coqui TTS ---
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

    # --- Stable Diffusion (генерация изображений) ---
    print("\n⏳ Загрузка Stable Diffusion...")
    try:
        from diffusers import StableDiffusionPipeline

        model_id = "runwayml/stable-diffusion-v1-5"
        IMAGE_MODEL = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            safety_checker=None,
        ).to("cuda")
        print("✅ Stable Diffusion загружен в VRAM!")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки Stable Diffusion: {e}")
        print("   Генерация изображений будет недоступна")
        IMAGE_MODEL = None

    # --- Освобождаем кэш ---
    gc.collect()
    torch.cuda.empty_cache()

    return VOICE_MODEL is not None

# ============================================================
# 🖼️ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# ============================================================
def generate_image(prompt: str, output_path: str, character: str = None) -> bool:
    """
    Генерирует изображение по промпту с учётом персонажа.

    Args:
        prompt: Описание изображения
        output_path: Путь для сохранения
        character: Имя персонажа (опционально)

    Returns:
        True если успешно, False иначе
    """
    global IMAGE_MODEL

    if IMAGE_MODEL is None:
        print("⚠️ Модель генерации изображений не загружена")
        return False

    try:
        # Добавляем стиль персонажа если указан
        enhanced_prompt = prompt
        if character and character in CHARACTERS:
            char_info = CHARACTERS[character]
            style_map = {
                "romantic": "soft lighting, romantic atmosphere, warm colors",
                "bold": "dramatic lighting, confident pose, vibrant colors",
                "intellectual": "elegant setting, sophisticated atmosphere, muted tones",
                "energetic": "dynamic composition, bright colors, lively atmosphere"
            }
            style = style_map.get(char_info.get("style", ""), "")
            if style:
                enhanced_prompt = f"{prompt}, {style}"

        print(f"🎨 Генерация изображения: {enhanced_prompt[:50]}...")

        # Генерируем изображение
        with torch.inference_mode():
            image = IMAGE_MODEL(
                enhanced_prompt,
                num_inference_steps=30,
                guidance_scale=7.5,
                width=512,
                height=512
            ).images[0]

        # Сохраняем
        image.save(output_path)
        print(f"✅ Изображение сохранено: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Ошибка генерации изображения: {e}")
        return False

# ============================================================
# 🎙️ КОНВЕЙЕР ГОЛОСОВОГО ЧАТА
# ============================================================
def process_voice_chat(task_data):
    """
    Полный цикл:
      STT (Whisper) → LLM (Qwen-7B) → TTS (Coqui XTTS v2) → Push
    С поддержкой персонажей и генерации изображений
    """
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE, ACTIVE_CHARACTER

    actual_task = task_data.get("task_data", {})
    task_id     = actual_task.get("task_id", "test_001")
    session_id  = actual_task.get("session_id", "demo_session")
    user_login  = actual_task.get("user_login", USER_LOGIN)
    web_text    = actual_task.get("text_message", "")

    # Получаем персонажа из задачи или используем активного
    character_key = actual_task.get("character", ACTIVE_CHARACTER)
    character = CHARACTERS.get(character_key, CHARACTERS[ACTIVE_CHARACTER])

    # Проверяем запрос на генерацию изображения
    generate_img = actual_task.get("generate_image", False)
    image_prompt = actual_task.get("image_prompt", "")

    print(f"\n🎙️ Обработка задачи {task_id} (персонаж: {character['name']}) ...")

    session_dir = ensure_dir(f"./uploads/{session_id}")
    local_input_audio = os.path.join(session_dir, "user_voice.wav")
    output_audio_name = os.path.join(session_dir, "bot_response.wav")

    # ── Скачиваем аудио с сервера (или пропускаем в демо) ──
    if not DEMO_MODE:
        download_url = (
            f"{SERVER_URL}/api/studio/fishhook/"
            f"download_source/{session_id}?filename=user_voice.wav"
        )
        try:
            res = requests.get(download_url, timeout=20)
            if res.status_code == 200:
                with open(local_input_audio, "wb") as f:
                    f.write(res.content)
                print("✅ Аудио скачано.")
        except Exception as e:
            print(f"⚠️ Не удалось скачать аудио: {e}")

    # ── ШАГ 1: Получение текста ──
    user_text = ""
    if web_text.strip():
        user_text = web_text.strip()
        print(f"✍️ Текстовый ввод: {user_text}")
    elif os.path.exists(local_input_audio) and os.path.getsize(local_input_audio) > 100:
        try:
            import whisper
            model_w = whisper.load_model("base")
            converted = os.path.join(session_dir, "clean_pcm.wav")
            os.system(
                f'ffmpeg -y -i "{local_input_audio}" '
                f'-ar 16000 -ac 1 -c:a pcm_s16le "{converted}" '
                f'> /dev/null 2>&1'
            )
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

    # ── ШАГ 2: Генерация ответа (LLM) с характером персонажа ──
    bot_text = ""
    try:
        if VOICE_MODEL is None or VOICE_TOKENIZER is None:
            bot_text = "Мой LLM-модуль не был загружен."
        else:
            # Используем характер персонажа
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
                chat_history.append(
                    {"role": "system", "content": system_prompt}
                )

            chat_history.append({"role": "user", "content": user_text})

            # Обрезаем контекст — не более 5 сообщений
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

            full_output = VOICE_TOKENIZER.decode(
                outputs[0], skip_special_tokens=True
            )
            bot_text = full_output.replace(prompt, "").strip()

            # Убираем дублирование роли
            if "assistant" in bot_text:
                bot_text = bot_text.split("assistant")[-1].strip()

            print(f"🤖 {character['name']} ответила: {bot_text}")

            chat_history.append({"role": "assistant", "content": bot_text})
            with open(history_file, "w", encoding="utf-8") as hf:
                json.dump(chat_history, hf, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"❌ Сбой LLM: {e}")
        bot_text = "Произошла ошибка при генерации ответа."

    # ── ШАГ 3: Синтез речи (TTS) с голосом персонажа ──
    clean_text = re.sub(r'\*.*?\*', '', bot_text).strip()
    try:
        if TTS_ENGINE is not None:
            # Используем голос персонажа если есть образец
            voice_sample = character.get("voice_sample")
            speaker_wav = None

            if voice_sample and os.path.exists(voice_sample):
                speaker_wav = voice_sample
                print(f"🎤 Используем голос персонажа: {voice_sample}")
            elif os.path.exists(local_input_audio) and os.path.getsize(local_input_audio) > 100:
                # Fallback: клонируем голос из входящего аудио
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
                raise FileNotFoundError("Нет reference wav для клонирования")
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

    # ── ШАГ 3.5: Генерация изображения (если запрошено) ──
    output_image_name = None
    if generate_img and image_prompt:
        output_image_name = os.path.join(session_dir, "generated_image.jpg")
        success = generate_image(image_prompt, output_image_name, character_key)
        if not success:
            output_image_name = None

    # ── ШАГ 4: Отправка результата (аудио + изображение) ──
    if not DEMO_MODE:
        try:
            import urllib.parse
            encoded_user = urllib.parse.quote(user_text)
            encoded_bot  = urllib.parse.quote(bot_text)
            upload_url = (
                f"{SERVER_URL}/api/studio/fishhook/submit_result"
                f"?task_id={task_id}&user_login={user_login}"
                f"&user_text={encoded_user}&bot_text={encoded_bot}"
            )

            # Формируем файлы для отправки
            files = {}
            with open(output_audio_name, "rb") as f:
                files["audio"] = (output_audio_name, f, "audio/wav")

                # Добавляем изображение если есть
                if output_image_name and os.path.exists(output_image_name):
                    with open(output_image_name, "rb") as img_f:
                        files["image"] = (output_image_name, img_f, "image/jpeg")

                        requests.post(
                            upload_url,
                            data={"task_id": task_id, "user_login": user_login},
                            files=files,
                            timeout=60,
                        )
                        print(f"🏁 Результат отправлен на сервер (аудио + изображение)!")
                else:
                    requests.post(
                        upload_url,
                        data={"task_id": task_id, "user_login": user_login},
                        files=files,
                        timeout=30,
                    )
                    print(f"🏁 Результат отправлен на сервер (только аудио)!")
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


# ============================================================
# 🎬 ЗАГЛУШКИ ДЛЯ НЕРЕАЛИЗОВАННЫХ ФУНКЦИЙ
# ============================================================
def process_video_animation(task_data):
    """Заглушка — видео-анимация пока не реализована."""
    print("⚠️ process_video_animation() — ещё не реализована.")

def process_heavy_tryon_naked(task_data):
    """Заглушка — виртуальная примерка пока не реализована."""
    print("⚠️ process_heavy_tryon_naked() — ещё не реализована.")


# ============================================================
# 🔄 ГЛАВНЫЙ ЦИКЛ ОПРОСА СЕРВЕРА
# ============================================================
def main_loop(login: str):
    clean_login = login.lower().strip()

    print("\n" + "=" * 60)
    print("🚀  FISHHOOK MULTIMODAL ENGINE — ЗАПУСК")
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
                    style = task_data.get("task_data", {}).get(
                        "prompt_style", ""
                    )
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


# ============================================================
# 🏁 ТОЧКА ВХОДА
# ============================================================
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