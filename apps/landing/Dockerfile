# martes.app — Landing page container
#
# Build context: repo root (Coolify pasa --project-directory=<repo-root>)
# Mismo patrón que apps/meta-agent/Dockerfile.
#
# El HTML se bake dentro de la imagen — sin bind mounts en producción.
# Para actualizar: editar apps/landing/ + mergear a main → Coolify rebuild.
FROM nginx:alpine

# Limpiar config por defecto de nginx
RUN rm /etc/nginx/conf.d/default.conf

# Config personalizada: gzip, cache headers, security headers
COPY apps/landing/nginx.conf /etc/nginx/conf.d/landing.conf

# Archivos estáticos baked en la imagen
COPY apps/landing/index.html /usr/share/nginx/html/index.html

EXPOSE 80

# nginx:alpine ya tiene su propio CMD (nginx -g 'daemon off;')
