# Plan de Deploy Automatico via Dominio + HTTPS

> **Patron**: GitHub Actions → HTTPS webhook → Traefik → Deploy script
> **Prerequisito**: DNS configurado apuntando al servidor

---

## Por que este patron es mejor

| Aspecto | Webhook HTTP/9876 (anterior) | HTTPS via dominio (nuevo) |
|---------|------------------------------|--------------------------|
| Seguridad | Puerto abierto, HTTP plano | HTTPS con cert SSL |
| Autenticacion | Header secreto | Header secreto + TLS |
| Mantenimiento | Servidor Python custom | Traefik lo maneja |
| Debug | Logs manuales | Logs de Traefik |
| Estandar | No | Si (patron GitHub normal) |

---

## Paso 1: Configurar DNS

En tu registrador de dominio agregar estos registros A:

| Tipo | Host | IP | TTL |
|------|------|----|-----|
| A | @ | 204.168.169.254 | 300 |
| A | www | 204.168.169.254 | 300 |
| A | * | 204.168.169.254 | 300 |

El wildcard `*` cubre todos los subdominios de tenants (t001.martes.app, etc.)

**Si usas Cloudflare**: proxy OFF para todos (nube gris, no naranja).
Traefik necesita recibir la IP real del cliente para Let's Encrypt.

---

## Paso 2: Actualizar ACME_EMAIL en .env del servidor

```bash
ssh root@204.168.169.254
sed -i 's/ACME_EMAIL=.*/ACME_EMAIL=tu@email.com/' /opt/martes/infra/.env
```

Traefik usara este email para registrar los certificados SSL con Let's Encrypt.

---

## Paso 3: Levantar el deploy endpoint via Traefik

Un container minimo que solo recibe el webhook y ejecuta el deploy script.
Traefik le da HTTPS automaticamente.

En `docker-compose.yml` agregar:

```yaml
deploy-hook:
  image: python:3.12-slim
  container_name: martes-deploy-hook
  restart: unless-stopped
  command: python /app/webhook.py
  volumes:
    - /opt/martes:/opt/martes:ro         # acceso read-only al repo
    - /var/run/docker.sock:/var/run/docker.sock  # para correr deploy
    - ./deploy-hook.py:/app/webhook.py:ro
  environment:
    DEPLOY_SECRET: ${DEPLOY_WEBHOOK_SECRET}
  networks:
    - platform-net
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.deploy.rule=Host(`deploy.martes.app`) && Path(`/webhook`)"
    - "traefik.http.routers.deploy.tls.certresolver=letsencrypt"
    - "traefik.http.services.deploy.loadbalancer.server.port=9876"
  deploy:
    resources:
      limits:
        memory: 64M
```

---

## Paso 4: GitHub Actions limpio

Con el dominio configurado, el workflow es simple y estandar:

```yaml
# .github/workflows/cd.yml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger deploy
        run: |
          curl -fsSL \
            -X POST \
            -H "X-Deploy-Secret: ${{ secrets.DEPLOY_SECRET }}" \
            -H "Content-Type: application/json" \
            -d '{"ref":"main"}' \
            https://deploy.martes.app/webhook
```

Solo 1 secret en GitHub: `DEPLOY_SECRET`.

---

## Paso 5: Flujo completo

```
Push a main en GitHub
        ↓
GitHub Actions (ubuntu-latest)
        ↓ POST https://deploy.martes.app/webhook
        ↓ Header: X-Deploy-Secret: CLZ_VTIeMK0...
        ↓
Cloudflare/DNS → 204.168.169.254:443
        ↓
Traefik (Let's Encrypt cert) → desencripta HTTPS
        ↓
Container deploy-hook:9876
        ↓ Verifica secret header
        ↓ git pull origin main
        ↓ docker compose up -d --build
        ↓
Responde 200 OK → GitHub Actions: success ✓
```

---

## Orden de ejecucion cuando tengas el DNS

1. Configurar registros DNS en tu registrador
2. Esperar propagacion (~5 min con TTL 300)
3. Verificar: `nslookup deploy.martes.app` debe resolver a `204.168.169.254`
4. Actualizar `ACME_EMAIL` en el .env del servidor
5. Agregar el servicio `deploy-hook` al docker-compose
6. `docker compose up -d` → Traefik genera el cert automaticamente
7. Crear el GitHub Actions workflow
8. Agregar solo 1 secret en GitHub: `DEPLOY_SECRET`
9. Push a main → primer deploy automatico

---

## Mientras tanto (sin dominio)

El deploy es manual:
```bash
ssh root@204.168.169.254
cd /opt/martes && git pull origin main
docker compose -f infra/docker-compose.yml up -d --build
```

O via Tailscale (si tienes la clave):
```bash
ssh root@100.104.89.128  # IP de Tailscale
```
