
# Dockerfile — service de criticité maintenance prédictive (M0-B1)
#
# Commande type pour build et lancer une fois ce fichier complété :
#   docker build -t fastia-maintenance:dev .
#   docker run --rm -p 8000:8000 fastia-maintenance:dev
#   curl http://localhost:8000/health

# ── Stage 1 : builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt \
    && find /install -type f -name "*.pyc" -delete \
    && find /install -type f -name "*.pyo" -delete \
    && find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true \
    && find /install -type d -name "tests"       -exec rm -rf {} + 2>/dev/null; true \
    && find /install -type d -name "test"        -exec rm -rf {} + 2>/dev/null; true

# ── Stage 2 : image de production (légère) ────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Récupère uniquement les packages installés (pas pip, pas les caches)
COPY --from=builder /install /usr/local

COPY app/ ./app/
COPY model/ ./model/

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]