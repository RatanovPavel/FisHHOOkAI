import os
import gc
import torch
import numpy as np
from PIL import Image, ImageFilter
import rembg
from diffusers import AutoPipelineForText2Image, StableDiffusionXLInpaintPipeline

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Пайплайн примерочной: Генерация модели -> RemBG маски одежды -> Инпаинтинг нового платья.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"\n=== [FishHookAI Fitting Room] СТАРТ ПРИМЕРОЧНОЙ НА {device.upper()} ===")
    
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

    # --- ЭТАП 1: ГЕНЕРАЦИЯ ЧЕЛОВЕКА В СТАРТОМ ПЛАТЬЕ ---
    print(f"\n{BLUE}[ЭТАП 1]: Генерация модели в базовом платье...{ENDC}")
    base_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    txt2img_pipe = AutoPipelineForText2Image.from_pretrained(
        base_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        txt2img_pipe.enable_model_cpu_offload()
    txt2img_pipe.safety_checker = None
    
    # Промпт для создания человека (модели)
    model_prompt = "Full body fashion photography of a beautiful elegant woman wearing a simple plain white tight dress, minimal studio background, look at camera, professional lighting, dslr, 8k"
    
    person_image = txt2img_pipe(prompt=model_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024).images[0]
    person_path = f"step1_person_{task_id}.png"
    person_image.save(person_path)
    
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 1 – Исходная модель в белом платье:{ENDC}")
        display(person_image)
    except Exception:
        pass

    print("[ОЧИСТКА 1]: Освобождаю память от генератора...")
    del txt2img_pipe
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 2: ВЫРЕЗАНИЕ ОДЕЖДЫ И СОЗДАНИЕ СИЛУЭТНОЙ МАСКИ ---
    print(f"\n{BLUE}[ЭТАП 2]: Анализ контуров одежды через rembg...{ENDC}")
    
    # rembg вырезает человека. Чтобы получить маску именно ПЛАТЬЯ, мы используем трюк с разницей каналов
    # (В идеале для этого используют модели вроде ClothSeg, но на T4 мы вытащим маску через дельту маски человека)
    output_rembg = rembg.remove(person_image)
    alpha = output_rembg.split()[-1]
    alpha_np = np.array(alpha)
    
    # Так как платье белое, а кожа и фон имеют другие оттенки, мы выжигаем маску зоны туловища
    # Для отладки делаем маску торса: 0 (защита лица и рук), 255 (зона платья)
    height, width = alpha_np.shape
    cloth_mask_np = np.zeros((height, width), dtype=np.uint8)
    
    # Автоматически берем среднюю зону тела (где обычно расположено платье), защищая лицо (верхние 25%) и ноги
    cloth_mask_np[int(height*0.22):int(height*0.85), :] = alpha_np[int(height*0.22):int(height*0.85), :]
    
    # Инвертируем: платье становится БЕЛЫМ (255 - зона замены), остальное ЧЕРНЫМ (0 - защита лица/фона)
    cloth_mask_np = np.where(cloth_mask_np > 30, 255, 0).astype(np.uint8)
    
    raw_mask = Image.fromarray(cloth_mask_np).convert("L")
    # Мягкое размытие краев на 15 пикселей для аккуратного прилегания новой ткани к коже
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=15))
    mask_image.save(f"step2_cloth_mask_{task_id}.png")
    
    try:
        from IPython.display import display
        print(f"{GREEN}[ЭКРАН]: Шаг 2 – Силуэтная маска платья (Белая зона — то, что заменится):{ENDC}")
        display(mask_image)
    except Exception:
        pass

    print("[ОЧИСТКА 2]: Очистка RAM перед инпаинтингом...")
    del output_rembg, alpha, alpha_np, cloth_mask_np, raw_mask
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 3: ИНПАИНТИНГ (ПРИМЕРКА НОВОГО ПЛАТЬЯ) ---
    print(f"\n{BLUE}[ЭТАП 3]: Инициализация модели примерки одежды...{ENDC}")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    # Промпт для НОВОГО платья (фасон, цвет, ткань)
    # prompt_style передается из ячейки Colab
    full_fit_prompt = f"A gorgeous high-end professional clothing presentation, woman wearing a {prompt_style}, perfect fit, beautiful realistic fabric texture, highly detailed fashion look, 8k"
    negative_prompt = "bad anatomy, deformed hands, broken fingers, white plain tight dress, bare skin, naked, ugly legs"
    
    print(f"[ЭТАП 3]: Одеваю модель в новый фасон: '{prompt_style}'")
    final_image = inpaint_pipe(
        prompt=full_fit_prompt,
        negative_prompt=negative_prompt,
        image=person_image,
        mask_image=mask_image,
        strength=0.98,             # Агрессивно меняем фасон старого платья
        guidance_scale=9.0,
        num_inference_steps=35
    ).images[0]
    
    final_filename = f"fresult_fitting_{task_id}.png"
    final_image.save(final_filename)
    
    try:
        from IPython.display import display
        print(f"\n{GREEN}[ЭКРАН]: Шаг 3 – Результат примерки в виртуальной примерочной!{ENDC}")
        display(final_image)
    except Exception:
        pass
        
    print(f"\n=== [FishHookAI] ПРИМЕРКА ДЛЯ СЕССИИ {task_id} ЗАВЕРШЕНА ===")
