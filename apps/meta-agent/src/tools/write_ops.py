"""Write tools con @approval — Human in the Loop en toda escritura."""

import json
import os
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import docker
import psycopg
from agno.approval.decorator import approval
from agno.tools.decorator import tool
from docker.errors import APIError, NotFound

from src.config import settings


def _docker() -> docker.DockerClient:
    return docker.from_env()


def _pg() -> str:
    url = settings.database_url
    return url.replace("+psycopg", "") if "+psycopg" in url else url


def _chown(path: Path, uid: int = 1000, gid: int = 1000) -> None:
    try:
        os.chown(path, uid, gid)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    except PermissionError:
        pass


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def create_tenant(name: str, plan: str, bot_token: str, email: str = "") -> str:
    """Crea un tenant completo: DB + config en disco + container Docker.
    Requiere aprobacion humana.
    """
    if plan not in ("basico", "equipo", "pro"):
        return json.dumps({"error": f"Plan invalido: {plan}"})

    tenant_code = ""
    steps: list[str] = []
    try:
        # 1. DB
        with psycopg.connect(_pg()) as conn:
            row = conn.execute(
                "SELECT tenant_code FROM tenants ORDER BY tenant_code DESC LIMIT 1"
            ).fetchone()
            n = int(row[0][1:]) if row else 0
            tenant_code = f"t{n + 1:03d}"
            conn.execute(
                "INSERT INTO tenants "
                "(tenant_code,name,email,plan,status,container_name,network_name) "
                "VALUES (%s,%s,%s,%s,'creating',%s,%s)",
                (tenant_code, name, email or None, plan,
                 f"hermes-{tenant_code}", f"tenant-{tenant_code}-net")
            )
            defaults = {
                "basico": (["telegram"], "deepseek/deepseek-chat", 512, 0.5),
                "equipo": (["telegram", "discord"], "deepseek/deepseek-chat", 768, 0.75),
                "pro": (
                    ["telegram", "discord", "whatsapp"],
                    "anthropic/claude-3.5-haiku", 1024, 1.0
                ),
            }
            platforms, model, mem, cpu = defaults[plan]
            conn.execute(
                "INSERT INTO instance_configs "
                "(tenant_id,template,platforms,skills,model,memory_limit_mb,cpu_limit) "
                "SELECT id,%s,%s,'{}', %s,%s,%s FROM tenants WHERE tenant_code=%s",
                (plan, platforms, model, mem, cpu, tenant_code)
            )
            conn.commit()
        steps.append("db_record")

        # 2. Config en disco
        tp = Path(settings.tenants_base_path) / tenant_code
        tmpl = Path(settings.templates_path) / plan
        tp.mkdir(parents=True, exist_ok=True)
        for sd in ["sessions", "memories", "skills", "cron", "logs", "wiki", "workspace"]:
            (tp / sd).mkdir(exist_ok=True)
        if (tmpl / "config.yaml").exists():
            shutil.copy2(tmpl / "config.yaml", tp / "config.yaml")
        env_file = tp / ".env"
        env_file.write_text(
            f"OPENROUTER_API_KEY={settings.openrouter_api_key}\n"
            f"TELEGRAM_BOT_TOKEN={bot_token}\n"
            f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        )
        os.chmod(env_file, 0o600)
        if (tmpl / "SOUL.md").exists():
            soul = (tmpl / "SOUL.md").read_text().replace("{{AGENT_NAME}}", name)
            (tp / "SOUL.md").write_text(soul)
        _chown(tp)
        steps.append("config_written")

        # 3. Container
        c = _docker()
        net = f"tenant-{tenant_code}-net"
        try:
            c.networks.get(net)
        except NotFound:
            c.networks.create(net, driver="bridge")

        limits = {"basico": (512, 0.5), "equipo": (768, 0.75), "pro": (1024, 1.0)}
        mem_mb, cpus = limits[plan]
        kwargs: dict[str, Any] = {
            "image": settings.hermes_image, "name": f"hermes-{tenant_code}",
            "detach": True, "restart_policy": {"Name": "unless-stopped"},
            # Arranca directamente en la red del tenant — evita la red bridge por defecto
            "network": net,
            "volumes": {str(tp): {"bind": "/opt/data", "mode": "rw"}},
            "environment": {"HERMES_UID": "1000", "HERMES_GID": "1000",
                            "API_SERVER_ENABLED": "true", "API_SERVER_HOST": "0.0.0.0",
                            "HERMES_DASHBOARD": "1" if plan in ("equipo", "pro") else "0"},
            "mem_limit": f"{mem_mb}m", "nano_cpus": int(cpus * 1e9),
            "command": ["gateway", "run"],
            "security_opt": ["no-new-privileges"],
            "pids_limit": 256, "cap_drop": ["ALL"],
            "cap_add": ["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
            "dns": ["1.1.1.1", "8.8.8.8"], "tmpfs": {"/tmp": "size=100m"},
            "log_config": {"Type": "json-file", "Config": {"max-size": "50m", "max-file": "3"}},
            "labels": {
                "martes.tenant": tenant_code, "martes.plan": plan,
                # Traefik labels — compatibles con Coolify's Traefik (certresolver: letsencrypt)
                "traefik.enable": "true",
                f"traefik.http.routers.{tenant_code}.rule": f"Host(`{tenant_code}.martes.app`)",
                f"traefik.http.routers.{tenant_code}.entrypoints": "websecure",
                f"traefik.http.routers.{tenant_code}.tls.certresolver": "letsencrypt",
                f"traefik.http.services.{tenant_code}.loadbalancer.server.port": "8642",
            },
        }
        container = c.containers.run(**kwargs)
        # Conectar redes adicionales. "coolify" es la red del proxy de Coolify —
        # permite que Coolify's Traefik enrute tXXX.martes.app al container.
        # En entornos sin Coolify (dev local) el except maneja la red inexistente.
        for network_name in ["martes-tenants", "coolify"]:
            try:
                c.networks.get(network_name).connect(container)
            except (NotFound, APIError):
                pass
        steps.append("container_created")

        # 4. Activar
        with psycopg.connect(_pg()) as conn:
            conn.execute("UPDATE tenants SET status='active' WHERE tenant_code=%s", (tenant_code,))
            conn.commit()
        steps.append("activated")

        return json.dumps({"success": True, "tenant_code": tenant_code,
                           "name": name, "plan": plan, "steps": steps})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e),
                           "tenant_code": tenant_code, "steps_completed": steps})


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def stop_tenant(tenant_code: str) -> str:
    """Detiene el container de un tenant. Preserva datos. Requiere aprobacion."""
    try:
        _docker().containers.get(f"hermes-{tenant_code}").stop(timeout=30)
        with psycopg.connect(_pg()) as conn:
            conn.execute("UPDATE tenants SET status='paused' WHERE tenant_code=%s", (tenant_code,))
            conn.commit()
        return json.dumps({"success": True, "tenant": tenant_code, "status": "paused"})
    except NotFound:
        return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})
    except (APIError, psycopg.Error) as e:
        return json.dumps({"error": str(e)})


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def restart_tenant(tenant_code: str) -> str:
    """Reinicia el container de un tenant. Requiere aprobacion."""
    try:
        _docker().containers.get(f"hermes-{tenant_code}").restart(timeout=30)
        with psycopg.connect(_pg()) as conn:
            conn.execute("UPDATE tenants SET status='active' WHERE tenant_code=%s", (tenant_code,))
            conn.commit()
        return json.dumps({"success": True, "tenant": tenant_code, "status": "active"})
    except NotFound:
        return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})
    except (APIError, psycopg.Error) as e:
        return json.dumps({"error": str(e)})


