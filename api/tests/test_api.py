"""API contract tests.

These run without a trained model — they cover validation, error handling, and
feature parity. The end-to-end prediction test arrives in Phase 4 alongside the
first exported ONNX file.

Run:  python -m pytest api/tests/ -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.features import FEATURE_DIMS, SEQUENCE_LENGTH, extract_features  # noqa: E402
from app.inference import _softmax  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

FIXTURES = REPO_ROOT / "ml" / "tests" / "fixtures"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def landmarks(n: int) -> list[list[float]]:
    rng = np.random.default_rng(n)
    return rng.normal(0.5, 0.05, size=(n, 3)).tolist()


def good_frame() -> dict:
    return {"pose": landmarks(33), "left_hand": landmarks(21), "right_hand": landmarks(21)}


def payload(num_frames: int = 10) -> dict:
    return {"frames": [good_frame() for _ in range(num_frames)], "fps": 30}


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

def test_healthz_reports_the_feature_contract():
    """/healthz doubles as machine-readable documentation of the tensor shape."""
    response = client.get("/healthz")
    assert response.status_code == 200

    body = response.json()
    assert body["sequence_length"] == SEQUENCE_LENGTH
    assert body["feature_dims"] == FEATURE_DIMS


def test_healthz_is_honest_when_no_model_is_loaded():
    body = client.get("/healthz").json()
    assert body["status"].startswith("degraded")
    assert body["model_version"] == "unloaded"


# --------------------------------------------------------------------------
# Prediction endpoint behaviour without a model
# --------------------------------------------------------------------------

def test_predict_returns_503_without_a_model():
    """A missing model must be a clear 503, never a 500 or a fabricated answer."""
    response = client.post("/v1/predict/word", json=payload())
    assert response.status_code == 503
    assert "model" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

def test_rejects_single_frame_clips():
    assert client.post("/v1/predict/word", json=payload(1)).status_code == 422


def test_rejects_wrong_pose_landmark_count():
    bad = payload(4)
    bad["frames"][0]["pose"] = landmarks(20)   # should be 33
    assert client.post("/v1/predict/word", json=bad).status_code == 422


def test_rejects_wrong_hand_landmark_count():
    bad = payload(4)
    bad["frames"][0]["left_hand"] = landmarks(15)   # should be 21
    assert client.post("/v1/predict/word", json=bad).status_code == 422


def test_rejects_clips_with_no_hands_at_all():
    """Almost always a lighting or framing problem — say so, don't guess."""
    handless = {
        "frames": [{"pose": landmarks(33), "left_hand": None, "right_hand": None}] * 6,
        "fps": 30,
    }
    response = client.post("/v1/predict/word", json=handless)
    assert response.status_code == 422
    assert "no hands detected" in json.dumps(response.json()).lower()


def test_accepts_a_clip_with_only_one_hand():
    """Most ASL signs are one-handed; this must not be rejected."""
    one_handed = {
        "frames": [
            {"pose": landmarks(33), "left_hand": None, "right_hand": landmarks(21)}
            for _ in range(6)
        ],
        "fps": 30,
    }
    # 503 (no model) rather than 422 proves validation let it through.
    assert client.post("/v1/predict/word", json=one_handed).status_code == 503


def test_rejects_absurdly_long_clips():
    assert client.post("/v1/predict/word", json=payload(400)).status_code == 422


# --------------------------------------------------------------------------
# Feature parity — the API copy must match the training source of truth
# --------------------------------------------------------------------------

@pytest.mark.skipif(not FIXTURES.exists(), reason="golden fixtures not generated")
def test_api_features_match_the_golden_vector():
    """api/app/features.py is a copy of ml/src/features.py. Prove it still behaves."""
    clip = json.loads((FIXTURES / "golden-clip.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "golden-features.json").read_text(encoding="utf-8"))

    actual = extract_features(clip["frames"]).astype(np.float64)
    expected_array = np.asarray(expected["features"], dtype=np.float64)

    assert float(np.abs(actual - expected_array).max()) < 1e-5


def test_api_features_file_is_byte_identical_to_the_training_copy():
    """Catch a divergent edit to one copy immediately, in CI."""
    a = (REPO_ROOT / "ml" / "src" / "features.py").read_bytes()
    b = (REPO_ROOT / "api" / "app" / "features.py").read_bytes()
    assert a == b, (
        "ml/src/features.py and api/app/features.py have diverged.\n"
        "Re-copy the training version over the API version, and check whether "
        "web/src/lib/features.ts needs the same change."
    )


# --------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------

def test_softmax_is_a_probability_distribution():
    out = _softmax(np.array([1.0, 2.0, 3.0]))
    assert np.isclose(out.sum(), 1.0)
    assert np.all(out > 0)
    assert out[2] > out[1] > out[0]


def test_softmax_survives_large_logits():
    """Without the max-subtraction trick this overflows to nan."""
    out = _softmax(np.array([1000.0, 1001.0, 999.0]))
    assert np.isfinite(out).all()
    assert np.isclose(out.sum(), 1.0)
