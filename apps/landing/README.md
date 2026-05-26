# apps/landing — martes.app Landing Page

Servida en `https://martes.app` como **Application independiente en Coolify**.
No forma parte del stack del meta-agente (`infra/docker-compose.yml`).

---

## Estructura

```
apps/landing/
├── Dockerfile       ← nginx:alpine con stage de build opcional (Astro/Next.js)
├── nginx.conf       ← gzip, security headers, SPA routing, cache por tipo
├── index.html       ← página actual (puro HTML + Tailwind CDN + Three.js)
└── README.md
```

---

## Desplegar en Coolify (primera vez)

Desde la **UI de Coolify** (sin SSH al VPS):

1. **New Project** → o usa el proyecto existente
2. **New Resource** → **Application**
3. Tipo: **Dockerfile** → GitHub → `aikapenelope/martes.app`
4. Branch: `main`
5. **Base Directory**: `/`  ← repo root (IMPORTANTE — para que los COPY del Dockerfile funcionen)
6. **Dockerfile location**: `apps/landing/Dockerfile`
7. **Port**: `80`
8. **Domain**: `martes.app`
9. Let's Encrypt: activado (Coolify lo gestiona automáticamente)
10. **Deploy**

---

## DNS (en tu registrador de dominio)

```
martes.app    A    204.168.169.254    TTL: 300
```

Una vez que el DNS propague, Coolify emite el certificado y
`https://martes.app` queda activo con HTTPS.

---

## Actualizar el contenido

Editar `apps/landing/index.html` → crear PR → mergear a `main`
→ Coolify detecta el push y reconstruye la imagen automáticamente.

---

## Migrar a un framework (Astro, Next.js, Vite)

1. Crear el proyecto del framework en `apps/landing/`:
   ```
   apps/landing/
   ├── src/           ← código fuente
   ├── public/        ← assets estáticos
   ├── package.json
   └── astro.config.mjs  (o next.config.js, vite.config.ts, etc.)
   ```

2. Descomentar el **STAGE BUILD** en `Dockerfile` y ajustar el path de salida.

3. Cambiar la línea `COPY apps/landing/index.html ...` por el `COPY --from=builder` correspondiente.

4. El resto (nginx.conf, Coolify config, dominio) no cambia.
