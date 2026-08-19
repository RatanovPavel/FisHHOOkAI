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

def fetch_task_from_server(user_login: str):
    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{user_login}"
    try:
        response = requests.get(endpoint, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
    except Exception as e:
        print(f" [СВЯЗЬ]: Ожидаю коннекта со skulla.ru... ({e})")
    return None

def submit_result_to_server(task_id: str, user_login: str, file_path: str):
    endpoint = f"{SERVER_URL}/api/studio/fishhook/submit_result"
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "rb") as f:
            files = {"image": (f"result_{task_id}.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": user_login}
            response = requests.post(endpoint, data=data, files=files, timeout=40)
            if response.status_code == 200 and response.json().get("status") == "received":
                print(f" [УСПЕХ]: Готовый рендер успешно передан в папку сессии на сервере!")
                return True
    except Exception as e:
        print(f" [СВЯЗЬ]: Ошибка отправки файла на бэкенд: {e}")
    return False

def process_try_on_task(task_data: dict):
    task_id = task_data["task_id"]
    session_id = task_data["session_id"] # Вытаскиваем ID сессии
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    print(f"\n🚀 [ИИ-ВОРКЕР]: Поймал задачу {task_id} для сессии {session_id}!")
    
    # 1. Скачиваем ИСХОДНИК before.png прямо из его папки сессии на сервере
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    print(f" [СЕТЬ]: Скачиваю исходное фото 'before.png' из папки сессии...")
    try:
        source_image = Image.open(requests.get(download_url, stream=True).raw).convert("RGB")
        source_image = source_image.resize((1024, 1024))
    except Exception as e:
        print(f" [ОШИБКА]: Не удалось скачать before.png для сессии {session_id}: {e}")
        return

    # 2. Вырезаем фон по контуру
    print(" [ИИ Этап 1]: Анализ физических контуров товара...")
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]
    alpha_np = np.array(alpha)
    
    inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    
    # Наша сочная неоновая фиолетово-синяя зацепка для фона
    gradient_bg = Image.new("RGB", (1024, 1024), (40, 10, 70))
    forced_source_image = Image.composite(source_image, gradient_bg, alpha)

    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask, gradient_bg
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # 3. Инпаинтинг нового фотореалистичного окружения вокруг товара
    print(" [ИИ Этап 2]: Запуск Stable Diffusion XL Inpaint на видеокарте...")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    negative_prompt = "plain black background, solid black, boring background, simple backdrop, grey wall"
    
    final_image = inpaint_pipe(
        prompt=prompt_style, negative_prompt=negative_prompt, image=forced_source_image,  
        mask_image=mask_image, strength=0.99, guidance_scale=9.5, num_inference_steps=30
    ).images
    
    final_filename = f"fresult_fitting_{task_id}.png"
    final_image.save(final_filename)
    
    del inpaint_pipe
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()
    
    # 4. Отправляем результат обратно (бэкенд сам положит его под именем 'after.png' в сессию)
    print(" [СЕТЬ]: Отправляю готовый результат обратно на сервер...")
    submit_result_to_server(task_id, user_login, final_filename)
    
    if os.path.exists(final_filename): 
        os.remove(final_filename)
    print(" [УСПЕХ]: Задача полностью сдана. Возвращаюсь к пингам очереди.")

def main_loop(user_login: str):
    print(f"\n=== [БОЕВОЙ ВОРКЕР FISHHOOK GPU] ПОДКЛЮЧЕН К СЕРВЕРУ SKULLA.RU ===")
    print(f"👤 Активный аккаунт селлера: {user_login}")
    
    while True:
        task_data = fetch_task_from_server(user_login)
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
