import os
import gc
import sys
import time
import torch
import requests
import numpy as np
from PIL import Image, ImageFilter
import rembg
from diffusers import StableDiffusionXLInpaintPipeline

# БАЗОВЫЙ АДРЕС СЕРВЕРА SKULLA
SERVER_URL = "https://skulla.ru"

# ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ ДЛЯ ПАЙПЛАЙНА (Загружаем один раз)
INPAINT_PIPE = None

class Log:
    @staticmethod
    def info(msg): print(f"\033[94m[ИНФО] {msg}\033[0m")
    @staticmethod
    def success(msg): print(f"\033[92m[УСПЕХ] {msg}\033[0m")
    @staticmethod
    def warn(msg): print(f"\033[93m[ВНИМАНИЕ] {msg}\033[0m")
    @staticmethod
    def error(msg): print(f"\033[91m[ОШИБКА] {msg}\033[0m")
    @staticmethod
    def debug(msg): print(f"\033[90m[ОТЛАДКА] {msg}\033[0m")

def init_ai_models():
    """Инициализирует модель Stable Diffusion строго один раз при старте"""
    global INPAINT_PIPE
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    Log.info("Глобальная инициализация весов SDXL Inpaint в память Колаба...")
    try:
        inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
        INPAINT_PIPE = StableDiffusionXLInpaintPipeline.from_pretrained(
            inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
        )
        if device == "cuda":
            INPAINT_PIPE.enable_model_cpu_offload()
        INPAINT_PIPE.safety_checker = None
        Log.success("Модель Stable Diffusion XL успешно загружена и готова к работе!")
    except Exception as e:
        Log.error(f"Не удалось загрузить модель при старте воркера: {e}")
        sys.exit(1)

def fetch_task_from_server(user_login: str):
    clean_login = user_login.lower().strip()
    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{clean_login}"
    try:
        response = requests.get(endpoint, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
    except Exception as e:
        Log.error(f"Сбой сети при опросе очереди задач: {e}")
    return None

def submit_result_to_server(task_id: str, user_login: str, file_path: str):
    endpoint = f"{SERVER_URL}/api/studio/fishhook/submit_result"
    clean_login = user_login.lower().strip()
    
    if not os.path.exists(file_path):
        Log.error(f"Файл результата {file_path} отсутствует!")
        return False
        
    try:
        with open(file_path, "rb") as f:
            files = {"image": ("after.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": clean_login}
            response = requests.post(endpoint, data=data, files=files, timeout=60)
            if response.status_code == 200 and response.json().get("status") == "received":
                Log.success("Файл успешно передан в сессию на сервер!")
                return True
    except Exception as e:
        Log.error(f"Сбой при отправке файла на бэкенд: {e}")
    return False

def process_try_on_task(task_data: dict):
    global INPAINT_PIPE
    task_id = task_data["task_id"]
    session_id = task_data["session_id"]
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    
    print("\n" + "="*60)
    Log.success(f"РАБОТА НАД ЗАДАЧЕЙ: {task_id}")
    Log.info(f"Сессия: {session_id} | Текст: '{prompt_style}'")
    print("="*60)
    
    # 1. СКАЧИВАНИЕ ИСХОДНИКА
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        if res.status_code != 200:
            Log.error(f"Не удалось скачать original.png: {res.text}")
            return
        source_image = Image.open(res.raw).convert("RGB")
        source_image = source_image.resize((1024, 1024))
    except Exception as e:
        Log.error(f"Ошибка сети при скачивании исходника: {e}")
        return

    # 2. МАСКИРОВАНИЕ ЧЕРЕЗ REMBG
    Log.info("Вырезание фона (rembg)...")
    try:
        output_rembg = rembg.remove(source_image)
        alpha = output_rembg.split()[-1]
        alpha_np = np.array(alpha)
        
        inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
        raw_mask = Image.fromarray(inverted_mask_np).convert("L")
        mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
        
        gradient_bg = Image.new("RGB", (1024, 1024), (40, 10, 70))
        forced_source_image = Image.composite(source_image, gradient_bg, alpha)
    except Exception as e:
        Log.error(f"Сбой на этапе rembg: {e}")
        return
    finally:
        # Моментально чистим промежуточные тяжелые массивы из RAM
        if 'output_rembg' in locals(): del output_rembg
        if 'alpha' in locals(): del alpha
        if 'alpha_np' in locals(): del alpha_np
        if 'inverted_mask_np' in locals(): del inverted_mask_np
        if 'raw_mask' in locals(): del raw_mask
        if 'gradient_bg' in locals(): del gradient_bg
        gc.collect()

    # 3. ИНПАИНТИНГ ФОНА НА ГЛОБАЛЬНОЙ МОДЕЛИ
    Log.info("Запуск генерации пикселей на глобальном пайплайне...")
    try:
        negative_prompt = "plain black background, solid black, boring background, simple backdrop, grey wall"
        
        # Используем синглтон-пайплайн INPAINT_PIPE
        final_image = INPAINT_PIPE(
            prompt=prompt_style, negative_prompt=negative_prompt, image=forced_source_image,  
            mask_image=mask_image, strength=0.99, guidance_scale=9.5, num_inference_steps=30
        ).images[0] # <--- ВЫТАЩИЛИ КАРТИНКУ ИЗ МАССИВА КОРРЕКТНО!
        
        final_filename = f"fresult_fitting_{task_id}.png"
        final_image.save(final_filename)
    except Exception as e:
        Log.error(f"Сбой во время инпаинтинга Stable Diffusion: {e}")
        return
    finally:
        # Очистка локальных переменных генерации
        if 'source_image' in locals(): del source_image
        if 'forced_source_image' in locals(): del forced_source_image
        if 'mask_image' in locals(): del mask_image
        if 'final_image' in locals(): del final_image
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()

    # 4. ОТПРАВКА НА СЕРВЕР В ПАПКУ СЕССИИ
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        
    if submit_success:
        Log.success(f"Задача {task_id} полностью закрыта!\n")
    else:
        Log.warn(f"Сервер отклонил файл для задачи {task_id}\n")

def main_loop(user_login: str):
    clean_login = user_login.lower().strip()
    
    # Сначала один раз загружаем ИИ-модели в память
    init_ai_models()
    
    print("\n" + "="*60)
    Log.success("ВОРКЕР FISHHOOK GPU ГОТОВ К БЕЗЛИМИТНОЙ РАБОТЕ")
    Log.info(f"Опрашиваю очередь для: '{clean_login}'")
    print("="*60)
    
    while True:
        task_data = fetch_task_from_server(clean_login)
        if task_data:
            process_try_on_task(task_data)
        else:
            print(".", end="", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.login)
