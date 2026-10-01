import sys
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

if os.path.exists("/content/CatVTON_repo") and "/content/CatVTON_repo" not in sys.path:
    sys.path.append("/content/CatVTON_repo")
    print("🎯 [SYSTEM PATH]: Пути репозитория CatVTON успешно подключены на Старте!")

# Далее идут остальные импорты и блоки try-except для IDm_VTON


import gc
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


def init_vton_models_stablediffusion():
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

# Дальше идут твои стандартные импорты без изменений:
import torch
#from huggingface_hub import snapshot_download
# Импортируем родной пайплайн CatVTON (убедись, что папка model скачана в проект)
#from model.pipeline import CatVTONPipeline
#from utils import init_weight_dtype
def init_vton_models():
    import sys
    import os
    if os.path.exists("/content/CatVTON_repo") and "/content/CatVTON_repo" not in sys.path:
        sys.path.append("/content/CatVTON_repo")
        print("🎯 [INIT GPU]: Пути CatVTON_repo успешно подключены внутри функции!")

    print("⏳ [ИНИЦИАЛИЗАЦИЯ GPU]: Загрузка специализированного пайплайна CatVTON...")
    
    # Твои рабочие локальные импорты теперь выполнятся идеально!
    from model.pipeline import CatVTONPipeline
    from utils import init_weight_dtype
    from diffusers import StableVideoDiffusionPipeline
    
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    global VTON_V3_PIPE, VIDEO_PIPE
    # Загружаем базовый инпаинт чекпоинт и накатываем веса внимания CatVTON
    VTON_V3_PIPE = CatVTONPipeline(
        base_ckpt="booksforcharlie/stable-diffusion-inpainting",
        attn_ckpt="zhengchong/CatVTON",
        attn_ckpt_version="mix",
        weight_dtype=init_weight_dtype("fp16"),
        use_tf32=True,
        device=DEVICE,
        skip_safety_check=True
    )

    print("⏳ [ИНИЦИАЛИЗАЦИЯ GPU]: Загрузка видео-движка Stable Video Diffusion...")
    try:
        VIDEO_PIPE = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=torch.float16,
            variant="fp16"
        )
        
        # 🚀 ЖЕСТКИЙ ФИКС: Заменяем enable_model_cpu_offload на enable_sequential_cpu_offload
        VIDEO_PIPE.enable_sequential_cpu_offload() # Режет веса на микро-слои!
        
        VIDEO_PIPE.unet.enable_forward_chunking()
        VIDEO_PIPE.vae.enable_slicing()
        print("🚀 [УСПЕХ]: Видео-движок SVD полностью готов и оптимизирован под T4!")
    except Exception as e:
        print(f"❌ Сбой при сборке видео-пайплайна: {e}")


    print("🚀 [УСПЕХ]: Станция примерки CatVTON полностью готова к работе на GPU!")

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

def process_heavy_tryon_naked_oneperson(task_data):
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
    
        
    # Считаем проценты от РЕАЛЬНОЙ высоты скачанной картинки (740px)
    actual_height = raw_image.height 
    head_limit = int(actual_height * 0.42)   # Четко под шею
    hands_limit = int(actual_height * 0.98)  # Ровно по пояс брюк

    # Закрашиваем БЕЛЫМ (255) строго область блузки
    clothing_draw[head_limit:hands_limit] = g_alpha_np[head_limit:hands_limit]


    # Мягко размываем края маски для бесшовной склейки ткани
    clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=3))

    try:
        # 4. ЧИСТЫЙ ИНФЕРЕНС: ЗАМЕНА ТКАНИ НА ВИДЕОКАРТЕ
        print("⚡ [GPU SDXL]: Запуск рендеринга новой блузки...")
        #clothing_prompt = f"{prompt_style}, high quality commercial clothing texture, fashion look"
        clothing_prompt = "nude young woman, accurate anatomy, high realism, photorealistic quality, correct proportions"
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


import io
import os
import requests
import numpy as np
from PIL import Image, ImageFilter

import io
import os
import requests
import numpy as np
from PIL import Image, ImageFilter

