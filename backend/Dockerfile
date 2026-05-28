# API gateway image (FastAPI). The heavy EnergyPlus worker is Dockerfile.worker.
FROM python:3.11-slim

WORKDIR /app

# Native libs for WeasyPrint PDF rendering (pango). Without them the API still
# runs; the /pdf endpoint just returns 503 and the HTML report is used.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STORAGE_DIR=/data/storage \
    DATABASE_URL=sqlite:////data/energy_modeler.db
RUN mkdir -p /data/storage

EXPOSE 8000
# Bind the platform-provided $PORT (Render/Railway/etc.) when present; default
# to 8000 for local/Fly. Shell form so the variable is expanded.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
