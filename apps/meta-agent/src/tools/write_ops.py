"""Write tools — Human in the Loop via conversación en Telegram.

El patrón @approval de Agno pausa el run y espera un POST al endpoint
/continue vía API REST — no envía ningún mensaje de regreso al chat.
Ese patrón es para apps con frontend propio, no para bots de Telegram.

El patrón correcto para Telegram: el Operador describe lo que va a hacer,
el admin confirma con 'sí', y ENTONCES se ejecuta la tool.
Las instrucciones del Operador ya garantizan ese flujo conversacional.
"""

import json
import os
import re
import shutil
import tarfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import docker
import psycopg
import yaml
from agno.tools.decorator import tool
from docker.errors import APIError, NotFound

from src.config import settings

_BACKUPS_DIR = Path("/var/lib/martes/backups")
_DEFAULT_TEMPLATE = "default"
_DEFAULT_MODEL = "openai/gpt-4o-mini"  # modelo inicial — cliente puede cambiar con /model


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


_BOT_TOKEN_RE = re.compile(r"^\d{8,12}:[A-Za-z0-9_-]{35}$")


def create_tenant(
    name: str,
    bot_token: str,
    telegram_user_id: str,
    model: str = _DEFAULT_MODEL,
    email: str = "",
) -> str:
    """Crea un tenant Hermes completo: DB + volumen + container Docker.

    Modelo Hermes libre: cada tenant tiene Hermes COMPLETO sin restricciones.
    No hay planes ni tiers — todos los tenants son iguales técnicamente.
    El único límite es el presupuesto de tokens (créditos en OpenRouter).
    El cliente puede cambiar cualquier configuración desde Telegram (/model, /skills, etc.).

    Parámetros:
    - name: nombre del cliente o empresa (ej: "Acme Corp")
    - bot_token: token del bot Telegram de @BotFather. Formato exacto: 123456789:ABCDefgh...
      (número de 8-12 dígitos, dos puntos, 35 caracteres alfanuméricos/guión/guión bajo)
    - telegram_user_id: ID numérico de Telegram del cliente (lo obtiene con @userinfobot)
    - model: modelo LLM inicial. Opciones válidas en OpenRouter:
      openai/gpt-4o-mini (default), openai/gpt-4o, deepseek/deepseek-v4-flash,
      anthropic/claude-3.5-haiku, anthropic/claude-opus-4-6
    - email: email de contacto (opcional)

    Requiere aprobacion humana.
    """
    # Validar formato de bot_token antes de hacer cualquier operación.
    # Formato oficial de Telegram: https://core.telegram.org/bots/api#authorizing-your-bot
    if not _BOT_TOKEN_RE.match(bot_token):
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"bot_token inválido: '{bot_token}'. "
                    "El formato correcto es '123456789:ABCDefgh...' — "
                    "número de 8-12 dígitos, dos puntos, 35 caracteres alfanuméricos. "
                    "Obtén el token con @BotFather en Telegram."
                ),
            }
        )

    # Validar que telegram_user_id es numérico.
    if not telegram_user_id.strip().lstrip("-").isdigit():
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"telegram_user_id inválido: '{telegram_user_id}'. "
                    "Debe ser un número entero. El cliente lo obtiene con @userinfobot."
                ),
            }
        )

    # "basico" es la etiqueta de billing interna. Siempre la misma —
    # no existe diferenciación técnica entre tenants.
    _billing_plan = "basico"
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
                (
                    tenant_code,
                    name,
                    email or None,
                    _billing_plan,
                    f"hermes-{tenant_code}",
                    f"tenant-{tenant_code}-net",
                ),
            )
            # Recursos uniformes — mismo hardware para todos los tenants
            conn.execute(
                "INSERT INTO instance_configs "
                "(tenant_id,template,platforms,skills,model,memory_limit_mb,cpu_limit) "
                "SELECT id,%s,'{telegram}','{}', %s,768,0.75 FROM tenants WHERE tenant_code=%s",
                (_DEFAULT_TEMPLATE, model, tenant_code),
            )
            conn.commit()
        steps.append("db_record")

        # 2. Volumen — copia template default, escribe .env y SOUL.md
        tp = Path(settings.tenants_base_path) / tenant_code
        tmpl = Path(settings.templates_path) / _DEFAULT_TEMPLATE
        tp.mkdir(parents=True, exist_ok=True)
        for sd in ["sessions", "memories", "skills", "cron", "logs", "wiki", "workspace", "home"]:
            (tp / sd).mkdir(exist_ok=True)

        # config.yaml: template default + modelo elegido
        if (tmpl / "config.yaml").exists():
            cfg = yaml.safe_load((tmpl / "config.yaml").read_text()) or {}
            if "model" not in cfg:
                cfg["model"] = {}
            cfg["model"]["default"] = model
            with open(tp / "config.yaml", "w") as f:
                yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        else:
            shutil.copy2(tmpl / "config.yaml", tp / "config.yaml")

        # .env: credenciales del tenant
        # TELEGRAM_ALLOWED_USERS es crítico: sin esto el bot no responde a nadie
        # Ref: https://hermes-agent.nousresearch.com/docs/user-guide/security
        env_file = tp / ".env"
        env_file.write_text(
            f"OPENROUTER_API_KEY={settings.openrouter_api_key}\n"
            f"OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
            f"TELEGRAM_BOT_TOKEN={bot_token}\n"
            f"TELEGRAM_ALLOWED_USERS={telegram_user_id}\n"
        )
        os.chmod(env_file, 0o600)

        # SOUL.md: personalidad inicial
        if (tmpl / "SOUL.md").exists():
            soul = (tmpl / "SOUL.md").read_text().replace("{{AGENT_NAME}}", name)
            (tp / "SOUL.md").write_text(soul)

        _chown(tp)
        steps.append("volume_configured")

        # 3. Container — Hermes completo, recursos uniformes
        c = _docker()
        net = f"tenant-{tenant_code}-net"
        try:
            c.networks.get(net)
        except NotFound:
            c.networks.create(net, driver="bridge")

        c.containers.run(
            image=settings.hermes_image,
            name=f"hermes-{tenant_code}",
            detach=True,
            restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
            network=net,
            volumes={str(tp): {"bind": "/opt/data", "mode": "rw"}},
            environment={
                "HERMES_UID": "1000",
                "HERMES_GID": "1000",
                # API_SERVER_ENABLED activa el health endpoint en localhost:8642 dentro
                # del container. Los health checks del meta-agente usan docker exec, no
                # red, así que localhost (127.0.0.1) es suficiente.
                # NO se pone API_SERVER_HOST=0.0.0.0 sin API_SERVER_KEY — el doc de
                # Hermes requiere ambos juntos al exponer fuera de localhost:
                # Ref: https://hermes-agent.nousresearch.com/docs/user-guide/docker
                "API_SERVER_ENABLED": "true",
            },
            # Recursos uniformes — el límite real es el token budget de OpenRouter
            mem_limit="768m",
            nano_cpus=int(0.75 * 1e9),
            command=["gateway", "run"],
            security_opt=["no-new-privileges"],
            pids_limit=256,
            cap_drop=["ALL"],
            cap_add=["NET_RAW", "CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER"],
            dns=["1.1.1.1", "8.8.8.8"],
            tmpfs={"/tmp": "size=100m"},
            log_config={"Type": "json-file", "Config": {"max-size": "50m", "max-file": "3"}},  # type: ignore[arg-type]
            labels={
                "martes.tenant": tenant_code,
                "martes.plan": _billing_plan,
                "martes.model": model,
            },
        )
        steps.append("container_created")

        # 4. Activar en DB
        with psycopg.connect(_pg()) as conn:
            conn.execute("UPDATE tenants SET status='active' WHERE tenant_code=%s", (tenant_code,))
            conn.commit()
        steps.append("activated")

        # 5. Registrar perfil en EntityMemory para que el agente recuerde este tenant
        # entre sesiones sin consultar la DB. Fallo silencioso — no bloquea el onboarding.
        # API: agno==2.6.8 learn/stores/entity_memory.py:create_entity()
        # Ref: https://docs.agno.com/learn/stores/entity-memory
        try:
            from agno.learn.stores.entity_memory import EntityMemoryStore

            from src.shared import learning

            store = learning.entity_memory_store
            if isinstance(store, EntityMemoryStore):
                store.create_entity(
                    entity_id=tenant_code,
                    entity_type="company",
                    name=name,
                    description=f"Tenant {tenant_code} en martes.app — agente Hermes personal",
                    properties={
                        "tenant_code": tenant_code,
                        "model": model,
                        "email": email or "no registrado",
                        "hermes_version": settings.hermes_image.split(":")[-1],
                    },
                    namespace="martes",
                )
                steps.append("entity_memory_created")
        except Exception:
            steps.append("entity_memory_skipped")

        return json.dumps(
            {
                "success": True,
                "tenant_code": tenant_code,
                "name": name,
                "model": model,
                "steps": steps,
                "message": (
                    f"Tenant {tenant_code} ({name}) activo. "
                    f"Bot listo en Telegram. Modelo: {model}. "
                    f"El cliente puede cambiar el modelo con /model."
                ),
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
                "tenant_code": tenant_code,
                "steps_completed": steps,
            }
        )


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


