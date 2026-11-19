FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MCP_TRANSPORT=streamable-http \
    HOME=/tmp \
    GITHUB_MCP_CACHE_DIR=/tmp/github-mcp-cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE* ./
COPY server.py github_client.py credential_store.py actions_ci.py actions_tools.py ./

RUN pip install --no-cache-dir . \
    && groupadd -r appuser \
    && useradd -r -g appuser -d /tmp -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health')" || exit 1

CMD ["python", "-m", "server"]

