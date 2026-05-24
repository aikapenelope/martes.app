-- Migración 002: Modelo Hermes libre — un solo plan
-- =============================================================================
-- Contexto: el refactor a modelo "Hermes libre" eliminó los tiers basico/equipo/pro.
-- Todos los tenants son técnicamente idénticos. El campo 'plan' es solo metadata
-- de billing interna. Esta migración actualiza el constraint para reflejar eso.
--
-- ⚠️  Esta migración NO se aplica automáticamente a una DB ya inicializada.
-- La aplicas UNA vez con el siguiente comando desde el servidor:
--
--   docker exec -i <container_db> psql -U martes -d martes < \
--     /path/to/db/migrations/002_single_plan.sql
--
-- O desde Coolify terminal / SSH:
--   docker exec -i $(docker ps -q -f name=db) psql -U martes -d martes << 'SQL'
--   [contenido de este archivo]
--   SQL
--
-- Para nuevas instalaciones desde cero, esta migración corre automáticamente.
-- =============================================================================

-- 1. Reemplazar constraint de plan: solo acepta 'basico' (etiqueta interna única)
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_plan_check;
ALTER TABLE tenants
    ADD CONSTRAINT tenants_plan_check CHECK (plan IN ('basico'));

COMMENT ON COLUMN tenants.plan IS
    'Etiqueta interna de billing. Siempre "basico" — modelo Hermes libre sin tiers.';

-- 2. Limpiar el default del template en instance_configs
ALTER TABLE instance_configs
    ALTER COLUMN template SET DEFAULT 'default';

COMMENT ON COLUMN instance_configs.template IS
    'Template de configuración. Siempre "default" — modelo Hermes libre sin tiers.';

-- 3. Forzar consistencia en filas existentes (por si quedaron con valores viejos)
UPDATE tenants
    SET plan = 'basico'
    WHERE plan IN ('equipo', 'pro', 'starter', 'growth', 'scale');

UPDATE instance_configs
    SET template = 'default'
    WHERE template IN ('basico', 'equipo', 'pro');

-- Verificación
DO $$
DECLARE
    invalid_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO invalid_count
    FROM tenants
    WHERE plan != 'basico';

    IF invalid_count > 0 THEN
        RAISE WARNING '% tenants tienen plan distinto a basico — revisar manualmente', invalid_count;
    ELSE
        RAISE NOTICE 'OK: todos los tenants tienen plan = basico';
    END IF;
END $$;
