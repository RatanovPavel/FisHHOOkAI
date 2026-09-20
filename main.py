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

def init_vton_models_good():
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


def init_vton_models():
    """Загружает тяжелую коммерческую модель SDXL Inpainting напрямую в VRAM"""
    global VTON_PIPE, REMBG_SESSION
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    Log.info("Инициализация стабильной сессии маскирования предметов...")
    import rembg
    REMBG_SESSION = rembg.new_session("u2net")
    
    Log.info("Инициализация тяжелого ИИ-движка SDXL Inpainting...")
    
    # Импортируем официальный пайплайн для моделей класса XL
    from diffusers import StableDiffusionXLInpaintPipeline
    
    # Загружаем официальное стабильное зеркало SDXL Inpaint от StabilityAI
    VTON_PIPE = StableDiffusionXLInpaintPipeline.from_pretrained(
        "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
        torch_dtype=dtype,
        safety_checker=None,
        variant="fp16" # Загружаем облегченные веса для жесткой экономии VRAM видеокарты
    )
    
    if device == "cuda":
        # Самый мощный режим разгрузки памяти: слои XL-модели не грузят системное ОЗУ 12ГБ
        VTON_PIPE.enable_sequential_cpu_offload()
        
    Log.success(" ТЯЖЕЛЫЙ КОММЕРЧЕСКИЙ SDXL-ДВИЖОК УСПЕШНО ЗАПУЩЕН НА FISHHOOK!")



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
    Log.success(f"ЗАПУСК ПРЕМЬЕРНОГО SDXL-КОНВЕЙЕРА (900x1200 FIX): {task_id}")
    print("-"*60)
    
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200
    
    # 1! СКАЧИВАЕМ ОРИГИНАЛ ТОВАРА С ВАШЕГО СЕРВЕРА
    import requests
    from io import BytesIO
    from PIL import ImageOps
    
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        if res.status_code != 200: return
        raw_image = Image.open(res.raw).convert("RGB")
    except Exception as e:
        Log.error(f"Ошибка загрузки исходного изображения с сервера: {e}")
        return

    # 2! УМНОЕ ЦЕНТРИРОВАНИЕ ТОВАРА НА СТРОГОМ ХОЛСТЕ 900x1200
    Log.info("Адаптация геометрии под эталонные пропорции маркетплейса...")
    garment_image = ImageOps.pad(raw_image, (TARGET_WIDTH, TARGET_HEIGHT), color=(255, 255, 255))

    # 3! АВТОМАТИЧЕСКОЕ МАСКИРОВАНИЕ ФОНА ВОКРУГ ПРЕДМЕТА
    Log.info("Прецизионное вырезание фона объекта...")
    try:
        import numpy as np
        from PIL import ImageFilter
        
        garment_mask_output = rembg.remove(garment_image, session=REMBG_SESSION)
        g_alpha = garment_mask_output.split()[-1]
        
        g_alpha_np = np.array(g_alpha)
        mask_img = Image.fromarray(255 - g_alpha_np).convert("L")
        
        # Минимальное сглаживание краев для бесшовной посадки теней под баночкой
        mask_blur = mask_img.filter(ImageFilter.GaussianBlur(radius=2))
    except Exception as e:
        Log.error(f"Ошибка на этапе создания предметной маски: {e}")
        return

    # Качественный негативный промпт для SDXL (модели XL очень послушно реагируют на исключения)
    negative_prompt = "text, letters, words, typography, watermark, logo, signature, blurry, low quality, bad shadows, ugly background, deformed object, extra lids, second cap, human, face, skin"

    Log.info("ИИ-движок SDXL приступает к высокохудожественному рендерингу окружения...")
    try:
        # Инференс на полную мощность SDXL. 40 шагов на XL дают звенящую резкость глянца и стекла
        final_image = VTON_PIPE(
            prompt=prompt_style,
            negative_prompt=negative_prompt,
            image=garment_image,
            mask_image=mask_blur,
            num_inference_steps=40,
            guidance_scale=8.0,
            strength=0.99
        ).images[0] # Забираем готовую картинку напрямую
        
        # Жестко фиксируем эталонный размер на выходе
        final_image = final_image.resize((TARGET_WIDTH, TARGET_HEIGHT), resample=Image.Resampling.LANCZOS)
        
        # Сохраняем результат под системным именем задачи
        final_filename = f"vton_result_{task_id}.png"
        final_image.save(final_filename)
        Log.success(f" Высокохудожественный SDXL-рендеринг карточки {final_image.size} завершен!")
        
    except Exception as e:
        Log.error(f"Критический сбой ИИ-генератора SDXL: {e}")
        return

    # 4! ОЧИСТКА ПАМЯТИ
    finally:
        if 'raw_image' in locals(): del raw_image
        if 'garment_mask_output' in locals(): del garment_mask_output
        if 'g_alpha' in locals(): del g_alpha
        if 'g_alpha_np' in locals(): del g_alpha_np
        if 'mask_img' in locals(): del mask_img
        if 'mask_blur' in locals(): del mask_blur
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # 5! ОТПРАВКА ГОТОВОЙ КАРТОЧКИ ОБРАТНО СЕЛЛЕРУ НА САЙТ
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт и отправлен на сервер!\n")


