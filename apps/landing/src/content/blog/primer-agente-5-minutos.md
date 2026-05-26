---
title: "Configura tu primer agente en 5 minutos"
description: "Guía paso a paso: desde cero hasta tener un Hermes respondiendo en Telegram. Solo necesitas un bot token de @BotFather y tu Telegram ID."
date: "2026-06-04"
tags: ["Tutorial", "Telegram", "Primeros pasos"]
author: "martes.app"
---

## Lo que necesitas antes de empezar

1. Una cuenta de Telegram
2. Un bot creado en [@BotFather](https://t.me/BotFather) — gratis, tarda 2 minutos
3. Tu Telegram ID numérico — lo obtiene [@userinfobot](https://t.me/userinfobot) en segundos

Eso es todo. No necesitas servidor, no necesitas cuenta AWS, no necesitas saber programar.

---

## Paso 1: Crea el bot en BotFather (2 min)

1. Abre Telegram y busca **@BotFather**
2. Envía `/newbot`
3. BotFather te pregunta el nombre del bot — escribe el nombre de tu empresa o cualquiera
4. BotFather te pregunta el username — debe terminar en `bot`, ej: `acme_corp_bot`
5. BotFather te responde con el **token** — se ve así: `123456789:AABBCCddEEFFggHHii...`

Guarda ese token. Lo necesitas en el siguiente paso.

---

## Paso 2: Obtén tu Telegram ID

1. Busca **@userinfobot** en Telegram
2. Envíale cualquier mensaje
3. Te responde con tu **User ID** — un número como `987654321`

---

## Paso 3: Escríbele al admin de martes.app

Envíale este mensaje al admin (por Telegram):

```
Quiero activar mi agente.
Nombre empresa: [tu empresa]
Bot token: [el token de BotFather]
Telegram ID: [tu número de @userinfobot]
```

El admin crea tu tenant en ~30 segundos. Recibirás confirmación cuando esté listo.

---

## Paso 4: Tu agente está activo

Abre el bot que creaste en BotFather y escríbele cualquier cosa. Hermes responde.

Desde el primer mensaje, Hermes:
- Empieza a aprender quién eres
- Tiene acceso a búsqueda web
- Puede ejecutar código Python
- Puede programar tareas automáticas
- Puede conectarse a tus herramientas (próximos pasos)

---

## Comandos útiles para empezar

```
/model                  → ver modelo actual y cambiarlo
/skills browse          → explorar skills disponibles
/skills install notion  → conectar Notion
/cron add               → programar una tarea automática
/memory                 → ver qué recuerda de ti
/help                   → ver todos los comandos
```

---

## Paso 5: Configura tu propia API key (opcional, recomendado)

El agente arranca con una platform key temporal (30 días). Para que el servicio continúe más allá, el cliente configura su propia key de OpenRouter:

1. Crea una cuenta en [openrouter.ai](https://openrouter.ai)
2. Genera una API key (gratis, pagas solo lo que usas)
3. Escríbele a tu agente:

```
Configura esta API key de OpenRouter: sk-or-v1-xxxxx
```

Hermes la configura solo, sin restart, efecto inmediato.

---

## Ejemplos de lo que puedes hacer desde el primer día

**Buscar información:**
```
"Busca las últimas noticias sobre IA en Venezuela y dame un resumen"
```

**Programar un informe:**
```
"Cada lunes a las 8am, recuérdame revisar los pagos pendientes de la semana"
```

**Conectar Airtable:**
```
"Instala el skill de Airtable y conecta mi base de datos de clientes"
```

**Automatizar:**
```
"Cuando alguien me escriba en este chat sobre una queja, guárdalo en la tabla 'Soporte' de mi Airtable"
```

---

¿Tienes preguntas? [Escríbenos aquí](#contact) o directamente al admin por Telegram.