def delete_tenant(tenant_code: str, keep_volume: bool = False) -> str:
    """Elimina un tenant de forma permanente: backup final → stop → remove container → archivo DB.

    Flujo:
    1. Backup final a SeaweedFS (siempre, para poder restaurar si el cliente regresa)
    2. Detener el container si está corriendo
    3. Eliminar el container Docker (remove)
    4. Eliminar la red Docker del tenant
    5. Eliminar el directorio de datos del host (salvo keep_volume=True)
    6. Marcar como 'archived' en DB

    keep_volume=True: preserva /var/lib/martes/tenants/{code}/ en disco.
    Útil si hay posibilidad de que el cliente reactive el servicio.
    Los backups en SeaweedFS siempre se conservan independientemente de keep_volume.

    Requiere aprobacion — operacion destructiva e irreversible.
    Ref docker remove: https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.Container.remove
    """
    from src import storage

    steps: list[str] = []
    c_client = _docker()

    try:
        # 1. Backup final a SeaweedFS
        backup_result = json.loads(backup_tenant(tenant_code))
        if backup_result.get("success"):
            steps.append(f"backup_ok:{backup_result.get('backup_file')}")
        else:
            # Continuar aun si el backup falla — ya hay backups previos en SeaweedFS
            steps.append(f"backup_warn:{backup_result.get('error', 'desconocido')}")

        # 2. Detener y eliminar el container
        try:
            container = c_client.containers.get(f"hermes-{tenant_code}")
            if container.status == "running":
                container.stop(timeout=30)
                steps.append("container_stopped")
            container.remove(force=True)
            steps.append("container_removed")
        except NotFound:
            steps.append("container_not_found")  # Ya no existía, ok

        # 3. Eliminar la red Docker del tenant
        net_name = f"tenant-{tenant_code}-net"
        try:
            c_client.networks.get(net_name).remove()
            steps.append("network_removed")
        except NotFound:
            steps.append("network_not_found")

        # 4. Eliminar directorio de datos del host (si no se quiere conservar)
        tenant_path = Path(settings.tenants_base_path) / tenant_code
        if not keep_volume and tenant_path.exists():
            import shutil

            shutil.rmtree(tenant_path)
            steps.append("volume_deleted")
        elif keep_volume:
            steps.append("volume_preserved")

        # 5. Marcar como archived en DB
        with psycopg.connect(_pg()) as conn:
            conn.execute(
                "UPDATE tenants SET status='archived' WHERE tenant_code=%s", (tenant_code,)
            )
            conn.commit()
        steps.append("db_archived")

        backups_in_seaweedfs = 0
        if storage.storage_available():
            backups_in_seaweedfs = len(storage.list_tenant_backups(tenant_code))

        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "steps": steps,
                "backups_in_seaweedfs": backups_in_seaweedfs,
                "volume_preserved": keep_volume,
                "message": (
                    f"Tenant {tenant_code} eliminado. "
                    f"{backups_in_seaweedfs} backup(s) conservados en SeaweedFS. "
                    + (
                        "Datos del volumen preservados en disco."
                        if keep_volume
                        else "Datos del volumen eliminados del disco."
                    )
                ),
            }
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "steps_completed": steps})


