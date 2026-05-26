-- Migración 004: métricas del servidor y log de backups para Metabase
--
-- server_metrics: historial de uso de disco. El health-check-all escribe
-- una fila cada 5 minutos. Permite ver tendencias y detectar crecimiento anormal.
--
-- backup_log: registro de cada backup creado. backup_tenant() escribe aquí
-- después de cada backup exitoso. Permite ver qué tenant fue respaldado cuándo,
-- con qué tamaño y si fue a SeaweedFS o disco local.

CREATE TABLE IF NOT EXISTS server_metrics (
    id          SERIAL PRIMARY KEY,
    disk_used_gb  NUMERIC(8,2) NOT NULL,
    disk_total_gb NUMERIC(8,2) NOT NULL,
    disk_pct      NUMERIC(5,1) NOT NULL,
    checked_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_server_metrics_time
    ON server_metrics(checked_at DESC);

COMMENT ON TABLE server_metrics IS
    'Métricas del servidor escritas por health-check-all cada 5 minutos.';
COMMENT ON COLUMN server_metrics.disk_pct IS
    '% de disco usado en /var/lib/martes. Alerta en >80%.';


CREATE TABLE IF NOT EXISTS backup_log (
    id          SERIAL PRIMARY KEY,
    tenant_code VARCHAR(10) NOT NULL REFERENCES tenants(tenant_code) ON DELETE CASCADE,
    filename    TEXT        NOT NULL,
    size_mb     NUMERIC(10,2),
    storage     VARCHAR(20) NOT NULL DEFAULT 'seaweedfs',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backup_log_tenant
    ON backup_log(tenant_code);
CREATE INDEX IF NOT EXISTS idx_backup_log_time
    ON backup_log(created_at DESC);

COMMENT ON TABLE backup_log IS
    'Registro de backups creados por backup_tenant(). Un registro por backup.';
COMMENT ON COLUMN backup_log.storage IS
    '"seaweedfs" si fue subido a S3, "local" si SeaweedFS no estaba disponible.';
