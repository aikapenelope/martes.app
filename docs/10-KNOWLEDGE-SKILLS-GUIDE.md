# Martes.app — Guia de Knowledge y Skills

## Donde va cada cosa

```
apps/meta-agent/src/
├── knowledge/              ← KNOWLEDGE (RAG con embeddings)
│   ├── hermes_reference.md
│   ├── procedures.md
│   └── config_reference.md
│
└── skills/                 ← SKILLS (lazy-loaded, bajo demanda)
    ├── tenant-management/
    │   └── SKILL.md
    ├── hermes-troubleshooting/
    │   └── SKILL.md
    ├── hermes-config/
    │   └── SKILL.md
    ├── backup-restore/
    │   └── SKILL.md
    ├── network-security/
    │   └── SKILL.md
    ├── monitoring-alerts/
    │   └── SKILL.md
    ├── tenant-onboarding/
    │   └── SKILL.md
    └── integrations/
        └── SKILL.md
```

---

## Knowledge (busqueda semantica via RAG)

### Que es
Documentos indexados en LanceDB con embeddings. El agente busca en ellos
cuando necesita contexto para responder. Usa busqueda semantica (no solo keywords).

### Donde se almacena
- **Archivos fuente**: `apps/meta-agent/src/knowledge/*.md` (en el repo)
- **Vectores**: `/var/lib/martes/meta-agent/lancedb/` (en el servidor, persistente)
- **Metadata**: PostgreSQL tabla interna de Agno

### Como agregar knowledge

#### Opcion 1: Desde el repo (recomendado)
1. Crear archivo `.md` o `.txt` en `apps/meta-agent/src/knowledge/`
2. Commit y push
3. En el servidor: `cd /opt/martes && git pull && docker compose -f infra/docker-compose.yml up -d --build meta-agent`
4. Se indexa automaticamente al arrancar (skip_if_exists=True, no duplica)

#### Opcion 2: Desde AgentOS UI (os.agno.com)
1. Conectar AgentOS: os.agno.com → Connect OS → URL del servidor
2. Sidebar → Knowledge
3. ADD NEW CONTENT → FILE / WEB / TEXT
4. Soporta: .pdf, .md, .txt, .csv, .json, .doc, .docx, .xlsx, .pptx
5. Se indexa inmediatamente

#### Opcion 3: Via el agente (wiki)
El Diagnosticador tiene tool `update_knowledge` que escribe en la wiki:
- Archivos en `/var/lib/martes/meta-agent/wiki/`
- Persiste entre reinicios (volumen montado)
- El agente puede guardar hallazgos automaticamente

### Formato recomendado para knowledge
```markdown
# Titulo del Documento

## Seccion 1
Contenido con datos especificos, numeros, comandos.

## Seccion 2
Mas contenido. Cuanto mas estructurado, mejor la busqueda.
```

---

## Skills (instrucciones lazy-loaded)

### Que es
Procedimientos paso a paso que el agente carga bajo demanda. No consumen
tokens hasta que se activan. El agente ve un resumen de skills disponibles
y carga el contenido completo solo cuando identifica que aplica.

### Donde se almacena
- **Archivos**: `apps/meta-agent/src/skills/{nombre}/SKILL.md` (en el repo)
- **No necesita base de datos** — se lee del filesystem al arrancar

### Como agregar una skill

#### Opcion 1: Manual en el repo
1. Crear carpeta: `apps/meta-agent/src/skills/{nombre-con-guiones}/`
2. Crear `SKILL.md` dentro con el formato correcto (ver abajo)
3. Commit, push, rebuild en servidor

#### Opcion 2: Via el Skill Builder (agente)
Decirle al meta-agente:
```
Crea una skill llamada "mi-nueva-skill" que explique [contenido]
```
El Skill Builder crea el archivo con formato correcto.

### Formato obligatorio de SKILL.md
```markdown
---
name: nombre-con-guiones
description: "Descripcion corta de la skill"
license: MIT
metadata:
  tags: [tag1, tag2]
  category: operations
---

# Titulo

## Seccion 1
Instrucciones paso a paso...

## Seccion 2
Mas instrucciones...
```

### Campos permitidos en frontmatter (SOLO estos):
- `name` (obligatorio): slug con guiones
- `description` (obligatorio): texto corto
- `license`: MIT
- `metadata`: objeto con tags y category
- `allowed-tools`: lista de tools que la skill puede usar
- `compatibility`: requisitos

### Campos NO permitidos (causan error):
- ~~version~~, ~~author~~, ~~platforms~~ → error de validacion

---

## Diferencia entre Knowledge y Skills

| | Knowledge | Skills |
|---|---|---|
| **Proposito** | Datos de referencia, hechos | Procedimientos, instrucciones |
| **Busqueda** | Semantica (embeddings) | Por nombre (lazy-load) |
| **Cuando se usa** | Agente busca cuando necesita contexto | Agente carga cuando identifica que aplica |
| **Tokens** | Solo los fragmentos relevantes | Contenido completo de la skill |
| **Persistencia** | LanceDB (volumen) + PostgreSQL | Filesystem (repo) |
| **Actualizacion** | Re-indexa al arrancar | Se recarga al arrancar |

### Regla general:
- **Datos, hechos, referencia** → Knowledge
- **Como hacer algo paso a paso** → Skill

---

## Persistencia (que sobrevive un restart)

| Dato | Donde | Sobrevive restart? |
|------|-------|-------------------|
| Sesiones del agente | PostgreSQL | SI |
| Memoria (learnings) | PostgreSQL + LanceDB | SI |
| Knowledge vectors | `/var/lib/martes/meta-agent/lancedb/` | SI |
| Wiki del agente | `/var/lib/martes/meta-agent/wiki/` | SI |
| Skills | En el repo (se copia al build) | SI |
| Datos de tenants | `/var/lib/martes/tenants/` | SI |
| PostgreSQL | `/var/lib/martes/pg-data/` | SI |

Todo esta montado como volumen en el host. Nada se pierde al reiniciar.

---

## Deploy / Redeploy

```bash
# En el servidor (204.168.169.254)
cd /opt/martes
git pull
docker compose -f infra/docker-compose.yml up -d --build meta-agent
```

Esto:
1. Baja los cambios del repo (nuevas skills, knowledge, codigo)
2. Rebuild la imagen del meta-agente
3. Recrea el container (volumenes persisten)
4. Re-indexa knowledge (skip_if_exists, rapido)
5. Carga skills nuevas automaticamente
