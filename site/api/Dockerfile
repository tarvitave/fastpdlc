FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Runs unprivileged. /data must exist in the IMAGE and be owned by appuser:
# Docker seeds an empty named volume from the image path, ownership included.
# Without this the volume is created root-owned and SQLite cannot open its file.
RUN useradd --uid 10001 --create-home appuser  && mkdir -p /data  && chown appuser:appuser /data
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
