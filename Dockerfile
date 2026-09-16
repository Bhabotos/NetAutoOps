# syntax=docker/dockerfile:1

# ---- builder: install dependencies into an isolated user site-packages dir ----
FROM python:3.14-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- runtime: copy only the installed packages + app code, run as non-root ----
FROM python:3.14-slim

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY app ./app

# logs/ and backups/ are normally host bind mounts (see docker-compose.yml);
# creating them here too so the app has somewhere to write even if run
# standalone without those mounts.
RUN mkdir -p logs backups config && chown -R appuser:appuser /app

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