def process_heavy_tryon_naked_catvton(task_data):
    """
    БОЕВАЯ ФУНКЦИЯ V3 (CatVTON):
    Скачивает person.png и garment.png, строит маску 0.22-0.48
    и сажает реальную вещь на модель без изменения лица.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]

    print(f"\n🚀 [CatVTON CONVEYER]: Запуск физической примерки для задачи {task_id}")
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200

    # 1. СКАЧИВАНИЕ ФОТО МОДЕЛИ (person.png)
    download_person_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=person.png"
    try:
        print(f"📥 Скачивание фото модели: {download_person_url}")
        res_p = requests.get(download_person_url, stream=True, timeout=30)
        
        if res_p.status_code != 200:
            print(f"❌ Сервер не отдал фото модели. Код: {res_p.status_code}")
            return
            
        raw_image = Image.open(io.BytesIO(res_p.content)).convert("RGB")
        print(f"🟢 Фото модели загружено. Размер: {raw_image.size}")
    except Exception as e:
        print(f"❌ Сбой сети при скачивании модели: {e}")
        return

    # 2. СКАЧИВАНИЕ ФОТО КРАСНОЙ БЛУЗКИ (garment.png)
    download_garment_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=garment.png"
    try:
        print(f"📥 Скачивание фото одежды: {download_garment_url}")
        res_g = requests.get(download_garment_url, stream=True, timeout=30)
        
        if res_g.status_code != 200:
            print(f"❌ Критично: Файл garment.png не найден! Сбой режима V3.")
            return
            
        garment_image = Image.open(io.BytesIO(res_g.content)).convert("RGB")
        print("🟢 Фото красной блузки успешно загружено на видеокарту!")
    except Exception as e:
        print(f"❌ Сбой сети при скачивании одежды: {e}")
        return

    # 3. НАША ЭТАЛОННАЯ МАСКА ТОРСА (0.22 - 0.48)
    try:
        global REMBG_SESSION
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        output_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = output_rembg.split()[-1]  
        g_alpha_np = np.array(g_alpha)
    except Exception as rem_err:
        print(f"❌ Ошибка rembg: {rem_err}")
        return

    clothing_draw = np.zeros_like(g_alpha_np)
    actual_height = raw_image.height 
    head_limit = int(actual_height * 0.22)   # Четко под подбородок/шею
    hands_limit = int(actual_height * 0.48)  # По линию пояса брюк
    clothing_draw[head_limit:hands_limit] = g_alpha_np[head_limit:hands_limit]
    
    # Делаем маску бинарной, с небольшим размытием краев для бесшовной склейки рукавов
    clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L").filter(ImageFilter.GaussianBlur(radius=3))

    # ----------------------------------------------------
    # 4. ЗАПУСК КАТАЛИЗАТОРА CatVTON
    # ----------------------------------------------------
    try:
        if garment_image:
            print("⚡ [GPU CatVTON]: Сшиваем узоры красной блузки внутрь маски...")
            
            # 🚀 ЖЕСТКИЙ ФИКС: Импортируем torch прямо здесь, локально!
            import torch
            
            # Официальная нормализация размеров от авторов CatVTON
            from utils import resize_and_crop, resize_and_padding
            VTON_SIZE = (768, 1024)
            
            person_scaled = resize_and_crop(raw_image, VTON_SIZE)
            mask_scaled = resize_and_crop(clothing_mask, VTON_SIZE)
            garment_scaled = resize_and_padding(garment_image, VTON_SIZE)

            # Теперь эта строка выполнится идеально!
            generator = torch.Generator(device="cuda").manual_seed(42)
            
            result_output = VTON_V3_PIPE(
                image=person_scaled,
                condition_image=garment_scaled,
                mask=mask_scaled,
                num_inference_steps=40,
                generator=generator
            )
            
            # 🚀 НАДЁЖНЫЙ ФИКС ВЫТАСКИВАНИЯ КАРТИНКИ:
            # 1. Если это объект с атрибутом images, берем его содержимое
            if hasattr(result_output, "images"):
                raw_output = result_output.images
            else:
                raw_output = result_output

            # 2. Если на этом этапе у нас всё ещё список (массив) — берем из него нулевой элемент!
            if isinstance(raw_output, list):
                final_image = raw_output[0]
            else:
                final_image = raw_output


        # ----------------------------------------------------
        # 5. БЛОК СБОРА И НАЛОЖЕНИЯ ПОЛУПРОЗРАЧНОЙ МАСКИ (ДЛЯ ОТЛАДКИ)
        # ----------------------------------------------------
        # Приводим финальную ИИ-картинку к нашему целевому размеру
        final_image = final_image.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        
        try:
            print("🎨 [ОТЛАДКА МАСКИ]: Накладываем полупрозрачный красный слой на финальное фото...")
            
            # 1. Приводим оригинальную черно-белую маску к размеру финального кадра
            debug_mask = clothing_mask.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
            
            # 2. Создаем полностью КРАСНЫЙ холст такого же размера (RGB: 255, 0, 0)
            red_layer = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), color=(255, 0, 0))
            
            # 3. Делаем маску полупрозрачной: берем ее белые пиксели и задаем им прозрачность ~100 из 255 (около 40% видимости)
            alpha_mask = debug_mask.point(lambda p: 100 if p > 10 else 0)
            
            # 4. Склеиваем финальную картинку с красным холстом по прозрачной маске
            # Там, где маска была белой, появится красный полупрозрачный фильтр. Где черной — останется ИИ-картинка.
            overlay_image = Image.composite(red_layer, final_image, alpha_mask)
            
            # Сохраняем именно картинку с оверлеем, чтобы глазами увидеть зону изменений на сайте!
            output_filename = f"vton_result_{task_id}.png"
            overlay_image.save(output_filename)
            print("✅ Отладочный оверлей успешно сохранен на диск.")
            
        except Exception as overlay_err:
            print(f"⚠️ Ошибка создания отладочного оверлея: {overlay_err}. Сохраняем чистый результат.")
            output_filename = f"vton_result_{task_id}.png"
            final_image.save(output_filename)

        # 6. ОТПРАВКА НА СЕРВЕР SKULLA
        submit_success = submit_result_to_server(task_id, user_login, output_filename)
        
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        if submit_success:
            print(f"🏁 Задача {task_id} полностью выполнена и отправлена на сайт!")            

    except Exception as e:
        print(f"❌ Критический сбой конвейера примерки: {e}")
        
    finally:
        if 'raw_image' in locals(): del raw_image
        if 'clothing_mask' in locals(): del clothing_mask
        if 'garment_image' in locals(): del garment_image
        if 'final_image' in locals(): del final_image
        import gc
        gc.collect()
        import torch
        torch.cuda.empty_cache()


import io
import os
import requests
import numpy as np
import rembg
from PIL import Image, ImageFilter

def process_heavy_tryon_naked_mask(task_data):
    """
    ОТЛАДОЧНАЯ ФУНКЦИЯ V3: Только строит и отправляет маску на сервер Skulla.
    Помогает визуально проверить геометрию в новом окружении T4 без запуска ИИ.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]

    print(f"\n🔬 [ДЕБАГ МАСКИ V3]: Режим визуализации для задачи {task_id}")
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200

    # 1. Скачиваем фото модели через твой универсальный роут скачивания
    download_person_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=person.png"
    try:
        print(f"📥 Скачивание фото модели: {download_person_url}")
        res_p = requests.get(download_person_url, stream=True, timeout=30)
        
        if res_p.status_code != 200:
            print(f"❌ Сервер не отдал фото модели. Код: {res_p.status_code}")
            return
            
        raw_image = Image.open(io.BytesIO(res_p.content)).convert("RGB")
        print(f"🟢 Фото успешно загружено. Размер: {raw_image.size}")
    except Exception as e:
        print(f"❌ Сбой при получении файла: {e}")
        return

    # 2. Видеокарта запускает rembg для построения силуэта человека
    print("✂️ [GPU REMBG]: Вырезаем силуэт человека на новой либе 1.19.0...")
    try:
        global REMBG_SESSION
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        output_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = output_rembg.split()[-1]  # Альфа-канал: человек белый (255), фон черный (0)
        g_alpha_np = np.array(g_alpha)
        print("✅ Силуэт успешно построен силами видеокарты!")
    except Exception as rem_err:
        print(f"❌ Ошибка сегментации rembg на GPU: {rem_err}")
        return

    # 3. МАТЕМАТИКА МАСКИ ТОРСА (Наши сдвинутые лимиты 0.28 - 0.52)
    clothing_draw = np.zeros_like(g_alpha_np)
    actual_height = raw_image.height 
    
    # Жесткая защита подбородка и лица модели
    head_limit = int(actual_height * 0.28)   
    hands_limit = int(actual_height * 0.52)  

    # Вырезаем область торса (одежды) по контуру силуэта и делаем её БЕЛОЙ (255)
    clothing_draw[head_limit:hands_limit] = g_alpha_np[head_limit:hands_limit]

    # Переводим массив в черно-белую картинку PIL (БЕЗ размытия, чтобы видеть чистые границы)
    clothing_mask = Image.fromarray(clothing_draw.astype(np.uint8), mode="L")

    # 4. СОХРАНЯЕМ МАСКУ КАК ИТОГОВЫЙ РЕЗУЛЬТАТ ДЛЯ СТЕНДА
    final_image = clothing_mask.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    output_filename = f"vton_result_{task_id}.png"
    final_image.save(output_filename)
    print(f"💾 Маска сохранена локально под именем: {output_filename}")

    # 5. ОТПРАВЛЯЕМ КАРТИНКУ МАСКИ НА СЕРВЕР SKULLA
    print("📤 Отправка файла маски на сервер для визуального анализа...")
    # 6. ОТПРАВКА НА СЕРВЕР SKULLA
    submit_success = submit_result_to_server(task_id, user_login, output_filename)
    
    if os.path.exists(output_filename):
        os.remove(output_filename)
        
    if submit_success:
        print(f"🏁 Задача {task_id} полностью выполнена и отправлена на сайт!")  

