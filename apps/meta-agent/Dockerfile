FROM python:3.12-slim

WORKDIR /app/apps/meta-agent

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias primero (cache de Docker)
COPY apps/meta-agent/pyproject.toml ./
RUN pip install --no-cache-dir .

# Copiar codigo fuente
COPY apps/meta-agent/src ./src/

# Copiar templates de Hermes
COPY infra/templates /app/infra/templates

# Python path para imports
ENV PYTHONPATH="/app/apps/meta-agent"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Puerto del AgentOS (webhook de Telegram + API)
EXPOSE 8000

# Entry point
CMD ["python", "-m", "src.main"]
