"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
MODELS_DIR = Path(os.getenv("MODELS_DIR", APP_DIR.parent / "models"))

WORD_MODEL_PATH = MODELS_DIR / os.getenv("WORD_MODEL_FILE", "word-v1.onnx")
WORD_LABELS_PATH = MODELS_DIR / os.getenv("WORD_LABELS_FILE", "word-v1.labels.json")

# Comma-separated list of allowed browser origins.
# CORS is reliably the first thing to break on the first real deploy: the app
# works on localhost, then the Vercel domain gets blocked. Set this on Render.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

TOP_K = int(os.getenv("TOP_K", "5"))

# When true, the API refuses to start without a model. Leave false in
# development so you can work on the frontend before any model exists.
REQUIRE_MODEL = os.getenv("REQUIRE_MODEL", "false").lower() in {"1", "true", "yes"}