def update_tenant_resources(
    tenant_code: str,
    memory_mb: int | None = None,
    cpu_cores: float | None = None,
) -> str:
    """Actualiza límites de memoria y CPU de un tenant en caliente, sin reiniciar.

    Usa docker update que modifica cgroups directamente en el container corriendo.
    El cambio es inmediato y no requiere restart ni recreación del container.
    Ref: https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.Container.update
    Ref: https://docs.docker.com/reference/cli/docker/container/update/

    Parámetros:
    - memory_mb: límite de RAM en MB. Ej: 512, 768, 1024, 2048
    - cpu_cores: núcleos de CPU. Ej: 0.5, 0.75, 1.0, 2.0

    Valores típicos para Hermes:
      Mínimo viable:   512 MB, 0.5 CPU  (tareas simples, poco contexto)
      Estándar:        768 MB, 0.75 CPU (por defecto al crear)
      Pesado:         1024 MB, 1.0 CPU  (tareas largas, contexto grande)
      Intensivo:      2048 MB, 2.0 CPU  (subagentes, code execution)

    No requiere aprobación — es un ajuste reversible y no destructivo.
    """
    if memory_mb is None and cpu_cores is None:
        return json.dumps({"error": "Especifica al menos memory_mb o cpu_cores."})

    try:
        container = _docker().containers.get(f"hermes-{tenant_code}")

        # Construir kwargs para container.update()
        update_kwargs: dict = {}
        if memory_mb is not None:
            if memory_mb < 256:
                return json.dumps({"error": "Mínimo 256 MB — menos puede causar OOM kills."})
            update_kwargs["mem_limit"] = f"{memory_mb}m"
            # memory-swap = 2x memory (permite burst sin swap agresivo)
            update_kwargs["memswap_limit"] = f"{memory_mb * 2}m"
        if cpu_cores is not None:
            if cpu_cores < 0.1:
                return json.dumps({"error": "Mínimo 0.1 CPU — menos afecta el rendimiento."})
            update_kwargs["nano_cpus"] = int(cpu_cores * 1e9)

        container.update(**update_kwargs)

        # Actualizar el label del container para reflejar el nuevo límite
        # (los labels no son actualizables en caliente — solo para referencia futura)

        # Leer los nuevos valores del inspect para confirmar
        container.reload()
        host_cfg = container.attrs.get("HostConfig", {})
        actual_mem_mb = round(host_cfg.get("Memory", 0) / (1024 * 1024))
        actual_nano = host_cfg.get("NanoCpus", 0)
        actual_cpu = round(actual_nano / 1e9, 2) if actual_nano else None

        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "applied": update_kwargs,
                "actual_memory_mb": actual_mem_mb,
                "actual_cpu_cores": actual_cpu,
                "restart_required": False,
                "message": (
                    f"Recursos actualizados en caliente para hermes-{tenant_code}. "
                    f"RAM: {actual_mem_mb} MB"
                    + (f" | CPU: {actual_cpu} cores" if actual_cpu else "")
                    + ". Sin reinicio."
                ),
            }
        )
    except NotFound:
        return json.dumps({"error": f"Container hermes-{tenant_code} no encontrado."})
    except APIError as e:
        return json.dumps({"error": str(e)})


