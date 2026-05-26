# Mejores Prácticas — Hermes en Producción

> **Audiencia**: operadores de martes.app y clientes que configuran su propio Hermes  
> **Nivel**: operacional — enfocado en qué funciona, qué evitar, y cómo maximizar el valor

---

## 1. Configuración del SOUL.md — La personalidad del agente

El archivo `SOUL.md` es el system prompt de Hermes. Es lo primero que hay que configurar bien porque define el tono, el rol, y los límites del agente.

### Estructura recomendada

```markdown
# [NOMBRE DEL NEGOCIO] — Asistente de [ROL]

## Quién eres
Eres [nombre del agente], el asistente de atención al cliente de [empresa].
Eres venezolano, conoces el mercado local, y hablas de forma cercana y profesional.

## Tu misión principal
[Describir 1-2 oraciones el objetivo principal del agente]

## Lo que puedes hacer
- [Acción concreta 1]
- [Acción concreta 2]
- [etc.]

## Lo que NO haces
- Jamás confirmas un precio sin verificar el inventario actual
- Nunca ofreces descuentos sin consultar primero
- No das información personal de otros clientes

## Tono y estilo
- Cercano y amable, sin ser excesivamente informal
- Usa "tú" (no "usted"), salvo que el cliente hable de usted
- Emojis con moderación — máximo 1-2 por mensaje
- Mensajes cortos — máximo 3-4 líneas para respuestas simples

## Cuando no puedes resolver algo
Di: "Para eso necesito conectarte con [nombre del dueño]. ¿Te parece si te llamo en [tiempo]?"
```

### Errores comunes en SOUL.md
- ❌ Demasiado largo — el agente se pierde y no lo sigue bien
- ❌ Vago — "sé útil" no le dice nada al LLM
- ❌ Sin límites claros — el agente puede comprometerse a cosas imposibles
- ✅ Específico, corto, con ejemplos concretos de respuestas

---

## 2. Selección de modelo — Costo vs calidad

### Matriz de decisión para Venezuela

| Uso | Modelo recomendado | Costo aproximado | Por qué |
|---|---|---|---|
| Atención al cliente simple (FAQs, pedidos) | `deepseek/deepseek-v4-flash` | ~$0.001/mensaje | 1M contexto, muy barato, español fluido |
| Generación de contenido creativo | `anthropic/claude-3.5-haiku` | ~$0.003/mensaje | Mejor calidad en copywriting |
| Análisis complejo (reportes, estrategia) | `openai/gpt-4o-mini` | ~$0.002/mensaje | Balance precio/calidad |
| Tareas largas (documentos, análisis extenso) | `x-ai/grok-4.3` | ~$0.005/mensaje | 1M contexto, bueno para contexto largo |

### Estimación de costos reales por cliente (PyME típica)
- 50 mensajes/día × $0.001/mensaje = **$0.05/día = $1.50/mes** en tokens
- 100 mensajes/día: ~$3/mes en tokens
- Generación de 5 posts/semana: ~$0.50/semana adicional

El costo de tokens es insignificante vs el valor generado.

### Cambiar modelo al vuelo
El cliente puede cambiar el modelo desde Telegram: `/model deepseek/deepseek-v4-flash`
No require reiniciar el agente. El cambio aplica en el próximo mensaje.

---

## 3. Configuración del config.yaml

El archivo `config.yaml` es el segundo nivel de configuración. Ejemplos prácticos:

```yaml
model:
  default: deepseek/deepseek-v4-flash  # Modelo principal
  temperature: 0.7                      # 0 = más determinístico, 1 = más creativo

agent:
  max_iterations: 15    # Máximo de pasos por tarea (subir si hace tareas complejas)
  approval_mode: smart  # auto | smart | manual

memory:
  enabled: true
  max_items: 1000       # Cuántos recuerdos mantener

telegram:
  allowed_users: [TU_TELEGRAM_ID]  # Importante para seguridad
```

---

## 4. Skills — Cuándo y cómo configurarlas

### Regla general
**No instales skills que no necesitas.** Cada skill añade contexto al system prompt y puede interferir con el comportamiento base.

### Stack recomendado para PyME venezolana

**Mínimo viable (sin instalar nada extra)**:
- Búsqueda web (incluida por defecto)
- Terminal/código
- Manejo de archivos

**Para comercio/retail**:
```bash
hermes skills install airtable     # Inventario y pedidos
hermes skills install google-workspace  # Gmail + Sheets
```

**Para contenido y marketing**:
```bash
hermes skills install notion       # Planificación de contenido
# FAL.ai para imágenes viene built-in (via Nous Portal o API key)
```

**Para análisis financiero**:
```bash
hermes skills install stocks       # Precios de crypto en tiempo real (sin API key)
```

### Configuración de credentials
Las skills necesitan sus API keys en el `.env` del tenant. Hermes las pide via el configurador:
```bash
hermes skills install shopify
# Pide: SHOPIFY_ACCESS_TOKEN, SHOPIFY_STORE_DOMAIN
```

Para clientes de martes.app: usar `inject_credential()` del meta-agente.

---

## 5. Automatizaciones (Cron) — Patrones que funcionan

### Patrón 1: Reporte matutino
```
# Se configura una vez, corre todos los días
"Todos los días a las 7am:
  - Consulta cuántos pedidos nuevos llegaron ayer en Airtable
  - Verifica el stock de los 5 productos más vendidos
  - Envíame un resumen por Telegram con lo que necesita atención"
```

### Patrón 2: Vigilancia de precio del dólar
```
"Cada hora de 9am a 6pm de lunes a viernes:
  - Consulta el precio del USDT en Binance P2P para Venezuela
  - Si cambió más del 2% desde la última consulta, notifícame"
```