def process_heavy_tryon_ext(task_data: dict):
    global VTON_PIPE, REMBG_SESSION
    task_id = task_data["task_id"]
    session_id = task_data["session_id"]
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    
    print("\n" + "="*60)
    Log.success(f"ЗАПУСК СТРОГОГО ВЕРТИКАЛЬНОГО КОНВЕЙЕРА (ФИКСИРОВАННЫЙ РАЗМЕР 900x1200): {task_id}")
    print("-"*60)
    
    # Жесткие эталонные размеры для Wildberries / Ozon
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200
    
    # 1! СКАЧИВАЕМ ОРИГИНАЛ ТОВАРА С ВАШЕГО СЕРВЕРА
    import requests
    from io import BytesIO
    from PIL import ImageOps
    
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        if res.status_code != 200: return
        raw_image = Image.open(res.raw).convert("RGB")
    except Exception as e:
        Log.error(f"Ошибка загрузки исходного изображения с сервера: {e}")
        return

    # 2! УМНОЕ ЦЕНТРИРОВАНИЕ ТОВАРА НА СТРОГОМ ХОЛСТЕ 900x1200
    Log.info("Адаптация геометрии под эталонный формат маркетплейса 900x1200...")
    garment_image = ImageOps.pad(raw_image, (TARGET_WIDTH, TARGET_HEIGHT), color=(255, 255, 255))

    # 3! АВТОМАТИЧЕСКОЕ МАСКИРОВАНИЕ ФОНА ВОКРУГ ПРЕДМЕТА
    Log.info("Удаление старого фона...")
    try:
        import numpy as np
        from PIL import ImageFilter
        
        garment_mask_output = rembg.remove(garment_image, session=REMBG_SESSION)
        g_alpha = garment_mask_output.split()[-1]
        
        g_alpha_np = np.array(g_alpha)
        mask_img = Image.fromarray(255 - g_alpha_np).convert("L")
        
        # Минимальное размытие для идеальной контурной резкости товара
        mask_blur = mask_img.filter(ImageFilter.GaussianBlur(radius=1))
    except Exception as e:
        Log.error(f"Ошибка на этапе создания предметной маски: {e}")
        return

    negative_prompt = "text, letters, words, typography, watermark, logo, signature, blurry, low quality, bad shadows, ugly background, deformed object, human, face, skin"

    Log.info("ЭТАП №1: ИИ-движок генерирует вертикальную композицию окружения...")
    try:
        base_image = VTON_PIPE(
            prompt=prompt_style,
            negative_prompt=negative_prompt,
            image=garment_image,
            mask_image=mask_blur,
            num_inference_steps=35,
            guidance_scale=7.5,
            strength=0.99
        ).images[0]
        
        Log.info("ЭТАП №2: Нейросетевой Hi-Res Fix (Генерация микродеталей)...")
        
        # Промежуточный апскейл для прорисовки текстур
        high_res_size = (TARGET_WIDTH * 2, TARGET_HEIGHT * 2)
        high_res_input = base_image.resize(high_res_size, resample=Image.Resampling.LANCZOS)
        high_res_full_mask = Image.new("L", high_res_size, 255)
        
        temp_hd_image = VTON_PIPE(
            prompt=prompt_style,
            negative_prompt=negative_prompt,
            image=high_res_input,
            mask_image=high_res_full_mask,
            num_inference_steps=20,
            guidance_scale=7.5,
            strength=0.32          
        ).images[0]
        
        Log.info("ФИНАЛЬНЫЙ ШАГ: Принудительное кадрирование и фиксация размера под 900x1200...")
        # Сжимаем HD-картинку обратно до эталонных 900x1200 через высококачественный фильтр LANCZOS
        final_image = temp_hd_image.resize((TARGET_WIDTH, TARGET_HEIGHT), resample=Image.Resampling.LANCZOS)
        
        # Сохраняем результат
        final_filename = f"vton_result_{task_id}.png"
        final_image.save(final_filename)
        Log.success(f" Вертикальный рендеринг карточки {final_image.size} успешно завершен!")
        
    except Exception as e:
        Log.error(f"Критический сбой ИИ-генератора фона: {e}")
        return

    # 4! БЕЗОПАСНАЯ ОЧИСТКА ПАМЯТИ НА ЛЕТУ
    finally:
        if 'raw_image' in locals(): del raw_image
        if 'garment_mask_output' in locals(): del garment_mask_output
        if 'g_alpha' in locals(): del g_alpha
        if 'g_alpha_np' in locals(): del g_alpha_np
        if 'mask_img' in locals(): del mask_img
        if 'mask_blur' in locals(): del mask_blur
        if 'base_image' in locals(): del base_image
        if 'high_res_input' in locals(): del high_res_input
        if 'high_res_full_mask' in locals(): del high_res_full_mask
        if 'temp_hd_image' in locals(): del temp_hd_image
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # 5! ОТПРАВКА ГОТОВОЙ КАРТОЧКИ ОБРАТНО СЕЛЛЕРУ НА САЙТ
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт и отправлен в сервис!\n")
    
    if os.path.exists(final_filename): 
        os.remove(final_filename)
        Log.info("[ОТЛАДКА]: Временный локальный файл удален с диска Colab.")
        
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт и отправлен в сервис!\n")