_CREDENTIAL_FILE_MAP: dict[str, str] = {
    "google_token": "google_token.json",
    "notion_key": ".env",
    "airtable_key": ".env",
    "github_token": ".env",
    "linear_key": ".env",
}

# Tipo literal para credenciales soportadas.
# Agno convierte Literal a enum en el JSON schema del tool — el LLM
# solo puede pasar uno de estos valores exactos.
# Ref: https://docs.agno.com/tools/introduction
CredentialType = Literal["google_token", "notion_key", "airtable_key", "github_token", "linear_key"]


def inject_credential(
    tenant_code: str,
    credential_type: CredentialType,
    credential_value: str,
) -> str:
    """Inyecta una credencial en el volumen del tenant. Requiere aprobacion.

    Parámetros:
    - tenant_code: código del tenant (ej: t001)
    - credential_type: tipo de credencial. Valores válidos:
        google_token — archivo google_token.json para integración Google
        notion_key   — NOTION_KEY en .env
        airtable_key — AIRTABLE_KEY en .env
        github_token — GITHUB_TOKEN en .env
        linear_key   — LINEAR_KEY en .env
    - credential_value: valor de la credencial (string, puede ser JSON)
    """
    tp = Path(settings.tenants_base_path) / tenant_code
    if not tp.exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe en disco."})
    target = _CREDENTIAL_FILE_MAP.get(credential_type)
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
        return json.dumps(
            {"success": True, "tenant": tenant_code, "credential": credential_type, "file": target}
        )
    except OSError as e:
        return json.dumps({"error": str(e)})


# Tipo literal para métodos de pago soportados.
# Agno convierte Literal a enum en el JSON schema — el LLM no puede
# inventarse métodos de pago fuera de este conjunto.
PaymentMethod = Literal["transferencia", "stripe", "crypto", "efectivo", "otro"]


