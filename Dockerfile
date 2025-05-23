FROM python:3.10-slim

# Установка системных зависимостей
# Используем && для объединения команд, уменьшая количество слоев
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    # Добавьте сюда любые другие системные зависимости, если они понадобятся
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование requirements.txt и установка зависимостей.
# Это позволяет Docker кэшировать этот слой, если requirements.txt не изменится.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование всего остального кода приложения
# Делаем это после установки зависимостей, чтобы изменения в коде не инвалидировали кэш зависимостей
COPY . .

# Создание папки для изображений (если она нужна внутри контейнера)
RUN mkdir -p /app/images

# Команда по умолчанию для запуска бота
CMD ["python", "-m", "asyncio", "bot.py"]