# Hermes en Docker — Restart, Update y Experiencia de Usuario

> **Fuente**: Repo `nousresearch/hermes-agent` v0.14.0, gateway/run.py
> **Conclusión principal**: Hermes está diseñado para contenedores. No necesita Docker socket.

---

## La respuesta directa al problema

El texto que analizaste era de un agente Hermes corriendo en un contexto diferente
(Mastra Cloud). **En nuestro setup con `restart: unless-stopped`, el problema no existe.**

---

## Cómo funciona el restart en containers (Hermes lo sabe)

Hermes detecta automáticamente que está en un container:

```python
# gateway/run.py línea ~9720
_in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")
if _under_service or _in_container:
    self.request_restart(detached=False, via_service=True)
```

Cuando el usuario escribe `/restart` en Telegram:

```
Usuario: /restart
Hermes:  "Reiniciando... espera un momento"
         ↓
         Drena las conversaciones activas (espera que terminen)
         ↓
         Exit code 75
         ↓
Docker ve exit 75 → restart: unless-stopped lo revive
         ↓
Hermes arranca de nuevo → notifica al usuario en Telegram
         ↓
Usuario: "Gateway restarted." (mensaje automático)
```

**No necesita Docker socket. Docker ya lo maneja.**

---

## Configuraciones que definen la experiencia durante restart

### 1. Drain timeout — cuánto espera antes de forzar el cierre

```yaml
# config.yaml del tenant
agent:
  restart_drain_timeout: 60  # segundos para terminar la conversación activa
                              # 0 = interrupt inmediato
```

- Si hay una conversación activa cuando llega `/restart`, Hermes espera
  hasta `restart_drain_timeout` segundos para que termine.
- Si el tiempo se agota, interrumpe y marca la sesión como `resume_pending`.
- **Default**: 60 segundos (del código fuente)

### 2. busy_input_mode — qué pasa si el usuario escribe durante el drain

```yaml
display:
  busy_input_mode: queue   # "queue" | "interrupt" | "steer"
```

| Modo | Qué hace durante drain/restart |
|------|-------------------------------|
| `interrupt` | Interrumpe lo que está haciendo (default) |
| `queue` | Guarda el mensaje para después del restart |
| `steer` | Inyecta el mensaje al agente en curso |

**Para producción SaaS recomendado**: `queue` — el cliente escribe, el agente
responde cuando vuelve, sin perder el mensaje.

### 3. Auto-resume — retoma conversaciones interrumpidas

Hermes marca sesiones interrumpidas como `resume_pending`. Al bootear:

```python
# gateway/run.py — _schedule_resume_pending_sessions()
# Busca sesiones con resume_reason en:
# {"restart_timeout", "shutdown_timeout", "restart_interrupted"}
# Las auto-continúa cuando los adapters están listos
```

No necesita configuración extra. Sale de la caja.

### 4. Notificación de restart completado

Cuando el gateway vuelve online, busca `.restart_notify.json` y le avisa
al usuario que lo solicitó:

```
Hermes: "✓ Gateway restarted and ready."
```

---

## /update — Actualizar la versión de Hermes

### Cómo funciona en Docker

```python
# gateway/run.py línea ~13545
# /update solo funciona en git repos, NO en Docker images
if not git_dir.exists():
    return "not_git_repo"
```

**En Docker, `/update` no funciona.** Hermes sabe que en Docker el update
es `docker pull` + recrear el container. La actualización la hace el admin
(o el meta-agente Agno).

### La forma correcta de actualizar en nuestro SaaS

```bash
# El Operador Agno ejecuta esto (con approval):
# 1. Parar el container
docker stop hermes-t001
# 2. Pull imagen nueva
docker pull nousresearch/hermes-agent:0.15.0
# 3. Recrear con nueva imagen (mismos parámetros)
docker run ... nousresearch/hermes-agent:0.15.0 gateway run
```

El Operador ya tiene `restart_tenant()`. Necesita un `upgrade_tenant()` que
cambie la imagen.

---

## Docker socket: NO lo necesitan los tenants Hermes

### Qué necesita el Docker socket
- Crear/parar/listar containers
- Acceder a logs del daemon
- Crear redes

### Qué hace Hermes sin socket
- Reiniciarse: exit 75 → Docker lo reinicia ✓
- Actualizarse: `docker pull` desde fuera ✓
- Ver sus propios logs: `docker logs` desde fuera ✓

**El Docker socket solo lo necesita el meta-agente Agno** (para gestionar
todos los tenants). Los tenants individuales nunca lo necesitan.

Dar el Docker socket a un tenant Hermes sería darle control total del
servidor — peor que root.

---

## Configuraciones finales recomendadas por tier

### Basico
```yaml
agent:
  max_turns: 30
  restart_drain_timeout: 30   # Drain corto, clientes simples

display:
  busy_input_mode: queue      # Guardar mensajes durante restart
```

### Equipo
```yaml
agent:
  max_turns: 50
  restart_drain_timeout: 60   # Drain completo

display:
  busy_input_mode: queue
```

### Pro
```yaml
agent:
  max_turns: 60
  restart_drain_timeout: 120  # Proyectos largos, más tiempo

display:
  busy_input_mode: steer      # Poder redirigir sin interrumpir
```

---

## Lo que el cliente puede hacer sin intervención del admin

| Comando en Telegram | Qué hace | Interrumpe? |
|---------------------|----------|------------|
| `/restart` | Reinicia el gateway gracefully | No (espera drain) |
| `/new` | Nueva sesión (limpia contexto) | No |
| `/stop` | Para el gateway (requiere restart manual) | Sí |
| `/update` | No disponible en Docker | — |

## Lo que el admin hace desde Agno

| Acción | Tool | Interrumpe? |
|--------|------|------------|
| Restart suave | `restart_tenant()` → `docker restart` | Sí (SIGTERM) |
| Update imagen | `upgrade_tenant()` (pendiente) | Sí (recrear) |
| Stop por no-pago | `stop_tenant()` | Sí |

---

## El problema real: restart desde Agno interrumpe

`docker restart` envía SIGTERM → Hermes cierra → Docker lo reinicia.
Hermes auto-resume maneja las sesiones interrumpidas, pero hay un gap
de ~5-15 segundos donde el cliente no puede escribir.

**La forma correcta de restart sin interrumpir**:

```bash
# SIGUSR1 → graceful drain → exit 75 → Docker reinicia
# Esto es lo que hace /restart internamente
kill -USR1 $(docker inspect --format '{{.State.Pid}}' hermes-t001)
```

Este sería el tool correcto en el Operador en vez de `docker restart`.