def register_payment(
    tenant_code: str,
    amount: float,
    method: PaymentMethod,
    months: int = 1,
    reference: str = "",
) -> str:
    """Registra un pago manual. Requiere aprobacion con audit trail.

    Parámetros:
    - tenant_code: código del tenant (ej: t001)
    - amount: monto en USD. Debe ser mayor a 0 (ej: 30.0)
    - method: método de pago. Valores válidos:
        transferencia, stripe, crypto, efectivo, otro
    - months: meses de servicio que cubre el pago (default: 1, máximo: 12)
    - reference: número de transacción o referencia (opcional)
    """
    if amount <= 0:
        return json.dumps({"error": f"amount debe ser mayor a 0. Recibido: {amount}"})
    if months < 1 or months > 12:
        return json.dumps({"error": f"months debe ser entre 1 y 12. Recibido: {months}"})
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
                (row[0], amount, method, reference or None, start, end),
            )
            conn.execute(
                "UPDATE tenants SET paid_until=%s, status='active' WHERE id=%s", (end, row[0])
            )
            conn.commit()
        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "amount": amount,
                "method": method,
                "paid_until": end.isoformat(),
            }
        )
    except psycopg.Error as e:
        return json.dumps({"error": str(e)})


def inject_wiki_content(
    tenant_code: str,
    company_name: str,
    company_description: str,
    team_members: str = "",
    tools_used: str = "",
    active_projects: str = "",
    custom_pages: str = "",
) -> str:
    """Pre-carga la LLM Wiki del tenant con informacion de la empresa."""
    from datetime import date as _date

    wiki = Path(settings.tenants_base_path) / tenant_code / "wiki"
    if not (Path(settings.tenants_base_path) / tenant_code).exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe."})
    today = _date.today().isoformat()
    slug = company_name.lower().replace(" ", "-")
    try:
        for d in [
            "raw/articles",
            "raw/papers",
            "raw/transcripts",
            "raw/assets",
            "entities",
            "concepts",
            "comparisons",
            "queries",
        ]:
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
        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "files_created": created,
                "message": f"Wiki de {company_name} inicializada.",
            }
        )
    except OSError as e:
        return json.dumps({"error": str(e)})


# =============================================================================
# BACKUP / RESTORE — Hermes tenant data
#
# Cada tenant tiene su volumen en /var/lib/martes/tenants/{tenant_code}/
# que se monta como /opt/data dentro del container Hermes.
#
# EXCLUSIONES OBLIGATORIAS (extraídas del repo oficial de Hermes):
# Ref: https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/backup.py
#
#   gateway.pid / cron.pid   — PIDs del proceso. Stale en cualquier restore.
#   *.db-wal / *.db-shm      — Sidecars WAL de SQLite. Si se incluyen junto al
#   *.db-journal               .db principal produce un "torn restore" (BD corrompida).
#   checkpoints/             — Caches locales de sesión, no portables.
#
# PERMISOS OBLIGATORIOS EN RESTORE:
#   .env, auth.json, state.db → chmod 600
#
# FLUJO DE BACKUP:
#   1. Crear tar.gz local excluyendo archivos estériles (_BACKUP_EXCLUDE_*)
#   2. Subir a SeaweedFS S3 → tenants/{code}/{code}_{ts}.tar.gz
#   3. Borrar archivo local (ya está en SeaweedFS)
#   4. Cleanup: mantener últimos settings.storage_keep_last backups
#
# FLUJO DE RESTORE (SOLO CON CONTAINER DETENIDO):
#   1. Descargar de SeaweedFS a /tmp/ (temporal)
#   2. Extraer sobre el directorio del tenant
#   3. Eliminar archivos estériles: gateway.pid, gateway.lock, *.db-wal, *.db-shm
#   4. Corregir permisos: .env 0600, auth.json 0600, state.db 0600
#   5. _chown() → permisos para usuario hermes (1000:1000)
# =============================================================================

# Nombres de archivo que nunca deben ir en un backup.
# Ref: hermes_cli/backup.py:_EXCLUDED_NAMES
_BACKUP_EXCLUDE_NAMES: frozenset[str] = frozenset({"gateway.pid", "cron.pid"})

# Sufijos de archivo que nunca deben ir en un backup.
# Ref: hermes_cli/backup.py:_EXCLUDED_SUFFIXES
_BACKUP_EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".db-wal",
    ".db-shm",
    ".db-journal",
    ".pyc",
    ".pyo",
)

