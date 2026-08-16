import os
import gc
import torch
import numpy as np
from PIL import Image, ImageFilter
import rembg
from diffusers import AutoPipelineForText2Image, StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Пайплайн с агрессивной заменой фона для кардинального изменения окружения.
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
    source_image = txt2img_pipe(prompt=product_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024).images[0]
    
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)
    
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 1 – Сгенерированный товар:{ENDC}")
        display(source_image)
    except Exception:
        pass

    print("[ОЧИСТКА 1]: Удаляю модель генерации товара...")
    del txt2img_pipe
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 2: УДАЛЕНИЕ ФОНА И АГРЕССИВНАЯ ПОДГОТОВКА ИСХОДНИКА ---
    print(f"\n{BLUE}[ЭТАП 2]: Запуск rembg и жесткое выжигание фона...{ENDC}")
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]
    alpha_np = np.array(alpha)
    
    # 1. Создаем маску: Товар = 0 (черный), Фон = 255 (белый)
    inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    mask_image.save(f"step2_mask_{task_id}.png")
    
    # [СЕКРЕТНЫЙ ХАК]: Вырезаем товар и сажаем его на чистый черный холст!
    # Это уничтожит серую студию и заставит инпаинт рисовать сочные эффекты с нуля
    black_bg = Image.new("RGB", (1024, 1024), (0, 0, 0))
    forced_source_image = Image.composite(source_image, black_bg, alpha)
    forced_source_image.save(f"step2_forced_source_{task_id}.png")

    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 2 – Товар на черной подложке для агрессивной перерисовки:{ENDC}")
        display(forced_source_image)
    except Exception:
        pass

    print("[ОЧИСТКА 2]: Выгружаю rembg...")
    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask, black_bg
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 3: ИНПАИНТИНГ ФОТО-ОКРУЖЕНИЯ ---
    print(f"\n{BLUE}[ЭТАП 3]: Инициализация модели инпаинтинга SDXL...{ENDC}")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    # Жесткий бан на серые студийные фоны
    negative_prompt = "grey background, studio background, plain wall, minimalism, boring background, simple backdrop"
    
    print(f"[ЭТАП 3]: Отрисовываю КАРДИНАЛЬНО новый фон: '{prompt_style}'")
    print(f"[ЭТАП 3]: Отрисовываю КАРДИНАЛЬНО новый фон: '{prompt_style}'")
    final_image = inpaint_pipe(
        prompt=prompt_style,
        negative_prompt=negative_prompt,
        image=forced_source_image,
        mask_image=mask_image,
        strength=0.85,             # Уменьшили с 0.99 для агрессивного смешивания с неоном
        guidance_scale=9.5,        # Увеличили, чтобы промпт сильнее влиял на картинку
        num_inference_steps=35
    ).images[0]
    
    final_filename = f"fresult_card_{task_id}.png"
    final_image.save(final_filename)
    
    try:
        from IPython.display import display
        print(f"\n{GREEN}[ЭКРАН]: Шаг 3 – Кардинально новая карточка:{ENDC}")
        display(final_image)
    except Exception:
        pass
        
    print(f"\n=== [FishHookAI] СЕССИЯ {task_id} ПОЛНОСТЬЮ ЗАВЕРШЕНА УСПЕШНО ===")
