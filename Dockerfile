FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# ---- etapa de ejecución (imagen de producción) ----
FROM base AS app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'))"
# $PORT lo define Render/Railway/Fly; por defecto 8000
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# ---- etapa de pruebas (docker compose run tests) ----
FROM base AS tests
COPY requirements-dev.txt requirements.txt ./
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["pytest", "--cov", "--cov-fail-under=80", "--cov-report=term-missing:skip-covered"]
