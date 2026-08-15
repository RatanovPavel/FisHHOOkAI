import os
import torch
import numpy as np
from PIL import Image, ImageFilter
from diffusers import StableDiffusionXLInpaintPipeline

def debug_inpaint_square_zone(
    image_path: str, 
    prompt: str, 
    output_path: str, 
    box_size: int = 512,       # Размер защищенного квадрата в пикселях
    blur_radius: int = 12       # Радиус размытия границ (из вашего исходного кода)
):
    """
    Скрипт для отладки инпаинтинга с фиксированной квадратной зоной защиты.
    Сохраняет маску для визуальной проверки корректности зон.
    """
    # 1. Загрузка и подготовка изображения (приводим к стандартному размеру SDXL)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Файл не найден: {image_path}")
        
    init_image = Image.open(image_path).convert("RGB")
    init_image = init_image.resize((1024, 1024)) # Стандарт для SDXL
    width, height = init_image.size
    
    # 2. Создание точной отладочной маски
    # 255 (белый) — зона перегенерации (фон)
    # 0 (черный) — зона защиты (ваш объект)
    mask_array = np.full((height, width), 255, dtype=np.uint8)
    
    # Расчет координат центрального квадрата
    start_x = (width - box_size) // 2
    start_y = (height - box_size) // 2
    
    # Вырезаем черную зону защиты в центре
    mask_array[start_y:start_y+box_size, start_x:start_x+box_size] = 0
    raw_mask = Image.fromarray(mask_array)
    
    # Сглаживание краев маски для плавной склейки нейросетью
    if blur_radius > 0:
        mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    else:
        mask_image = raw_mask

    # [ОТЛАДКА] Сохраняем маску на диск, чтобы глазами проверить зону защиты
    debug_mask_path = "debug_mask_preview.png"
    mask_image.save(debug_mask_path)
    print(f"[ОТЛАДКА] Маска для проверки сохранена в: {debug_mask_path}")
    print(f"[ОТЛАДКА] Защищен квадрат размером {box_size}x{box_size} в центре кадра 1024x1024")

    # 3. Запуск нейросети
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    print("[AI] Загрузка пайплайна инпаинтинга...")
    pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype,
        variant="fp16" if device == "cuda" else None
    )
    pipe.to(device)
    
    if device == "cuda":
        pipe.enable_model_cpu_offload()
    pipe.safety_checker = None

    print(f"[AI] Генерация фона вокруг защищенной зоны...")
    final_image = pipe(
        prompt=prompt,
        image=init_image,
        mask_image=mask_image,
        strength=0.99,            # Максимальная сила перерисовки белой зоны
        guidance_scale=8.0,
        num_inference_steps=30
    ).images[0]

    # 4. Сохранение финального результата отладки
    final_image.save(output_path)
    print(f"[Успех] Тест завершен. Результат: {output_path}")

if __name__ == "__main__":
    # Параметры для теста
    INPUT_IMG = "step1_earbuds_001.png" # Исходный квадратный объект
    TEST_PROMPT = "a professional studio product shot, luxury podium, cyber punk lighting, 8k"
    OUTPUT_IMG = "debug_result.png"
    
    debug_inpaint_square_zone(
        image_path=INPUT_IMG,
        prompt=TEST_PROMPT,
        output_path=OUTPUT_IMG,
        box_size=600,      # Размер неизменяемого квадрата (в пикселях внутри 1024x1024)
        blur_radius=12     # Размытие стыка (0 — идеально острый квадратный край)
    )
