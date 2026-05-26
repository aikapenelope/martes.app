# =============================================================================
# martes.app — Landing page
# =============================================================================
#
# Build context: repo root  (Coolify → Base Directory: "/")
# Dockerfile:    apps/landing/Dockerfile
#
# Deploy standalone en Coolify como Application independiente del stack
# del meta-agente. Coolify gestiona SSL (Let's Encrypt) y routing.
#
# Para migrar a un framework (Astro, Next.js, Vite):
#   1. Añadir el proyecto del framework en apps/landing/
#   2. Añadir el stage de build abajo (ver comentario "STAGE BUILD")
#   3. El stage final (nginx) no cambia — solo el COPY cambia de origen
# =============================================================================

# -----------------------------------------------------------------------------
# STAGE BUILD (opcional — activar cuando el frontend necesite compilación)
#
# Ejemplo Astro:
#   FROM node:20-alpine AS builder
#   WORKDIR /app
#   COPY apps/landing/package*.json ./
#   RUN npm ci
#   COPY apps/landing/ .
#   RUN npm run build          # genera apps/landing/dist/
#
# Ejemplo Next.js static export:
#   FROM node:20-alpine AS builder
#   WORKDIR /app
#   COPY apps/landing/package*.json ./
#   RUN npm ci
#   COPY apps/landing/ .
#   RUN npm run build          # genera apps/landing/out/
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# STAGE FINAL — nginx sirve los archivos estáticos
# -----------------------------------------------------------------------------
FROM nginx:alpine AS final

# Limpiar config por defecto
RUN rm /etc/nginx/conf.d/default.conf

# Copiar nuestra config de nginx (gzip, security headers, cache)
COPY apps/landing/nginx.conf /etc/nginx/conf.d/landing.conf

# Copiar archivos estáticos baked en la imagen
# Cuando se active el stage build, cambiar por:
#   COPY --from=builder /app/dist /usr/share/nginx/html    # Astro
#   COPY --from=builder /app/out  /usr/share/nginx/html    # Next.js static
COPY apps/landing/index.html /usr/share/nginx/html/index.html

# Puerto interno — Coolify/Traefik hace el SSL externamente
EXPOSE 80

# nginx:alpine ya incluye CMD ["nginx", "-g", "daemon off;"]
