# Build both apps and merge their dist/ outputs.
# Final layout in /usr/share/nginx/html:
#   ./              → VE landing (primary)
#   ./us/           → US landing (original)
#   ./blog/         → US blog (assets from US, also exposed at /_astro/)
#   ./docs/         → US docs

FROM node:20-alpine AS deps-ve
WORKDIR /app/landing-ve
COPY apps/landing/package.json apps/landing/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS deps-us
WORKDIR /app/landing-us
COPY apps/landing-us/package.json apps/landing-us/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS build-ve
WORKDIR /app/landing-ve
COPY --from=deps-ve /app/landing-ve/node_modules ./node_modules
COPY apps/landing/ ./
RUN npm run build

FROM node:20-alpine AS build-us
WORKDIR /app/landing-us
COPY --from=deps-us /app/landing-us/node_modules ./node_modules
COPY apps/landing-us/ ./
RUN npm run build

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# VE primary at root
COPY --from=build-ve /app/landing-ve/dist/ /usr/share/nginx/html/

# US _astro at /us/_astro/ AND at root /_astro/ (blog/docs need it there)
# Different hashes per project → no collision with VE assets
COPY --from=build-us /app/landing-us/dist/_astro/ /usr/share/nginx/html/_astro/
COPY --from=build-us /app/landing-us/dist/_astro/ /usr/share/nginx/html/us/_astro/

# Fix _astro refs in us/index.html: /_astro/ → /us/_astro/
COPY --from=build-us /app/landing-us/dist/index.html /tmp/us-index.html
RUN sed 's|"/_astro/|"/us/_astro/|g' /tmp/us-index.html > /usr/share/nginx/html/us/index.html

# US blog and docs
COPY --from=build-us /app/landing-us/dist/blog/ /usr/share/nginx/html/blog/
COPY --from=build-us /app/landing-us/dist/docs/ /usr/share/nginx/html/docs/

COPY apps/landing/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
