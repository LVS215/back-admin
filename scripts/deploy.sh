#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Load environment
ENV_FILE=".env.production"
if [ -f "$ENV_FILE" ]; then
    log "Loading environment from $ENV_FILE"
    export $(cat $ENV_FILE | grep -v '^#' | xargs)
else
    error "$ENV_FILE not found"
    exit 1
fi

# Backup database before deployment
log "Creating database backup..."
./scripts/backup_db.sh

# Stop existing containers
log "Stopping existing containers..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Pull latest changes
log "Pulling latest changes..."
git pull origin main

# Build and start containers
log "Building and starting containers..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run migrations
log "Running database migrations..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate

# Collect static files
log "Collecting static files..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Clear cache
log "Clearing cache..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py clear_cache

# Restart services
log "Restarting services..."
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart

# Health check
log "Performing health check..."
sleep 10
if curl -s -o /dev/null -w "%{http_code}" https://$ALLOWED_HOSTS/api/health/ | grep -q "200"; then
    log "Deployment successful!"
else
    error "Health check failed"
    exit 1
fi

log "Deployment completed successfully"
