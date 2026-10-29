FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
# pg_isready is used by the entrypoint; curl is used by the API healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r jategroup && useradd -r -g jategroup -u 1001 jateuser \
    && mkdir -p /app/storage/pdfs && chown -R jateuser:jategroup /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=1001:1001 --chmod=755 entrypoint.sh /app/entrypoint.sh
COPY --chown=1001:1001 app /app/app
USER 1001:1001
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
