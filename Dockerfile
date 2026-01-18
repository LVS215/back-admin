# Используем официальный Python образ
FROM python:3.10-slim-bullseye

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Создаем пользователя для безопасности
RUN groupadd -r django && \
    useradd -r -g django django

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Для psycopg2
    gcc \
    libpq-dev \
    # Для Pillow (обработка изображений)
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    # Для других зависимостей
    curl \
    wget \
    gettext \
    # Для мониторинга
    procps \
    # Утилиты для разработки
    nano \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем проект
COPY . .

# Создаем необходимые директории
RUN mkdir -p static media logs && \
    chown -R django:django /app && \
    chmod -R 755 /app

# Меняем владельца файлов
RUN chown -R django:django /app

# Переключаемся на непривилегированного пользователя
USER django

# Собираем статические файлы
RUN python manage.py collectstatic --noinput

# Открываем порт
EXPOSE 8000

# Запускаем приложение через Gunicorn
CMD ["gunicorn", "blog.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