import io
import os
import requests
import numpy as np
import rembg
from PIL import Image, ImageFilter

import io
import os
import requests
import numpy as np
import rembg
from PIL import Image, ImageFilter

def process_heavy_tryon_naked_debugmask(task_data):
    """
    УМНАЯ ОПТИМИЗИРОВАННАЯ МАСКА V3:
    1. Находит силуэт человека на оригинале ОДИН раз.
    2. Синхронно масштабирует и фото, и маску так, чтобы человек занимал ровно 3/4 высоты кадра.
    3. Отсекает жесткие лимиты торса и шлет красный оверлей на сервер.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]

    print(f"\n🔬 [УМНАЯ ОПТИМИЗИРОВАННАЯ МАСКА]: Задача {task_id}")
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200
    VTON_WIDTH = 768
    VTON_HEIGHT = 1024

    # 1. Скачиваем фото модели
    download_person_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=person.png"
    try:
        res_p = requests.get(download_person_url, stream=True, timeout=30)
        if res_p.status_code != 200:
            print(f"❌ Сервер не отдал модель. Код: {res_p.status_code}")
            return
        raw_image = Image.open(io.BytesIO(res_p.content)).convert("RGB")
        orig_w, orig_h = raw_image.size
    except Exception as e:
        print(f"❌ Сбой сети при скачивании: {e}")
        return

    # ----------------------------------------------------
    # ШАГ 1: ЕДИНСТВЕННЫЙ ЗАПУСК REMBG НА ИСХОДНИКЕ
    # ----------------------------------------------------
    try:
        global REMBG_SESSION
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        orig_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = orig_rembg.split()[-1]  # Достаем PIL-картинку альфа-канала оригинального силуэта
        orig_alpha_np = np.array(g_alpha)
    except Exception as rem_err:
        print(f"❌ Ошибка rembg: {rem_err}")
        return

    # Находим крайние координаты человека по оригинальному силуэту
    white_pixels = np.argwhere(orig_alpha_np > 10)
    if len(white_pixels) == 0:
        print("⚠️ Человек на фото не обнаружен! Стандартный ресайз.")
        person_scaled = raw_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.Resampling.LANCZOS)
        mask_scaled = g_alpha.resize((VTON_WIDTH, VTON_HEIGHT), Image.Resampling.NEAREST)
    else:
        y_min, x_min = white_pixels.min(axis=0)
        y_max, x_max = white_pixels.max(axis=0)
        
        current_person_height = y_max - y_min
        center_y = (y_min + y_max) // 2
        center_x = (x_min + x_max) // 2

        # ----------------------------------------------------
        # ШАГ 2: ВЫЧИСЛЯЕМ МАСШТАБ (3/4 от 1024 = 768)
        # ----------------------------------------------------
        desired_person_height = int(VTON_HEIGHT * 0.75) 
        scale = desired_person_height / current_person_height
        
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Масштабируем ОДНОВРЕМЕННО и оригинал, и оригинальную маску rembg
        resized_raw = raw_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_alpha = g_alpha.resize((new_w, new_h), Image.Resampling.NEAREST) # Для маски строго NEAREST
        
        # Пересчитываем координаты центра на новом масштабе
        new_center_y = int(center_y * scale)
        new_center_x = int(center_x * scale)
        
        # Границы кропа для вырезания холста 768x1024
        crop_top = new_center_y - (VTON_HEIGHT // 2)
        crop_left = new_center_x - (VTON_WIDTH // 2)
        
        # Создаем пустые холсты нужного размера для CatVTON
        person_scaled = Image.new("RGB", (VTON_WIDTH, VTON_HEIGHT), color=(0, 0, 0))
        alpha_scaled = Image.new("L", (VTON_WIDTH, VTON_HEIGHT), color=0)
        
        # Вычисляем пересечение геометрии для безопасного кропа и вставки
        src_left = max(0, crop_left)
        src_top = max(0, crop_top)
        src_right = min(new_w, crop_left + VTON_WIDTH)
        src_bottom = min(new_h, crop_top + VTON_HEIGHT)
        
        dst_left = max(0, -crop_left)
        dst_top = max(0, -crop_top)
        
        # Синхронно вырезаем кусок из фото и кусок из маски rembg
        cropped_person = resized_raw.crop((src_left, src_top, src_right, src_bottom))
        cropped_alpha = resized_alpha.crop((src_left, src_top, src_right, src_bottom))
        
        # Вставляем вырезанные куски по центру наших холстов 768x1024
        person_scaled.paste(cropped_person, (dst_left, dst_top))
        alpha_scaled.paste(cropped_alpha, (dst_left, dst_top))
        
        print(f"🎯 Синхронная автоподгонка завершена. Маска масштабирована без повторного запуска rembg!")

    # ----------------------------------------------------
    # ШАГ 3: ДИНАМИЧЕСКОЕ НАЛОЖЕНИЕ МАСКИ ТОРСА ОТ РОСТА ЧЕЛОBЕКА
    # ----------------------------------------------------
    g_alpha_final_np = np.array(alpha_scaled)
    clothing_draw = np.zeros_like(g_alpha_final_np)
    
    # 🚀 ИСПРАВЛЕНО: Находим точные границы уже СКАЛИРОВАННОГО человека на новом холсте 1024px
    final_white_pixels = np.argwhere(g_alpha_final_np > 10)
    
    if len(final_white_pixels) == 0:
        # Если что-то пошло не так, оставляем аварийный дефолт
        head_limit = int(VTON_HEIGHT * 0.38)
        hands_limit = int(VTON_HEIGHT * 0.62)
    else:
        # Находим макушку (y_min_f) и стопы (y_max_f) отмасштабированного силуэта
        y_min_f, _ = final_white_pixels.min(axis=0)
        y_max_f, _ = final_white_pixels.max(axis=0)
        
        # Чистый рост человека на холсте в пикселях
        scaled_person_height = y_max_f - y_min_f
        
        # 🎯 ХИРУРГИЧЕСКИЙ РАСЧЕТ ТОРСА:
        # Шея начнется строго на 18% ниже макушки
        head_limit = int(y_min_f + scaled_person_height * 0.18)
        # Пояс закончится строго на 46% ниже макушки (выше бедер и юбки)
        hands_limit = int(y_min_f + scaled_person_height * 0.46)
        
        print(f"📐 Рост на холсте: {scaled_person_height}px. Динамическая маска: {head_limit}px - {hands_limit}px")

    # Вырезаем область блузки строго внутри отмасштабированного силуэта
    clothing_draw[head_limit:hands_limit] = g_alpha_final_np[head_limit:hands_limit]
    mask_scaled = Image.fromarray(clothing_draw.astype(np.uint8), mode="L")


    # Сборка тестового красного оверлея
    red_layer = Image.new("RGB", (VTON_WIDTH, VTON_HEIGHT), color=(255, 0, 0))
    alpha_mask = mask_scaled.point(lambda p: 100 if p > 10 else 0)
    overlay_image = Image.composite(red_layer, person_scaled, alpha_mask)

    # Приводим к финальному размеру отображения на сайте
    final_preview = overlay_image.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    
    output_filename = f"vton_result_{task_id}.png"
    final_preview.save(output_filename)

    # 6. ОТПРАВКА НА СЕРВЕР SKULLA
    print(f"📤 Отправка кадра геометрии {output_filename} на бэкенд...")
    submit_success = submit_result_to_server(task_id, user_login, output_filename)
    
    if os.path.exists(output_filename):
        os.remove(output_filename)
        
    if submit_success:
        print(f"🏁 Задача {task_id} полностью выполнена и отправлена на сайт!")            

import io
import os
import requests
import numpy as np
import rembg
import torch
from PIL import Image, ImageFilter

def process_heavy_tryon_naked(task_data):
    """
    ФИНАЛЬНЫЙ БОЕВОЙ КОНВЕЙЕР V3 (CatVTON):
    1. Находит силуэт человека и синхронно масштабирует маску и фото под 3/4 высоты кадра.
    2. Вырезает идеальную маску торса по нашей проверенной геометрии (0.18 - 0.46 от макушки).
    3. Запускает CatVTON для сквозного переноса кроя и ткани garment.png.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]

    print(f"\n🚀 [CatVTON PRODUCTION V3]: Запуск примерки для задачи {task_id}")
    TARGET_WIDTH = 900
    TARGET_HEIGHT = 1200
    VTON_WIDTH = 768
    VTON_HEIGHT = 1024

    # 1. Скачиваем фото модели
    download_person_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=person.png"
    try:
        res_p = requests.get(download_person_url, stream=True, timeout=30)
        if res_p.status_code != 200:
            print(f"❌ Сервер не отдал модель. Код: {res_p.status_code}")
            return
        raw_image = Image.open(io.BytesIO(res_p.content)).convert("RGB")
        orig_w, orig_h = raw_image.size
    except Exception as e:
        print(f"❌ Сбой сети при скачивании модели: {e}")
        return

    # 2. Скачиваем фото одежды (garment.png)
    download_garment_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename=garment.png"
    try:
        res_g = requests.get(download_garment_url, stream=True, timeout=30)
        if res_g.status_code != 200:
            print(f"❌ Критично: Файл garment.png не найден на сервере!")
            return
        garment_image = Image.open(io.BytesIO(res_g.content)).convert("RGB")
    except Exception as e:
        print(f"❌ Сбой сети при скачивании одежды: {e}")
        return

    # ----------------------------------------------------
    # ШАГ 1: ЕДИНСТВЕННЫЙ ЗАПУСК REMBG НА ИСХОДНИКЕ
    # ----------------------------------------------------
    try:
        global REMBG_SESSION
        if 'REMBG_SESSION' not in globals() or REMBG_SESSION is None:
            from rembg import new_session
            REMBG_SESSION = new_session("u2net")
            
        orig_rembg = rembg.remove(raw_image, session=REMBG_SESSION)
        g_alpha = orig_rembg.split()[-1]  
        orig_alpha_np = np.array(g_alpha)
    except Exception as rem_err:
        print(f"❌ Ошибка rembg: {rem_err}")
        return

    # Твой умный расчет масштабирования силуэта
    white_pixels = np.argwhere(orig_alpha_np > 10)
    if len(white_pixels) == 0:
        print("⚠️ Человек на фото не обнаружен! Стандартный ресайз.")
        person_scaled = raw_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.Resampling.LANCZOS)
        alpha_scaled = g_alpha.resize((VTON_WIDTH, VTON_HEIGHT), Image.Resampling.NEAREST)
    else:
        y_min, x_min = white_pixels.min(axis=0)
        y_max, x_max = white_pixels.max(axis=0)
        
        current_person_height = y_max - y_min
        center_y = (y_min + y_max) // 2
        center_x = (x_min + x_max) // 2

        # ----------------------------------------------------
        # ШАГ 2: СИНХРОННЫЙ УМНЫЙ РЕСАЙЗ ФОТО И МАСКИ ДО КРОПА
        # ----------------------------------------------------
        desired_person_height = int(VTON_HEIGHT * 0.75) 
        scale = desired_person_height / current_person_height
        
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        resized_raw = raw_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        resized_alpha = g_alpha.resize((new_w, new_h), Image.Resampling.NEAREST)
        
        new_center_y = int(center_y * scale)
        new_center_x = int(center_x * scale)
        
        crop_top = new_center_y - (VTON_HEIGHT // 2)
        crop_left = new_center_x - (VTON_WIDTH // 2)
        
        person_scaled = Image.new("RGB", (VTON_WIDTH, VTON_HEIGHT), color=(0, 0, 0))
        alpha_scaled = Image.new("L", (VTON_WIDTH, VTON_HEIGHT), color=0)
        
        src_left = max(0, crop_left)
        src_top = max(0, crop_top)
        src_right = min(new_w, crop_left + VTON_WIDTH)
        src_bottom = min(new_h, crop_top + VTON_HEIGHT)
        
        dst_left = max(0, -crop_left)
        dst_top = max(0, -crop_top)
        
        cropped_person = resized_raw.crop((src_left, src_top, src_right, src_bottom))
        cropped_alpha = resized_alpha.crop((src_left, src_top, src_right, src_bottom))
        
        person_scaled.paste(cropped_person, (dst_left, dst_top))
        alpha_scaled.paste(cropped_alpha, (dst_left, dst_top))

    # ----------------------------------------------------
    # ШАГ 3: РАСШИРЕННЫЙ РАСЧЕТ МАСКИ ПОД ДЛИННЫЙ РУКАВ И ПОДОЛ
    # ----------------------------------------------------
    g_alpha_final_np = np.array(alpha_scaled)
    clothing_draw = np.zeros_like(g_alpha_final_np)
    
    final_white_pixels = np.argwhere(g_alpha_final_np > 10)
    if len(final_white_pixels) == 0:
        head_limit = int(VTON_HEIGHT * 0.38)
        hands_limit = int(VTON_HEIGHT * 0.62)
    else:
        y_min_f, _ = final_white_pixels.min(axis=0)
        y_max_f, _ = final_white_pixels.max(axis=0)
        scaled_person_height = y_max_f - y_min_f
        
        # Начинаем строго под подбородком (18% от макушки)
        head_limit = int(y_min_f + scaled_person_height * 0.18)
        
        # 🚀 УДЛИНЯЕМ ПОДОЛ: Опускаем нижнюю границу до середины бёдер (56% вместо 0.46)
        # Это даст красной блузке место, чтобы закончиться во всю длину!
        hands_limit = int(y_min_f + scaled_person_height * 0.56)

    # 🚀 СУПЕР-ФИКС ДЛЯ ДЛИННЫХ РУКАВОВ: 
    # Закрашиваем весь силуэт человека целиком в этом диапазоне высоты.
    # Поскольку руки девушки опущены вдоль тела, они целиком попадут в эту зону, 
    # и ИИ сможет перерисовать голые предплечья в ткань длинного рукава!
    clothing_draw[head_limit:hands_limit] = g_alpha_final_np[head_limit:hands_limit]
    mask_scaled = Image.fromarray(clothing_draw.astype(np.uint8), mode="L")



    # ПОДГОТОВКА КАРТИНКИ ОДЕЖДЫ (РЕЗАЙЗ ПОД ЕДИНЫЙ РАЗМЕР ХОЛСТА)
    garment_scaled = garment_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.Resampling.LANCZOS)

    # ----------------------------------------------------
    # ШАГ 4: ЗАПУСК НЕЙРОСЕТИ ОРИГИНАЛЬНОГО CatVTON
    # ----------------------------------------------------
    # ----------------------------------------------------
    # 4. ЗАПУСК КАТАЛИЗАТОРА CatVTON
    # ----------------------------------------------------
    try:
        if garment_image:
            print("⚡ [GPU CatVTON]: Проверка готовности пайплайна примерки...")
            import torch
            
            # 🚀 ДОПИСЫВАЕМ СЮДА: Если прошлым шагом была анимация и CatVTON стерт — собираем его заново!
            global VTON_V3_PIPE
            if 'VTON_V3_PIPE' not in globals() or VTON_V3_PIPE is None:
                print("🔄 Пайплайн CatVTON отсутствует в памяти. Пересобираем движок примерки одежды...")
                # Вызываем твою готовую глобальную функцию инициализации моделей
                init_vton_models()
                
            # Дальше идет твой стандартный рабочий код подготовки размеров и инференса CatVTON...


        print("⚡ [GPU CatVTON]: Запуск сшивания физической ткани блузки...")
        import torch
        
        # Фиксируем генератор на GPU
        generator = torch.Generator(device="cuda").manual_seed(42)
        
        # Вызываем CatVTON строго по паспорту авторов без текстового мусора
        result_output = VTON_V3_PIPE(
            image=person_scaled,
            condition_image=garment_scaled,
            mask=mask_scaled,
            num_inference_steps=40,
            generator=generator
        )
        
        if hasattr(result_output, "images"):
            raw_output = result_output.images
        else:
            raw_output = result_output

        if isinstance(raw_output, list):
            final_image = raw_output[0]
        else:
            final_image = raw_output

        # ----------------------------------------------------
        # ШАГ 5: СОХРАНЕНИЕ И ОТПРАВКА НА СЕРВЕР SKULLA
        # ----------------------------------------------------
        final_image = final_image.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        output_filename = f"vton_result_{task_id}.png"
        final_image.save(output_filename)

        print(f"📥 [УСПЕХ]: Фото сгенерировано. Отправка на бэкенд...")
        submit_success = submit_result_to_server(task_id, user_login, output_filename)
        
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        if submit_success:
            print(f"🏁 [ПРОДУКТ ГОТОВ V3]: Новая вещь надета. Задача {task_id} завершена!")

    except Exception as e:
        print(f"❌ Критический сбой CatVTON: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'raw_image' in locals(): del raw_image
        if 'clothing_mask' in locals(): del clothing_mask
        if 'garment_image' in locals(): del garment_image
        if 'final_image' in locals(): del final_image
        import gc
        gc.collect()
        torch.cuda.empty_cache()

import io
import os
import requests
import imageio
import torch
from PIL import Image

def process_video_animation(task_data):
    """
    БОЕВАЯ ВИДЕО-ФУНКЦИЯ: Скачивает готовый результат примерки родительской задачи 
    и генерирует из него плавный MP4 видеоролик на GPU.
    """
    actual_task = task_data.get("task_data", {})
    task_id = actual_task["task_id"]           # Это ID видео-задачи (нужен для сохранения MP4)
    session_id = actual_task["session_id"]
    user_login = actual_task["user_login"]
    
    # 🚀 ЖЕСТКИЙ ФИКС: Вытаскиваем ID родительской задачи примерки одежды!
    # Если сервер его не прислал (мало ли), откатываемся на обычный task_id
    parent_task_id = actual_task.get("parent_task_id", task_id)

    print(f"\n🎬 [ИИ-ОЖИВЛЕНИЕ]: Запуск генерации видео для задачи {task_id}")

    # 🚀 ИСПРАВЛЕНО: Запрашиваем файл vton_result_task_..., который ТОЧНО лежит на сервере!
    download_url = f"{SERVER_URL}/api/studio/fishhook/download_source/{session_id}?filename={parent_task_id}.png"
    
    try:
        print(f"📥 Скачивание родительского кадра для анимации: {download_url}")
        res = requests.get(download_url, stream=True, timeout=30)
        if res.status_code != 200:
            print(f"❌ Сервер не отдал картинку. Код: {res.status_code}")
            return
        input_image = Image.open(io.BytesIO(res.content)).convert("RGB")
        
        # SVD требует, чтобы размеры были строго кратны 64. Идеальный стандарт: 576x1024
        input_image = input_image.resize((448, 768), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"❌ Сбой сети при подготовке кадра: {e}")
        return


    # ----------------------------------------------------
    # 2. СКОРОСТНОЙ ИИ-ИНФЕРЕНС ДВИЖЕНИЯ
    # ----------------------------------------------------
    try:
        global VIDEO_PIPE
        print("⚡ [GPU SVD]: Быстрый расчет динамики кадра...")
        import torch
        
        generator = torch.Generator(device="cuda").manual_seed(42)
        
        # 🚀 ВОЗВРАЩАЕМ СКОРОСТЬ И ЖИЗНЬ: 
        # Всего 20 шагов вместо 45 (рендер взлетит!), но подняли motion_bucket до 140, 
        # чтобы девушка плавно двигалась, и ослабили привязку до 0.01, чтобы убрать ступор
        video_frames = VIDEO_PIPE(
            image=input_image,
            height=768,
            width=448,
            num_frames=25,
            num_inference_steps=20,   # Ускорили рендер в 2.5 раза!
            decode_chunk_size=4, 
            motion_bucket_id=140,     # Модель оживет, пойдет плавное позирование
            fps=7,
            noise_aug_strength=0.01,  # Разрешаем ИИ естественно двигать плечи и волосы
            generator=generator
        ).frames

        # ----------------------------------------------------
        # 3. ЭТАП КРИСТАЛЬНОЙ ЧЁТКОСТИ (Быстрый Апскейл кадров)
        # ----------------------------------------------------
        output_video_name = f"vton_video_{task_id}.mp4"
        print(f"🎨 [ИИ-УЛУЧШАЙЗЕР]: Убираем размытие с автомобиля и фона...")
        
        # Жесткий хак совместимости PyTorch (чтобы не было ошибки functional_tensor)
        import sys
        import torchvision.transforms.functional as tv_F
        sys.modules['torchvision.transforms.functional_tensor'] = tv_F
        
        # Подключаем библиотеки апскейлера
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
        
        # 🚀 ИСПРАВЛЕНО СИНХРОНИЗАЦИЯ ВЕСОВ: num_block обязан быть равен 23, чтобы матрицы совпали!
        model_esr = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
        
        # Инициализируем улучшайзер с фиксом model_dir='.' и восклицательным знаком в домене
        upsampler = RealESRGANer(
            scale=2, 
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth', 
            model=model_esr, 
            tile=400, 
            device='cuda'
        )


        print(f"🎬 Физическое улучшение и склейка 25 кадров в Full HD...")
        
        # Конфигурируем кодек H.264
        writer = imageio.get_writer(
            output_video_name, 
            fps=12, 
            format='FFMPEG', 
            mode='I',
            codec='libx264',
            pixelformat='yuv420p',
            macro_block_size=8
        )
        
        import cv2
        
        for frame in video_frames:
            img_np = np.array(frame)
            
            # Накладываем фильтр чёткости RealESRGAN
            enhanced_frame, _ = upsampler.enhance(img_np, outscale=2)
            
            # 🚀 НАСТОЯЩИЙ ИСПРАВЛЕННЫЙ ФИКС ГЕОМЕТРИИ (Убирает полоску в 50 пикселей):
            # Проверяем структуру матрицы. Если первое число в форме равно 3 (каналы цвета впереди):
            if len(enhanced_frame.shape) == 3 and enhanced_frame.shape[0] == 3:
                # Принудительно разворачиваем оси из (3, H, W) в правильный формат (H, W, 3)
                enhanced_frame = np.transpose(enhanced_frame, (1, 2, 0))
            
            # Переводим каналы цвета из BGR (OpenCV) обратно в RGB для правильных цветов
            rgb_frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2RGB)
            
            # Принудительно фиксируем правильный тип данных картинки (целые числа от 0 до 255)
            final_frame_np = rgb_frame.astype(np.uint8)
            
            # Записываем чёткий, цветной и правильно отформатированный кадр в MP4
            writer.append_data(final_frame_np)
            
        writer.close()
        print("✅ Кристально чистый цветной видеоролик успешно собран на диск.")




        # ----------------------------------------------------
        # 4. ОТПРАВКА НА СЕРВЕР SKULLA И ЛОКАЛЬНОЕ СОХРАНЕНИЕ
        # ----------------------------------------------------
        # Создаем в корне Колаба папку /content/vton_outputs/, если её ещё нет
        save_dir = "/content/vton_outputs"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
            
        # Формируем надежный путь для вечного хранения на диске Колаба
        permanent_video_path = os.path.join(save_dir, output_video_name)
        
        # Копируем созданный ролик в нашу архивную папку перед отправкой
        import shutil
        shutil.copyfile(output_video_name, permanent_video_path)
        print(f"💾 [АРХИВ]: Копия ролика сохранена на диск Колаба: {permanent_video_path}")

        print(f"📤 Отправка промо-ролика {output_video_name} на бэкенд...")
        submit_success = submit_result_to_server(task_id, user_login, output_video_name)
        
        # 🚀 ИСПРАВЛЕНО: Удаляем временный файл в корне проекта ТОЛЬКО если отправка прошла успешно!
        # Если сервер упадет, файл останется лежать в корне воркера для подстраховки.
        if submit_success:
            #if os.path.exists(output_video_name):
                #os.remove(output_video_name)
            print(f"🏁 [ПОБЕДА]: Видеоролик успешно доставлен на сайт. Задача {task_id} закрыта!")
        else:
            print(f"⚠️ [СБОЙ СЕТИ]: Сервер не принял файл. Ролик ОСТАВЛЕН на диске воркера под именем {output_video_name}")


    except Exception as e:
        print(f"❌ Критический сбой видео-конвейера: {e}")
        
    finally:
        if 'input_image' in locals(): del input_image
        if 'video_frames' in locals(): del video_frames
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
        # Если сервер отдал задачу
        if task_data and task_data.get("status") == "success":
            style = task_data.get("task_data", {}).get("prompt_style", "")
            
            # 🚀 ЕСЛИ С ФРОНТА ПРИЛЕТЕЛ КЛЮЧ АНИМАЦИИ — ВКЛЮЧАЕМ ВИДЕО-КОНВЕЙЕР!
            if style == "animate_video":
                process_video_animation(task_data)
            else:
                # Иначе гоним нашу стандартную идеальную примерку одежды V3
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
