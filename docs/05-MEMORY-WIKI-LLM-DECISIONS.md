# Martes.app — Memoria, Wiki, y LLM (Decisiones Finales)

> **Status**: Aprobado  
> **Date**: May 2026

---

## 1. Sistema de Memoria (Ya Incluido en Hermes)

Hermes tiene memoria persistente built-in. No necesitamos agregar nada:

| Componente | Qué hace | Dónde vive |
|-----------|----------|-----------|
| `MEMORY.md` | El agente escribe lo que aprende del usuario | `/opt/data/MEMORY.md` |
| `memory` tool | Guardar/recuperar notas persistentes | SQLite (state.db) |
| Session search | Buscar en conversaciones pasadas | SQLite FTS5 |
| Memory nudges | Auto-recordatorio de guardar info importante | Automático |

Cada miembro del equipo es identificado por su user_id de Telegram/Discord. El agente mantiene memoria separada por persona dentro del mismo container.

---

## 2. LLM Wiki — Activado en Todos los Tenants

El skill `llm-wiki` (basado en el patrón de Karpathy) crea una base de conocimiento en markdown que el agente construye y consulta:

```
/opt/data/wiki/
├── SCHEMA.md           → Define el dominio del equipo
├── index.md            → Catálogo de todo el conocimiento
├── log.md              → Historial de acciones
├── entities/           → Personas, empresas, productos
├── concepts/           → Procesos, metodologías
├── comparisons/        → Análisis comparativos
└── raw/                → Documentos fuente
```

### Cómo Funciona

- El agente lee documentos que el equipo le pasa (URLs, PDFs, texto)
- Los procesa y crea páginas wiki interconectadas
- Cuando le preguntan algo, consulta su wiki primero
- El conocimiento se acumula y mejora con el tiempo
- NO usa vectores/embeddings — usa búsqueda de texto + índice markdown

### Inyección Inicial por el Meta-Agente

Cuando se crea un tenant, el meta-agente escribe contenido base en el wiki:

```python
# El meta-agente inyecta durante el provisioning:

1. SCHEMA.md → Personalizado al dominio del equipo
2. raw/company-info.md → Información de la empresa
3. raw/team-members.md → Quién es quién en el equipo
4. raw/processes.md → Procesos internos documentados
5. entities/ → Páginas pre-creadas para cada miembro del equipo
```

El equipo puede seguir alimentando el wiki después:
- "Agente, lee este documento y agrégalo al wiki"
- "Agente, aquí está nuestro proceso de ventas, recuérdalo"
- El agente ingesta, procesa, y cross-referencia automáticamente

---

## 3. LLM / OpenRouter — Nosotros Proveemos la Key

### Decisión

Incluimos una API key de OpenRouter en el precio. El tenant no necesita configurar nada.

### Modelo por Defecto

**DeepSeek V4** via OpenRouter:
- Input: $0.30/M tokens (con 90% descuento en cache hits → $0.03/M)
- Output: $0.50/M tokens
- Costo estimado por tenant: **$2-5/mes** (uso moderado de PYME)
- Calidad: suficiente para tareas de oficina, email, scheduling

### Cómo Se Configura

En el `.env` del tenant (inyectado por el meta-agente):
```env
OPENROUTER_API_KEY=sk-or-v1-shared-key-with-rate-limit
DEFAULT_MODEL=deepseek/deepseek-chat
```

### Rate Limiting

OpenRouter soporta rate limits por API key. Podemos crear sub-keys por tenant:
- Starter: 100 requests/hora
- Pro: 500 requests/hora

O usar una sola key compartida y monitorear uso via OpenRouter dashboard.

### Upgrade de Modelo

Si un tenant quiere un modelo mejor (Claude, GPT-4.1):
- Opción A: Paga un tier más alto ($100/mo) → le ponemos Claude Haiku
- Opción B: BYOK → pone su propia key de Anthropic/OpenAI

---

## 4. No Necesitamos Embeddings

El LLM Wiki de Hermes NO usa RAG ni vectores. Funciona con:
- `search_files` (grep en los archivos markdown)
- `index.md` (catálogo manual mantenido por el agente)
- `[[wikilinks]]` (cross-references entre páginas)

Esto es más simple, más barato, y no requiere una API de embeddings separada.

Si en el futuro un tenant necesita RAG sobre documentos grandes (1000+ páginas), podemos agregar el plugin de memoria `holographic` o `mem0` que sí usan vectores. Pero para el MVP no es necesario.

---

## 5. Configuración Final por Template

### Template "Oficina" ($75/mo)

```yaml
# config.yaml (inyectado por meta-agente)
model:
  provider: openrouter
  model: deepseek/deepseek-chat

skills:
  - google-workspace
  - notion
  - airtable
  - himalaya
  - llm-wiki          # ← Wiki activado
  - ocr-and-documents

memory:
  provider: builtin   # Memoria built-in (MEMORY.md + session search)

tools:
  enabled:
    - web_search
    - memory
    - todo
    - clarify
    - cronjob
    - vision_analyze
    - skills_list
    - skill_view
```

### Template "Desarrollo" ($100/mo)

```yaml
model:
  provider: openrouter
  model: deepseek/deepseek-chat  # O claude-haiku si paga más

skills:
  - google-workspace
  - github-pr-workflow
  - github-code-review
  - github-issues
  - linear
  - notion
  - llm-wiki
  - ocr-and-documents
  - test-driven-development
  - systematic-debugging
  - writing-plans

memory:
  provider: builtin

tools:
  enabled:
    - web_search
    - web_extract
    - terminal
    - read_file
    - write_file
    - patch
    - search_files
    - memory
    - todo
    - clarify
    - cronjob
    - execute_code
    - delegate_task
    - vision_analyze
    - skills_list
    - skill_view
    - skill_manage
```

---

## 6. Lo Que Queda Por Fuera (Resolver Después)

| Item | Por qué no ahora |
|------|-------------------|
| Plugins de memoria avanzada (Honcho, Mem0) | Overkill para PYMEs. Agregar si hay demanda. |
| Embeddings/RAG | LLM Wiki cubre el 90% de casos sin vectores. |
| Custom skills por tenant | Complejidad. Primero validar con skills built-in. |
| WhatsApp gateway | Requiere Meta Business verification (semanas). |
| Modelo Claude/GPT incluido | Caro. DeepSeek V4 es suficiente para MVP. Upgrade como upsell. |
| Multi-idioma del agente | Hermes ya soporta 16 idiomas. Solo configurar en SOUL.md. |
