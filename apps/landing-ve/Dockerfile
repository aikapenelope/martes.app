# =============================================================================
# Multi-stage build: builds both apps/landing-ve (VE) and apps/landing (US),
# then merges their dist/ outputs into a single nginx container.
#
# Final layout in /usr/share/nginx/html:
#   ./index.html            → VE landing (primary)
#   ./us-version/index.html → US landing
#   ./blog/...              → US blog
#   ./docs/...              → US docs
#   ./robots.txt            → VE robots
#   ./sitemap.xml           → VE sitemap
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: install deps for landing-ve
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps-ve
WORKDIR /app/landing-ve
COPY apps/landing-ve/package.json apps/landing-ve/package-lock.json* ./
RUN npm install --no-audit --no-fund

# -----------------------------------------------------------------------------
# Stage 2: install deps for landing (US)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps-us
WORKDIR /app/landing
COPY apps/landing/package.json apps/landing/package-lock.json* ./
RUN npm install --no-audit --no-fund

# -----------------------------------------------------------------------------
# Stage 3: build landing-ve (VE primary)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS build-ve
WORKDIR /app/landing-ve
COPY --from=deps-ve /app/landing-ve/node_modules ./node_modules
COPY apps/landing-ve/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 4: build landing (US + blog + docs)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS build-us
WORKDIR /app/landing
COPY --from=deps-us /app/landing/node_modules ./node_modules
COPY apps/landing/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 5: merge both builds into a single nginx root
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Copy VE build (primary landing)
COPY --from=build-ve /app/landing-ve/dist/ /usr/share/nginx/html/

# Copy US build (preserving structure under us-version/)
# We need to map:
#   /app/landing/dist/index.html        → /usr/share/nginx/html/us-version/index.html
#   /app/landing/dist/blog/             → /usr/share/nginx/html/blog/
#   /app/landing/dist/docs/             → /usr/share/nginx/html/docs/
#   /app/landing/dist/_astro/           → /usr/share/nginx/html/us-version/_astro/
#   /app/landing/dist/blog/_astro/      → /usr/share/nginx/html/blog/_astro/
#   /app/landing/dist/docs/_astro/      → /usr/share/nginx/html/docs/_astro/

# US landing root → us-version/
COPY --from=build-us /app/landing/dist/index.html /usr/share/nginx/html/us-version/index.html
COPY --from=build-us /app/landing/dist/_astro/     /usr/share/nginx/html/us-version/_astro/

# US blog → blog/
COPY --from=build-us /app/landing/dist/blog/ /usr/share/nginx/html/blog/

# US docs → docs/
COPY --from=build-us /app/landing/dist/docs/ /usr/share/nginx/html/docs/

# nginx config
COPY apps/landing-ve/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
