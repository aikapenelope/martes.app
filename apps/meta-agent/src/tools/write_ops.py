"""Tools de escritura — el Operador los usa con @approval (Human in the Loop).

TODAS las funciones aqui requieren confirmacion humana antes de ejecutarse.
Ninguna se ejecuta automaticamente. El agente propone, el humano aprueba.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any

import docker
import psycopg
from agno.approval.decorator import approval
from agno.tools.decorator import tool
from docker.errors import APIError, NotFound

from src.config import settings


def _get_docker() -> docker.DockerClient:
    return docker.from_env()


def _get_conn_str() -> str:
    url = settings.database_url
    if "+psycopg" in url:
        url = url.replace("+psycopg", "")
    return url


# ---------------------------------------------------------------------------
# Tenant creation
# ---------------------------------------------------------------------------


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def create_tenant(
    name: str,
    plan: str,
    bot_token: str,
    email: str = "",
    api_key: str = "",
) -> str:
    """Crea un tenant nuevo completo: registro en DB + config en disco + container Docker.

    Este es el flujo completo de onboarding. Requiere aprobacion humana.

    Args:
        name: Nombre del cliente/empresa.
        plan: Plan contratado (basico, equipo, pro).
        bot_token: Token del bot de Telegram del tenant.
        email: Email de contacto (opcional).
        api_key: OpenRouter API key custom (usa la del sistema si vacio).
    """
    if plan not in ("basico", "equipo", "pro"):
        return json.dumps({"error": f"Plan invalido: {plan}. Usar: basico, equipo, pro"})

    steps_done: list[str] = []
    tenant_code = ""

    try:
        # Step 1: Crear registro en DB
        with psycopg.connect(_get_conn_str()) as conn:
            row = conn.execute(
                "SELECT tenant_code FROM tenants ORDER BY tenant_code DESC LIMIT 1"
            ).fetchone()
            last_num = int(row[0][1:]) if row else 0
            tenant_code = f"t{last_num + 1:03d}"

            conn.execute(
                """
                INSERT INTO tenants
                    (tenant_code, name, email, plan, status, container_name, network_name)
                VALUES (%s, %s, %s, %s, 'creating', %s, %s)
                """,
                (tenant_code, name, email or None, plan,
                 f"hermes-{tenant_code}", f"tenant-{tenant_code}-net"),
            )

            # Defaults por plan
            platforms = {"basico": ["telegram"], "equipo": ["telegram", "discord"],
                         "pro": ["telegram", "discord", "whatsapp"]}
            models = {"basico": "deepseek/deepseek-chat", "equipo": "deepseek/deepseek-chat",
                      "pro": "anthropic/claude-3.5-haiku"}
            limits = {"basico": (512, 0.5), "equipo": (768, 0.75), "pro": (1024, 1.0)}

            conn.execute(
                """
                INSERT INTO instance_configs
                    (tenant_id, template, platforms, skills, model, memory_limit_mb, cpu_limit)
                SELECT id, %s, %s, '{}', %s, %s, %s FROM tenants WHERE tenant_code = %s
                """,
                (plan, platforms[plan], models[plan],
                 limits[plan][0], limits[plan][1], tenant_code),
            )
            conn.commit()
        steps_done.append("db_record")

        # Step 2: Escribir config en disco
        tenant_path = Path(settings.tenants_base_path) / tenant_code
        template_path = Path(settings.templates_path) / plan

        tenant_path.mkdir(parents=True, exist_ok=True)
        for subdir in ["sessions", "memories", "skills", "cron", "logs", "wiki", "workspace"]:
            (tenant_path / subdir).mkdir(exist_ok=True)

        # Config
        config_src = template_path / "config.yaml"
        if config_src.exists():
            shutil.copy2(config_src, tenant_path / "config.yaml")

        # .env
        effective_key = api_key or settings.openrouter_api_key
        env_content = (
            f"OPENROUTER_API_KEY={effective_key}\n"
            f"TELEGRAM_BOT_TOKEN={bot_token}\n"
            f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        )
        env_file = tenant_path / ".env"
        env_file.write_text(env_content)
        os.chmod(env_file, 0o600)

        # SOUL.md
        soul_src = template_path / "SOUL.md"
        if soul_src.exists():
            soul_content = soul_src.read_text().replace("{{AGENT_NAME}}", name)
            (tenant_path / "SOUL.md").write_text(soul_content)

        # Permisos
        _chown_recursive(tenant_path, 1000, 1000)
        steps_done.append("config_written")

        # Step 3: Crear container
        client = _get_docker()
        container_name = f"hermes-{tenant_code}"
        network_name = f"tenant-{tenant_code}-net"
        mem_mb, cpus = limits[plan]

        try:
            client.networks.get(network_name)
        except NotFound:
            client.networks.create(network_name, driver="bridge")

        run_kwargs: dict[str, Any] = {
            "image": settings.hermes_image,
            "name": container_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "volumes": {str(tenant_path): {"bind": "/opt/data", "mode": "rw"}},
            "environment": {
                "HERMES_UID": "1000", "HERMES_GID": "1000",
                "API_SERVER_ENABLED": "true", "API_SERVER_HOST": "0.0.0.0",
                "HERMES_DASHBOARD": "1" if plan in ("equipo", "pro") else "0",
            },
            "mem_limit": f"{mem_mb}m",
            "nano_cpus": int(cpus * 1e9),
            "command": ["gateway", "run"],
            "security_opt": ["no-new-privileges"],
            "pids_limit": 256,
            "cap_drop": ["ALL"],
            "cap_add": ["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
            "dns": ["1.1.1.1", "8.8.8.8"],
            "tmpfs": {"/tmp": "size=100m"},
            "log_config": {"Type": "json-file", "Config": {"max-size": "50m", "max-file": "3"}},
            "labels": {
                "martes.tenant": tenant_code, "martes.plan": plan,
                "traefik.enable": "true",
                f"traefik.http.routers.{tenant_code}.rule": f"Host(`{tenant_code}.martes.app`)",
                f"traefik.http.routers.{tenant_code}.tls.certresolver": "letsencrypt",
                f"traefik.http.services.{tenant_code}.loadbalancer.server.port": "8642",
            },
        }
        container = client.containers.run(**run_kwargs)

        # Connect to networks
        try:
            net = client.networks.get(network_name)
            net.connect(container)
        except Exception:
            pass
        try:
            traefik_net = client.networks.get("martes-tenants")
            traefik_net.connect(container)
        except NotFound:
            pass

        steps_done.append("container_created")

        # Step 4: Activar
        with psycopg.connect(_get_conn_str()) as conn:
            conn.execute(
                "UPDATE tenants SET status = 'active' WHERE tenant_code = %s",
                (tenant_code,),
            )
            conn.commit()
        steps_done.append("activated")

        return json.dumps({
            "success": True,
            "tenant_code": tenant_code,
            "name": name,
            "plan": plan,
            "container": container_name,
            "steps": steps_done,
        })

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "tenant_code": tenant_code,
            "steps_completed": steps_done,
        })


# ---------------------------------------------------------------------------
# Tenant lifecycle
# ---------------------------------------------------------------------------


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def stop_tenant(tenant_code: str) -> str:
    """Detiene el container de un tenant. Preserva datos. Requiere aprobacion.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
    """
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    try:
        container = client.containers.get(name)
        container.stop(timeout=30)
        with psycopg.connect(_get_conn_str()) as conn:
            conn.execute(
                "UPDATE tenants SET status = 'paused' WHERE tenant_code = %s",
                (tenant_code,),
            )
            conn.commit()
        return json.dumps({
            "success": True, "tenant": tenant_code, "action": "stopped",
            "message": f"Container {name} detenido. Datos preservados.",
        })
    except NotFound:
        return json.dumps({"error": f"Container {name} no encontrado."})
    except (APIError, psycopg.Error) as e:
        return json.dumps({"error": str(e)})


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def restart_tenant(tenant_code: str) -> str:
    """Reinicia el container de un tenant. Requiere aprobacion.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
    """
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    try:
        container = client.containers.get(name)
        container.restart(timeout=30)
        with psycopg.connect(_get_conn_str()) as conn:
            conn.execute(
                "UPDATE tenants SET status = 'active' WHERE tenant_code = %s",
                (tenant_code,),
            )
            conn.commit()
        return json.dumps({
            "success": True, "tenant": tenant_code, "action": "restarted",
        })
    except NotFound:
        return json.dumps({"error": f"Container {name} no encontrado."})
    except (APIError, psycopg.Error) as e:
        return json.dumps({"error": str(e)})


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def remove_tenant(tenant_code: str) -> str:
    """Elimina container y red de un tenant (para archivado). Requiere aprobacion.

    PELIGROSO: No elimina datos del volumen, pero si el container y la red.

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
    """
    client = _get_docker()
    name = f"hermes-{tenant_code}"
    network_name = f"tenant-{tenant_code}-net"
    try:
        try:
            container = client.containers.get(name)
            container.stop(timeout=10)
            container.remove()
        except NotFound:
            pass
        try:
            network = client.networks.get(network_name)
            network.remove()
        except NotFound:
            pass
        with psycopg.connect(_get_conn_str()) as conn:
            conn.execute(
                "UPDATE tenants SET status = 'archived' WHERE tenant_code = %s",
                (tenant_code,),
            )
            conn.commit()
        return json.dumps({
            "success": True, "tenant": tenant_code, "action": "removed",
            "message": "Container y red eliminados. Volumen preservado.",
        })
    except (APIError, psycopg.Error) as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def inject_credential(
    tenant_code: str,
    credential_type: str,
    credential_value: str,
) -> str:
    """Inyecta una credencial en el volumen de un tenant. Requiere aprobacion.

    Args:
        tenant_code: Codigo del tenant.
        credential_type: Tipo (google_token, notion_key, github_token, linear_key).
        credential_value: Valor de la credencial.
    """
    tenant_path = Path(settings.tenants_base_path) / tenant_code
    if not tenant_path.exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe en disco."})

    file_map = {
        "google_token": "google_token.json",
        "notion_key": ".env",
        "airtable_key": ".env",
        "github_token": ".env",
        "linear_key": ".env",
    }
    target = file_map.get(credential_type)
    if not target:
        return json.dumps({"error": f"Tipo desconocido: {credential_type}"})

    try:
        if target == ".env":
            env_file = tenant_path / ".env"
            key = credential_type.upper()
            lines = env_file.read_text().splitlines() if env_file.exists() else []
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={credential_value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={credential_value}")
            env_file.write_text("\n".join(lines) + "\n")
            os.chmod(env_file, 0o600)
        else:
            cred_file = tenant_path / target
            cred_file.write_text(credential_value)
            os.chmod(cred_file, 0o600)

        _chown_recursive(tenant_path, 1000, 1000)
        return json.dumps({
            "success": True, "tenant": tenant_code,
            "credential": credential_type, "file": target,
        })
    except OSError as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


@approval(type="audit")  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def register_payment(
    tenant_code: str,
    amount: float,
    method: str,
    months: int = 1,
    reference: str = "",
) -> str:
    """Registra un pago manual de un tenant. Requiere aprobacion.

    Args:
        tenant_code: Codigo del tenant.
        amount: Monto pagado en USD.
        method: Metodo (transferencia, zelle, pago_movil, crypto).
        months: Meses pagados (default 1).
        reference: Referencia del pago.
    """
    from datetime import date, timedelta

    try:
        with psycopg.connect(_get_conn_str()) as conn:
            tenant = conn.execute(
                "SELECT id, paid_until FROM tenants WHERE tenant_code = %s",
                (tenant_code,),
            ).fetchone()
            if tenant is None:
                return json.dumps({"error": f"Tenant {tenant_code} no encontrado."})

            today = date.today()
            paid_until = tenant[1]
            start = paid_until if paid_until and paid_until > today else today
            end = start + timedelta(days=30 * months)

            conn.execute(
                """
                INSERT INTO payments
                    (tenant_id, amount, method, reference, period_start, period_end)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (tenant[0], amount, method, reference or None, start, end),
            )
            conn.execute(
                "UPDATE tenants SET paid_until = %s, status = 'active' WHERE id = %s",
                (end, tenant[0]),
            )
            conn.commit()

        return json.dumps({
            "success": True, "tenant": tenant_code,
            "amount": amount, "method": method,
            "period_end": end.isoformat(),
            "message": f"Pago registrado. Activo hasta {end}.",
        })
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# LLM Wiki — pre-populate tenant wiki before container starts
# ---------------------------------------------------------------------------


