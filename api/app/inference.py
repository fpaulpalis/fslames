"""ONNX inference: landmark frames in, ranked sign predictions out.

The ONNX session is created once at process start and reused. Creating it per
request would add hundreds of milliseconds and defeat the point of keeping a
warm container.

Note there is no PyTorch here. Training happens in torch; serving uses
onnxruntime, which is ~50 MB instead of ~2 GB. That difference is what lets
the API run on a small, cheap instance.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort

from .features import FEATURE_DIMS, SEQUENCE_LENGTH, extract_features

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when a prediction is attempted before the model is available."""


class SignClassifier:
    """Wraps one exported model plus its label metadata."""

    def __init__(self, model_path: Path, labels_path: Path) -> None:
        self.model_path = model_path
        self.labels_path = labels_path
        self.session: ort.InferenceSession | None = None
        self.labels: list[dict] = []
        self.model_version: str = "unloaded"
        # False for a --random smoke model. Surfaced on /healthz so an
        # untrained model can never quietly masquerade as a real one.
        self.trained: bool = False
        self._input_name: str = ""

    # -- lifecycle ---------------------------------------------------------

    def load(self) -> None:
        """Load labels and create the ONNX session. Safe to call once at startup."""
        if not self.labels_path.exists():
            raise FileNotFoundError(f"labels file not found: {self.labels_path}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"model file not found: {self.model_path}")

        metadata = json.loads(self.labels_path.read_text(encoding="utf-8"))
        self.labels = metadata["labels"]
        self.model_version = metadata.get("model_version", self.model_path.stem)
        self.trained = bool(metadata.get("trained", True))

        # Single-threaded is the right default for a small container: the model
        # is tiny, and thread contention across concurrent requests costs more
        # than intra-op parallelism gains.
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self.session.get_inputs()[0].name

        self._verify_contract()
        logger.info(
            "loaded %s (%d classes) from %s",
            self.model_version, len(self.labels), self.model_path.name,
        )
        if not self.trained:
            logger.warning(
                "THIS MODEL IS UNTRAINED (exported with --random). Its predictions "
                "are meaningless and exist only to test the serving path."
            )

    def _verify_contract(self) -> None:
        """Fail at startup, not mid-request, if the model does not match the code.

        A mismatch here means someone exported a model built against a
        different feature spec. Better to refuse to boot than to serve
        plausible-looking nonsense.
        """
        assert self.session is not None
        shape = self.session.get_inputs()[0].shape  # e.g. ['batch', 64, 332]

        if len(shape) != 3:
            raise ValueError(f"expected a rank-3 model input, got shape {shape}")

        _, seq, dims = shape
        if isinstance(seq, int) and seq != SEQUENCE_LENGTH:
            raise ValueError(
                f"model expects {seq} frames but features.py produces "
                f"{SEQUENCE_LENGTH}. The model and the feature code are out of sync."
            )
        if isinstance(dims, int) and dims != FEATURE_DIMS:
            raise ValueError(
                f"model expects {dims} features/frame but features.py produces "
                f"{FEATURE_DIMS}. The model and the feature code are out of sync."
            )

        output_classes = self.session.get_outputs()[0].shape[-1]
        if isinstance(output_classes, int) and output_classes != len(self.labels):
            raise ValueError(
                f"model outputs {output_classes} classes but the labels file "
                f"lists {len(self.labels)}."
            )

    @property
    def is_loaded(self) -> bool:
        return self.session is not None

    # -- inference ---------------------------------------------------------

    def predict(self, frames: list[dict], top_k: int = 5) -> list[dict]:
        """Run one clip through the model and return the top_k candidates.

        We return a ranked list rather than a single answer because that is an
        honest interface for a ~100-class model: a correct sign sitting in
        fourth place is still useful to a learner, whereas one confidently
        wrong answer reads as a broken product.
        """
        if self.session is None:
            raise ModelNotLoadedError("model is not loaded")

        features = extract_features(frames)                    # (T, FEATURE_DIMS)
        batch = features[np.newaxis, ...].astype(np.float32)   # (1, T, FEATURE_DIMS)

        logits = self.session.run(None, {self._input_name: batch})[0][0]
        probabilities = _softmax(logits)

        k = min(top_k, len(self.labels))
        top_indices = np.argsort(probabilities)[::-1][:k]

        results = []
        for index in top_indices:
            entry = self.labels[int(index)]
            results.append(
                {
                    "label": entry["label"],
                    "slug": entry.get("slug", entry["label"].lower()),
                    "gloss_en": entry.get("gloss_en", entry["label"].lower()),
                    "gloss_fil": entry.get("gloss_fil", ""),
                    "confidence": float(probabilities[index]),
                }
            )
        return results


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax — subtracting the max prevents overflow."""
    shifted = x - np.max(x)
    exponentiated = np.exp(shifted)
    return exponentiated / np.sum(exponentiated)
