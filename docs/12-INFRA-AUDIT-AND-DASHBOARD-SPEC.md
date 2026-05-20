# Martes.app — Analisis de Infraestructura Docker y Configuracion Hermes

> **Status**: Auditoria de produccion
> **Date**: May 2026
> **Hermes Version**: 0.14.0

---

## 1. Docker: Estado actual vs lo correcto

### Problema critico encontrado: cap_drop ALL

Nuestro `write_ops.py` hace `cap_drop: ["ALL"]` + `cap_add: ["NET_RAW"]`.

Pero el entrypoint de Hermes (`docker/entrypoint.sh`) necesita:
- `CHOWN` — para `chown -R hermes:hermes /opt/data`
- `SETUID` — para `usermod` y `gosu` (bajar privilegios)
- `SETGID` — para `groupmod`
- `DAC_OVERRIDE` — para escribir `/etc/passwd` durante `usermod`
- `FOWNER` — para `chmod` en archivos que no son del proceso

**Fix necesario** en `write_ops.py`:
```python
"cap_drop": ["ALL"],
"cap_add": ["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
```

Despues de que el entrypoint baja a usuario `hermes` via `gosu`, estas
capabilities se pierden (gosu las dropea). Asi que el proceso Hermes
corre sin privilegios, pero el entrypoint puede hacer su setup.

### Verificacion: lo que el entrypoint hace como root

1. `usermod -u $HERMES_UID hermes` — remapea UID
2. `groupmod -o -g $HERMES_GID hermes` — remapea GID
3. `chown -R hermes:hermes $HERMES_HOME` — fix ownership del volumen
4. `chown hermes:hermes config.yaml && chmod 640` — permisos de config
5. `exec gosu hermes "$0" "$@"` — re-exec como usuario hermes

Despues del paso 5, el proceso corre como UID 1000 (o lo que sea HERMES_UID)
sin ninguna capability elevada.

### Nuestro HERMES_UID=1000 vs default 10000

El Dockerfile crea `hermes` con UID 10000. Nosotros pasamos `HERMES_UID=1000`.
El entrypoint hace `usermod -u 1000 hermes` al arrancar.

**Esto funciona** pero agrega ~1-2 segundos al startup (usermod + chown).
Alternativa: usar UID 10000 y hacer `chown 10000:10000` en el host.

**Recomendacion**: Cambiar a UID 10000 (el default de Hermes) para evitar
el remapeo en cada restart. Menos overhead, menos posibilidad de error.

---

## 2. Configuracion de los 3 tiers: es correcta?

### Basico — CORRECTO con ajustes menores

| Setting | Nuestro valor | Valor correcto | Nota |
|---------|--------------|----------------|------|
| `platform_toolsets.telegram` | `[web, memory, todo, cronjob, clarify, session_search]` | OK | Minimo viable |
| `compression.threshold` | 0.30 | OK | Agresivo, ahorra tokens |
| `agent.max_turns` | 30 | OK | Suficiente para tareas simples |
| `tool_loop_guardrails.hard_stop` | true | OK | Critico |
| `security.allow_lazy_installs` | false | OK | Bloquea instalaciones |
| `streaming.enabled` | true | OK | Mejor UX |

**Falta**: `GATEWAY_ALLOW_ALL_USERS=false` en .env (fail-closed por default en v0.14.0)

### Equipo — CORRECTO

| Setting | Nuestro valor | Correcto? |
|---------|--------------|-----------|
| `platform_toolsets` | `[web, memory, todo, cronjob, clarify, vision, skills, session_search]` | SI |
| 2 plataformas | telegram + discord | SI |
| `compression.threshold` | 0.40 | SI |
| `agent.max_turns` | 50 | SI |

### Pro — NECESITA REVISION

| Setting | Nuestro valor | Problema |
|---------|--------------|---------|
| `platform_toolsets` | `[hermes-telegram]` | Incluye `terminal` — PELIGROSO sin sandbox |
| `terminal.backend` | `docker` | Requiere Docker-in-Docker o socket mount |
| `code_execution` | enabled | OK si terminal esta sandboxed |

**Problema del plan Pro**: El preset `hermes-telegram` incluye `terminal` y `file`.
Si el terminal backend es `docker`, Hermes necesita acceso al Docker socket
para crear containers sandbox. Pero nosotros NO montamos el socket en los
containers de tenants (solo el meta-agente lo tiene).