import os
import gc
import requests
import numpy as np
import torch
from PIL import Image, ImageFilter, ImageOps

# Вспомогательная функция для генерации умной маски (Одежда + Фон, без Лица и Кожи)
def generate_vton_mask(garment_image: Image.Image, garment_mask_output) -> Image.Image:
    """
    Создает маску, где под замену (белый цвет) попадает ФОН и ОДЕЖДА человека,
    а лицо, волосы и открытая кожа остаются защищенными (черный цвет).
    """
    # 1. Базовая маска фона (инвертированный силуэт из rembg)
    g_alpha = garment_mask_output.split()[-1]
    g_alpha_np = np.array(g_alpha)
    
    # Фон изначально белый (255), человек — черный (0)
    bg_mask_np = 255 - g_alpha_np
    
    # 2. Сегментация человека для поиска одежды
    # Для идеального результата в продакшене здесь вызывается cloth-segmentation.
    # В качестве надежного и быстрого fallback-варианта мы маскируем центральную 
    # часть силуэта (торс и ноги), гарантированно защищая верхнюю часть (голову).
    
    w, h = garment_image.size
    clothing_mask = Image.new("L", (w, h), 0)
    clothing_draw = np.array(clothing_mask)
    
    # Заполняем область одежды внутри силуэта человека (исключая верхние ~15-20% под голову)
    head_height_limit = int(h * 0.22)
    # Все, что внутри силуэта человека и ниже уровня головы, помечаем как одежду под замену
    clothing_draw[head_height_limit:] = g_alpha_np[head_height_limit:]
    
    # Слываем маску фона и маску одежды вместе
    combined_mask_np = np.maximum(bg_mask_np, clothing_draw)
    
    # Защищаем края: размываем и возвращаем как PIL Image
    final_mask = Image.fromarray(combined_mask_np.astype(np.uint8), mode="L")
    return final_mask


