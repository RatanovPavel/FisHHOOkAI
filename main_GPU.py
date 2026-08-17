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

# НАСТРОЙКА АДРЕСА ВАШЕГО СЕРВЕРА
SERVER_URL = "https://skulla.ru"  # Замените на ваш актуальный домен или тестовый IP

def fetch_task_from_server(worker_token: str):
    """Шлет GET запрос на сервер skulla.ru для получения новой задачи"""
    endpoint = f"{SERVER_URL}/api/worker/get_task"
    headers = {"Authorization": f"Bearer {worker_token}"}
    
    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
        elif response.status_code == 403:
            print(f" [ОШИБКА]: Токен воркера {worker_token} не валиден или истек тариф!")
            time.sleep(10)
    except Exception as e:
        print(f" [СВЯЗЬ]: Сервер skulla.ru временно недоступен: {e}")
    return None

def submit_result_to_server(worker_token: str, task_id: str, user_login: str, file_path: str):
    """Шлет готовый файл обратно на сервер через POST FormData"""
    endpoint = f"{SERVER_URL}/api/worker/submit_result"
    headers = {"Authorization": f"Bearer {worker_token}"}
    
    if not os.path.exists(file_path):
        print(f" [ОШИБКА]: Файл результата {file_path} не найден на диске!")
        return False
        
    try:
        with open(file_path, "rb") as f:
            files = {"image": (f"result_{task_id}.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": user_login}
            
            response = requests.post(endpoint, headers=headers, data=data, files=files, timeout=30)
            if response.status_code == 200 and response.json().get("status") == "received":
                print(f" [УСПЕХ]: Готовая карточка для {user_login} отправлена на skulla.ru!")
                return True
    except Exception as e:
        print(f" [ОШИБКА]: Не удалось отправить результат на сервер: {e}")
    return False


def process_try_on_task(task_data: dict, worker_token: str):
    """Основной движок инпаинтинга одежды на реальном фото пользователя"""
    task_id = task_data["task_id"]
    user_login = task_data["user_login"]
    image_url = task_data["image_url"]
    prompt_style = task_data["prompt_style"]
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    print(f"\n🚀 [ИИ]: Начинаю обработку задачи {task_id} для селлера {user_login}...")
    
    # 1. Скачиваем исходную фотографию товара/человека по ссылке от skulla.ru
    print(" [СЕТЬ]: Скачиваю исходное фото товара...")
    try:
        source_image = Image.open(requests.get(image_url, stream=True).raw).convert("RGB")
        source_image = source_image.resize((1024, 1024)) # Приводим к стандарту SDXL
    except Exception as e:
        print(f" [ОШИБКА]: Не удалось скачать картинку по ссылке {image_url}: {e}")
        return

    # 2. Вырезаем фон и делаем маску
    print(" [ИИ Шаг 1]: Запуск rembg и создание маски очертаний...")
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]
    alpha_np = np.array(alpha)
    
    inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    
    # Делаем сочную темно-фиолетовую подложку-зацепку для взрывного неона
    gradient_bg = Image.new("RGB", (1024, 1024), (40, 10, 70))
    forced_source_image = Image.composite(source_image, gradient_bg, alpha)

    # Чистим память от тяжелого rembg
    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask, gradient_bg
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # 3. Инпаинтинг нового фона вокруг товара
    print(" [ИИ Шаг 2]: Инициализация SDXL Inpaint и рендер фона...")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    negative_prompt = "plain black background, solid black, boring background, simple backdrop, grey wall"
    
    final_image = inpaint_pipe(
        prompt=prompt_style,
        negative_prompt=negative_prompt,
        image=forced_source_image,  
        mask_image=mask_image,
        strength=0.99,             
        guidance_scale=9.5,        
        num_inference_steps=30
    ).images
    
    final_filename = f"fresult_fitting_{task_id}.png"
    final_image.save(final_filename)
    
    # Удаляем инпаинт из памяти, подготавливая GPU к следующему циклу опроса
    del inpaint_pipe
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()
    
    # 4. Отправляем готовую работу обратно на skulla.ru
    submit_result_to_server(worker_token, task_id, user_login, final_filename)
    
    # Подчищаем локальные файлы
    if os.path.exists(final_filename): os.remove(final_filename)

def main_loop(worker_token: str):
    """Бесконечный цикл опроса сервера (Polling)"""
    print(f"\n=== [FishHookAI ВОРКЕР] ЗАПУЩЕН И ОЖИДАЕТ ЗАДАЧ С СЕРВЕРА ===")
    print(f"🔑 Используемый токен лицензии: {worker_token}")
    
    while True:
        # Стучимся на skulla.ru
        task_data = fetch_task_from_server(worker_token)
        
        if task_data:
            # Если ваш сервер отдал задачу — запускаем конвейер
            process_try_on_task(task_data, worker_token)
        else:
            # Если задач нет — спим 5 секунд и проверяем снова
            print(".", end="", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    # Если скрипт запускается через терминал
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.token)
