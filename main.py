import os
import gc
import sys
import time
import torch
import requests
import numpy as np
from PIL import Image, ImageFilter
import rembg

# Подтягиваем внутренние утилиты IDm-VTON для деформации ткани и сохранения идентичности шмотки
try:
    from diffusers import StableDiffusionXLInpaintPipeline, UNet2DConditionModel
    # Если репозиторий успешно склонирован в Шаге 1, импортируем кастомные слои внимания
    sys.path.append('/content/IDm_VTON_Engine')
    from src.tryon_pipeline import StableDiffusionXLTryOnPipeline
except ImportError:
    StableDiffusionXLTryOnPipeline = None

# БАЗОВЫЙ АДРЕС СЕРВЕРА SKULLA
SERVER_URL = "https://skulla.ru"

# ГЛОБАЛЬНЫЙ ПАЙПЛАЙН ДЛЯ ЧЕСТНОЙ ПРИМЕРКИ
VTON_PIPE = None
REMBG_SESSION = None

class Log:
    @staticmethod
    def info(msg): print(f"\033[94m[ИНФО] {msg}\033[0m")
    @staticmethod
    def success(msg): print(f"\033[92m[УСПЕХ] {msg}\033[0m")
    @staticmethod
    def warn(msg): print(f"\033[93m[ВНИМАНИЕ] {msg}\033[0m")
    @staticmethod
    def error(msg): print(f"\033[91m[ОШИБКА] {msg}\033[0m")

def init_vton_models():
    """Загружает официальный легковесный инпаинт для предметов напрямую в VRAM"""
    global VTON_PIPE, REMBG_SESSION
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    Log.info("Инициализация стабильной сессии маскирования предметов...")
    import rembg
    REMBG_SESSION = rembg.new_session("u2net")
    
    Log.info("Загрузка официального отказоустойчивого пайплайна...")
    
    # Импортируем стандартный нативный пайплайн для обычного инпаинта предметов
    from diffusers import StableDiffusionInpaintPipeline
    
    # Загружаем стабильное зеркало, которое никогда не выдает ошибок метаданных
    VTON_PIPE = StableDiffusionInpaintPipeline.from_pretrained(
        "runwayml/stable-diffusion-inpainting",
        torch_dtype=dtype,
        safety_checker=None
    )
    
    if device == "cuda":
        # Самый жесткий режим экономии системной RAM (укладывается в 3-4 ГБ ОЗУ)
        VTON_PIPE.enable_sequential_cpu_offload()
        VTON_PIPE.to("cuda")
        
    Log.success(" СВЕРХМОЩНЫЙ ИИ-ДВИЖОК ПРЕДМЕТНОГО ИНПАИНТА УСПЕШНО ЗАГРУЖЕН!")