def process_heavy_tryon_naked_777(task_data: dict):
    global VTON_PIPE, REMBG_SESSION
    print(f"🔍 [DEBUG]: Что прислал сервер: {task_data}")
    
    actual_task = task_data.get("task_data", {})
    
    # 🚀 Теперь берем все ключи ИЗ НЕГО:
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]
    prompt_style = actual_task["prompt_style"]
    
    print("\n" + "="*60)
    print(f" ЗАПУСК ПОСЛЕДОВАТЕЛЬНОГО SDXL INPAINT КОНВЕЙЕРА (ОДЕЖДА -> ФОН): {task_id}")
    print("="*60)
    
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200
    
    # #1 СКАЧИВАЕМ ОРИГИНАЛ ТОВАРА С СЕРВЕРА
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    try:
        res = requests.get(download_url, stream=True, timeout=15)
        if res.status_code != 200:
            return
        raw_image = Image.open(res.raw).convert("RGB")
    except Exception as e:
        Log.error(f"Ошибка загрузки исходного изображения с сервера: {e}")
        return

    # #2 УМНОЕ ЦЕНТРИРОВАНИЕ ТОВАРА СТРОГО 900х1200
    Log.info("Адаптация геометрии под эталонный формат маркетплейса 900х1200...")
    garment_image = ImageOps.pad(raw_image, (TARGET_WIDTH, TARGET_HEIGHT), color=(255, 255, 255))
    
    try:
        import rembg
        
        # Шаг А: Вырезаем силуэт человека (альфа-канал)
        garment_mask_output = rembg.remove(garment_image, session=REMBG_SESSION)
        g_alpha = garment_mask_output.split()[-1]
        g_alpha_np = np.array(g_alpha)
        
        # --- МАСКА №1: ТОЛЬКО ОДЕЖДА (Лицо, кисти рук и оригинальный фон полностью заблокированы) ---
        # 1. Создаем базовый холст: заливаем его БЕЛЫМ (255). В логике SDXL Inpaint белый — это полная защита.
        clothing_draw = np.full_like(g_alpha_np, 255)
        
        head_limit = int(TARGET_HEIGHT * 0.25)  # Защита головы и шеи
        hands_limit = int(TARGET_HEIGHT * 0.76)  # Защита ладоней и пальцев

        # 2. Вырезаем область торса (одежду) по контуру силуэта и делаем её ЧЕРНОЙ (0).
        # Для SDXL Inpaint черный цвет — это зона, которую нужно стереть и сгенерировать!
        # При этом лицо и руки остаются белыми (защищенными)
        clothing_draw[head_limit:hands_limit] = 255 - g_alpha_np[head_limit:hands_limit]

        # Перевод массива в PIL изображение с мягким размытием краев ткани
        clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=3))

        # --- МАСКА №2: ТОЛЬКО ФОН (Весь человек полностью заблокирован, меняется только окружение) ---
        # Здесь оставляем вашу верную логику: человек черный (0 - защита), фон белый (255 - замена)
        bg_mask_np = 255 - g_alpha_np
        bg_mask = Image.fromarray(bg_mask_np.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=4))

        
    except Exception as e:
        Log.error(f"Ошибка на этапе подготовки масок сегментации: {e}")
        return

    negative_prompt = (
        "text, letters, words, typography, watermark, logo, signature, blurry, low quality, "
        "bad shadows, ugly background, deformed object, deformed hands, extra fingers, mutated hands, "
        "three arms, extra limbs, deformed face, bad skin, ugly eyes, unrealistic anatomy"
    )
    
    try:
        # =====================================================================
        # ЭТАП №1: ИИ МЕНЯЕТ ТОЛЬКО ОДЕЖДУ (ЛИЦО И ФОН НЕ ТРОГАЮТСЯ)
        # =====================================================================
        Log.info("ЭТАП 1/2: SDXL перерисовывает одежду внутри изолированного силуэта...")
        # Точечный промпт на изменение ткани
        clothing_prompt = f"high quality commercial clothing texture, fashion look, {prompt_style}"
        
        person_with_new_cloth = VTON_PIPE(
            prompt=clothing_prompt,
            negative_prompt=negative_prompt,
            image=garment_image,
            mask_image=clothing_mask,
            num_inference_steps=30,
            guidance_scale=8.0,
            strength=0.80  # Достаточно для полной смены ткани, но сохраняет позу рук
        ).images[0]        # Корректно забираем первую PIL-картинку из SDXL пайплайна
        
        # =====================================================================
        # ЭТАП №2: ИИ ГЕНЕРИРУЕТ НОВЫЙ ФОН (ЛИЦО И НОВАЯ ОДЕЖДА НЕ ТРОГАЮТСЯ)
        # =====================================================================
        Log.info("ЭТАП 2/2: SDXL генерирует коммерческий интерьер вокруг готовой модели...")
        # Передаем картинку с новой одеждой из Этапа 1 и маску фона
        
        final_image = VTON_PIPE(
            prompt=prompt_style,  # Основной промпт (например, про пену и ванну)
            negative_prompt=negative_prompt,
            image=person_with_new_cloth,
            mask_image=bg_mask,
            num_inference_steps=35,
            guidance_scale=7.5,
            strength=0.99  # Фон затирается полностью с нуля
        ).images[0]        # Корректно забираем финальную PIL-картинку
        
        # Сохраняем результат
        final_filename = f"vton_result_{task_id}.png"
        final_image.save(final_filename)
        Log.success(f"Рендеринг карточки {final_image.size} успешно завершен за 2 чистых прохода!")
        
    except Exception as e:
        Log.error(f"Критический сбой ИИ-генерации: {e}")
        import traceback
        traceback.print_exc()
        return
        
    # #4 БЕЗОПАСНАЯ ОЧИСТКА ПАМЯТИ НА ЛЕТУ
    finally:
        if 'raw_image' in locals(): del raw_image
        if 'garment_mask_output' in locals(): del garment_mask_output
        if 'clothing_mask' in locals(): del clothing_mask
        if 'bg_mask' in locals(): del bg_mask
        if 'person_with_new_cloth' in locals(): del person_with_new_cloth
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
    # #5 ОТПРАВКА ГОТОВОЙ КАРТОЧКИ ОБРАТНО СЕЛЛЕРУ НА САЙТ
    submit_success = submit_result_to_server(task_id, user_login, final_filename)
    if os.path.exists(final_filename):
        os.remove(final_filename)
        
    if submit_success:
        Log.success(f"Боевой цикл задачи {task_id} полностью закрыт и отправлен в сервис!\n")
    else:
        Log.error(f"Не удалось отправить результат задачи {task_id} на сервер.")


