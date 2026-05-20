FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema (para psycopg y docker)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias primero (cache de Docker)
COPY apps/meta-agent/pyproject.toml /app/apps/meta-agent/
RUN pip install --no-cache-dir -e /app/apps/meta-agent/

# Copiar codigo fuente
COPY apps/meta-agent/src /app/apps/meta-agent/src

# Copiar templates de Hermes
COPY infra/templates /app/infra/templates

# Directorio de trabajo del meta-agente
WORKDIR /app/apps/meta-agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Puerto del AgentOS (webhook de Telegram + API)
EXPOSE 8000

# Entry point
CMD ["python", "src/main.py"]
