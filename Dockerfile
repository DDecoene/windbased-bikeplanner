FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser
COPY app/ app/
RUN mkdir -p /app/overpass_cache && chown -R appuser:appuser /app

EXPOSE 8000

# Fix volume permissions at startup (volume mount overrides build-time chown)
CMD ["sh", "-c", "chown -R appuser:appuser /app/overpass_cache && exec su -s /bin/sh appuser -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000'"]
