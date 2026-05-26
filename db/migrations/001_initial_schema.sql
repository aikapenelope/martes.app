-- Martes.app — Schema inicial de plataforma
-- Se ejecuta automaticamente al iniciar PostgreSQL por primera vez
-- (montado en /docker-entrypoint-initdb.d/)

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TENANTS: Clientes del SaaS
-- =============================================================================
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_code     VARCHAR(10) UNIQUE NOT NULL,  -- t001, t002, etc.
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    plan            VARCHAR(20) NOT NULL CHECK (plan IN ('basico', 'equipo', 'pro')),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'archived', 'creating')),
    container_name  VARCHAR(100),
    network_name    VARCHAR(100),
    paid_until      DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tenant_code ON tenants(tenant_code);

-- =============================================================================
-- INSTANCE_CONFIGS: Configuracion tecnica de cada tenant
-- =============================================================================
CREATE TABLE instance_configs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    template        VARCHAR(20) NOT NULL,  -- basico, equipo, pro
    platforms       TEXT[] NOT NULL DEFAULT '{}',  -- {telegram, discord, whatsapp}
    skills          TEXT[] NOT NULL DEFAULT '{}',  -- {web, memory, todo, ...}
    model           VARCHAR(100) NOT NULL DEFAULT 'deepseek/deepseek-chat',
    memory_limit_mb INTEGER NOT NULL DEFAULT 512,
    cpu_limit       NUMERIC(3,2) NOT NULL DEFAULT 0.50,
    extra_config    JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id)
);

-- =============================================================================
-- PAYMENTS: Registro manual de pagos
-- =============================================================================
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    amount          NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(10) NOT NULL DEFAULT 'USD',
    method          VARCHAR(50),  -- transferencia, zelle, pago_movil, crypto
    reference       VARCHAR(255),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    notes           TEXT,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_tenant ON payments(tenant_id);
CREATE INDEX idx_payments_period ON payments(period_start, period_end);

-- =============================================================================
-- HEALTH_CHECKS: Historial de health checks por tenant
-- =============================================================================
CREATE TABLE health_checks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL CHECK (status IN ('healthy', 'unhealthy', 'stopped', 'not_found')),
    response_ms     INTEGER,
    details         JSONB DEFAULT '{}',
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_health_checks_tenant ON health_checks(tenant_id);
CREATE INDEX idx_health_checks_time ON health_checks(checked_at DESC);

-- =============================================================================
-- ERROR_LOGS: Errores de containers para diagnostico
-- =============================================================================
CREATE TABLE error_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,
    source          VARCHAR(50) NOT NULL DEFAULT 'container',  -- container, meta-agent, system
    severity        VARCHAR(20) NOT NULL DEFAULT 'error'
                    CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    message         TEXT NOT NULL,
    details         JSONB DEFAULT '{}',
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_error_logs_tenant ON error_logs(tenant_id);
CREATE INDEX idx_error_logs_unresolved ON error_logs(resolved) WHERE resolved = FALSE;

-- =============================================================================
-- FUNCION: Auto-update de updated_at
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tenants_updated
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_instance_configs_updated
    BEFORE UPDATE ON instance_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
