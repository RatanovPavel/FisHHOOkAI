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

# ЦВЕТНАЯ КОНСОЛЬ ДЛЯ УДОБСТВА ОТЛАДКИ (ANSI ESCAPE CODES)
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

def fetch_task_from_server(user_login: str):
    """Шлет GET-запрос на FastAPI роут для проверки очереди задач"""
    # Принудительно приводим логин к нижнему регистру, как на бэкенде
    clean_login = user_login.lower().strip()
    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{clean_login}"
    
    try:
        Log.debug(f"Опрос очереди: GET {endpoint}")
        response = requests.get(endpoint, timeout=5)
        
        Log.debug(f"Ответ сервера статуса: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            Log.debug(f"Тело ответа от сервера: {data}")
            if data.get("status") == "success":
                return data
        elif response.status_code == 404:
            Log.warn(f"Роут не найден (404). Проверь префиксы в FastAPI!")
    except Exception as e:
        Log.error(f"Сбой сети при опросе очереди задач: {e}")
    return None

def submit_result_to_server(task_id: str, user_login: str, file_path: str):
    """Шлет готовый файл обратно на сервер через POST FormData"""
    endpoint = f"{SERVER_URL}/api/studio/fishhook/submit_result"
    clean_login = user_login.lower().strip()
    
    if not os.path.exists(file_path):
        Log.error(f"Файл результата {file_path} физически отсутствует на диске Колаба!")
        return False
        
    Log.info(f"Старт отправки файла {file_path} на сервер...")
    try:
        with open(file_path, "rb") as f:
            # Важно: имя поля 'image' должно строго совпадать с аргументом image: UploadFile в FastAPI
            files = {"image": ("after.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": clean_login}
            
            Log.debug(f"POST Запрос на {endpoint} | Data: {data}")
            response = requests.post(endpoint, data=data, files=files, timeout=60)
            
            Log.debug(f"Код ответа при отправке файла: {response.status_code}")
            Log.debug(f"Тело ответа при отправке файла: {response.text}")
            
            if response.status_code == 200 and response.json().get("status") == "received":
                Log.success("Файл успешно принят сервером skulla.ru и сохранен в сессию!")
                return True
            else:
                Log.error(f"Сервер вернул некорректный статус: {response.status_code} -> {response.text}")
    except Exception as e:
        Log.error(f"Критический сбой при отправке файла на бэкенд: {e}")
    return False

def process_try_on_task(task_data: dict):
    """Основной конвейер ИИ-обработки с глубоким логированием памяти и шагов"""
    task_id = task_data["task_id"]
    session_id = task_data["session_id"]
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    print("\n" + "="*60)
    Log.success(f"ПОЙМАНА ЖИВАЯ ЗАДАЧА: {task_id}")
    Log.info(f"Сессия сайта: {session_id} | Пользователь: {user_login}")
    Log.info(f"Текст генерации: '{prompt_style}'")
    Log.info(f"Режим вычислений: {device.upper()} ({dtype})")
    print("="*60)
    
    # ИНДИКАТОР ПАМЯТИ GPU ДО СТАРТА
    if device == "cuda":
        Log.debug(f"Память GPU до рендера: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
    
    # 1. СКАЧИВАНИЕ ИСХОДНИКА ORIGINAL.PNG ИЗ СЕССИИ
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    Log.info(f"Запрос на скачивание исходника: GET {download_url}")
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        Log.debug(f"Ответ сервера при скачивании original.png: {res.status_code}")
        if res.status_code != 200:
            Log.error(f"Не удалось скачать original.png. Сервер ответил: {res.text}")
            return
            
        source_image = Image.open(res.raw).convert("RGB")
        Log.success(f"Файл original.png успешно скачан. Разрешение: {source_image.size}")
        source_image = source_image.resize((1024, 1024))
        Log.debug("Изображение приведено к стандарту SDXL (1024x1024)")
    except Exception as e:
        Log.error(f"Критическая ошибка при скачивании исходника по сети: {e}")
        return

    # 2. МАСКИРОВАНИЕ ЧЕРЕЗ REMBG
    Log.info("Запуск ИИ-модуля №1: Вырезание фона (rembg)...")
    try:
        start_rembg = time.time()
        output_rembg = rembg.remove(source_image)
        alpha = output_rembg.split()[-1]
        alpha_np = np.array(alpha)
        
        inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
        raw_mask = Image.fromarray(inverted_mask_np).convert("L")
        mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
        
        gradient_bg = Image.new("RGB", (1024, 1024), (40, 10, 70))
        forced_source_image = Image.composite(source_image, gradient_bg, alpha)
        Log.success(f"Маска силуэта успешно создана за {time.time() - start_rembg:.2f} сек.")
    except Exception as e:
        Log.error(f"Сбой на этапе создания маски (rembg): {e}")
        return

    # Чистим ОЗУ перед тяжелым диффузором
    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask, gradient_bg
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # 3. ИНПАИНТИНГ ФОНА НА GPU
    Log.info("Запуск ИИ-модуля №2: Загрузка весов SDXL Inpaint в память...")
    try:
        start_sdxl = time.time()
        inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
        inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
            inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
        )
        if device == "cuda":
            inpaint_pipe.enable_model_cpu_offload()
            Log.debug(f"Память GPU после загрузки модели: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
        inpaint_pipe.safety_checker = None
        
        Log.info("Старт генерации пикселей нового фона (Ткачество нейросети)...")
        negative_prompt = "plain black background, solid black, boring background, simple backdrop, grey wall"
        
        final_image = inpaint_pipe(
            prompt=prompt_style, negative_prompt=negative_prompt, image=forced_source_image,  
            mask_image=mask_image, strength=0.99, guidance_scale=9.5, num_inference_steps=30
        ).images
        
        final_filename = f"fresult_fitting_{task_id}.png"
        final_image.save(final_filename)
        Log.success(f"Рендер фона успешно завершен за {time.time() - start_sdxl:.2f} сек! Файл сохранен локально.")
    except Exception as e:
        Log.error(f"Сбой во время инпаинтинга Stable Diffusion: {e}")
        return
    finally:
        # Тотальное уничтожение пайплайна для предотвращения CUDA Out Of Memory
        if 'inpaint_pipe' in locals(): del inpaint_pipe
        gc.collect()
        if device == "cuda": torch.cuda.empty_cache()

    # 4. ОТПРАВКА НА СЕРВЕР В ПАПКУ СЕССИИ
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        
    if submit_success:
        Log.success(f"Цикл обработки задачи {task_id} полностью закрыт со статусом УСПЕХ!\n")
    else:
        Log.warn(f"Задача {task_id} отрендерена, но сервер отказался принимать файл результат.\n")

def main_loop(user_login: str):
    clean_login = user_login.lower().strip()
    print("\n" + "="*60)
    Log.success("ОТЛАДОЧНЫЙ ВОРКЕР FISHHOOK GPU УСПЕШНО ЗАПУЩЕН")
    Log.info(f"Сканирую очередь для аккаунта сайта: '{clean_login}'")
    Log.info(f"Целевой сервер коммутации: {SERVER_URL}")
    print("="*60)
    
    while True:
        task_data = fetch_task_from_server(clean_login)
        if task_data:
            process_try_on_task(task_data)
        else:
            # Выводим точку-индикатор в консоль, чтобы видеть, что цикл живой и тикает
            print(".", end="", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.login)
