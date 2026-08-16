import numpy as np
from PIL import Image

def run_dual_ai_pipeline(prompt_style: str, task_id: str):
    """
    Простейший отладочный скрипт.
    Просто рисует четкий квадрат и выводит его в блокнот.
    """
    print(f"[ОТЛАДКА] Запуск теста для задачи: {task_id}")
    
    # 1. Задаем размер холста (стандарт SDXL)
    width, height = 1024, 1024
    
    # 2. Создаем маску: 255 (белый фон) — зона перегенерации
    mask_array = np.full((height, width), 255, dtype=np.uint8)
    
    # 3. Вырезаем ЧЕТКИЙ черный квадрат защиты в центре (без размытия)
    box_size = 500  # Размер квадрата в пикселях
    start_x = (width - box_size) // 2
    start_y = (height - box_size) // 2
    
    # Закрашиваем центр черным цветом (0)
    mask_array[start_y:start_y+box_size, start_x:start_x+box_size] = 0
    
    # Превращаем массив в картинку
    mask_image = Image.fromarray(mask_array).convert("L")
    
    # 4. Выводим картинку прямо в блокнот Colab для проверки
    try:
        from IPython.display import display
        print("[ОТЛАДКА] Маска создана. Черный центр — зона защиты:")
        display(mask_image)
    except Exception as e:
        print(f"Не удалось вывести в блокнот, но маска создана: {e}")
        
    # Сохраняем на всякий случай в файлы
    mask_image.save(f"debug_square_{task_id}.png")

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