import os
import gc
import torch
import numpy as np
from PIL import Image, ImageFilter
import rembg
from diffusers import AutoPipelineForText2Image, StableDiffusionXLInpaintPipeline
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

def analyze_product_with_qwen(image_path: str, device: str) -> str:
    """
    Нейросеть Qwen2-VL анализирует изображение товара и определяет его точный тип.
    """
    print("[Qwen ИИ-Анализатор]: Инициализация Qwen2-VL...")
    
    #model_id = "Qwen/Qwen2-VL-7B-Instruct"
    model_id = "Qwen/Qwen2-VL-2B-Instruct"
    # Загружаем модель с оптимизацией по памяти (Bfloat16/Float16) для T4 GPU
    processor = AutoProcessor.from_pretrained(model_id)
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_id, 
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto"
    )
    
    # Формируем умный запрос для Qwen
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": "Identify the specific main commercial product in this image. Answer with only 2-4 words naming the object (e.g. 'wireless earbuds', 'perfume bottle', 'running sneaker'). No full sentences."}
            ]
        }
    ]
    
    # Подготовка входных данных
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    ).to(device)
    
    # Генерация ответа
    print("[Qwen ИИ-Анализатор]: Сканирую пиксели и определяю категорию...")
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=15)
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
    
    clean_object = output_text.strip().lower().replace(".", "")
    print(f"[Qwen ИИ-Анализатор]: Товар успешно распознан ➔ '{clean_object}'")
    
    # Экстренная выгрузка Qwen из памяти
    del model, processor, inputs, generated_ids
    gc.collect()
    torch.cuda.empty_cache()
    
    return clean_object

def generate_smart_prompt(detected_object: str) -> tuple:
    """
    Автоматически составляет коммерческий промпт на основе категории товара.
    """
    obj = detected_object
    
    # Сценарий 1: Гаджеты и Электроника
    if any(x in obj for x in ["earbud", "phone", "watch", "tech", "gadget", "headphone"]):
        category = "ELECTRONICS"
        prompt = f"cyberpunk aesthetic, full background filled with bright GREEN neon glowing laser lines, vibrant emerald and mint studio lights, luxury cinematic gold podium under {detected_object}, volumetric colorful green smoke filling the entire screen, photo realistic, 8k resolution, highly detailed"
        negative = "plain black background, boring studio, simple wall, white backdrop"
        gradient_rgb = (10, 45, 20) # Зеленая зацепка
        
    # Сценарий 2: Косметика, Парфюмерия, Эко-товары
    elif any(x in obj for x in ["bottle", "cream", "perfume", "cosmetic", "glass", "jar"]):
        category = "COSMETICS / ECO"
        prompt = f"premium eco minimalism aesthetic, a luxury podium made of light natural oak wood supporting {detected_object}, fresh green monstera leaves in soft focus, bright warm morning sunlight with realistic window shadows, crystal clear water splashes and micro drops flying in the air, clean white studio background, photorealistic, 8k resolution"
        negative = "dark background, neon, cyber punk, black spaces, smoke, lasers"
        gradient_rgb = (200, 220, 200) # Светлая зацепка под белую студию
        
    # Сценарий 3: Обувь, Одежда, Аксессуары
    elif any(x in obj for x in ["shoe", "sneaker", "bag", "clothing", "boot"]):
        category = "FASHION / STREETWEAR"
        prompt = f"urban street style fashion photography, {detected_object} standing on a minimalist raw concrete geometric block, dramatic hard shadows, dark moody background with subtle orange neon accent lighting, professional hyperrealistic commercial shot, 8k"
        negative = "nature, leaves, white background, clean studio, bright sun"
        gradient_rgb = (30, 20, 15) # Темно-коричневая/бетонная зацепка
        
    # Сценарий по умолчанию: Универсальная премиум-презентация
    else:
        category = "UNIVERSAL PREMIUM"
        prompt = f"commercial product photography of {detected_object}, luxury black marble studio background, gold geometric lines decoration, dramatic volumetric rim lighting, high-end display showcase, photorealistic, 8k"
        negative = "ugly, cheap, blurry, bad lighting"
        gradient_rgb = (20, 20, 20) # Темно-серая зацепка
        
    return category, prompt, negative, gradient_rgb


