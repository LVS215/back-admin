FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копирование приложения
COPY . .

# Создание пользователя для безопасности
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/media /app/staticfiles && \
    chown -R appuser:appuser /app

USER appuser

# Создание директории для логов
RUN mkdir -p logs

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