# Directorios que nunca deben ir en un backup.
_BACKUP_EXCLUDE_DIRS: frozenset[str] = frozenset({"checkpoints", "__pycache__"})

# Archivos estériles a eliminar DESPUÉS de restaurar un backup.
_RESTORE_STALE_FILES: tuple[str, ...] = ("gateway.pid", "gateway.lock", "cron.pid")

# Archivos sensibles que necesitan chmod 600 tras el restore.
_RESTORE_SECRET_FILES: tuple[str, ...] = (".env", "auth.json", "state.db")


def _tar_filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """Filter para tarfile.add() que excluye archivos estériles de Hermes.

    Compatible con el parámetro filter= de TarFile.add() en Python 3.12+.
    Ref: https://docs.python.org/3/library/tarfile.html#tarfile.TarFile.add
    """
    name = Path(tarinfo.name).name
    if name in _BACKUP_EXCLUDE_NAMES:
        return None
    if name.endswith(_BACKUP_EXCLUDE_SUFFIXES):
        return None
    parts = Path(tarinfo.name).parts
    if any(p in _BACKUP_EXCLUDE_DIRS for p in parts):
        return None
    return tarinfo


def backup_tenant(tenant_code: str) -> str:
    """Crea backup completo del tenant y lo sube a SeaweedFS.

    Excluye archivos estériles siguiendo las prácticas oficiales de Hermes:
    gateway.pid, cron.pid, *.db-wal, *.db-shm, *.db-journal, checkpoints/
    Ref: https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/backup.py

    Si SeaweedFS no está disponible, el backup queda en disco local como fallback.
    Requiere aprobacion.
    """
    from src import storage

    tenant_path = Path(settings.tenants_base_path) / tenant_code
    if not tenant_path.exists():
        return json.dumps({"error": f"Tenant {tenant_code} no encontrado en disco."})
    try:
        _BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{tenant_code}_{ts}.tar.gz"
        backup_file = _BACKUPS_DIR / filename

        # 1. Crear tar.gz excluyendo archivos estériles
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(tenant_path, arcname=tenant_code, filter=_tar_filter)
        size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)

        # 2. Subir a SeaweedFS si está disponible
        remote_key: str | None = None
        deleted_old: list[str] = []
        if storage.storage_available():
            remote_key = storage.upload_backup(backup_file, tenant_code, filename)
            backup_file.unlink()
            deleted_old = storage.cleanup_old_backups(tenant_code)
        else:
            remote_key = None

        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "backup_file": filename,
                "size_mb": size_mb,
                "storage": "seaweedfs" if remote_key else "local",
                "remote_key": remote_key,
                "deleted_old": deleted_old,
                "message": (
                    f"Backup {filename} ({size_mb} MB) "
                    + (
                        f"subido a SeaweedFS. {len(deleted_old)} backups antiguos eliminados."
                        if remote_key
                        else "guardado en disco local (SeaweedFS no disponible)."
                    )
                ),
            }
        )
    except (OSError, tarfile.TarError) as e:
        return json.dumps({"success": False, "error": str(e)})


