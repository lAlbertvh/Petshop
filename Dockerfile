FROM python:3.10-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование всего проекта
COPY . .

# Копирование зависимостей
COPY requirements.txt .

# Установка Python-пакетов
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создание папки для изображений (если нужно)
RUN mkdir -p /app/images

# Создание папки для базы данных (если нужно)
RUN mkdir -p /app

# Запуск бота
CMD ["python", "bot.py"]