# martes.app — Landing page (Astro)
# Build context: repo root (Coolify → Base Directory: "/")
# Dockerfile:    apps/landing/Dockerfile

# ── Stage 1: build Astro ─────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY apps/landing/package.json ./
RUN npm install
COPY apps/landing/ .
RUN npm run build
# Genera dist/ con HTML estático

# ── Stage 2: nginx sirve dist/ ───────────────────────────────────────────────
FROM nginx:alpine AS final
RUN rm /etc/nginx/conf.d/default.conf
COPY apps/landing/nginx.conf /etc/nginx/conf.d/landing.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
