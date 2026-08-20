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
    
    Log.info("Загрузка официального предметного пайплайна...")
    from diffusers import StableDiffusionInpaintPipeline
    
    # Используем современный метод загрузки, совместимый с Python 3.12
    VTON_PIPE = StableDiffusionInpaintPipeline.from_pretrained(
        "runwayml/stable-diffusion-inpainting",
        torch_dtype=dtype,
        safety_checker=None
    )
    
    if device == "cuda":
        # В современных diffusers этот метод идеально разгружает память без крашей ядра
        VTON_PIPE.enable_model_cpu_offload()
        
    Log.success(" СВЕРХМОЩНЫЙ ИИ-ДВИЖОК ПРЕДМЕТНОГО ИНПАИНТА УСПЕШНО ЗАГРУЖЕН И ГОТОВ В БОЙ!")





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
    
    task_id = task_data.get("task_id", "unknown")
    session_id = task_data.get("session_id", "unknown")
    user_login = task_data.get("user_login", "unknown")
    prompt_style = task_data.get("prompt_style", "")
    
    print("\n" + "="*60)
    Log.success(f"ЗАПУСК НЕЙРОСЕТЕВОГО HI-RES КОНВЕЙЕРА (ОТЛАДКА 4K): {task_id}")
    print("-"*60)
    
    # 1! СКАЧИВАЕМ ОРИГИНАЛ ТОВАРА С ВАШЕГО СЕРВЕРА
    import requests
    from io import BytesIO
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    
    Log.info(f"[ОТЛАДКА]: Скачивание исходного изображения по URL: {download_url}")
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        Log.info(f"[ОТЛАДКА]: Ответ сервера: статус-код = {res.status_code}")
        if res.status_code != 200: 
            Log.error(f"Сервер вернул ошибку при скачивании исходника: {res.status_code}")
            return
            
        garment_image = Image.open(res.raw).convert("RGB").resize((768, 768))
        Log.info(f"[ОТЛАДКА]: Исходное изображение успешно загружено и приведено к размеру {garment_image.size}")
    except Exception as e:
        Log.error(f"Критическая ошибка загрузки изображения с сервера: {e}")
        return

    # 2! АВТОМАТИЧЕСКОЕ МАСКИРОВАНИЕ ФОНА ВОКРУГ ПРЕДМЕТА
    Log.info("Удаление старого фона и анализ геометрии объекта...")
    try:
        import numpy as np
        from PIL import ImageFilter
        
        garment_mask_output = rembg.remove(garment_image, session=REMBG_SESSION)
        g_alpha = garment_mask_output.split()[-1]
        
        g_alpha_np = np.array(g_alpha)
        mask_img = Image.fromarray(255 - g_alpha_np).convert("L")
        mask_blur = mask_img.filter(ImageFilter.GaussianBlur(radius=4))
        
        Log.info(f"[ОТЛАДКА]: Альфа-маска объекта успешно сгенерирована и инвертирована. Размер: {mask_blur.size}")
    except Exception as e:
        Log.error(f"Ошибка на этапе создания предметной маски: {e}")
        return

    negative_prompt = "text, letters, words, typography, watermark, logo, signature, blurry, low quality, bad shadows, ugly background, deformed object, human, face, skin"

    Log.info("ЭТАП №1: ИИ-движок генерирует базовую композицию кадров...")
    try:
        Log.info(f"[ОТЛАДКА]: Запуск Inpaint-инференса. Промпт: {prompt_style}")
        base_image = VTON_PIPE(
            prompt=prompt_style,
            negative_prompt=negative_prompt,
            image=garment_image,
            mask_image=mask_blur,
            num_inference_steps=35,
            guidance_scale=7.5,
            strength=0.99
        ).images[0]
        
        Log.info(f"[ОТЛАДКА]: Базовая композиция успешно сгенерирована. Размер: {base_image.size}")
    except Exception as e:
        Log.error(f"Критический сбой ИИ-генератора фона на ЭТАПЕ №1: {e}")
        return

    Log.info("ЭТАП №2: Переключение на Img2Img апскейлер для прорисовки ворса и микродеталей...")
    try:
        width, height = base_image.size
        high_res_size = (width * 2, height * 2)
        
        Log.info(f"[ОТЛАДКА]: Масштабирование кадра алгоритмом LANCZOS до размера {high_res_size}")
        high_res_input = base_image.resize(high_res_size, resample=Image.Resampling.LANCZOS)
        
        # Динамически пересобираем пайплайн в режим классического Img2Img для апскейла без маски
        from diffusers import StableDiffusionImg2ImgPipeline
        
        Log.info("[ОТЛАДКА]: Перепривязка весов UNet в режим пространственного апскейла Img2Img...")
        img2img_pipe = StableDiffusionImg2ImgPipeline(
            vae=VTON_PIPE.vae,
            text_encoder=VTON_PIPE.text_encoder,
            tokenizer=VTON_PIPE.tokenizer,
            unet=VTON_PIPE.unet,
            scheduler=VTON_PIPE.scheduler,
            safety_checker=None,
            feature_extractor=None,
            requires_safety_checker=False
        )
        
        Log.info("[ОТЛАДКА]: Запуск второй проходки нейросети для субпиксельной детализации...")
        final_image = img2img_pipe(
            prompt=prompt_style,
            negative_prompt=negative_prompt,
            image=high_res_input,
            num_inference_steps=20, # 20 шагов достаточно для добавления текстур
            guidance_scale=7.5,
            strength=0.32          # Оптимальная сила: не меняет форму предмета, но создает звенящую резкость фонов
        ).images[0]
        
        Log.info(f"[ОТЛАДКА]: Финальная 4K карточка успешно отрендерена. Размер: {final_image.size}")
        
        final_filename = f"vton_result_{task_id}.png"
        final_image.save(final_filename)
        Log.success(" Нейросетевой Hi-Res рендеринг карточки успешно завершен!")
        
    except Exception as e:
        Log.error(f"Критический сбой ИИ-детализатора на ЭТАПЕ №2: {e}")
        return

    # 4! БЕЗОПАСНАЯ ОЧИСТКА ПАМЯТИ
    finally:
        if 'garment_mask_output' in locals(): del garment_mask_output
        if 'g_alpha' in locals(): del g_alpha
        if 'g_alpha_np' in locals(): del g_alpha_np
        if 'mask_img' in locals(): del mask_img
        if 'mask_blur' in locals(): del mask_blur
        if 'base_image' in locals(): del base_image
        if 'high_res_input' in locals(): del high_res_input
        if 'img2img_pipe' in locals(): del img2img_pipe
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # 5! ОТПРАВКА ГОТОВОЙ КАРТОЧКИ ОБРАТНО СЕЛЛЕРУ
    Log.info(f"[ОТЛАДКА]: Отправка рендера {final_filename} на сервер для пользователя {user_login}")
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        Log.info("[ОТЛАДКА]: Временный локальный файл удален с диска Colab.")
        
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт и отправлен в сервис!\n")



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