def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Умный конвейер с использованием мультимодальной нейросети Qwen2-VL.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"\n=== [FishHookAI] СТАРТ УМНОГО КОНВЕЙЕРА (Qwen2-VL) НА {device.upper()} ===")
    
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'

    # --- ЭТАП 1: ГЕНЕРАЦИЯ ТОВАРА ---
    print(f"\n{BLUE}[ЭТАП 1]: Инициализация модели генерации товара...{ENDC}")
    base_repo = "stabilityai/stable-diffusion-xl-base-1.0"
    txt2img_pipe = AutoPipelineForText2Image.from_pretrained(
        base_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        txt2img_pipe.enable_model_cpu_offload()
    txt2img_pipe.safety_checker = None
    
    # Для теста Квена можно будет подставлять: "A luxury perfume bottle on grey background"
    product_prompt = "A high-end product shot of white wireless earbuds inside an open charging case, isolated on studio grey background, commercial photography, sharp focus, 8k resolution"
    
    source_image = txt2img_pipe(prompt=product_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024).images[0]
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)
    
    print("[ОЧИСТКА 1]: Выгружаю генератор товара...")
    del txt2img_pipe
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 2: ВЫРЕЗАНИЕ ФОНА И ИИ-АНАЛИЗ ЧЕРЕЗ QWEN ---
    print(f"\n{BLUE}[ЭТАП 2]: Вырезание фонда и запуск Qwen2-VL...{ENDC}")
    output_rembg = rembg.remove(source_image)
    
    # Сохраняем промежуточный вырезанный товар, чтобы Qwen анализировал его без лишнего мусора
    cropped_product_path = f"step2_cropped_{task_id}.png"
    output_rembg.save(cropped_product_path)
    
    alpha = output_rembg.split()[-1]
    alpha_np = np.array(alpha)
    
    # Создаем маску защиты по контуру
    inverted_mask_np = np.where(alpha_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    mask_image.save(f"step2_mask_{task_id}.png")
    
    # [УМНЫЙ ШАГ]: Отдаем вырезанную картинку в Qwen2-VL
    detected_obj = analyze_product_with_qwen(cropped_product_path, device)
    category, smart_prompt, smart_negative, target_rgb = generate_smart_prompt(detected_obj)
    
    print(f"\n{GREEN}[Qwen МАРШРУТИЗАЦИЯ]:")
    print(f" -> Распознанный объект: '{detected_obj}'")
    print(f" -> Выбранная бизнес-категория: {category}")
    print(f" -> Сгенерированный ИИ промпт фона: '{smart_prompt}'{ENDC}")

    # Создаем динамическую подложку-зацепку на основе выбранной категории (target_rgb)
    gradient_bg = Image.new("RGB", (1024, 1024), target_rgb)
    forced_source_image = Image.composite(source_image, gradient_bg, alpha)
    forced_source_image.save(f"step2_forced_source_{task_id}.png")

    print("[ОЧИСТКА 2]: Выгружаю rembg...")
    del output_rembg, alpha, alpha_np, inverted_mask_np, raw_mask, gradient_bg
    gc.collect()
    if device == "cuda": torch.cuda.empty_cache()

    # --- ЭТАП 3: ИНПАИНТИНГ ИДЕАЛЬНОГО ФОНА ПОД КАТЕГОРИЮ ---
    print(f"\n{BLUE}[ЭТАП 3]: Инициализация модели инпаинтинга SDXL...{ENDC}")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None
    )
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None
    
    final_prompt = smart_prompt if prompt_style == "auto" else prompt_style
    
    final_image = inpaint_pipe(
        prompt=final_prompt,
        negative_prompt=smart_negative,
        image=forced_source_image,  
        mask_image=mask_image,
        strength=0.99,             
        guidance_scale=9.5,        
        num_inference_steps=30
    ).images[0]
    
    final_filename = f"fresult_card_{task_id}.png"
    final_image.save(final_filename)
    
    try:
        from IPython.display import display
        print(f"\n{GREEN}[ЭКРАН]: Финальный результат под категорию {category}:{ENDC}")
        display(final_image)
    except Exception:
        pass
        
    print(f"\n=== [FishHookAI] СЕССИЯ {task_id} ПОЛНОСТЬЮ ЗАВЕРШЕНА ===")
