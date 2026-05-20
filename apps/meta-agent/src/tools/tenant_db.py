"""Tools para CRUD de tenants en PostgreSQL."""

import json
from datetime import date, datetime, timedelta, timezone

import psycopg

from src.config import settings


def _get_conn_str() -> str:
    """Retorna connection string para psycopg (sin el prefijo de driver)."""
    # DATABASE_URL viene como postgresql+psycopg://... necesitamos postgresql://...
    url = settings.database_url
    if "+psycopg" in url:
        url = url.replace("+psycopg", "")
    return url


def _next_tenant_code() -> str:
    """Genera el siguiente codigo de tenant (t001, t002, etc.)."""
    with psycopg.connect(_get_conn_str()) as conn:
        row = conn.execute(
            "SELECT tenant_code FROM tenants ORDER BY tenant_code DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return "t001"
        last_num = int(row[0][1:])  # "t003" -> 3
        return f"t{last_num + 1:03d}"


def create_tenant_record(
    name: str,
    plan: str,
    email: str | None = None,
    platforms: list[str] | None = None,
    model: str | None = None,
) -> str:
    """Crea un registro de tenant en la base de datos.

    Args:
        name: Nombre del cliente/empresa.
        plan: Plan contratado (basico, equipo, pro).
        email: Email de contacto (opcional).
        platforms: Plataformas habilitadas (default segun plan).
        model: Modelo LLM a usar (default segun plan).

    Returns:
        JSON con el tenant creado incluyendo tenant_code.
    """
    if plan not in ("basico", "equipo", "pro"):
        return json.dumps({"success": False, "error": f"Plan invalido: {plan}"})

    tenant_code = _next_tenant_code()

    # Defaults por plan
    default_platforms: dict[str, list[str]] = {
        "basico": ["telegram"],
        "equipo": ["telegram", "discord"],
        "pro": ["telegram", "discord", "whatsapp"],
    }
    default_models: dict[str, str] = {
        "basico": "deepseek/deepseek-chat",
        "equipo": "deepseek/deepseek-chat",
        "pro": "anthropic/claude-3.5-haiku",
    }

    effective_platforms = platforms or default_platforms[plan]
    effective_model = model or default_models[plan]

    # Limites por plan
    plan_limits: dict[str, dict[str, int | float]] = {
        "basico": {"memory_mb": 512, "cpus": 0.5},
        "equipo": {"memory_mb": 768, "cpus": 0.75},
        "pro": {"memory_mb": 1024, "cpus": 1.0},
    }
    limits = plan_limits[plan]

    try:
        with psycopg.connect(_get_conn_str()) as conn:
            # Insertar tenant
            row = conn.execute(
                """
                INSERT INTO tenants
                    (tenant_code, name, email, plan, status, container_name, network_name)
                VALUES (%s, %s, %s, %s, 'creating', %s, %s)
                RETURNING id, tenant_code, created_at
                """,
                (
                    tenant_code,
                    name,
                    email,
                    plan,
                    f"hermes-{tenant_code}",
                    f"tenant-{tenant_code}-net",
                ),
            ).fetchone()

            if row is None:
                return json.dumps({"success": False, "error": "Error al insertar tenant."})

            tenant_id = str(row[0])

            # Insertar config de instancia
            conn.execute(
                """
                INSERT INTO instance_configs
                    (tenant_id, template, platforms, skills, model, memory_limit_mb, cpu_limit)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row[0],
                    plan,
                    effective_platforms,
                    [],  # Skills se configuran segun template
                    effective_model,
                    int(limits["memory_mb"]),
                    float(limits["cpus"]),
                ),
            )
            conn.commit()

        return json.dumps(
            {
                "success": True,
                "tenant_id": tenant_id,
                "tenant_code": tenant_code,
                "name": name,
                "plan": plan,
                "platforms": effective_platforms,
                "model": effective_model,
                "container_name": f"hermes-{tenant_code}",
            }
        )

    except psycopg.Error as e:
        return json.dumps({"success": False, "error": str(e)})


def update_tenant_status(tenant_code: str, status: str) -> str:
    """Actualiza el estado de un tenant.

    Args:
        tenant_code: Codigo del tenant.
        status: Nuevo estado (active, paused, archived, creating).

    Returns:
        JSON con el resultado.
    """
    valid_statuses = ("active", "paused", "archived", "creating")
    if status not in valid_statuses:
        return json.dumps(
            {"success": False, "error": f"Estado invalido: {status}. Validos: {valid_statuses}"}
        )

    try:
        with psycopg.connect(_get_conn_str()) as conn:
            result = conn.execute(
                "UPDATE tenants SET status = %s WHERE tenant_code = %s RETURNING id, name",
                (status, tenant_code),
            ).fetchone()
            conn.commit()

            if result is None:
                return json.dumps(
                    {"success": False, "error": f"Tenant {tenant_code} no encontrado."}
                )

            return json.dumps(
                {
                    "success": True,
                    "tenant_code": tenant_code,
                    "new_status": status,
                    "name": result[1],
                }
            )

    except psycopg.Error as e:
        return json.dumps({"success": False, "error": str(e)})


def register_payment(
    tenant_code: str,
    amount: float,
    method: str,
    months: int = 1,
    reference: str | None = None,
    notes: str | None = None,
) -> str:
    """Registra un pago manual de un tenant.

    Args:
        tenant_code: Codigo del tenant.
        amount: Monto pagado.
        method: Metodo de pago (transferencia, zelle, pago_movil, crypto).
        months: Meses pagados (default 1).
        reference: Referencia del pago (opcional).
        notes: Notas adicionales (opcional).

    Returns:
        JSON con el resultado.
    """
    try:
        with psycopg.connect(_get_conn_str()) as conn:
            # Obtener tenant
            tenant = conn.execute(
                "SELECT id, paid_until FROM tenants WHERE tenant_code = %s",
                (tenant_code,),
            ).fetchone()

            if tenant is None:
                return json.dumps(
                    {"success": False, "error": f"Tenant {tenant_code} no encontrado."}
                )

            tenant_id = tenant[0]
            current_paid_until = tenant[1]

            # Calcular periodo
            today = date.today()
            period_start = (
                current_paid_until if current_paid_until and current_paid_until > today else today
            )
            period_end = period_start + timedelta(days=30 * months)

            # Registrar pago
            conn.execute(
                """
                INSERT INTO payments
                    (tenant_id, amount, method, reference, period_start, period_end, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (tenant_id, amount, method, reference, period_start, period_end, notes),
            )

            # Actualizar paid_until del tenant
            conn.execute(
                "UPDATE tenants SET paid_until = %s, status = 'active' WHERE id = %s",
                (period_end, tenant_id),
            )
            conn.commit()

            return json.dumps(
                {
                    "success": True,
                    "tenant_code": tenant_code,
                    "amount": amount,
                    "method": method,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "message": f"Pago de ${amount} registrado. Activo hasta {period_end}.",
                }
            )

    except psycopg.Error as e:
        return json.dumps({"success": False, "error": str(e)})


def get_all_tenants() -> str:
    """Obtiene todos los tenants con su estado actual.

    Returns:
        JSON con la lista de tenants.
    """
    try:
        with psycopg.connect(_get_conn_str()) as conn:
            rows = conn.execute(
                """
                SELECT t.tenant_code, t.name, t.plan, t.status, t.paid_until,
                       t.container_name, t.created_at,
                       ic.platforms, ic.model
                FROM tenants t
                LEFT JOIN instance_configs ic ON ic.tenant_id = t.id
                ORDER BY t.tenant_code
                """
            ).fetchall()

            tenants = []
            now = datetime.now(tz=timezone.utc).date()
            for row in rows:
                paid_until = row[4]
                days_remaining = (paid_until - now).days if paid_until else None
                tenants.append(
                    {
                        "tenant_code": row[0],
                        "name": row[1],
                        "plan": row[2],
                        "status": row[3],
                        "paid_until": paid_until.isoformat() if paid_until else None,
                        "days_remaining": days_remaining,
                        "container_name": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "platforms": row[7],
                        "model": row[8],
                    }
                )

            return json.dumps({"success": True, "count": len(tenants), "tenants": tenants})

    except psycopg.Error as e:
        return json.dumps({"success": False, "error": str(e)})