@approval  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def inject_credential(tenant_code: str, credential_type: str, credential_value: str) -> str:
    """Inyecta una credencial en el volumen del tenant. Requiere aprobacion."""
    tp = Path(settings.tenants_base_path) / tenant_code
    if not tp.exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe en disco."})
    file_map = {"google_token": "google_token.json", "notion_key": ".env",
                "airtable_key": ".env", "github_token": ".env", "linear_key": ".env"}
    target = file_map.get(credential_type)
    if not target:
        return json.dumps({"error": f"Tipo desconocido: {credential_type}"})
    try:
        if target == ".env":
            env_file = tp / ".env"
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
            cred = tp / target
            cred.write_text(credential_value)
            os.chmod(cred, 0o600)
        _chown(tp)
        return json.dumps({"success": True, "tenant": tenant_code,
                           "credential": credential_type, "file": target})
    except OSError as e:
        return json.dumps({"error": str(e)})


@approval(type="audit")  # type: ignore[arg-type]
@tool(requires_confirmation=True)
def register_payment(tenant_code: str, amount: float, method: str,
                     months: int = 1, reference: str = "") -> str:
    """Registra un pago manual. Requiere aprobacion con audit trail."""
    try:
        with psycopg.connect(_pg()) as conn:
            row = conn.execute(
                "SELECT id, paid_until FROM tenants WHERE tenant_code=%s", (tenant_code,)
            ).fetchone()
            if not row:
                return json.dumps({"error": f"Tenant {tenant_code} no encontrado."})
            today = date.today()
            pu = row[1]
            start = pu if pu and pu > today else today
            end = start + timedelta(days=30 * months)
            conn.execute(
                "INSERT INTO payments (tenant_id,amount,method,reference,period_start,period_end) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (row[0], amount, method, reference or None, start, end)
            )
            conn.execute(
                "UPDATE tenants SET paid_until=%s, status='active' WHERE id=%s", (end, row[0])
            )
            conn.commit()
        return json.dumps({"success": True, "tenant": tenant_code, "amount": amount,
                           "method": method, "paid_until": end.isoformat()})
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})


