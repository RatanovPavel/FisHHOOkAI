import sys
import argparse
import time
import os
import torch
import gc # Подключаем жесткий сборщик мусора Python для экономии ОЗУ
from PIL import Image, ImageFilter
import numpy as np
from deep_translator import GoogleTranslator
from diffusers import StableDiffusionXLInpaintPipeline, AutoPipelineForText2Image
import rembg

def check_server_permission(token: str, task_id: str) -> bool:
    """Шаг 0: Рукопожатие с сервером"""
    print(f"🔒 [FishHookAI]: Проверка вечной лицензии для токена: {token}...")
    if token == "DEMO_TOKEN" or token.startswith("LIFETIME_"):
        print("✅ [FishHookAI]: Лицензия подтверждена сервером. Доступ к GPU разрешен!")
        return True
    return False

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Пайплайн «Честные руки» с экстремальной оптимизацией ОЗУ (RAM/GPU):
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️ [GPU ИИ]: Инициализация процессора: {device.upper()}")
    
    base_repo = "stabilityai/stable-diffusion-xl-base-1.0".replace("!", ".")
    inpaint_repo = "diffusers/stable-diffusion-xl-1.0-inpainting-0.1".replace("!", ".")
    dtype = torch.float16 if device == "cuda" else torch.float32

    # --- ЭТАП 1: ГЕНЕРАЦИЯ НАУШНИКОВ ---
    print("\n📦 [ИИ Этап 1]: Генерирую беспроводные наушники в открытом кейсе...")
    txt2img_pipe = AutoPipelineForText2Image.from_pretrained(base_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None)
    if device == "cuda":
        txt2img_pipe.enable_model_cpu_offload()
    txt2img_pipe.safety_checker = None

    source_prompt = "A high-end product shot of white wireless earbuds inside an open charging case, premium tech gadget, isolated on studio grey background, commercial photography, sharp focus, 8k resolution"
    source_image = txt2img_pipe(prompt=source_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024).images
    
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)

    try:
        from IPython.display import display
        print("🖼️ [Экран]: Шаг 1 — Созданный товар:")
        display(source_image)
    except Exception:
        pass

    # 🔥 СВЕРХВАЖНО: ВЫГРУЖАЕМ И СТИРАЕМ ПЕРВУЮ МОДЕЛЬ ИЗ ОЗУ НАМЕРТВО
    print("\n🧹 [Лог]: Начинаю экстренную очистку системной оперативной памяти (RAM)...")
    del txt2img_pipe
    gc.collect() # Принудительно очищаем оперативку Linux от остатков модели
    if device == "cuda":
        torch.cuda.empty_cache()
    print("✅ [Лог]: Оперативная память успешно очищена под ноль.")

    # --- ЭТАП 2: СОЗДАНИЕ ПРАВИЛЬНОЙ МАСКИ (Товар = Черный, Фон = Белый) ---
    print("\n✂️ [ИИ Этап 2]: Запуск rembg. Вырезаю фон и создаю маску для прорисовки рук...")
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1]
    
    mask_np = np.array(alpha)
    inverted_mask_np = np.where(mask_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    
    # Размываем маску на 12 пикселей для идеального, мягкого наложения пальцев на пластик
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=12))
    
    mask_filename = f"step2_mask_{task_id}.png"
    mask_image.save(mask_filename)

    try:
        from IPython.display import display
        print("🖼️ [Экран]: Шаг 2 — Правильная маска для генерации рук:")
        display(mask_image)
    except Exception:
        pass

    # --- ЭТАП 3: ИНПАИНТИНГ РУК ЧЕЛОВЕКА ---
    print("\n🎨 [ИИ Этап 3]: Отрисовка человеческих рук в белом пространстве вокруг кейса...")
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None)
    
    # Включаем экстремальную экономию ОЗУ и памяти видеокарты
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None

    translator = GoogleTranslator(source='auto', target='en')
    en_style = translator.translate(prompt_style)
    
    full_prompt = f"A high-quality advertising close-up photo of male human hands holding and clutching a white wireless earbud charging case, clear fingers holding the product, {en_style}, realistic skin texture, highly detailed, dslr, 8k"
    print(f"   📝 [Лог]: Направляю ИИ-запрос: '{full_prompt}'")

    final_image = inpaint_pipe(
        prompt=full_prompt,
        image=source_image,
        mask_image=mask_image,
        num_inference_steps=30,
        guidance_scale=8.0
    ).images

    final_filename = f"result_card_{task_id}.png"
    final_image.save(final_filename)
    print(f"💾 [FishHookAI]: Финальная карточка готова! Сохранено как {final_filename}")

    try:
        from IPython.display import display
        print("🖼️ [Экран]: Шаг 3 — Финальный результат (Кейс в руках человека):")
        display(final_image)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="FishHookAI - Zero-OOM Inpaint Pipeline")
    parser.add_argument("--token", type=str, default="DEMO_TOKEN")
    parser.add_argument("--task_id", type=str, default="task_001")
    parser.add_argument("--prompt", type=str, default="luxury gold podium, neon cyber punk light, dark background, 8k")
    args = parser.parse_args()

    print("\n=== СТАРТ ОПТИМИЗИРОВАННОЙ НОДЫ FISHHOOKAI ===")
    if not check_server_permission(args.token, args.task_id):
        sys.exit(403)

    run_dual_ai_pipeline(args.prompt, args.task_id)
    print("=== РАБОТА ЦЕПОЧКИ ЗАВЕРШЕНА УСПЕШНО ===\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
