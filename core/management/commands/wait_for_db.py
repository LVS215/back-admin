import time
from django.db import connections
from django.db.utils import OperationalError
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """Ожидание подключения к базе данных"""
    
    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        db_conn = None
        max_retries = 30
        retry_count = 0
        
        while not db_conn and retry_count < max_retries:
            try:
                db_conn = connections['default']
                db_conn.cursor()
                self.stdout.write(self.style.SUCCESS('Database available!'))
                return
            except OperationalError:
                self.stdout.write('Database unavailable, waiting 1 second...')
                time.sleep(1)
                retry_count += 1
        
        self.stdout.write(self.style.ERROR('Could not connect to database'))
        raise SystemExit(1)
