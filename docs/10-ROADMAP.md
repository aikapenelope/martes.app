# Roadmap — martes.app

> **Estado a**: 2 junio 2026  
> **Sistema**: Producción — 1 tenant activo (t001), 1 archivado (t002 → purgeado pendiente)  
> **Stack**: Hetzner CX43 · Coolify · Agno AgentOS 2.6.8 · SeaweedFS 4.28 · Hermes v2026.5.16 · Metabase v0.61.2.6  
> **PRs abiertos**: ninguno

---

## ✅ Completado

### Sprints A, B, C, D, F (PRs #57–68)

Todos los sprints de robustez, producción, backups, hardening y gaps operativos
están implementados y en main. Ver `CHANGELOG.md` para el detalle completo.

**Resumen de lo que se implementó:**
- A3: validación Pydantic (Literal types, regex bot_token, validación numérica)
- A1: resolución nombre→código en ambos agentes
- A2: EntityMemory wire-up + db=db en LearningMachine
- B0: health-check + billing-check automáticos con alertas Telegram
- B1: get_server_capacity()
- B2: diagnose_container_error() con clasificación automática
- B3: upgrade_tenant() con rollback automático
- C3: lifecycle rules SeaweedFS (expiración 30 días)
- D2: fix SeaweedFS healthcheck (puerto 8888→8333/healthz)
- Fix health check localhost→127.0.0.1
- recreate_tenant_container() para restore tras delete
- Fix restore: _restore_filter para symlinks de uv
- purge_archived_tenant() + skill COMANDOS
- Billing SaaS: trial 30d, alertas escalonadas, auto-suspend
- find_stale_resources() + docker-cleanup semanal
- Gitleaks CI + cloud-init cleanup
- Metabase v0.61.2.6 en compose (solo Tailscale)
- Platform key expiry (BYOK bootstrapping, TTL 2h, auth.json detection)
- health_checks y error_logs ahora se pueblan desde el código
- F4: gitleaks secret scanner en CI
- F5: red `martes-tenants` eliminada del cloud-init

---

## Operacional pendiente

*No es código — son acciones que el admin ejecuta en el servidor o via el bot.*

| Item | Qué hacer | Prioridad |
|---|---|---|
| **C1** | Test completo backup→restore: backup t001 → stop → borrar volumen → restore → recreate → health → mensaje Telegram | 🔴 Antes de E1 |
| **C2** | Verificar backup automático: `GET http://100.104.89.128:8000/schedules/{id}/runs` → status=success, triggered_at≈03:00 UTC | 🟡 Verificación |
| **D1** | Test `register_payment()` con t001 real: registrar pago → verificar `paid_until` en DB → verificar en Metabase | 🟡 Test |
| **Metabase setup** | Primer login → conectar `db:5432` con schema `public` únicamente → ocultar `martes_knowledge` en Data Model → crear dashboards | 🟡 Configuración |

---

## Sprint Metabase — Dashboards recomendados

*Una vez configurado el acceso, crear estas vistas en Metabase.*

### Dashboard 1 — Tenants
Pregunta a Metabot: *"muéstrame todos los tenants activos con su paid_until y días restantes"*

| Métrica | Tabla | Campo |
|---|---|---|
| Tenants activos hoy | `tenants` | `status = 'active'` |
| Vencen esta semana | `tenants` | `paid_until BETWEEN today AND today+7` |
| Revenue acumulado | `payments` | `SUM(amount)` por mes |
| Distribución por modelo | `instance_configs` | `GROUP BY model` |

### Dashboard 2 — Uptime
Pregunta a Metabot: *"historial de health checks de t001 esta semana"*

| Métrica | Tabla | Campo |
|---|---|---|
| Uptime % por tenant | `health_checks` | `COUNT(status='healthy') / COUNT(*)` |
| Response time promedio | `health_checks` | `AVG(response_ms)` |
| Incidentes sin resolver | `error_logs` | `resolved = false` |

---

## Pendiente de código

### Alta prioridad

**`inject_credential` con `openrouter_api_key`** — Cuando el admin inyecta la key propia del cliente via `inject_credential()`, el marker `.platform_key_expires` debe borrarse inmediatamente en lugar de esperar el ciclo de 30 min. Requiere añadir `openrouter_api_key` a la lista de tipos de `inject_credential` y borrar el marker en el mismo acto.

