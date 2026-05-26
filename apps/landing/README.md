# martes.app — Landing page

Servida en producción via nginx:alpine en `infra/docker-compose.yml`.
Accesible en `https://martes.app`.

## Estructura

```
apps/landing/
├── index.html       ← página principal (reemplazar con el código final)
└── README.md
```

## Despliegue

El servicio `landing` en `infra/docker-compose.yml` sirve este directorio
con nginx. Cualquier cambio en esta carpeta redespliega automáticamente via
Coolify cuando se mergea a `main`.

## Para reemplazar el placeholder

Pega aquí tu código HTML/CSS/JS final. Si el frontend necesita un paso de
build (Next.js, Astro, Vite), se añade un `Dockerfile` en este directorio y
se actualiza el servicio en `docker-compose.yml`.
