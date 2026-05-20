---
name: tenant-management
description: "Procedimientos para gestionar tenants Hermes en martes.app"
version: 1.0.0
author: martes.app
platforms: [linux]
metadata:
  tags: [infrastructure, docker, tenants, hermes]
  category: operations
---

# Gestion de Tenants Hermes

## Crear Tenant Nuevo

### Prerequisitos
- Nombre del cliente
- Plan (basico $30/mo, equipo $100/mo, pro $200/mo)
- Bot token de Telegram (creado con @BotFather)

### Comando
```
Crea tenant [nombre] plan [plan] token [bot_token]
```

El Operador ejecuta el flujo completo:
1. Registro en PostgreSQL
2. Config en disco (template del plan)
3. Container Docker con limites
4. Verificacion de health

### Verificacion post-creacion
- Container status: running
- Health endpoint: respondiendo en <5s
- Telegram: el bot responde al /start

---

## Pausar Tenant (No Pago)

```
Pausa tenant [codigo]
```

- Detiene container (datos preservados)
- Marca status = 'paused' en DB
- El cliente no puede usar el bot hasta reactivar

---

## Reactivar Tenant

```
Reactiva tenant [codigo]
```

- Reinicia container
- Verifica health
- Marca status = 'active'

---

## Conectar Integracion

```
Conecta [servicio] a [codigo] token [valor]
```

Servicios soportados:
- google_token (OAuth JSON)
- notion_key
- airtable_key
- github_token
- linear_key

Despues de inyectar: restart del container para que Hermes cargue.

---

## Registrar Pago

```
Registra pago [codigo] $[monto] [metodo]
```

Metodos: transferencia, zelle, pago_movil, crypto
Calcula automaticamente period_start y period_end.

---

## Troubleshooting

### Container no arranca
1. Revisar logs: `logs [codigo]`
2. Errores comunes:
   - "Permission denied" → permisos del volumen
   - "Token must contain a colon" → bot token invalido
   - "OOM" → necesita mas RAM (upgrade plan)

### Container unhealthy
1. Verificar que esta corriendo
2. Intentar restart
3. Si persiste: revisar logs por errores de config

### Tenant no responde en Telegram
1. Container running + healthy?
2. Bot token correcto en .env?
3. TELEGRAM_ALLOWED_USERS no bloquea?
4. Restart para forzar reconexion
