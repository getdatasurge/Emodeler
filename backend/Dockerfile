# API gateway image (FastAPI). The heavy EnergyPlus worker is Dockerfile.worker.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STORAGE_DIR=/data/storage \
    DATABASE_URL=sqlite:////data/energy_modeler.db
RUN mkdir -p /data/storage

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
