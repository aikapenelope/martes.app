---
name: blog-landing
description: Skill para crear y publicar artículos en el blog de martes.app. Genera posts en Markdown con el frontmatter correcto, los guarda en el repositorio y crea un PR. Úsalo cuando el admin pida escribir un artículo, anuncio o tutorial para el sitio web.
---

# Skill: Blog de martes.app

## Dónde viven los posts

```
apps/landing/src/content/blog/
├── que-es-martes-app.md
├── hermes-v0-14-0-novedades.md
├── primer-agente-5-minutos.md
└── [nuevo-post].md        ← aquí van los nuevos
```

## Estructura de un post

Cada archivo `.md` en `apps/landing/src/content/blog/` tiene este frontmatter:

```markdown
---
title: "Título del artículo"
description: "Una frase que describe el artículo. Aparece en la card del blog y en SEO."
date: "2026-06-15"          # ISO 8601 — fecha de publicación
tags: ["Producto", "Hermes"] # Entre 1 y 3 tags
author: "martes.app"         # Siempre este valor salvo que el admin diga otro
---

Contenido aquí en Markdown normal.
```

## Tags disponibles

| Tag | Cuándo usarlo |
|---|---|
| `Producto` | Anuncios, cambios, nueva funcionalidad del servicio |
| `Hermes` | Novedades de Hermes Agent, versiones, capacidades |
| `Tutorial` | Guías paso a paso para clientes o empresas |
| `LATAM` | Contexto venezolano, mercado latinoamericano |
| `Actualización` | Cambios técnicos, upgrades, fixes |
| `Caso de uso` | Historia de cómo una empresa usa el producto |

## Estructura del contenido

Un post bien hecho tiene:

1. **TL;DR al inicio** (si es técnico) — 2-3 líneas del resumen
2. **Secciones con `##`** — máximo 5-6 secciones
3. **Ejemplos de código** en bloques ``` cuando sea relevante
4. **CTA al final** — enlace a `#contacto` o al siguiente paso lógico

Longitud ideal: 600-1200 palabras. Nunca más de 2000.

## Estilo de escritura

- **Voz**: directa, sin rodeos, técnica pero accesible
- **Idioma**: español latinoamericano (sin voseo, sin "vos")
- **Tono**: profesional pero cercano — como explicarle a un colega
- **Headings**: concisos, en negativo si aplica ("Por qué no usamos X")
- **Sin**: exclamaciones excesivas, jerga de marketing, promesas vacías

## Cómo crear y publicar un post

### Paso 1: Generar el archivo

Crea `apps/landing/src/content/blog/[slug].md` donde `[slug]` es:
- Minúsculas, palabras separadas por guión
- Sin tildes ni caracteres especiales
- Descriptivo del contenido
- Ejemplo: `como-conectar-airtable-hermes.md`

### Paso 2: Verificar el build

```bash
cd apps/landing && npm run build
```

Si el build pasa (0 errores), el post está listo.

### Paso 3: Crear el PR

```bash
git checkout -b blog/[slug]
git add apps/landing/src/content/blog/[slug].md
git commit -m "blog: [Título del artículo]"
git push origin blog/[slug]
gh pr create --title "blog: [Título]" --body "[Descripción]"
```

### Paso 4: Merge y deploy

El admin mergea el PR → Coolify reconstruye la imagen → `martes.app/blog` muestra el nuevo post.

## Ejemplo de post completo

```markdown
---
title: "Cómo conectar Airtable con tu agente Hermes"
description: "Guía paso a paso para integrar Airtable y dejar que tu agente lea y escriba bases de datos automáticamente."
date: "2026-07-01"
tags: ["Tutorial", "Hermes"]
author: "martes.app"
---

## TL;DR

El skill de Airtable viene incluido en Hermes. Solo necesitas instalar el skill y conectar tu API key para que el agente pueda leer, crear y actualizar registros.

## Requisitos

- Un tenant activo en martes.app
- Una cuenta de Airtable (free tier funciona)
- Tu API key de Airtable

## Paso 1: Instalar el skill

Escríbele a tu bot:

\`\`\`
/skills install airtable
\`\`\`

El agente lo instala en segundos. Sin restart.

## Paso 2: Conectar tu API key

\`\`\`
inject_credential t001 airtable_key pat_xxxx
\`\`\`

## Paso 3: Úsalo

Ahora puedes pedirle cosas como:

\`\`\`
"Lista los registros de mi tabla Clientes donde Status = Activo"
"Crea un nuevo registro en Ventas con estos datos: ..."
"Sincroniza todos los contactos de esta semana a Airtable"
\`\`\`

---

¿Tienes preguntas? [Escríbenos aquí](/#contacto).
```