import io
import os
import requests
import numpy as np
from PIL import Image, ImageFilter

def process_heavy_tryon_naked123456(task_data):
    """
    ОТЛАДОЧНАЯ ФУНКЦИЯ: Только строит и отправляет маску одежды на сервер.
    Помогает визуально проверить геометрию без запуска Stable Diffusion.
    """
    # 1. Распаковываем данные задачи, пришедшие от сервера
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]

    print(f"\n🔬 [ДЕБАГ МАСКИ]: Запуск режима визуализации для задачи {task_id}")
    
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200

    # 2. Скачиваем оригинал фото из папки сессии через твой рабочий эндпоинт
        # Добавили /api перед /studio, чтобы точно попасть в роут сервера Skulla
    #download_url = f"{SERVER_URL}/api/studio/fishhook/download_source_v2/{user_login}/{task_id}"
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    
    try:
        response = requests.get(download_url, stream=True, timeout=30)
        if response.status_code != 200:
            print(f"❌ Ошибка скачивания! Сервер вернул код: {response.status_code}")
            return
            
        raw_image = Image.open(io.BytesIO(response.content)).convert("RGB")
        print(f"🟢 Оригинал успешно скачан. Размер: {raw_image.size}")
        
    except Exception as e:
        print(f"❌ Сбой при получении файла: {e}")
        return

    # 3. Видеокарта запускает rembg для построения базового силуэта человека
    print("✂️ [GPU REMBG]: Вырезаем силуэт человека...")
    try:
        # 🔥 СТРОКА СЮДА: Объявляем глобальную переменную на СЕЙ ПЕРВОЙ строчке блока!
        global REMBG_SESSION
        
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        output_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = output_rembg.split()[-1]  # Альфа-канал
        g_alpha_np = np.array(g_alpha)
    except Exception as rem_err:
        print(f"❌ Ошибка rembg на GPU: {rem_err}")
        return


        # --- МАСКА: ТОЛЬКО БЛУЗКА (НАША ИСПРАВЛЕННАЯ РАБОЧАЯ ГЕОМЕТРИЯ) ---
        clothing_draw = np.zeros_like(g_alpha_np)
        
        # Считаем проценты от РЕАЛЬНОЙ высоты скачанной картинки
        actual_height = raw_image.height 
        head_limit = int(actual_height * 0.22)   
        hands_limit = int(actual_height * 0.48)  

        # Закрашиваем БЕЛЫМ строго торс (блузку)
        clothing_draw[head_limit:hands_limit] = g_alpha_np[head_limit:hands_limit]

        # Мягко размываем края маски для бесшовной склейки ткани
        clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=3))

        # --- ЧИСТЫЙ ИНФЕРЕНС: ЗАМЕНА ТКАНИ НА ВИДЕОКАРТЕ ---
        Log.info("⚡ [GPU SDXL]: Запуск рендеринга новой блузки...")
        clothing_prompt = f"{prompt_style}, high quality commercial clothing texture, fashion look"
        
        # Запускаем SDXL Inpaint строго по маске блузки
        final_image = VTON_PIPE(
            prompt=clothing_prompt,
            negative_prompt="deformed hands, extra fingers, mutated hands, three arms, extra limbs, bad skin, ugly eyes, unrealistic anatomy, face mutation, human, skin, background change, pants change",
            image=raw_image,
            mask_image=clothing_mask,
            num_inference_steps=35, # 35 шагов дадут отличную текстуру ткани
            guidance_scale=7.5,
            strength=0.80
        ).images[0] # Забираем готовую картинку из массива результатов

        # --- СОХРАНЕНИЕ КАРТОЧКИ ---
        final_image = final_image.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        output_filename = f"vton_result_{task_id}.png"
        final_image.save(output_filename)
        Log.success(f"💾 Карточка блузки сгенерирована за 1 проход на GPU и сохранена как {output_filename}")

        # Отправляем готовый результат обратно на сервер Skulla
        submit_success = submit_result_to_server(task_id, user_login, output_filename)
        
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        if submit_success:
            Log.success(f"🏁 Задача {task_id} полностью выполнена и отправлена на сайт!")

    except Exception as e:
        Log.error(f"Критический сбой конвейера генерации одежды: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Жестко вычищаем видеопамять от тяжелых объектов
        if 'raw_image' in locals(): del raw_image
        if 'clothing_mask' in locals(): del clothing_mask
        if 'final_image' in locals(): del final_image
        import gc
        gc.collect()
        torch.cuda.empty_cache()

import io
import os
import requests
import numpy as np
import torch
from PIL import Image, ImageFilter

def process_heavy_tryon_naked(task_data):
    """
    БОЕВАЯ ФУНКЦИЯ: Меняет строго синюю блузку за 1 проход на GPU.
    Лицо, руки, штаны и оригинальный фон улицы остаются нетронутыми.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]
    prompt_style = actual_task["prompt_style"]

    print(f"\n🚀 [ИИ-ВОРКЕР]: Запуск генерации одежды для задачи {task_id}")
    
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200

    # 1. Скачиваем оригинал фото из папки сессии
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}"
    
    try:
        response = requests.get(download_url, stream=True, timeout=30)
        if response.status_code != 200:
            print(f"❌ Ошибка скачивания! Сервер вернул код: {response.status_code}")
            return
            
        raw_image = Image.open(io.BytesIO(response.content)).convert("RGB")
        print(f"🟢 Оригинал успешно скачан. Размер: {raw_image.size}")
        
    except Exception as e:
        print(f"❌ Сбой при получении файла: {e}")
        return

    # 2. Видеокарта запускает rembg для построения силуэта человека
    try:
        global REMBG_SESSION
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        output_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = output_rembg.split()[-1]  
        g_alpha_np = np.array(g_alpha)
    except Exception as rem_err:
        print(f"❌ Ошибка rembg на GPU: {rem_err}")
        return

    # 3. МАТЕМАТИКА МАСКИ БЛУЗКИ (НАША ИСПРАВЛЕННАЯ РАБОЧАЯ ГЕОМЕТРИЯ)
    clothing_draw = np.zeros_like(g_alpha_np)
    
    # Считаем проценты строго от реальной высоты скачанной картинки (740px)
    actual_height = raw_image.height 
<<<<<<< HEAD
    head_limit = int(actual_height * 0.32)   # Четко под шею
=======
    head_limit = int(actual_height * 0.22)   # Четко под шею
>>>>>>> 0ad1155e6864f1578c5a126227cc115cb7d2ea9e
    hands_limit = int(actual_height * 0.98)  # Ровно по пояс брюк

    # Закрашиваем БЕЛЫМ (255) строго область блузки
    clothing_draw[head_limit:hands_limit] = g_alpha_np[head_limit:hands_limit]

    # Мягко размываем края маски для бесшовной склейки ткани
    clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=3))

    try:
        # 4. ЧИСТЫЙ ИНФЕРЕНС: ЗАМЕНА ТКАНИ НА ВИДЕОКАРТЕ
        print("⚡ [GPU SDXL]: Запуск рендеринга новой блузки...")
        #clothing_prompt = f"{prompt_style}, high quality commercial clothing texture, fashion look"
        clothing_prompt = "nude body, correct anatomy, high realism, photorealistic quality, correct proportions"
        # Запускаем SDXL Inpaint строго по маске блузки
        final_image = VTON_PIPE(
            prompt=clothing_prompt,
            negative_prompt="deformed hands, extra fingers, mutated hands, three arms, extra limbs, bad skin, ugly eyes, unrealistic anatomy, face mutation, background change",
            image=raw_image,
            mask_image=clothing_mask,
            num_inference_steps=35, # 35 шагов дадут отличную текстуру ткани
            guidance_scale=8.5,
            strength=0.98
        ).images[0] # Забираем готовую картинку из массива результатов

        # 5. СОХРАНЕНИЕ КАРТОЧКИ
        final_image = final_image.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        output_filename = f"vton_result_{task_id}.png"
        final_image.save(output_filename)
        print(f"💾 Карточка блузки успешно сгенерирована и сохранена локально")

        # 6. ОТПРАВКА НА СЕРВЕР SKULLA
        submit_success = submit_result_to_server(task_id, user_login, output_filename)
        
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        if submit_success:
            print(f"🏁 Задача {task_id} полностью выполнена и отправлена на сайт!")

    except Exception as e:
        print(f"❌ Критический сбой конвейера генерации одежды: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Жестко вычищаем видеопамять от тяжелых объектов
        if 'raw_image' in locals(): del raw_image
        if 'clothing_mask' in locals(): del clothing_mask
        if 'final_image' in locals(): del final_image
        import gc
        gc.collect()
        torch.cuda.empty_cache()

def main_loop(user_login: str):
    clean_login = user_login.lower().strip()
    init_vton_models()

    print("\n" + "="*60)
    Log.success("ПРОФЕССИОНАЛЬНЫЙ СТАНК FISHHOOK IDM-VTON ЗАПУЩЕН")
    print("="*60)

    while True:
        # 1. Запрашиваем задачу с сервера
        task_data = fetch_task_from_server(clean_login)
        
        # 2. Проверяем, что ответ пришел и сервер подтвердил статус "success"
        if task_data and task_data.get("status") == "success":
            Log.info(f"🚀 Найдена активная задача! Начинаем двухэтапную генерацию...")
            
            # Передаем весь объект, так как task_id лежит прямо внутри него
            process_heavy_tryon_naked(task_data) 
        else:
            # Если задач нет (статус "no_tasks"), плавно печатаем точки ожидания
            print(".", end="", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.login)
