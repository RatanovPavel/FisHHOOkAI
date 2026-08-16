import os
import gc
import torch
import numpy as np
from PIL import Image, ImageFilter
import rembg
from diffusers import AutoPipelineForText2Image, StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Полный пайплайн: Генерация товара -> RemBG -> Мягкая маска по контуру объекта -> Инпаинтинг фона.
    С экстремальной очисткой RAM/VRAM для предотвращения краша ядра.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"\n=== [FishHookAI] СТАРТ ПОЛНОГО ПАЙПЛАЙНА НА {device.upper()} ===")
    
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

    # --- ЭТАП 1: ГЕНЕРАЦИЯ ИСХОДНОГО ТОВАРА ---
    print(f"\n{BLUE}[ЭТАП 1]: Инициализация модели генерации товара...{ENDC}")
    base_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    txt2img_pipe = AutoPipelineForText2Image.from_pretrained(
        base_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        txt2img_pipe.enable_model_cpu_offload()
    txt2img_pipe.safety_checker = None
    
    product_prompt = "A high-end product shot of white wireless earbuds inside an open charging case, isolated on studio grey background, commercial photography, sharp focus, 8k resolution"
    print(f"[ЭТАП 1]: Генерирую товар по запросу: '{product_prompt}'")
    
    source_image = txt2img_pipe(
        prompt=product_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024
    ).images[0]
    
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)
    
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 1 – Сгенерированный товар (сохранен в {source_filename}):{ENDC}")
        display(source_image)
    except Exception:
        pass

    # ОЧИСТКА ПАМЯТИ ПОСЛЕ ЭТАПА 1
    print("[ОЧИСТКА 1]: Удаляю модель генерации товара из памяти...")
    del txt2img_pipe
    gc.collect()
    if device == "cuda": 
        torch.cuda.empty_cache()

    # --- ЭТАП 2: УДАЛЕНИЕ ФОНА И СОЗДАНИЕ МАСКИ ПО ОЧЕРТАНИЯМ ---
    print(f"\n{BLUE}[ЭТАП 2]: Запуск rembg. Вырезаю фон по контуру товара...{ENDC}")
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]  # Получаем альфа-канал силуэта
    alpha_np = np.array(alpha)
    
    # Инвертируем: Товар = 0 (черный, защита), Фон = 255 (белый, замена)
    inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    
    # Размываем маску по контуру на 12 пикселей для идеального бесшовного стыка (как на первом скрине)
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    
    mask_filename = f"step2_mask_{task_id}.png"
    mask_image.save(mask_filename)
    
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 2 – Маска по точным очертаниям товара (сохранена в {mask_filename}):{ENDC}")
        print("[ПОЯСНЕНИЕ]: Черный силуэт в точности повторяет форму наушников и защищает их.")
        display(mask_image)
    except Exception:
        pass

    # КРИТИЧЕСКАЯ ОЧИСТКА ПАМЯТИ ПОСЛЕ REMBG И ONNX (Защита от краша сессии)
    print("[ОЧИСТКА 2]: Выгружаю rembg и очищаю системный кэш RAM...")
    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask
    gc.collect()
    if device == "cuda": 
        torch.cuda.empty_cache()

    # --- ЭТАП 3: ИНПАИНТИНГ ФОТО-ОКРУЖЕНИЯ ---
    print(f"\n{BLUE}[ЭТАП 3]: Инициализация модели инпаинтинга SDXL...{ENDC}")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    print(f"[ЭТАП 3]: Отрисовываю новое окружение по запросу: '{prompt_style}'")
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
    
    try:
        from IPython.display import display
        print(f"\n{GREEN}[ЭКРАН]: Шаг 3 – Финальная карточка (сохранена в {final_filename}):{ENDC}")
        print("[ПОЯСНЕНИЕ]: Фон вокруг наушников полностью перерисован ИИ по контуру.")
        display(final_image)
    except Exception:
        pass
        
    print(f"\n=== [FishHookAI] СЕССИЯ {task_id} ПОЛНОСТЬЮ ЗАВЕРШЕНА УСПЕШНО ===")
