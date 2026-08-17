import os
import time
import requests
from PIL import Image, ImageDraw

# БАЗОВЫЙ АДРЕС ТВОЕГО СЕРВЕРА SKULLA
SERVER_URL = "https://skulla.ru"  # Сюда Колаб будет слать запросы

def fetch_task_from_server(user_login: str):
    """Шлет GET-запрос на FastAPI роут для проверки очереди задач"""
    endpoint = f"{SERVER_URL}/api/studio/fishhook/get_task/{user_login}"
    try:
        response = requests.get(endpoint, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data
    except Exception as e:
        print(f" [СВЯЗЬ]: Ожидаю коннекта с сервером skulla.ru... ({e})")
    return None

def submit_result_to_server(task_id: str, user_login: str, file_path: str):
    """Шлет готовый файл-заглушку обратно на сервер"""
    endpoint = f"{SERVER_URL}/api/studio/fishhook/submit_result"
    
    if not os.path.exists(file_path):
        print(f" [ОШИБКА]: Файл {file_path} не найден на диске!")
        return False
        
    try:
        with open(file_path, "rb") as f:
            files = {"image": (f"result_{task_id}.png", f, "image/png")}
            data = {"task_id": task_id, "user_login": user_login}
            
            response = requests.post(endpoint, data=data, files=files, timeout=15)
            if response.status_code == 200 and response.json().get("status") == "received":
                print(f" [УСПЕХ]: Тестовый результат отправлен на сервер для {user_login}!")
                return True
    except Exception as e:
        print(f" [ОШИБКА]: Сбой отправки файла на бэкенд: {e}")
    return False

def process_fake_task(task_data: dict):
    """Имитация работы ИИ без задействования видеокарты"""
    task_id = task_data["task_id"]
    user_login = task_data["user_login"]
    prompt_style = task_data["prompt_style"]
    image_url = task_data["image_url"]
    
    print(f"\n📥 [ИМИТАТОР]: Поймал задачу {task_id} от {user_login}!")
    print(f" 📝 Текст от селлера: '{prompt_style}'")
    
    # 1. Скачиваем исходную картинку, чтобы проверить, что сеть работает
    print(" [ИМИТАТОР]: Скачиваю исходное фото товара по сети...")
    try:
        source_image = Image.open(requests.get(image_url, stream=True).raw).convert("RGB")
    except Exception as e:
        print(f" [ВНИМАНИЕ]: Не удалось скачать фото товара, создаю заглушку: {e}")
        source_image = Image.new("RGB", (1024, 1024), (100, 100, 100))

    # 2. Имитируем «тяжелую генерацию» нейросети в течение 5 секунд
    print(" [ИИ ЭТАП]: Нейросеть думает (видеокарта отдыхает)...")
    for i in range(5, 0, -1):
        print(f"   Осталось {i} сек...")
        time.sleep(1)
        
    # 3. Рисуем тестовый результат (просто пишем текст промпта поверх картинки)
    final_image = source_image.copy()
    draw = ImageDraw.Draw(final_image)
    # Рисуем рамку и текст
    draw.rectangle([50, 50, 974, 974], outline="lime", width=15)
    
    final_filename = f"fake_result_{task_id}.png"
    final_image.save(final_filename)
    
    # 4. Отправляем результат обратно на сервер skulla.ru
    print(" [СЕТЬ]: Отправляю результат в папку сессии...")
    submit_result_to_server(task_id, user_login, final_filename)
    
    if os.path.exists(final_filename):
        os.remove(final_filename)
    print(" [ИМИТАТОР]: Задача сдана. Возвращаюсь к пингам.")

def main_loop(user_login: str):
    """Бесконечный цикл опроса (ЦП режим)"""
    print(f"\n=== [ЭКО-ВОРКЕР FISHHOOK] ЗАПУЩЕН НА ЦЕНТРАЛЬНОМ ПРОЦЕССОРЕ ===")
    print(f"👤 Активный логин селлера: {user_login}")
    print("📡 Видеокарта НЕ используется. Время T4 НЕ тратится.")
    
    while True:
        task_data = fetch_task_from_server(user_login)
        if task_data:
            process_fake_task(task_data)
        else:
            print(".", end="", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", type=str, required=True)
    args = parser.parse_args()
    main_loop(args.login)
