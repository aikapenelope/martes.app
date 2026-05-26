# Martes.app — Plan Sprint 2+: Mejoras de Produccion

> **Status**: Aprobado, pendiente de implementacion
> **Date**: May 2026

---

## Prioridades Sprint 2 (Infraestructura)

1. Docker socket proxy (seguridad critica)
2. `inject_wiki_content()` tool
3. MCP server config en templates
4. Skills pre-instalados por plan
5. Health monitoring con scheduler Agno
6. `upgrade_tenant()` tool
7. Log rotation + resource alerts
8. `TELEGRAM_ALLOWED_USERS` por tenant

## Prioridades Sprint 3 (Produccion)

9. Backup automatizado (tar.gz → R2)
10. Egress control (bloquear metadata, redes internas)
11. PostgreSQL WAL archiving
12. Volume snapshots con pause/unpause
13. Honcho integration (plan Pro)
14. Shell hooks para audit trail

---

## Configuracion de Hermes: Preconfigurado vs Elaborado

### Automatico al crear tenant:
- `config.yaml` (template del plan)
- `.env` (credenciales)
- `SOUL.md` (personalidad)
- `skills/` (pre-instalados segun plan)

### Post-creacion via tools:
- Wiki inicial (`inject_wiki_content()`)
- OAuth tokens (`inject_credential()`)
- Skills adicionales (`install_skill()`)
- MCP servers (`update_tenant_config()`)
- Allowed users (`update_env_var()`)

---

## Secciones faltantes en config.yaml de templates

```yaml
streaming:
  enabled: true
  edit_interval: 0.3

stt:
  enabled: true

tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
  hard_stop_after:
    exact_failure: 3
    same_tool_failure: 5

code_execution:  # solo Pro
  timeout: 30
  max_tool_calls: 20

delegation:  # solo Pro
  max_iterations: 30
  max_spawn_depth: 1
```

---

## Skills pre-instalados por plan

| Plan | Skills |
|------|--------|
| Basico | llm-wiki, google-workspace |
| Equipo | + notion, airtable, ocr-and-documents |
| Pro | + github-pr-workflow, linear, code-execution |

---

## LLM Wiki: Inyeccion de conocimiento

El meta-agente crea la estructura wiki al crear tenant:
```
wiki/
├── SCHEMA.md          ← Dominio del cliente
├── index.md           ← Indice
├── log.md             ← Log
└── entities/
    └── company.md     ← Info basica
```

El agente Hermes luego expande organicamente.
