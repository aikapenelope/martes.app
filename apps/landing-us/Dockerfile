FROM node:20-alpine AS base
WORKDIR /app

FROM base AS deps
COPY apps/landing-us/package.json apps/landing-us/package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY apps/landing-us/ ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/landing-us/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
