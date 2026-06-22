# Build both apps and merge their dist/ outputs.
# Final layout in /usr/share/nginx/html:
#   ./              → VE landing (primary)
#   ./us/           → US landing (original)
#   ./blog/         → US blog
#   ./docs/         → US docs

FROM node:20-alpine AS deps-ve
WORKDIR /app/landing-ve
COPY apps/landing-ve/package.json apps/landing-ve/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS deps-us
WORKDIR /app/landing
COPY apps/landing/package.json apps/landing/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS build-ve
WORKDIR /app/landing-ve
COPY --from=deps-ve /app/landing-ve/node_modules ./node_modules
COPY apps/landing-ve/ ./
RUN npm run build

FROM node:20-alpine AS build-us
WORKDIR /app/landing
COPY --from=deps-us /app/landing/node_modules ./node_modules
COPY apps/landing/ ./
RUN npm run build

# VE primary at root
FROM nginx:1.27-alpine AS runtime
COPY --from=build-ve /app/landing-ve/dist/  /usr/share/nginx/html/

# US at /us/
COPY --from=build-us /app/landing/dist/index.html  /usr/share/nginx/html/us/index.html
COPY --from=build-us /app/landing/dist/_astro/      /usr/share/nginx/html/us/_astro/
COPY --from=build-us /app/landing/dist/blog/        /usr/share/nginx/html/blog/
COPY --from=build-us /app/landing/dist/docs/        /usr/share/nginx/html/docs/

COPY apps/landing-ve/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
