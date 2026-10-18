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
    packages = [
        "transformers",
        "accelerate",
        "bitsandbytes",  # ← 4-bit квантование (стабильнее AWQ)
        "optimum",
        "TTS",           # ← Coqui TTS (именно TTS, не coqui-tts!)
        "openai-whisper",
        "SpeechRecognition",
        "gtts",
        "pydub",
    ]
    
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
USER_LOGIN = "RATANOV_PAVEL"       # ← Ваш логин на сервере
SERVER_URL = "https://skulla.ru"     # ← Адрес сервера
DEMO_MODE  = False                   # ← True = работа без сервера (тест)

# ============================================================
# 🧠 ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ МОДЕЛЕЙ (в VRAM)
# ============================================================
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
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE

    if not check_gpu():
        print("⛔ Без GPU дальнейшая работа невозможна.")
        return False

    # --- Qwen-14B (LLM) с 4-bit квантованием через bitsandbytes ---
    print("\n⏳ Загрузка Qwen2.5-14B-Instruct (4-bit)...")
    try:
        model_id = "Qwen/Qwen2.5-14B-Instruct"
        VOICE_TOKENIZER = AutoTokenizer.from_pretrained(model_id)
        VOICE_MODEL = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch.float16,
            load_in_4bit=True,  # ← 4-bit квантование через bitsandbytes
            low_cpu_mem_usage=True,
        )
        print("✅ Qwen-14B (4-bit) загружен в VRAM!")
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

    # --- Освобождаем кэш ---
    gc.collect()
    torch.cuda.empty_cache()

    return VOICE_MODEL is not None

# ============================================================
# 🎙️ КОНВЕЙЕР ГОЛОСОВОГО ЧАТА
# ============================================================
def process_voice_chat(task_data):
    """
    Полный цикл:
      STT (Whisper) → LLM (Qwen-14B) → TTS (XTTS v2) → Push
    """
    global VOICE_MODEL, VOICE_TOKENIZER, TTS_ENGINE

    actual_task = task_data.get("task_data", {})
    task_id     = actual_task.get("task_id", "test_001")
    session_id  = actual_task.get("session_id", "demo_session")
    user_login  = actual_task.get("user_login", USER_LOGIN)
    web_text    = actual_task.get("text_message", "")

    print(f"\n🎙️ Обработка задачи {task_id} ...")

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

    # ── ШАГ 2: Генерация ответа (LLM) ──
    bot_text = ""
    try:
        if VOICE_MODEL is None or VOICE_TOKENIZER is None:
            bot_text = "Мой LLM-модуль не был загружен."
        else:
            system_prompt = (
                "Ты — эрудированная и дружелюбная девушка-собеседница. "
                "Отвечай кратко и по делу, строго на русском языке."
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

            print(f"🤖 Qwen ответил: {bot_text}")

            chat_history.append({"role": "assistant", "content": bot_text})
            with open(history_file, "w", encoding="utf-8") as hf:
                json.dump(chat_history, hf, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"❌ Сбой LLM: {e}")
        bot_text = "Произошла ошибка при генерации ответа."

    # ── ШАГ 3: Синтез речи (TTS) ──
    clean_text = re.sub(r'\*.*?\*', '', bot_text).strip()
    try:
        if TTS_ENGINE is not None:
            speaker_wav = (
                local_input_audio
                if os.path.exists(local_input_audio)
                   and os.path.getsize(local_input_audio) > 100
                else None
            )
            if speaker_wav:
                TTS_ENGINE.tts_to_file(
                    text=clean_text,
                    language="ru",
                    speaker_wav=speaker_wav,
                    file_path=output_audio_name,
                )
                print("✅ XTTS v2: голос клонирован!")
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

    # ── ШАГ 4: Отправка результата ──
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
            with open(output_audio_name, "rb") as f:
                files = {"image": (output_audio_name, f, "audio/wav")}
                requests.post(
                    upload_url,
                    data={"task_id": task_id, "user_login": user_login},
                    files=files,
                    timeout=30,
                )
            print(f"🏁 Результат отправлен на сервер!")
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
    else:
        print(f"🏁 [DEMO] Результат сохранён локально: {output_audio_name}")

    # Очистка
    for fp in [local_input_audio, output_audio_name]:
        if os.path.exists(fp):
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
    # В Colab / Kaggle argparse может не работать —
    # используем переменную USER_LOGIN из конфигурации выше.
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--login", type=str, default=USER_LOGIN)
        args = parser.parse_args()
        login = args.login
    except SystemExit:
        login = USER_LOGIN

    main_loop(login)