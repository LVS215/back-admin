#!/bin/bash
#!/bin/bash

# Load environment
source .env.production

# Create backup directory
BACKUP_DIR="backups/$(date +%Y-%m-%d_%H-%M-%S)"
mkdir -p $BACKUP_DIR

# Backup PostgreSQL database
log "Backing up PostgreSQL database..."
docker-compose exec db pg_dump -U $DB_USER $DB_NAME > $BACKUP_DIR/db_backup.sql

# Backup media files
log "Backing up media files..."
tar -czf $BACKUP_DIR/media.tar.gz media/

# Backup logs
log "Backing up logs..."
tar -czf $BACKUP_DIR/logs.tar.gz logs/

# Create backup info file
cat > $BACKUP_DIR/backup_info.txt << EOF
Backup created: $(date)
Database: $DB_NAME
Backup size: $(du -sh $BACKUP_DIR | cut -f1)
EOF

log "Backup completed: $BACKUP_DIR"
