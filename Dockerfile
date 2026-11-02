FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 james \
    && useradd --uid 10001 --gid james --no-create-home james

COPY --chown=james:james james ./james
COPY --chown=james:james migrations ./migrations
COPY --chown=james:james wsgi.py ./
COPY --chown=james:james scripts/check_receipt_tools.py ./scripts/check_receipt_tools.py
RUN mkdir -p /app/instance && chown james:james /app/instance

USER james
CMD ["sh", "-c", "exec gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --access-logfile -"]
