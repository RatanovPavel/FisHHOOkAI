# Используем базовый ИИ-образ
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# Системные зависимости без точек в командах
RUN apt-get update && apt-get install -y wget git && rm -rf /var/lib/apt/lists/*

# Копируем список библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем наш главный ИИ-скрипт
COPY main.py .

# Папка, куда Докер будет кэшировать скачанные ИИ-модели
ENV HF_HOME=/app/ai_cache

ENTRYPOINT ["python", "main.py"]
