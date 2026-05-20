---
name: tenant-onboarding
description: "Flujo completo de onboarding de un cliente nuevo en martes.app"
license: MIT
metadata:
  tags: [onboarding, tenant, client, setup]
  category: operations
---

# Onboarding de Cliente Nuevo

## Prerequisitos (el admin debe tener)

1. **Nombre** del cliente/empresa
2. **Plan** acordado (basico $30, equipo $100, pro $200)
3. **Bot token** de Telegram (creado con @BotFather para el cliente)
4. **Email** de contacto (opcional)
5. **Pago confirmado** (transferencia, zelle, pago movil, crypto)

## Flujo paso a paso

### 1. Crear el bot de Telegram del cliente

El admin (tu) crea el bot:
1. Hablar con @BotFather en Telegram
2. `/newbot`
3. Nombre: "[Empresa] Assistant" o similar
4. Username: `empresa_assistant_bot` (debe terminar en `bot`)
5. Copiar el token (formato: `123456:ABC-DEF...`)

### 2. Decirle al meta-agente

```
Crea tenant [nombre] plan [plan] token [bot_token]
```

Ejemplo:
```
Crea tenant "Agencia Digital XYZ" plan equipo token 7891234:AAF-xyz123abc
```

### 3. El meta-agente ejecuta (automatico con aprobacion)

1. Registro en PostgreSQL (tenant_code asignado: t001, t002...)
2. Config en disco (template del plan copiado)
3. Container Docker creado con limites
4. Health check verificado
5. Status marcado como "active"

### 4. Post-creacion (opcional)

- **Conectar Google**: `Conecta google_token a t001 token ya29.xxx`
- **Conectar Notion**: `Conecta notion_key a t001 token ntn_xxx`
- **Inyectar wiki**: Crear contenido inicial sobre la empresa
- **Agregar usuarios**: Editar TELEGRAM_ALLOWED_USERS en .env

### 5. Informar al cliente

"Tu agente esta listo. Escribele a @empresa_assistant_bot en Telegram."

## Checklist post-onboarding

- [ ] Container running y healthy
- [ ] Bot responde al /start en Telegram
- [ ] Pago registrado en el sistema
- [ ] paid_until correcto (30 dias desde hoy)
- [ ] Cliente informado de como usar su agente

## Errores comunes en onboarding

| Problema | Causa | Solucion |
|----------|-------|----------|
| Bot no responde | Token incorrecto | Verificar con @BotFather |
| Container crash | .env mal formateado | Revisar logs |
| Health check falla | API server no habilitado | Verificar env vars |
| "Creating" indefinido | Error en algun paso | Revisar steps_completed en respuesta |
