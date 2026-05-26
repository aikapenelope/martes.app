# Observabilidad — Cómo Ver Todo lo que Hacen los Agentes

> Guía completa de monitoreo para martes.app.
> Fuente: https://docs.agno.com/agent-os/tracing

---

## Arquitectura de observabilidad

```
Meta-agente (AgentOS)
│
├── tracing=True + OpenTelemetry instalado
│     └── Cada turno → span de ejecución guardado en ai.martes_traces
│           ├── Qué tool se llamó y cuánto tardó
│           ├── Qué modelo respondió
│           ├── Tokens consumidos y costo por paso
│           └── Errores y reintentos
│
├── Sesiones → ai.martes_sessions
│     └── Historial de conversaciones por usuario
│
├── Métricas → acumuladas en sessions.metrics
│     └── Cost, input_tokens, output_tokens, cache_read_tokens por sesión
│
└── os.agno.com (browser) → lee todo lo anterior via AgentOS API
      └── Acceso via SSH tunnel: http://localhost:8000
```

No se necesita backend externo (Jaeger, Zipkin, etc.). Las trazas se
guardan en PostgreSQL y os.agno.com las lee directamente via la API del AgentOS.

---

## Cómo conectarse a os.agno.com

El AgentOS corre en el VPS en el puerto 8000 (Tailscale) y 7777 (interno).
Para que os.agno.com pueda conectarse desde el browser, se usa un SSH tunnel
que expone el puerto 8000 del VPS como localhost en tu máquina.

### Comando de tunnel (ejecutar en tu terminal local)

```bash
ssh -L 8000:100.104.89.128:8000 root@204.168.169.254 -N
```

Deja esa terminal abierta mientras uses os.agno.com.

### Conectar en os.agno.com

1. Abre https://os.agno.com en tu browser
2. Click "Add new OS" (o selecciona el que ya tengas)
3. **Endpoint URL**: `http://localhost:8000`
4. **Environment**: Local
5. **CONNECT**

La conexión es browser → localhost:8000 (tunnel) → VPS:8000 (Tailscale) → AgentOS.
No necesitas el tunnel abierto todo el tiempo — solo cuando estés en os.agno.com.

---

## Qué puedes ver en os.agno.com

### Sessions (Conversaciones)
- Todas las conversaciones del meta-agente con el admin
- Para cada sesión: historial completo de mensajes
- Métricas acumuladas de la sesión (tokens, costo)

### Agents → Runs (Ejecuciones)
- Cada vez que el Diagnosticador o el Operador procesan un mensaje
- Qué tools llamaron (list_containers, create_tenant, etc.)
- Inputs y outputs de cada tool
- Duración de cada paso

### Traces (Trazas) — requiere OpenTelemetry
- Árbol de ejecución de cada turno con timing por step
- Modelo que respondió en cada paso
- Tokens y costo por llamada al LLM
- Errores y reintentos

### Knowledge
- Documentos indexados (hermes_reference.md, procedures.md)
- Permite buscar en la knowledge base manualmente

### Memory
- MEMORY.md y USER.md de los agentes
- Lo que el agente ha aprendido sobre el admin

---

## Dónde están los datos de tokens y costos

### Via Telegram (forma más rápida)
Mándale al meta-agente en Telegram:
```
cuanto hemos gastado
```
El Diagnosticador consulta la tabla `ai.martes_sessions` y reporta:
- Costo total acumulado
- Tokens usados por modelo
- Desglose: main model / learning / compression

### Via os.agno.com
Sessions → selecciona una sesión → tab "Metrics"
Muestra el desglose completo por modelo con:
- `cost`, `input_tokens`, `output_tokens`, `cache_read_tokens`
- Breakdown por `model` (turno principal), `learning_model`, `compression_model`

### Via API directa (desde terminal)
```bash
# Con el SSH tunnel activo:
curl -H "Authorization: Bearer <OS_SECURITY_KEY>" \
  http://localhost:8000/sessions | python3 -m json.tool

# El campo metrics.cost de cada session tiene el costo acumulado
# El campo metrics.details.model tiene el desglose por modelo
```

---

## Qué activa OpenTelemetry exactamente

### Sin OpenTelemetry (estado anterior)
- ✅ Sessions guardadas en DB
- ✅ Métricas de tokens/costo en sessions
- ❌ La tabla `ai.martes_traces` no se crea
- ❌ os.agno.com → tab Traces vacío
- ❌ No se puede ver el árbol de ejecución por turno

### Con OpenTelemetry (estado actual después del PR)
- ✅ Todo lo anterior
- ✅ Tabla `ai.martes_traces` con spans de ejecución
- ✅ os.agno.com → tab Traces muestra árbol completo
- ✅ Timing por tool call (cuánto tardó list_containers, create_tenant, etc.)
- ✅ Costo desglosado por step dentro del mismo turno

---

## Nota sobre el modo "Local" en os.agno.com

La conexión via SSH tunnel muestra el ambiente como "Local" en os.agno.com.
Esto NO limita lo que puedes ver — sesiones, runs, trazas, knowledge y memoria
son completamente visibles. "Local" solo indica el tipo de conexión (localhost),
no el entorno de producción del agente.

El OS_SECURITY_KEY protege el API: cualquier llamada sin el header
`Authorization: Bearer <key>` devuelve 401. os.agno.com usa este key
automáticamente una vez configurado al conectar.

---

## Referencias

- Tracing en AgentOS: https://docs.agno.com/agent-os/tracing
- Agno Sessions API: https://docs.agno.com/agent-os/using-the-api
- Conectar a os.agno.com: https://docs.agno.com/agent-os/connect-your-os
