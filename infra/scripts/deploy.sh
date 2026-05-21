#!/bin/bash
set -e
LOG=/var/log/martes-deploy.log
echo "[deploy] Started at $(date)" >> $LOG
cd /opt/martes
git fetch origin main >> $LOG 2>&1
git checkout main >> $LOG 2>&1
git pull origin main >> $LOG 2>&1
# Rebuild and restart all services EXCEPT deploy-hook (would kill itself)
if docker compose version > /dev/null 2>&1; then
    docker compose -f infra/docker-compose.yml up -d --build \
        db meta-agent traefik portainer >> $LOG 2>&1
else
    docker-compose -f infra/docker-compose.yml up -d --build \
        db meta-agent traefik portainer >> $LOG 2>&1
fi
echo "[deploy] Done at $(date)" >> $LOG
docker ps --format "{{.Names}}: {{.Status}}" >> $LOG 2>&1
