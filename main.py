import os
import gc
import torch
import numpy as np
from PIL import Image
import rembg
from diffusers import AutoPipelineForText2Image, StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Полный пайплайн: Генерация товара -> RemBG -> Авто-расчет квадратной маски -> Инпаинтинг фона.
    С выводом всех промежуточных этапов в блокнот.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"\n=== [FishHookAI] СТАРТ ПОЛНОГО ПАЙПЛАЙНА НА {device.upper()} ===")
    
    # Стили вывода текста в Colab
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

    # --- ЭТАП 1: ГЕНЕРАЦИЯ ИСХОДНОГО ТОВАРА ---
    print(f"\n{BLUE}[ЭТАП 1]: Инициализация модели генерации товара...{ENDC}")
    base_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    txt2img_pipe = AutoPipelineForText2Image.from_pretrained(
        base_repo, 
        torch_dtype=dtype, 
        variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        txt2img_pipe.enable_model_cpu_offload()
    txt2img_pipe.safety_checker = None
    
    # Промпт для создания самого товара
    product_prompt = "A high-end product shot of white wireless earbuds inside an open charging case, isolated on studio grey background, commercial photography, sharp focus, 8k resolution"
    print(f"[ЭТАП 1]: Генерирую товар по запросу: '{product_prompt}'")
    
    source_image = txt2img_pipe(
        prompt=product_prompt, 
        num_inference_steps=25, 
        guidance_scale=7.5, 
        width=1024, 
        height=1024
    ).images[0]
    
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)
    
    # Выводим сгенерированный товар
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 1 – Сгенерированный товар (сохранен в {source_filename}):{ENDC}")
        display(source_image)
    except Exception:
        pass

    # Экстренная очистка памяти перед загрузкой второй тяжелой модели
    print("[ОЧИСТКА]: Удаляю модель генерации товара из ОЗУ/VRAM...")
    del txt2img_pipe
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    # --- ЭТАП 2: УДАЛЕНИЕ ФОНА И РАСЧЕТ КВАДРАТНОЙ МАСКИ ЗАЩИТЫ ---
    print(f"\n{BLUE}[ЭТАП 2]: Запуск rembg для анализа силуэта товара...{ENDC}")
    # Вырезаем фон, чтобы получить маску прозрачности (альфа-канал)
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]  # Вытаскиваем только альфа-канал (прозрачность)
    alpha_np = np.array(alpha)
    
    # Находим реальные пиксельные границы объекта (где альфа > 10)
    pos = np.where(alpha_np > 10)
    if len(pos[0]) > 0 and len(pos[1]) > 0:
        ymin, ymax = np.min(pos[0]), np.max(pos[0])
        xmin, xmax = np.min(pos[1]), np.max(pos[1])
        
        # Вычисляем центр объекта и его максимальный габарит
        obj_width = xmax - xmin
        obj_height = ymax - ymin
        max_side = max(obj_width, obj_height)
        
        center_x = (xmin + xmax) // 2
        center_y = (ymin + ymax) // 2
        
        # Добавляем небольшой отступ (padding), чтобы края товара не срезались (+15% к размеру)
        box_size = int(max_side * 1.15)
        # Ограничиваем, чтобы маска не вылетела за края картинки 1024x1024
        box_size = min(box_size, 1024)
        
        start_x = max(0, center_x - box_size // 2)
        start_y = max(0, center_y - box_size // 2)
        # Корректируем конечные координаты под размер холста
        if start_x + box_size > 1024: start_x = 1024 - box_size
        if start_y + box_size > 1024: start_y = 1024 - box_size
    else:
        # Если rembg не нашел объект, падаем на стандартный квадрат по центру
        print("[ВНИМАНИЕ]: Объект не обнаружен, применяю дефолтный размер.")
        box_size = 550
        start_x = (1024 - box_size) // 2
        start_y = (1024 - box_size) // 2

    # Создаем финальную квадратную маску инпаинтинга
    # 255 (белый фон) — зона для перерисовки, 0 (черный квадрат) — жесткая защита товара
    mask_array = np.full((1024, 1024), 255, dtype=np.uint8)
    mask_array[start_y:start_y+box_size, start_x:start_x+box_size] = 0
    mask_image = Image.fromarray(mask_array).convert("L")
    
    mask_filename = f"step2_mask_{task_id}.png"
    mask_image.save(mask_filename)
    
    # Выводим маску
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 2 – Автоматическая квадратная маска вокруг товара (размер {box_size}x{box_size}):{ENDC}")
        print("[ПОЯСНЕНИЕ]: Черная квадратная зона полностью защищает ваш товар от изменений.")
        display(mask_image)
    except Exception:
        pass

    # --- ЭТАП 3: ИНПАИНТИНГ ФОТО-ОКРУЖЕНИЯ ---
    print(f"\n{BLUE}[ЭТАП 3]: Инициализация модели инпаинтинга SDXL...{ENDC}")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, 
        torch_dtype=dtype, 
        variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    print(f"[ЭТАП 3]: Генерирую фотореалистичное окружение по запросу: '{prompt_style}'")
    final_image = inpaint_pipe(
        prompt=prompt_style,
        image=source_image,
        mask_image=mask_image,
        strength=0.99,
        guidance_scale=8.0,
        num_inference_steps=30
    ).images[0]
    
    final_filename = f"fresult_card_{task_id}.png"
    final_image.save(final_filename)
    
    # Выводим финальный результат
    try:
        from IPython.display import display
        print(f"\n{GREEN}[ЭКРАН]: Шаг 3 – Финальная карточка товара:{ENDC}")
        print(f"[ПОЯСНЕНИЕ]: Окружение полностью изменилось, товар внутри квадрата остался оригинальным.")
        display(final_image)
    except Exception:
        pass
        
    print(f"\n=== [FishHookAI] СЕССИЯ {task_id} УСПЕШНО СКОМПИЛИРОВАНА ===")
