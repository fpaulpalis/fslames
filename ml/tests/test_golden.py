"""Golden-vector parity test — Python side.

The TypeScript twin lives at web/src/lib/features.test.ts and loads the SAME
two fixture files. Together they are the guard against the failure mode that
would otherwise cost days: features.py and features.ts drifting apart, the
model training perfectly, and the browser predicting nonsense with no error.

Run with pytest, or directly:  py -3.11 ml/tests/test_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features import FEATURE_DIMS, SEQUENCE_LENGTH, extract_features  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOLERANCE = 1e-5


def load_fixtures() -> tuple[list[dict], np.ndarray]:
    clip = json.loads((FIXTURES / "golden-clip.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "golden-features.json").read_text(encoding="utf-8"))
    return clip["frames"], np.asarray(expected["features"], dtype=np.float64)


def test_golden_vector_matches():
    frames, expected = load_fixtures()
    actual = extract_features(frames).astype(np.float64)

    assert actual.shape == expected.shape == (SEQUENCE_LENGTH, FEATURE_DIMS)

    max_diff = float(np.abs(actual - expected).max())
    assert max_diff < TOLERANCE, (
        f"feature transform drifted from the golden fixture (max diff {max_diff:.2e}).\n"
        "Either you changed features.py on purpose — in which case regenerate with\n"
        "  py -3.11 ml/src/make_golden.py\n"
        "and port the same change to web/src/lib/features.ts in the SAME commit —\n"
        "or you introduced a bug."
    )


def test_fixture_is_not_trivial():
    """Guard against a fixture of all zeros silently passing everything."""
    _, expected = load_fixtures()
    assert np.abs(expected).max() > 0.1
    assert np.count_nonzero(expected) > expected.size * 0.5


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  FAIL  {name}: {exc}")
    sys.exit(1 if failures else 0)
