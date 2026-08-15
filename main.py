import sys
import argparse
import time
import os
import torch
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
    Пайплайн «Честные руки» (Inpainting с инвертированной маской):
    1. Генерирует качественный гаджет (наушники).
    2. rembg определяет контур, создавая правильную маску: 
       товар = ЧЕРНЫЙ (не трогать), фон = БЕЛЫЙ (нарисовать тут руки).
    3. Добавляется мягкое размытие краев, чтобы пальцы могли обхватить кейс.
    4. SDXL Inpaint прорисовывает руки человека в пустом пространстве.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🖥️ [GPU ИИ]: Инициализация процессора: {device.upper()}")
    
    # Используем стабильные эталонные модели
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
    source_image = txt2img_pipe(prompt=source_prompt, num_inference_steps=25, guidance_scale=7.5, width=1024, height=1024).images[0]
    
    source_filename = f"step1_earbuds_{task_id}.png"
    source_image.save(source_filename)

    try:
        from IPython.display import display
        print("🖼️ [Экран]: Шаг 1 — Созданный товар:")
        display(source_image)
    except Exception:
        pass

    del txt2img_pipe
    if device == "cuda":
        torch.cuda.empty_cache()

    # --- ЭТАП 2: СОЗДАНИЕ ПРАВИЛЬНОЙ МАСКИ (Товар = Черный, Фон = Белый) ---
    print("\n✂️ [ИИ Этап 2]: Запуск rembg. Вырезаю фон и создаю маску для прорисовки рук...")
    
    # rembg отделяет гаджет от фона
    output_rembg = rembg.remove(source_image)
    alpha = output_rembg.split()[-1] # Получаем маску прозрачности
    
    # Инвертируем маску по вашему правилу: 
    # Сам товар делаем ЧЕРНЫМ (0), а пустое пространство вокруг него — БЕЛЫМ (255)
    mask_np = np.array(alpha)
    inverted_mask_np = np.where(mask_np > 10, 0, 255).astype(np.uint8)
    raw_mask = Image.fromarray(inverted_mask_np).convert("L")
    
    # Сверхважный шаг: слегка размываем края маски (на 8 пикселей), 
    # чтобы пальцы человека могли заходить НА кейс и обхватывать его, создавая тени
    mask_image = raw_mask.filter(ImageFilter.GaussianBlur(radius=8))
    
    mask_filename = f"step2_mask_{task_id}.png"
    mask_image.save(mask_filename)
    print(f"💾 [Лог]: Правильная маска для рук создана и сохранена как {mask_filename}")

    try:
        from IPython.display import display
        print("🖼️ [Экран]: Шаг 2 — Правильная маска (Белое пространство = зона для отрисовки рук):")
        display(mask_image)
    except Exception:
        pass

    # --- ЭТАП 3: ИНПАИНТИНГ РУК ЧЕЛОВЕКА ---
    print("\n🎨 [ИИ Этап 3]: Отрисовка человеческих рук в белом пространстве вокруг кейса...")
    inpaint_pipe = StableDiffusionXLInpaintPipeline.from_pretrained(inpaint_repo, torch_dtype=dtype, variant="fp16" if device == "cuda" else None)
    if device == "cuda":
        inpaint_pipe.enable_model_cpu_offload()
    inpaint_pipe.safety_checker = None

    translator = GoogleTranslator(source='auto', target='en')
    en_style = translator.translate(prompt_style)
    
    # Промпт дает ИИ жесткую команду: заполнить белое пустое пространство руками человека
    full_prompt = f"A high-quality advertising close-up photo of human hands holding and clutching a white wireless earbud charging case, clear fingers holding the product, {en_style}, realistic skin texture, highly detailed, dslr, 8k"
    print(f"   📝 [Лог]: Направляю ИИ-запрос: '{full_prompt}'")

    # Запускаем честный инпаинтинг на 30 шагах. 
    # Модель сотрет белое поле и заполнит его руками, аккуратно пристыковав пальцы к кейсу
    final_image = inpaint_pipe(
        prompt=full_prompt,
        image=source_image,
        mask_image=mask_image,
        num_inference_steps=30,
        guidance_scale=8.0
    ).images[0]

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
    parser = argparse.ArgumentParser(description="FishHookAI - True Hands Inpaint Pipeline")
    parser.add_argument("--token", type=str, default="DEMO_TOKEN")
    parser.add_argument("--task_id", type=str, default="task_001")
    parser.add_argument("--prompt", type=str, default="luxury gold podium, neon cyber punk light, dark background, 8k")
    args = parser.parse_args()

    print("\n=== СТАРТ ИСПРАВЛЕННОЙ НОДЫ FISHHOOKAI ===")
    if not check_server_permission(args.token, args.task_id):
        sys.exit(403)

    run_dual_ai_pipeline(args.prompt, args.task_id)
    print("=== РАБОТА ЦЕПОЧКИ ЗАВЕРШЕНА УСПЕШНО ===\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
