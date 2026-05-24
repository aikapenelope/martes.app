"""Storage layer — cliente boto3 para SeaweedFS S3-compatible.

SeaweedFS implementa la API S3 de Amazon completa en el puerto 8333.
Usamos boto3 (el SDK oficial de AWS) para interactuar con él exactamente
igual que con AWS S3 o cualquier otro servicio S3-compatible.

El endpoint apunta al servicio 'seaweedfs' via Docker DNS interno —
no hay red pública involucrada.

Ref boto3: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
Ref SeaweedFS S3 API: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointResolutionError

from src.config import settings

logger = logging.getLogger(__name__)


def _s3() -> Any:
    """Devuelve un cliente boto3 configurado para SeaweedFS.

    SeaweedFS requiere signature_version='s3v4'.
    region_name='us-east-1' es exigido por boto3 aunque SeaweedFS lo ignora.
    Ref: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def storage_available() -> bool:
    """Verifica si SeaweedFS es accesible. Usado como guard en todas las ops."""
    if not settings.storage_access_key or not settings.storage_secret_key:
        return False
    try:
        _s3().list_buckets()
        return True
    except (ClientError, EndpointResolutionError, Exception):
        return False


def ensure_bucket() -> None:
    """Crea el bucket martes-backups si no existe.

    SeaweedFS auto-crea el bucket via S3_BUCKET env var al arrancar,
    pero esta función garantiza que exista antes de subir objetos.
    Después de confirmar el bucket, aplica la lifecycle rule de 30 días.
    """
    client = _s3()
    bucket = settings.storage_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            client.create_bucket(Bucket=bucket)
            logger.info("Bucket '%s' creado en SeaweedFS", bucket)
        else:
            raise
    # Lifecycle rule — safety net sobre cleanup_old_backups(keep_last=7)
    ensure_bucket_lifecycle()


def ensure_bucket_lifecycle(days: int = 30) -> bool:
    """Configura lifecycle rule en SeaweedFS para expirar objetos tras N días.

    Capa de seguridad adicional sobre cleanup_old_backups(keep_last=7):
    si el cleanup programado falla silenciosamente, los objetos se eliminan
    automáticamente a los 30 días por la lifecycle rule del bucket.

    Idempotente — reemplaza cualquier configuración anterior con la misma rule.
    Solo aplica al prefix 'tenants/' para no afectar otros posibles objetos en
    el bucket.

    SeaweedFS soporta Expiration en lifecycle rules. Transition no está soportado.
    Ref: https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API
    Ref source: seaweedfs/weed/s3api/s3api_bucket_lifecycle_config.go
    Ref boto3: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/
               services/s3/client/put_bucket_lifecycle_configuration.html

    Returns:
        True si la rule fue configurada correctamente, False en caso de error.
    """
    try:
        _s3().put_bucket_lifecycle_configuration(
            Bucket=settings.storage_bucket,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "expire-old-backups",
                        "Status": "Enabled",
                        "Filter": {"Prefix": "tenants/"},
                        "Expiration": {"Days": days},
                    }
                ]
            },
        )
        logger.info(
            "Lifecycle rule configurada: objetos en tenants/ expiran a los %d días",
            days,
        )
        return True
    except Exception as exc:
        # No-fatal — el cleanup programado sigue siendo la línea primaria.
        # SeaweedFS más antiguo o mal configurado puede no soportar lifecycle.
        logger.debug("No se pudo configurar lifecycle rule en SeaweedFS: %s", exc)
        return False


def upload_backup(local_path: Path, tenant_code: str, filename: str) -> str:
    """Sube un archivo de backup a SeaweedFS y devuelve la key S3.

    Estructura de keys:
      tenants/{tenant_code}/{filename}

    Ejemplo:
      tenants/t001/t001_20260524_030000.tar.gz

    Args:
        local_path: Ruta local del archivo .tar.gz a subir.
        tenant_code: Código del tenant (ej: 't001').
        filename: Nombre del archivo (ej: 't001_20260524_030000.tar.gz').

    Returns:
        La key S3 del objeto subido.
    """
    ensure_bucket()
    key = f"tenants/{tenant_code}/{filename}"
    _s3().upload_file(
        Filename=str(local_path),
        Bucket=settings.storage_bucket,
        Key=key,
    )
    logger.info("Backup subido: s3://%s/%s", settings.storage_bucket, key)
    return key


def download_backup(tenant_code: str, filename: str, local_dest: Path) -> Path:
    """Descarga un backup de SeaweedFS a disco local.

    Args:
        tenant_code: Código del tenant.
        filename: Nombre del archivo en el bucket.
        local_dest: Directorio local donde guardar el archivo.

    Returns:
        Ruta local del archivo descargado.
    """
    key = f"tenants/{tenant_code}/{filename}"
    local_dest.mkdir(parents=True, exist_ok=True)
    dest_file = local_dest / filename
    _s3().download_file(
        Bucket=settings.storage_bucket,
        Key=key,
        Filename=str(dest_file),
    )
    logger.info("Backup descargado: %s → %s", key, dest_file)
    return dest_file


def list_tenant_backups(tenant_code: str) -> list[dict[str, Any]]:
    """Lista todos los backups de un tenant en SeaweedFS, ordenados del más reciente al más antiguo.

    Returns:
        Lista de dicts con: filename, key, size_mb, created_at (ISO 8601).
    """
    prefix = f"tenants/{tenant_code}/"
    response = _s3().list_objects_v2(
        Bucket=settings.storage_bucket,
        Prefix=prefix,
    )
    objects = response.get("Contents", [])
    backups = []
    for obj in objects:
        key: str = obj["Key"]
        filename = key.split("/")[-1]
        if not filename.endswith(".tar.gz"):
            continue
        last_modified: datetime = obj["LastModified"]
        backups.append(
            {
                "filename": filename,
                "key": key,
                "size_mb": round(obj["Size"] / (1024 * 1024), 2),
                "created_at": last_modified.astimezone(timezone.utc).isoformat(),
            }
        )
    # Más reciente primero
    backups.sort(key=lambda b: b["created_at"], reverse=True)
    return backups


def delete_backup(tenant_code: str, filename: str) -> None:
    """Elimina un backup específico de SeaweedFS."""
    key = f"tenants/{tenant_code}/{filename}"
    _s3().delete_object(Bucket=settings.storage_bucket, Key=key)
    logger.info("Backup eliminado: s3://%s/%s", settings.storage_bucket, key)


def cleanup_old_backups(tenant_code: str, keep_last: int | None = None) -> list[str]:
    """Elimina backups antiguos conservando solo los últimos `keep_last`.

    Args:
        tenant_code: Código del tenant.
        keep_last: Cuántos backups retener. Por defecto: settings.storage_keep_last.

    Returns:
        Lista de filenames eliminados.
    """
    limit = keep_last if keep_last is not None else settings.storage_keep_last
    backups = list_tenant_backups(tenant_code)  # ya ordenados, más reciente primero
    to_delete = backups[limit:]  # los que superan el límite
    deleted = []
    for b in to_delete:
        delete_backup(tenant_code, b["filename"])
        deleted.append(b["filename"])
    if deleted:
        logger.info(
            "Cleanup tenant %s: %d backups eliminados (keep_last=%d)",
            tenant_code,
            len(deleted),
            limit,
        )
    return deleted
