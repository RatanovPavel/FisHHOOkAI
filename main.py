import os
import torch
import numpy as np
from PIL import Image, ImageFilter
from diffusers import StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Функция для отладки инпаинтинга с фиксированной квадратной зоной защиты.
    Именно её сейчас ищет ваш ноутбук.
    """
    # Конфигурация путей (подставьте имя вашего исходного изображения товара)
    image_path = f"step1_earbuds_{task_id}.png" 
    output_path = f"fresult_card_{task_id}.png"
    
    if not os.path.exists(image_path):
        # Если файла с task_id нет, попробуем взять дефолтный тестовый, чтобы код не падал
        image_path = "step1_earbuds_001.png"
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Положите исходное изображение товара в файлы Colab под именем: {image_path}")

    # 1. Загрузка исходного изображения товара
    init_image = Image.open(image_path).convert("RGB")
    init_image = init_image.resize((1024, 1024))
    width, height = init_image.size
    
    # 2. Создание квадратной маски (Защита центральной зоны)
    # 255 (белый) — зона перегенерации фона
    # 0 (черный) — защищенный квадрат товара
    mask_array = np.full((height, width), 255, dtype=np.uint8)
    
    box_size = 600  # Размер охраняемого квадрата в пикселях
    start_x = (width - box_size) // 2
    start_y = (height - box_size) // 2
    
    mask_array[start_y:start_y+box_size, start_x:start_x+box_size] = 0
    raw_mask = Image.fromarray(mask_array)
    
    # Размытие границ для плавной склейки (из вашего исходного кода radius=12)
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    
    # Сохраняем маску для визуальной отладки
    mask_image.save(f"step2_mask_{task_id}.png")
    print(f"[ОТЛАДКА] Квадратная маска сохранена в: step2_mask_{task_id}.png")

    # 3. Инициализация и запуск SDXL Inpaint
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

    print(f"[AI] Генерация нового окружения вокруг квадратной зоны...")
    final_image = pipe(
        prompt=prompt_style,
        image=init_image,
        mask_image=mask_image,
        strength=0.99,
        guidance_scale=8.0,
        num_inference_steps=30
    ).images[0]

    # 4. Сохранение результата
    final_image.save(output_path)
    print(f"[Успех] Карточка готова и сохранена в: {output_path}")