@tool(requires_confirmation=True)
def inject_wiki_content(tenant_code: str, company_name: str, company_description: str,
                        team_members: str = "", tools_used: str = "",
                        active_projects: str = "", custom_pages: str = "") -> str:
    """Pre-carga la LLM Wiki del tenant con informacion de la empresa."""
    from datetime import date as _date
    wiki = Path(settings.tenants_base_path) / tenant_code / "wiki"
    if not (Path(settings.tenants_base_path) / tenant_code).exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe."})
    today = _date.today().isoformat()
    slug = company_name.lower().replace(" ", "-")
    try:
        for d in ["raw/articles", "raw/papers", "raw/transcripts", "raw/assets",
                  "entities", "concepts", "comparisons", "queries"]:
            (wiki / d).mkdir(parents=True, exist_ok=True)
        (wiki / "SCHEMA.md").write_text(
            f"# Wiki Schema — {company_name}\n\n## Domain\n{company_description}\n\n"
            f"## Conventions\n- File names: lowercase, hyphens\n"
            f"- Use [[wikilinks]]\n- Update index.md and log.md on every change\n\n"
            f"## Tag Taxonomy\n- company, team, project, client, process\n"
        )
        (wiki / "index.md").write_text(
            f"# Wiki Index — {company_name}\n\n> Updated: {today}\n\n"
            f"## Entities\n- [[{slug}]] — {company_name}\n"
        )
        (wiki / "log.md").write_text(
            f"# Wiki Log\n\n## [{today}] create | Wiki inicializada\n- Empresa: {company_name}\n"
        )
        sections = f"\n## Team\n{team_members}" if team_members else ""
        sections += f"\n## Tools\n{tools_used}" if tools_used else ""
        sections += f"\n## Active Projects\n{active_projects}" if active_projects else ""
        (wiki / "entities" / f"{slug}.md").write_text(
            f"---\ntitle: {company_name}\ncreated: {today}\nupdated: {today}\n"
            f"type: entity\ntags: [company]\n---\n\n# {company_name}\n\n"
            f"{company_description}\n{sections}\n"
        )
        # Custom pages
        created = [f"entities/{slug}.md"]
        if custom_pages:
            import json as _json
            try:
                for p in _json.loads(custom_pages):
                    pn, pc = p.get("name", ""), p.get("content", "")
                    if pn and pc:
                        pp = wiki / ("concepts" / pn if "/" not in pn else pn)
                        pp.parent.mkdir(parents=True, exist_ok=True)
                        pp.write_text(pc)
                        created.append(pn)
            except Exception:
                pass
        # WIKI_PATH en .env
        env = Path(settings.tenants_base_path) / tenant_code / ".env"
        if env.exists():
            text = env.read_text()
            if "WIKI_PATH" not in text:
                env.write_text(text + "\nWIKI_PATH=/opt/data/wiki\n")
                os.chmod(env, 0o600)
        _chown(wiki)
        return json.dumps({"success": True, "tenant": tenant_code,
                           "files_created": created,
                           "message": f"Wiki de {company_name} inicializada."})
    except OSError as e:
        return json.dumps({"error": str(e)})
