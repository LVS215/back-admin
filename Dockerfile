FROM python:3.11-slim as builder

WORKDIR /app

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt .
RUN pip install --upgrade pip && pip install --user -r requirements-prod.txt

# Финальный образ
FROM python:3.11-slim

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование Python пакетов
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Копирование приложения
COPY . .

# Создание пользователя
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
