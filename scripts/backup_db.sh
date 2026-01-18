#!/bin/bash

# Скрипт резервного копирования базы данных

set -e

# Настройки
BACKUP_DIR="backups"
DATE=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql.gz"
RETENTION_DAYS=7

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Проверка переменных окружения
if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_HOST" ]; then
    error "Переменные окружения базы данных не установлены"
    exit 1
fi

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# Резервное копирование
log "Начало резервного копирования базы данных $DB_NAME..."

if pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    log "Резервное копирование успешно завершено: $BACKUP_FILE"
    
    # Проверка размера файла
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Размер файла бэкапа: $FILE_SIZE"
else
    error "Ошибка при резервном копировании"
    exit 1
fi

# Очистка старых бэкапов
log "Очистка бэкапов старше $RETENTION_DAYS дней..."
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Вывод информации о оставшихся бэкапах
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "backup_*.sql.gz" | wc -l)
log "Всего бэкапов в директории: $BACKUP_COUNT"

# Восстановление из бэкапа (опционально, закомментировано)
# log "Для восстановления из бэкапа выполните:"
# echo "gunzip -c $BACKUP_FILE | psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
