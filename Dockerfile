# CareerNavigator AI — production image (FastAPI + built React workspace + Tesseract)
FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY research/01_resume_intelligence/requirements-prod.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY research/01_resume_intelligence/ ./
COPY --from=frontend /src/frontend/dist /app/frontend_dist

# SQLite accounts and any durable files. blitz.cloud keeps VOLUME paths across restarts.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV CAREERNAV_STATIC_DIR=/app/frontend_dist \
    CAREERNAV_DATABASE_URL=sqlite:////app/data/careernavigator.sqlite \
    CAREERNAV_COOKIE_SECURE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# blitz.cloud sets PORT (default 8080) and reads EXPOSE from the image.
EXPOSE 8080
CMD ["sh", "-c", "mkdir -p /app/data && uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 75"]
