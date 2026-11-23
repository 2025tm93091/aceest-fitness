# ---------------------------------------------------------------------------
# ACEest Fitness & Gym — Production Dockerfile
# ---------------------------------------------------------------------------
# Design principles:
#   - Slim base image (small attack surface + fast pulls)
#   - Non-root user (security best practice)
#   - Layer caching (requirements before source)
#   - HEALTHCHECK so Docker/K8s knows when the app is ready
#   - Matches local Python 3.14 so "works locally" == "works in container"
# ---------------------------------------------------------------------------

FROM python:3.14-slim

# Release identifier baked into the image (shown by GET / and GET /version).
#   docker build --build-arg APP_VERSION=2.0.0 -t <user>/aceest-fitness:v2 .
ARG APP_VERSION=1.0.0
LABEL org.opencontainers.image.title="aceest-fitness" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.source="https://github.com/2025tm93091/aceest-fitness"

# Prevent .pyc files and enable unbuffered stdout (better for docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${APP_VERSION} \
    ACEEST_DB_PATH=/tmp/aceest_fitness.db

WORKDIR /app

# ---- Layer 1: dependencies (cached unless requirements.txt changes) ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Layer 2: application source ----
COPY app.py core.py db.py report.py ./

# ---- Layer 3: non-root user for security ----
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# ---- Runtime ----
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health').status == 200 else 1)"

CMD ["python", "app.py"]