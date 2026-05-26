# Sprint G — Descartado

> **Estado**: cerrado  
> **Fecha**: junio 2026

---

## Resumen

El Sprint G fue descartado completamente. Los dos items que contenía resultaron innecesarios:

### `install_skill_in_tenant()` — obsoleto por PR #76

Con las restricciones de container eliminadas (cap_drop, pids_limit, tmpfs, security_opt),
Hermes tiene capacidades completas de fábrica. El cliente puede instalar skills
directamente desde Telegram sin intervención del admin:

```
Cliente → Hermes: "instala la skill de airtable"
Hermes → terminal tool: hermes skills install airtable
Hermes → /restart  (exit 75 → Docker lo levanta en segundos)
Hermes: "Skill de airtable instalada. Puedes usarla ahora."
```

No se necesita ningún tool en el meta-agente para esto.

### PocketBase CRM — descartado hasta Sprint I

Ver `docs/10-ROADMAP.md` sección "Descartado" para el razonamiento completo.

La investigación de arquitectura se conserva en:
- `docs/hermes-guia/07-POCKETBASE-CRM-INVESTIGACION.md`
- `docs/hermes-guia/08-ARQUITECTURA-POCKETBASE-COMPLETA.md`

---

## Sprint I (futuro)

Retomar PocketBase CRM cuando:
1. PocketBase alcance v1.0.0
2. El ecosistema MCP sea estable
3. Haya clientes reales que justifiquen el dashboard visual

Estimado: Q4 2026 – Q1 2027.