**Opciones para Pro**:
1. Montar Docker socket en tenants Pro (riesgo de seguridad)
2. Usar `terminal.backend: local` pero con `cwd: /opt/data/workspace` (limitado)
3. Quitar terminal del preset y usar toolsets individuales sin terminal
4. Usar Modal/Daytona como backend remoto (requiere API key adicional)

**Recomendacion**: Opcion 3 para el MVP. Usar toolsets individuales:
```yaml
platform_toolsets:
  telegram: [web, memory, todo, cronjob, clarify, vision, skills,
             session_search, browser, image_gen, tts]
  # Sin terminal, sin file, sin execute_code, sin delegate
```

Si un cliente Pro necesita terminal, se habilita caso por caso con
socket mount y documentacion de riesgo.

---

## 3. Puede Agno manejar/reparar problemas de Hermes?

### Lo que Agno PUEDE hacer:
- **Detectar** containers unhealthy (via DockerTools + health endpoint)
- **Reiniciar** containers que fallan (via write_ops con approval)
- **Leer logs** para diagnosticar (via DockerTools.get_container_logs)
- **Verificar** config.yaml y .env (via filesystem access al volumen)
- **Aprender** de incidentes pasados (LearningMachine)

### Lo que Agno NO puede hacer directamente:
- **Modificar config.yaml** de un tenant en caliente (requiere restart)
- **Resolver loops** dentro de Hermes (eso lo hace tool_loop_guardrails)
- **Detener un agente** que esta en medio de una ejecucion (solo puede parar el container)
- **Debuggear** problemas de red internos del container

### Como se complementan:

```
Hermes (auto-proteccion interna):
├── tool_loop_guardrails → detiene loops automaticamente
├── compression → maneja contexto largo
├── session_reset → limpia contexto periodicamente
└── memory flush → guarda antes de perder contexto

Agno (supervision externa):
├── Health checks periodicos → detecta containers caidos
├── Log analysis → identifica patrones de error
├── Auto-restart → reinicia containers unhealthy (con approval)
└── Learning → recuerda que funciono y que no
```

### Para resolver loops desde Agno:
No es necesario. Hermes v0.14.0 tiene `tool_loop_guardrails` con `hard_stop`.
Si un agente entra en loop:
1. Hermes detecta el patron (exact_failure, same_tool_failure)
2. Emite warning al usuario
3. Si persiste, hard_stop detiene la ejecucion
4. El usuario puede hacer /new para empezar sesion limpia

Si el hard_stop no funciona (bug en Hermes), Agno detecta via health check
que el container esta consumiendo CPU/memoria anormal y puede reiniciarlo.

---

## 4. Resumen de fixes necesarios

### Critico (afecta funcionamiento):
1. **cap_add** faltantes: agregar CHOWN, SETUID, SETGID, DAC_OVERRIDE, FOWNER
2. **Plan Pro terminal**: quitar terminal del preset o documentar riesgo

### Recomendado (mejora):
3. Cambiar HERMES_UID de 1000 a 10000 (evita usermod en cada restart)
4. Agregar `GATEWAY_ALLOW_ALL_USERS=false` al .env template (fail-closed)
5. Agregar `TELEGRAM_HOME_CHANNEL` al .env (para cron deliveries)

### Opcional (futuro):
6. Docker socket proxy para plan Pro (si se habilita terminal)
7. Webhook mode para Telegram en produccion (vs polling)

---

## 5. Dashboard (Opcion B) — Especificacion

### Flujo de usuario (cliente):
1. Cliente visita martes.app
2. Ve landing con pricing
3. Contacta por WhatsApp/email
4. Admin crea cuenta manualmente
5. Cliente recibe link de login
6. Dashboard muestra:
   - Estado de su agente (online/offline)
   - Plataformas conectadas
   - Uso del mes (mensajes, tokens estimados)
   - Integraciones activas
   - Boton para conectar nuevas integraciones (OAuth flow)

### Stack recomendado:
- **Frontend**: Next.js (static export) o Astro (SSG)
- **Auth**: Clerk o simple magic link
- **API**: El meta-agente expone datos via AgentOS API
- **Hosting**: Mismo servidor, servido por Traefik

### Endpoints necesarios (ya existen parcialmente):
- `GET /tenants/{code}` — info del tenant
- `GET /tenants/{code}/health` — estado del container
- `GET /tenants/{code}/usage` — metricas de uso
- `POST /tenants/{code}/integrations` — conectar integracion

### Prioridad: Sprint 4+ (no blocker para MVP)
El MVP funciona 100% via Telegram. El dashboard es una mejora de UX
para cuando haya 10+ clientes y el admin necesite visibilidad sin
hablarle al bot cada vez.
