"""FastAPI application — the word-prediction service.

Letter prediction deliberately has no endpoint here: letters are static
handshapes classified entirely in the browser, so they need no network round
trip and cost nothing to serve. See web/src/lib/letter-model.ts.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .features import FEATURE_DIMS, SEQUENCE_LENGTH
from .inference import ModelNotLoadedError, SignClassifier
from .schemas import HealthResponse, PredictRequest, PredictResponse

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

classifier = SignClassifier(config.WORD_MODEL_PATH, config.WORD_LABELS_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load the model once, at startup, before serving any traffic."""
    try:
        classifier.load()
    except FileNotFoundError as exc:
        if config.REQUIRE_MODEL:
            raise
        # Development convenience: the frontend can be built long before the
        # first model exists. /healthz reports the degraded state honestly and
        # /v1/predict/word returns a clear 503 rather than a confusing crash.
        logger.warning("starting WITHOUT a model — predictions will 503. (%s)", exc)
    yield


app = FastAPI(
    title="Strong ASL Inference API",
    description="Landmark-based sign language prediction. Accepts coordinates, never video.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    """Liveness probe. Render pings this; it also documents the feature contract."""
    if not classifier.is_loaded:
        status = "degraded: no model loaded"
    elif not classifier.trained:
        status = "degraded: untrained smoke model - predictions are meaningless"
    else:
        status = "ok"

    return HealthResponse(
        status=status,
        model_version=classifier.model_version,
        trained=classifier.trained,
        num_classes=len(classifier.labels),
        sequence_length=SEQUENCE_LENGTH,
        feature_dims=FEATURE_DIMS,
    )


@app.post("/v1/predict/word", response_model=PredictResponse)
def predict_word(request: PredictRequest) -> PredictResponse:
    """Classify one recorded sign and return the most likely matches."""
    if not classifier.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="No model is loaded on this server yet.",
        )

    frames = [frame.model_dump() for frame in request.frames]

    try:
        predictions = classifier.predict(frames, top_k=config.TOP_K)
    except ModelNotLoadedError:
        raise HTTPException(status_code=503, detail="No model is loaded on this server yet.")
    except ValueError as exc:
        # Malformed landmark geometry that slipped past schema validation.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PredictResponse(
        predictions=predictions,
        model_version=classifier.model_version,
        trained=classifier.trained,
    )
