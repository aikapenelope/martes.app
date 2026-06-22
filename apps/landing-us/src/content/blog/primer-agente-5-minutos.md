---
title: "Configura tu primer agente en 5 minutos"
description: "Guía paso a paso: desde cero hasta tener un Hermes respondiendo en Telegram. Solo necesitas un bot token de @BotFather y tu Telegram ID."
date: "2026-05-12"
tags: ["Tutorial", "Telegram", "Setup"]
author: "martes.app"
---

## De cero a un Hermes respondiendo en Telegram

Esta guia es para usuarios no tecnicos. Si puedes mandar un email, puedes seguir estos pasos.

**Tiempo total: 5 minutos.**

---

## Requisitos

- Una cuenta de Telegram (la que uses para chatear)
- 5 minutos
- Nada mas (nosotros hosteamos el resto)

---

## Paso 1: Habla con @BotFather (1 min)

En Telegram, busca `@BotFather` (cuenta oficial con check azul) y manda `/newbot`.

Te va a preguntar:

```
BotFather: Alright, a new bot. How are we going to call it?
Tu: Mi primer Hermes

BotFather: Good. Now let's choose a username for your bot.
Tu: mi_primer_hermes_bot
```

**Copia el token HTTP que te da.** Se ve asi:

```
7123456789:AAH_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
```

Guardalo. Lo necesitaras en el siguiente paso.

---

## Paso 2: Crear tu cuenta en martes.app (1 min)

Ve a [martes.app](https://martes.app) y registrate con tu email.

---

## Paso 3: Crear el tenant (2 min)

En el dashboard:
1. Click en "Nuevo tenant"
2. Nombre: el que quieras
3. Plataforma: **Telegram**
4. Token: el que copiaste en el paso 1
5. Click "Crear"

Espera 30 segundos. El sistema:
- Despliega un Hermes v0.14.0
- Lo conecta a tu bot de Telegram
- Le carga las skills built-in

---

## Paso 4: Probar

En Telegram, busca tu bot (el username que elegiste, ej `@mi_primer_hermes_bot`) y mandale:

```
Hola
```

Tu Hermes te responde.

---

## Que sigue

Ahora puedes:
- Agregar skills custom en el dashboard
- Conectarlo a Google Calendar, Drive, etc.
- Configurar automatizaciones recurrentes

Todo desde el panel. Sin tocar codigo.
