# Inference API image.
# Target: ~300 MB. Keep it that way — do not add torch, opencv, or mediapipe.
# Feature extraction here is pure numpy; landmarks arrive already computed by
# the browser.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies first, so edits to application code reuse the cached layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY models/ ./models/

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

# Refuse to start without a model in production — a container that boots
# "successfully" and then 503s every request is much harder to notice.
ENV REQUIRE_MODEL=true

# Render provides $PORT. Default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