```python
# En inject_credential(), si credential_type == "openrouter_api_key":
marker_file = tenant_path / _PLATFORM_KEY_EXPIRES_FILE
marker_file.unlink(missing_ok=True)   # cleanup inmediato
```

**`martes_traces` pruning** — La tabla `ai.martes_traces` crece con cada llamada LLM. Sin limpiarla, puede acumular cientos de miles de filas/año. Añadir un schedule semanal que ejecute:

```sql
DELETE FROM martes_traces WHERE created_at < NOW() - INTERVAL '30 days';
```

También aplica a `martes_sessions` antiguas (sesiones > 90 días sin actividad).

### Media prioridad

**`health_checks` pruning** — Similar a traces. Con 5 tenants × cada-5-minutos = 1,440 filas/día. A 30 días: 43,200 filas. Manejable, pero conviene un schedule semanal de limpieza para datos > 90 días.

**Billing agent (Agno conversacional)** — Un tercer agente junto al Operador y Diagnosticador, especializado en consultas de billing. Le preguntarías al bot: *"¿quiénes vencen esta semana?"*, *"¿cuánto revenue llevo este mes?"*. Lee de DB, no escribe. ~50 líneas de código. Complementa a Metabase para consultas ad-hoc desde Telegram.

---

## Sprint E — Producto

### E1 · Primer cliente real (beta)

**Bloqueante**: C1 (test backup→restore) debe completarse antes.

Pre-requisitos checklist:
- [ ] C1 ejecutado sin errores end-to-end
- [ ] Billing-check configurado y probado con fecha real
- [ ] Metabase configurado para ver el cliente

Flujo de onboarding:
```
1. Admin: "crea tenant [nombre] token [bot_token] telegram_id [id]"
   → paid_until se setea automáticamente a hoy + 30 días (trial)
   → .platform_key_expires también creado (TTL 2h)

2. Cliente configura su propia OpenRouter key en Hermes
   → Platform key expira y desaparece automáticamente

3. Admin: "registra pago de [tenant] $30 transferencia"
   → paid_until se extiende 30 días desde la fecha actual

4. billing-check corre diariamente
   → recordatorio a 7 días y 3 días antes
   → auto-suspend si no hay pago tras grace period
```

### E2 · upgrade_tenant() en producción

Cuando NousResearch publique la siguiente versión estable de Hermes:
1. Revisar release notes para breaking changes en `config.yaml` o `.env`
2. `upgrade_tenant("t001", "nousresearch/hermes-agent:vNUEVO")` primero
3. Verificar health + mensaje de prueba en Telegram
4. Si ok: upgradar todos los tenants activos uno a uno

---

## Descartado — Hermes dashboard por tenant

**Investigación completada (junio 2026):** El dashboard de Hermes (puerto 9119) usa un token de sesión efímero inyectado en el HTML. No tiene autenticación propia, solo localhost binding por diseño.

Para exponerlo por tenant se necesitaría:
- Un segundo container por tenant (`hermes-dashboard-tXXX`)
- Wildcard DNS `*.dashboard.martes.app`
- Traefik con basic auth por subdomain
- Doble el número de containers en el servidor

**Conclusión**: No justifica la complejidad ni el riesgo (el dashboard expone API keys y config completa del cliente). Los clientes gestionan su bot desde Telegram con los comandos de Hermes (`/model`, `/skills`, `/status`, etc.).

---

## Capacidad del servidor (referencia)

| Configuración | Tenants |
|---|---|
| 768 MB / 0.75 CPU (estándar) | ~17 máximo |
| Uso real idle (~200 MB) | ~60 caben |
| **Práctica segura** | **20–25 tenants** |

Para escalar: upgrade a CX53 (32GB, €45/mes) o segundo servidor dedicado a tenants.

Con `get_server_capacity()` implementado, el agente da este cálculo en tiempo real.

---

## Lecciones aprendidas

Ver la sección completa en `CHANGELOG.md` → Notas técnicas.

Adiciones recientes:
1. Agno usa schema `"ai"` para sus tablas — schema `"public"` es exclusivo de martes.app
2. Hermes dashboard: no exponer sin una capa de auth robusta delante (Basic Auth mínimo)
3. `tarfile.FilterError` en Python 3.12: capturar en lugar de propagar para restores robustos
4. BYOK bootstrapping: proveer platform key inicial + TTL de expiración es el estándar de la industria para agentes SaaS
5. `auth.json` en el volumen del tenant = evidencia de que el cliente configuró su propia auth, independiente del proveedor
