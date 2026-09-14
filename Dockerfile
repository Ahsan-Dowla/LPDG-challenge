# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="LPDG Gateway Ranking" \
      org.opencontainers.image.description="Smart meter gateway visit prioritization API" \
      org.opencontainers.image.version="2.0.0"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source and entrypoints
COPY src/ src/
COPY main.py scripts/ ./

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/data /app/outputs && \
    chown -R appuser:appuser /app

USER appuser

ENV DATA_DIR=/app/data \
    OUTPUT_DIR=/app/outputs \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    RANKING_STRATEGY=optimized \
    LOG_LEVEL=INFO \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
