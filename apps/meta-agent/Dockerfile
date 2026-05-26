# martes.app — meta-agent (Agno AgentOS + Telegram)
# Build: GitHub Actions → GHCR
# Deploy: Coolify auto-deploy via GitHub App
FROM python:3.12-slim

WORKDIR /app/apps/meta-agent

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl wget && \
    rm -rf /var/lib/apt/lists/*

COPY apps/meta-agent/pyproject.toml ./
RUN pip install --no-cache-dir .

COPY apps/meta-agent/src ./src/
COPY infra/templates /app/infra/templates

ENV PYTHONPATH="/app/apps/meta-agent"

HEALTHCHECK --interval=30s --timeout=10s --start-period=25s --retries=3 \
    CMD curl -f http://localhost:7777/health || exit 1

EXPOSE 7777

CMD ["python", "-m", "src.main"]
