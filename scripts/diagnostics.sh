#!/bin/bash

echo "=== System Diagnostics ==="
echo "Date: $(date)"
echo "Uptime: $(uptime)"
echo

echo "=== Docker Status ==="
docker-compose ps
echo

echo "=== Docker Logs (last 10 lines) ==="
docker-compose logs --tail=10
echo

echo "=== Disk Usage ==="
df -h
echo

echo "=== Memory Usage ==="
free -h
echo

echo "=== Database Connection ==="
docker-compose exec db pg_isready -U postgres
echo

echo "=== Redis Connection ==="
docker-compose exec redis redis-cli ping
echo

echo "=== Application Health ==="
curl -s http://localhost:8000/api/health/ || echo "Health check failed"
echo

echo "=== Recent Errors ==="
tail -20 logs/error.log 2>/dev/null || echo "No error log found"
