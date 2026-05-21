#!/bin/bash
set -e
echo "[deploy] Started at $(date)" >> /var/log/martes-deploy.log
cd /opt/martes
git pull origin main >> /var/log/martes-deploy.log 2>&1
docker compose -f infra/docker-compose.yml up -d --build >> /var/log/martes-deploy.log 2>&1
echo "[deploy] Done at $(date)" >> /var/log/martes-deploy.log
docker ps --format "{{.Names}}: {{.Status}}" >> /var/log/martes-deploy.log 2>&1