@tool(requires_confirmation=True)
def inject_wiki_content(
    tenant_code: str,
    company_name: str,
    company_description: str,
    domain: str = "",
    team_members: str = "",
    tools_used: str = "",
    active_projects: str = "",
    custom_pages: str = "",
) -> str:
    """Pre-popula la wiki del tenant con conocimiento inicial de la empresa.

    Crea la estructura LLM Wiki (Karpathy pattern) en el volumen del tenant
    con contenido real. El agente Hermes arranca con contexto desde el dia 1.

    Puede llamarse antes O despues de crear el container (la wiki persiste en volumen).

    Args:
        tenant_code: Codigo del tenant (e.g. t001).
        company_name: Nombre de la empresa o cliente.
        company_description: Que hace la empresa, su industria, audiencia.
        domain: Dominio de conocimiento (marketing, desarrollo, finanzas, etc.).
        team_members: Lista de miembros del equipo (JSON o texto libre).
        tools_used: Herramientas que usa el equipo (Notion, GitHub, Jira...).
        active_projects: Proyectos activos actuales (JSON o texto libre).
        custom_pages: Paginas markdown adicionales en formato JSON:
                      '[{"name": "archivo.md", "content": "# Titulo..."}]'
    """
    from datetime import date

    wiki_path = Path(settings.tenants_base_path) / tenant_code / "wiki"

    if not (Path(settings.tenants_base_path) / tenant_code).exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe en disco."})

    today = date.today().isoformat()

    try:
        # Crear estructura de directorios
        for subdir in ["raw/articles", "raw/papers", "raw/transcripts",
                       "raw/assets", "entities", "concepts", "comparisons", "queries"]:
            (wiki_path / subdir).mkdir(parents=True, exist_ok=True)

        # --- SCHEMA.md — define el dominio y convenciones ---
        effective_domain = domain or "Asistente de equipo inteligente"
        schema_content = f"""# Wiki Schema — {company_name}

## Domain
{effective_domain}. Conocimiento acumulativo del equipo de {company_name}.

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `proyecto-alfa.md`)
- Every wiki page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md` under the correct section
- Every action must be appended to `log.md`

## Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [from taxonomy below]
sources: []
---
```

## Tag Taxonomy
- Company: company, team, member, project, client
- Work: task, deadline, meeting, decision, process
- Tools: notion, github, slack, telegram, google-workspace
- Meta: reference, procedure, template

## Page Thresholds
- Create a page when an entity/concept appears in 2+ contexts OR is central
- Split pages when they exceed ~200 lines
- Archive when content is fully superseded
"""
        (wiki_path / "SCHEMA.md").write_text(schema_content)

        # --- index.md — catalogo inicial ---
        index_content = f"""# Wiki Index — {company_name}

> Catalogo de contenido. Cada pagina listada con resumen de una linea.
> Ultima actualizacion: {today} | Total paginas: 1

## Entities
- [[{company_name.lower().replace(" ", "-")}]] — Informacion de la empresa

## Concepts

## Projects

## Processes
"""
        (wiki_path / "index.md").write_text(index_content)

        # --- log.md ---
        log_content = f"""# Wiki Log — {company_name}

> Log cronologico de todas las acciones. Solo append.
> Formato: `## [YYYY-MM-DD] accion | tema`

## [{today}] create | Wiki inicializada por martes.app
- Dominio: {effective_domain}
- Estructura creada con SCHEMA.md, index.md, log.md
- Entidad inicial: {company_name}
"""
        (wiki_path / "log.md").write_text(log_content)

        # --- entities/company.md — pagina principal de la empresa ---
        company_slug = company_name.lower().replace(" ", "-")
        members_section = ""
        if team_members:
            members_section = f"\n## Team\n{team_members}\n"

        tools_section = ""
        if tools_used:
            tools_section = f"\n## Tools\n{tools_used}\n"

        projects_section = ""
        if active_projects:
            projects_section = f"\n## Active Projects\n{active_projects}\n"

        company_content = f"""---
title: {company_name}
created: {today}
updated: {today}
type: entity
tags: [company]
sources: []
---

# {company_name}

{company_description}
{members_section}{tools_section}{projects_section}
## Notes

<!-- El agente actualiza esta seccion con lo que aprende -->
"""
        (wiki_path / "entities" / f"{company_slug}.md").write_text(company_content)

        # --- Paginas custom adicionales (opcionales) ---
        custom_created: list[str] = []
        if custom_pages:
            try:
                pages = json.loads(custom_pages)
                for page in pages:
                    page_name = page.get("name", "")
                    page_content = page.get("content", "")
                    if page_name and page_content:
                        # Determinar subdirectorio por prefijo
                        if "/" in page_name:
                            page_path = wiki_path / page_name
                        else:
                            page_path = wiki_path / "concepts" / page_name
                        page_path.parent.mkdir(parents=True, exist_ok=True)
                        page_path.write_text(page_content)
                        custom_created.append(page_name)
            except json.JSONDecodeError:
                pass  # custom_pages en texto libre, ignorar

        # --- Configurar WIKI_PATH en .env del tenant ---
        env_file = Path(settings.tenants_base_path) / tenant_code / ".env"
        if env_file.exists():
            env_text = env_file.read_text()
            if "WIKI_PATH" not in env_text:
                env_text += "\nWIKI_PATH=/opt/data/wiki\n"
                env_file.write_text(env_text)
                os.chmod(env_file, 0o600)

        # Fijar permisos
        _chown_recursive(wiki_path, 1000, 1000)

        files_created = ["SCHEMA.md", "index.md", "log.md",
                         f"entities/{company_slug}.md"] + custom_created

        return json.dumps({
            "success": True,
            "tenant_code": tenant_code,
            "wiki_path": str(wiki_path),
            "company": company_name,
            "files_created": files_created,
            "message": (
                f"Wiki de {company_name} inicializada. "
                "El agente Hermes tendra contexto desde el primer mensaje."
            ),
        })

    except OSError as e:
        return json.dumps({"error": str(e)})


def _chown_recursive(path: Path, uid: int, gid: int) -> None:
    """Cambia ownership recursivamente."""
    try:
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    except PermissionError:
        pass