def restore_tenant_from_backup(tenant_code: str, backup_filename: str) -> str:
    """Restaura un tenant desde un backup en SeaweedFS o disco local.

    IMPORTANTE: el container DEBE estar detenido antes de restaurar.
    Tras extraer el backup, limpia archivos estériles:
    - gateway.pid, gateway.lock, cron.pid (PIDs stale)
    - *.db-wal, *.db-shm (sidecars WAL — producen BD corrupta si quedan)
    - Permisos: .env, auth.json, state.db → chmod 600
    Ref: https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/backup.py

    Requiere aprobacion — operacion destructiva.
    """
    from src import storage

    if not backup_filename.endswith(".tar.gz"):
        return json.dumps({"error": "Nombre de backup inválido. Debe terminar en .tar.gz"})

    tenant_path = Path(settings.tenants_base_path) / tenant_code
    temp_file: Path | None = None

    try:
        # Verificar que no hay container corriendo (prevenir corrupción)
        try:
            c = docker.from_env().containers.get(f"hermes-{tenant_code}")
            if c.status == "running":
                return json.dumps(
                    {
                        "error": f"Container hermes-{tenant_code} está corriendo. "
                        "Usa stop_tenant() primero para evitar corrupción de datos."
                    }
                )
        except NotFound:
            pass  # Container no existe, ok para restaurar

        # Localizar backup: SeaweedFS primero, disco local como fallback
        local_path = _BACKUPS_DIR / backup_filename
        if storage.storage_available():
            temp_dir = Path("/tmp/martes_restore")
            temp_file = storage.download_backup(tenant_code, backup_filename, temp_dir)
            backup_file = temp_file
        elif local_path.exists():
            backup_file = local_path
        else:
            return json.dumps(
                {
                    "error": (
                        f"Backup '{backup_filename}' no encontrado en SeaweedFS ni en disco local."
                    )
                }
            )

        # Extraer backup
        tenant_path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(backup_file, "r:gz") as tar:
            members = tar.getmembers()
            if members and not members[0].name.startswith(tenant_code):
                return json.dumps(
                    {
                        "error": f"El backup no corresponde al tenant {tenant_code}. "
                        f"Contenido: {members[0].name}"
                    }
                )
            tar.extractall(path=Path(settings.tenants_base_path), filter="data")

        # Limpiar archivos estériles del backup
        cleaned: list[str] = []
        for name in _RESTORE_STALE_FILES:
            stale = tenant_path / name
            if stale.exists():
                stale.unlink()
                cleaned.append(name)
        for suffix in (".db-wal", ".db-shm", ".db-journal"):
            for stale_wal in tenant_path.rglob(f"*{suffix}"):
                stale_wal.unlink()
                cleaned.append(stale_wal.name)

        # Corregir permisos de archivos sensibles (chmod 600)
        for secret_name in _RESTORE_SECRET_FILES:
            secret_path = tenant_path / secret_name
            if secret_path.exists():
                os.chmod(secret_path, 0o600)

        _chown(tenant_path)
        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "restored_from": backup_filename,
                "cleaned_stale": cleaned,
                "message": (
                    f"Tenant {tenant_code} restaurado desde {backup_filename}. "
                    + (f"Archivos estériles eliminados: {cleaned}. " if cleaned else "")
                    + "Puedes reiniciar el container con restart_tenant()."
                ),
            }
        )
    except (OSError, tarfile.TarError) as e:
        return json.dumps({"success": False, "error": str(e)})
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)


@tool
def update_tenant_model(tenant_code: str, model_id: str) -> str:
    """Cambia el modelo LLM de un tenant sin reiniciar.
    Hermes recarga config.yaml en cada turno — efecto en el próximo mensaje.
    El cliente también puede cambiarlo él mismo con /model en Telegram.

    Modelos disponibles en OpenRouter:
    - openai/gpt-4o-mini     (default, balanceado)
    - openai/gpt-4o          (más potente)
    - deepseek/deepseek-v4-flash  (1M ctx, muy barato)
    - anthropic/claude-3.5-haiku  (buena calidad)
    - anthropic/claude-opus-4.6   (premium)
    No requiere aprobación.
    """
    config_path = Path(settings.tenants_base_path) / tenant_code / "config.yaml"
    if not config_path.exists():
        return json.dumps({"error": f"config.yaml no encontrado para {tenant_code}."})
    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        previous = (config.get("model") or {}).get("default", "desconocido")
        if "model" not in config or not isinstance(config["model"], dict):
            config["model"] = {}
        config["model"]["default"] = model_id
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "previous_model": previous,
                "new_model": model_id,
                "message": f"{previous} → {model_id}. Efecto en el próximo mensaje.",
            }
        )
    except (OSError, yaml.YAMLError) as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def update_tenant_soul(tenant_code: str, soul_content: str) -> str:
    """Actualiza la personalidad (SOUL.md) de un tenant sin reiniciar.
    Hermes carga SOUL.md fresco en cada turno.
    No requiere aprobación.
    """
    soul_path = Path(settings.tenants_base_path) / tenant_code / "SOUL.md"
    if not (Path(settings.tenants_base_path) / tenant_code).exists():
        return json.dumps({"error": f"Tenant {tenant_code} no existe."})
    try:
        soul_path.write_text(soul_content, encoding="utf-8")
        os.chmod(soul_path, 0o644)
        _chown(soul_path)
        return json.dumps(
            {
                "success": True,
                "tenant": tenant_code,
                "chars": len(soul_content),
                "message": "SOUL.md actualizado. Efecto en el próximo mensaje.",
            }
        )
    except OSError as e:
        return json.dumps({"success": False, "error": str(e)})
