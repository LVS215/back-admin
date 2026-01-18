#!/bin/bash

# Скрипт развертывания на продакшн сервер

set -e  # Выход при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Проверка переменных окружения
check_env() {
    log "Проверка переменных окружения..."
    
    required_vars=(
        "SECRET_KEY"
        "DB_NAME"
        "DB_USER"
        "DB_PASSWORD"
        "DB_HOST"
        "DB_PORT"
        "REDIS_URL"
        "ALLOWED_HOSTS"
        "DEBUG"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            error "Переменная окружения $var не установлена"
            exit 1
        fi
    done
    
    if [ "$DEBUG" = "True" ]; then
        warn "DEBUG установлен в True. Убедитесь, что это продакшн сервер!"
    fi
    
    log "Переменные окружения проверены"
}

# Проверка зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    # Проверка Docker
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен"
        exit 1
    fi
    
    # Проверка Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose не установлен"
        exit 1
    fi
    
    # Проверка доступности портов
    ports=(80 443 5432 6379)
    for port in "${ports[@]}"; do
        if netstat -tuln | grep ":$port " > /dev/null; then
            warn "Порт $port уже занят"
        fi
    done
    
    log "Зависимости проверены"
}

# Создание директорий
create_directories() {
    log "Создание необходимых директорий..."
    
    directories=(
        "logs"
        "logs/nginx"
        "static"
        "media"
        "backups"
        "ssl"
    )
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            log "Создана директория: $dir"
        fi
    done
    
    # Установка прав
    chmod -R 755 logs
    chmod -R 755 static
    chmod -R 755 media
    
    log "Директории созданы"
}

# Настройка Nginx
setup_nginx() {
    log "Настройка Nginx..."
    
    if [ ! -f "nginx/nginx.conf" ]; then
        error "Файл nginx/nginx.conf не найден"
        exit 1
    fi
    
    # Создание SSL сертификатов (если нужно)
    if [ ! -f "ssl/certificate.crt" ] || [ ! -f "ssl/private.key" ]; then
        warn "SSL сертификаты не найдены. Используется self-signed сертификат для тестирования"
        
        mkdir -p ssl
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/private.key \
            -out ssl/certificate.crt \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    fi
    
    log "Nginx настроен"
}

# Сборка и запуск контейнеров
build_and_start() {
    log "Сборка Docker образов..."
    docker-compose build
    
    log "Запуск контейнеров..."
    docker-compose up -d
    
    log "Ожидание запуска сервисов..."
    sleep 10
    
    # Проверка состояния контейнеров
    log "Проверка состояния контейнеров..."
    docker-compose ps
    
    # Проверка логов
    log "Проверка логов..."
    docker-compose logs --tail=10
}

# Выполнение миграций
run_migrations() {
    log "Выполнение миграций базы данных..."
    
    max_retries=10
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if docker-compose exec -T web python manage.py migrate --noinput; then
            log "Миграции выполнены успешно"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        warn "Попытка $retry_count/$max_retries не удалась. Повтор через 5 секунд..."
        sleep 5
    done
    
    error "Не удалось выполнить миграции после $max_retries попыток"
    exit 1
}

# Сборка статических файлов
collect_static() {
    log "Сборка статических файлов..."
    docker-compose exec -T web python manage.py collectstatic --noinput
    log "Статические файлы собраны"
}

# Создание суперпользователя
create_superuser() {
    log "Создание суперпользователя..."
    
    if [ -n "$SUPERUSER_USERNAME" ] && [ -n "$SUPERUSER_EMAIL" ] && [ -n "$SUPERUSER_PASSWORD" ]; then
        log "Создание суперпользователя с предоставленными учетными данными"
        
        cat << EOF | docker-compose exec -T web python manage.py shell
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='$SUPERUSER_USERNAME').exists():
    User.objects.create_superuser(
        username='$SUPERUSER_USERNAME',
        email='$SUPERUSER_EMAIL',
        password='$SUPERUSER_PASSWORD'
    )
    print('Суперпользователь создан')
else:
    print('Суперпользователь уже существует')
EOF
    else
        warn "Учетные данные суперпользователя не указаны. Создание пропущено."
        warn "Чтобы создать суперпользователя, установите переменные:"
        warn "SUPERUSER_USERNAME, SUPERUSER_EMAIL, SUPERUSER_PASSWORD"
    fi
}

# Загрузка начальных данных
load_fixtures() {
    log "Загрузка начальных данных..."
    
    fixtures=(
        "categories.json"
        "tags.json"
        "users.json"
    )
    
    for fixture in "${fixtures[@]}"; do
        if [ -f "fixtures/$fixture" ]; then
            log "Загрузка фикстуры: $fixture"
            docker-compose exec -T web python manage.py loaddata "fixtures/$fixture"
        else
            warn "Фикстура $fixture не найдена"
        fi
    done
}

# Настройка кэша
setup_cache() {
    log "Настройка кэша..."
    docker-compose exec -T web python manage.py clear_cache
    log "Кэш очищен"
}

# Проверка здоровья приложения
health_check() {
    log "Проверка здоровья приложения..."
    
    max_retries=10
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -f http://localhost:8000/api/health/ > /dev/null 2>&1; then
            log "Приложение работает корректно"
            return 0
        fi
        
        retry_count=$((retry_count + 1))
        warn "Попытка $retry_count/$max_retries не удалась. Повтор через 5 секунд..."
        sleep 5
    done
    
    error "Приложение не прошло проверку здоровья после $max_retries попыток"
    docker-compose logs web
    exit 1
}

# Основная функция
main() {
    log "Начало развертывания Blog API..."
    
    # Смена директории на корень проекта
    cd "$(dirname "$0")/.."
    
    # Выполнение шагов развертывания
    check_env
    check_dependencies
    create_directories
    setup_nginx
    build_and_start
    run_migrations
    collect_static
    create_superuser
    load_fixtures
    setup_cache
    health_check
    
    log "Развертывание успешно завершено!"
    log "Приложение доступно по адресу: http://localhost"
    log "API документация: http://localhost/api/docs"
    log "Админ-панель: http://localhost/admin"
    log ""
    log "Для просмотра логов выполните: docker-compose logs -f"
    log "Для остановки приложения: docker-compose down"
}

# Запуск основной функции
main "$@"