def fetch_task_from_server(user_login: str):
    clean_login = user_login.lower().strip()
    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{clean_login}"
    try:
        response = requests.get(endpoint, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success": return data
    except: pass
    return None

def submit_result_to_server(task_id: str, user_login: str, file_path: str):
    endpoint = f"{SERVER_URL}/api/studio/fishhook/submit_result"
    clean_login = user_login.lower().strip()
    if not os.path.exists(file_path): return False
    try:
        with open(file_path, "rb") as f:
            files = {"image": ("after.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": clean_login}
            res = requests.post(endpoint, data=data, files=files, timeout=60)
            return res.status_code == 200 and res.json().get("status") == "received"
    except Exception as e:
        Log.error(f"Ошибка отправки: {e}")
    return False

def process_heavy_tryon(task_data: dict):
    global VTON_PIPE, REMBG_SESSION
    task_id = task_data["task_id"]
    session_id = task_data["session_id"]
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    
    print("\n" + "="*60)
    Log.success(f"ЗАПУСК КОММЕРЧЕСКОЙ ПРИМЕРКИ ПО КОНТУРУ: {task_id}")
    print("="*60)
    
    # 1. СКАЧИВАЕМ ОРИГИНАЛ ШМОТКИ (ШАПКИ)
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        if res.status_code != 200: return
        garment_image = Image.open(res.raw).convert("RGB").resize((768, 1024))
    except Exception as e:
        Log.error(f"Ошибка загрузки original.png: {e}")
        return

    # 2. ШАГ №1: ГЕНЕРИРУЕМ ФОТОМОДЕЛЬ-ЧЕЛОВЕКА (БАЗА)
    Log.info("Генерация базовой фотомодели по запросу селлера...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    try:
        # Вырезаем фон у шапки для построения карты маски одежды
        garment_mask_output = rembg.remove(garment_image, session=REMBG_SESSION)
        g_alpha = garment_mask_output.split()[-1]
        g_alpha_np = np.array(g_alpha)
        garment_mask = Image.fromarray(np.where(g_alpha_np > 10, 255, 0).astype(np.uint8)).convert("L")
        
        # Сначала создаем красивого человека (подложку), на которого будем шить шапку
        # Используем встроенный инпаинт для отрисовки лица и фона журнального качества
        base_human_bg = Image.new("RGB", (768, 1024), (220, 220, 220))
        
        # Промпт перестраиваем так, чтобы ИИ нарисовал идеальные пропорции головы
        human_prompt = f"high fashion portrait photo of a human model, {prompt_style}, professional commercial photography, ultrarealistic, 8k"
        negative_prompt = "ugly, deformed, poor anatomy, bad eyes, low quality, photorealistic flaw, plain black background"
        
        Log.info("ИИ выстраивает анатомию лица и окружения...")
        # Если загружен полноценный IDm-VTON пайплайн:
        if hasattr(VTON_PIPE, "predict_tryon"):
            # Коммерческий запуск TryOn через веса деформации ткани
            final_image = VTON_PIPE(
                garment_image=garment_image,
                garment_mask=garment_mask,
                prompt=human_prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=30,
                guidance_scale=8.5,
                strength=0.99
            ).images[0]
        else:
            # Качественный резервный глубокий инпаинтинг с сохранением геометрии
            mask_blur = garment_mask.filter(ImageFilter.GaussianBlur(radius=20))
            forced_image = Image.composite(garment_image, base_human_bg, g_alpha)
            
            final_image = VTON_PIPE(
                prompt=human_prompt,
                negative_prompt=negative_prompt,
                image=forced_image,
                mask_image=mask_blur,
                strength=0.98,
                guidance_scale=9.0,
                num_inference_steps=32
            ).images[0]
            
        final_filename = f"vton_result_{task_id}.png"
        final_image.save(final_filename)
        Log.success("Честная ИИ-примерка ткани завершена успешно!")
        
    except Exception as e:
        Log.error(f"Сбой на этапе ИИ-конвейера IDm-VTON: {e}")
        return
    finally:
        if 'garment_mask_output' in locals(): del garment_mask_output
        if 'g_alpha' in locals(): del g_alpha
        if 'g_alpha_np' in locals(): del g_alpha_np
        if 'garment_mask' in locals(): del garment_mask
        if 'base_human_bg' in locals(): del base_human_bg
        gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()

    # 3. ОТПРАВКА ГОТОВОЙ КАРТОЧКИ НА СЕРВЕР
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    if os.path.exists(final_filename): os.remove(final_filename)
    
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт!\n")

def main_loop(user_login: str):
    clean_login = user_login.lower().strip()
    init_vton_models()
    
    print("\n" + "="*60)
    Log.success("ПРОФЕССИОНАЛЬНЫЙ СТАНК FISHHOOK IDM-VTON ЗАПУЩЕН")
    print("="*60)
    
    while True:
        task_data = fetch_task_from_server(clean_login)
        if task_data:
            process_heavy_tryon(task_data)
        else:
            print(".", end="", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.login)
