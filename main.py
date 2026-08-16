import os
import torch
import numpy as np
from PIL import Image
from diffusers import StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Генерация фотореалистичного окружения вокруг жесткой квадратной маски защиты.
    """
    print(f"\n[AI] Запуск генерации фона для задачи: {task_id}")
    
    # 1. Параметры холста (стандарт для SDXL)
    width, height = 1024, 1024
    
    # 2. Создаем базовое изображение для теста (например, серый студийный фон)
    # В продакшене здесь будет загружаться ваше реальное фото товара
    init_image = Image.new("RGB", (width, height), (200, 200, 200))
    
    # 3. Создаем маску: 255 (белый) — перегенерация, 0 (черный) — защита центра
    mask_array = np.full((height, width), 255, dtype=np.uint8)
    
    box_size = 500  # Размер вашего четкого квадрата защиты
    start_x = (width - box_size) // 2
    start_y = (height - box_size) // 2
    mask_array[start_y:start_y+box_size, start_x:start_x+box_size] = 0
    
    mask_image = Image.fromarray(mask_array).convert("L")
    
    # 4. Инициализация нейросети SDXL Inpaint на GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    print("[AI] Загрузка модели Stable Diffusion XL Inpaint...")
    pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=dtype,
        variant="fp16" if device == "cuda" else None
    )
    pipe.to(device)
    
    # Оптимизация памяти для видеокарты T4
    if device == "cuda":
        pipe.enable_model_cpu_offload()
    pipe.safety_checker = None

    # 5. Генерация фотореализма вокруг маски
    print(f"[AI] Отрисовка фона по запросу: {prompt_style}")
    final_image = pipe(
        prompt=prompt_style,
        image=init_image,
        mask_image=mask_image,
        strength=0.99,            # Максимальная перерисовка фона
        guidance_scale=8.0,
        num_inference_steps=30    # 30 шагов для высокой детализации
    ).images[0]

    # 6. Вывод результата прямо в блокнот Colab
    try:
        from IPython.display import display
        print("[AI] Генерация успешно завершена! Результат:")
        display(final_image)
    except Exception as e:
        print(f"Не удалось отобразить, но файл сохранен. Ошибка: {e}")
        
    # Сохраняем финальную карточку на диск
    final_image.save(f"fresult_card_{task_id}.png")
    print(f"[Успех] Файл сохранен как: fresult_card_{task_id}.png")