### Patrón 3: Publicación de contenido
```
"Cada martes y jueves a las 11am:
  - Lee los 2 productos más vistos esta semana en mi Airtable
  - Genera un post de Instagram con emoji y hashtags venezolanos relevantes
  - Envíame las opciones para que elija cuál publicar"
```

### Patrón 4: Seguimiento de pagos pendientes
```
"Cada día a las 5pm:
  - En mi Airtable, busca pedidos con status 'esperando pago' de hace más de 24h
  - Para cada uno, envía un recordatorio de pago al cliente por WhatsApp
  - Registra que se envió el recordatorio"
```

### Errores comunes en automatizaciones
- ❌ Automatizaciones que escriben sin supervisión en redes sociales (siempre mejor pedir aprobación primero)
- ❌ Cron demasiado frecuente con calls API costosas
- ✅ Empezar con notificaciones (sin acciones) y agregar acciones gradualmente

---

## 6. WhatsApp Business — Configuración correcta

### Modo de operación
Hermes con WhatsApp Business API actúa como asistente en nombre del número de la empresa. **No reemplaza** al humano — escala la capacidad.

### Principios operativos
1. **Identify as AI**: si el cliente pregunta "¿Eres un robot?", Hermes debe responder honestamente
2. **Escalation path claro**: siempre hay una forma de hablar con un humano
3. **Horario de respuesta humana**: el agente puede manejar todo 24/7, pero comunicar cuándo hay soporte humano adicional

### Template de respuesta fuera de horario
```
"Hola [nombre]! 👋 Soy el asistente de [empresa]. 
Puedo ayudarte con consultas de productos, precios y pedidos ahora mismo.
¿En qué te puedo ayudar?"
```

---

## 7. Memoria — Cómo funciona en la práctica

### Qué recuerda Hermes por defecto
- Lo que el cliente le dijo explícitamente ("trabajo en el sector construcción")
- Sus preferencias de producto manifestadas en conversaciones anteriores
- Pedidos anteriores y su estado
- El nombre del cliente (si se identificó)

### Qué NO recuerda automáticamente
- Información de pagos que no pasó por el sistema
- Conversaciones de otros canales (a menos que se configuren juntos)
- Lo que el dueño hizo manualmente fuera del agente

### Buenas prácticas de memoria
- Instruir en SOUL.md: "Cuando un cliente se identifique, recuerda su nombre y úsalo en conversaciones futuras"
- No sobrecargar la memoria — Hermes puede colapsar si tiene demasiados "recuerdos" irrelevantes
- Revisar la wiki del agente (`/wiki` en Telegram) para ver qué está recordando

---

## 8. Seguridad — Lo esencial

### Para clientes de martes.app
✅ Ya configurado: `TELEGRAM_ALLOWED_USERS` restringe quién puede hablar con el meta-agente  
✅ Ya configurado: cada tenant tiene su propia red Docker aislada  
✅ Ya configurado: credenciales en `.env` con `chmod 600`  

### Para configuraciones propias
- **SIEMPRE** configurar `TELEGRAM_ALLOWED_USERS` o `TELEGRAM_ALLOWED_CHATS`
- **NUNCA** exponer el dashboard (puerto 9119) sin autenticación delante
- **REVISAR** el modo de aprobación: en producción, `smart` o `manual` para operaciones que toquen dinero
- Hacer backup semanal del volumen del agente (`backup_tenant()` si usa martes.app)

### Nivel de acceso del agente
Hermes tiene acceso completo al sistema dentro de su container. Puede leer y escribir archivos, ejecutar código, y hacer llamadas de red. Esto es por diseño — es lo que lo hace poderoso. La seguridad está en la configuración correcta de los permisos y el `SOUL.md`.

---

## 9. Métricas de éxito — Cómo saber que está funcionando

### Métricas de negocio (las que importan)
- Tiempo de respuesta promedio (antes vs después)
- Tasa de conversión de consultas a pedidos
- Volumen de pedidos gestionados sin intervención humana
- Horas/semana ahorradas en atención al cliente

### Métricas de operación del agente (técnicas)
- Uptime del container (via `check_all_health()` en martes.app)
- Response time del health check (via Metabase)
- Errores clasificados en `error_logs`
- Consumo de tokens/semana (via dashboard de OpenRouter)

### Señal de que necesita ajuste
- El cliente responde "no entendí lo que dijiste" frecuentemente → mejorar SOUL.md
- El agente se va por las ramas y hace cosas no pedidas → reducir `max_iterations` o agregar límites en SOUL.md
- Respuestas muy largas que confunden → instruir explícitamente en SOUL.md "respuestas máximo 3 líneas para preguntas simples"

---

## 10. Actualizaciones — Cuándo y cómo

### Hermes se actualiza frecuentemente (vAÑO.MES.DIA)
- v0.14.0 = v2026.5.16
- Próxima versión estable estimada: ~junio-julio 2026

### Estrategia de actualización para martes.app
1. Esperar al menos 1 semana después del release
2. Probar en un tenant de prueba primero (`upgrade_tenant("t_test", "nousresearch/hermes-agent:vNUEVO")`)
3. Verificar health y funcionalidad básica
4. Si todo ok, actualizar tenants activos uno a uno

### Qué revisar en cada actualización
- Breaking changes en `config.yaml`
- Cambios en `.env` variables
- Nuevas platforms o skills disponibles
- Mejoras de seguridad

El rollback automático está implementado en `upgrade_tenant()` — si el nuevo container no pasa el health check en 30 segundos, regresa a la versión anterior.
