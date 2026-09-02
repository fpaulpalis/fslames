"""Generate the golden-vector fixture that guards train/serve parity.

Writes two committed files:
    ml/tests/fixtures/golden-clip.json      raw landmark input (the wire format)
    ml/tests/fixtures/golden-features.json  the exact expected output

Python and TypeScript both load the clip, run their own feature transform, and
assert they match the expected output. If someone edits features.py without
editing features.ts (or reorders a column, or transposes an axis), this fails
loudly instead of silently degrading predictions in the browser.

Regenerate ONLY when you intend to change the feature contract:
    py -3.11 ml/src/make_golden.py
...and then update web/src/lib/features.ts in the same commit.

Run:  py -3.11 ml/src/make_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from features import FEATURE_DIMS, SEQUENCE_LENGTH, extract_features

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# 37 frames: deliberately not 64, so the resampling path is exercised, and odd
# so it cannot accidentally divide evenly.
NUM_FRAMES = 37
DECIMALS = 6


def synthetic_clip() -> list[dict]:
    """A deterministic clip that walks through every branch of the transform.

    It is not a real sign — it does not need to be. It needs to be reproducible
    and to touch the missing-pose and missing-hand code paths, because those
    are the easiest places for two implementations to disagree.
    """
    rng = np.random.default_rng(20260903)
    frames: list[dict] = []

    for i in range(NUM_FRAMES):
        t = i / (NUM_FRAMES - 1)

        # A body that drifts slightly and breathes, so velocity is non-trivial.
        pose = rng.normal(0.5, 0.02, size=(33, 3))
        pose[11] = [0.42 + 0.01 * t, 0.40, 0.0]          # left shoulder
        pose[12] = [0.58 + 0.01 * t, 0.40, 0.0]          # right shoulder
        pose[15] = [0.45, 0.60 - 0.25 * t, 0.05 * t]     # left wrist rising
        pose[16] = [0.55, 0.62 - 0.20 * t, -0.03 * t]    # right wrist rising

        hand_l = rng.normal(0.5, 0.02, size=(21, 3))
        hand_l[0] = [0.45, 0.60 - 0.25 * t, 0.0]
        hand_r = rng.normal(0.5, 0.02, size=(21, 3))
        hand_r[0] = [0.55, 0.62 - 0.20 * t, 0.0]

        frames.append(
            {
                # Frame 12 loses the pose  -> exercises carry-forward.
                "pose": None if i == 12 else pose.tolist(),
                # Frames 5-8 lose the left hand -> exercises zero-fill + presence flag.
                "left_hand": None if 5 <= i <= 8 else hand_l.tolist(),
                # Frame 30 loses the right hand.
                "right_hand": None if i == 30 else hand_r.tolist(),
            }
        )

    return frames


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)

    frames = synthetic_clip()
    features = extract_features(frames)
    assert features.shape == (SEQUENCE_LENGTH, FEATURE_DIMS)

    clip_path = FIXTURES / "golden-clip.json"
    features_path = FIXTURES / "golden-features.json"

    clip_path.write_text(
        json.dumps({"fps": 30, "frames": frames}, separators=(",", ":")),
        encoding="utf-8",
    )
    features_path.write_text(
        json.dumps(
            {
                "shape": list(features.shape),
                "decimals": DECIMALS,
                "features": np.round(features.astype(np.float64), DECIMALS).tolist(),
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    print(f"wrote {clip_path}  ({clip_path.stat().st_size / 1024:.0f} KB)")
    print(f"wrote {features_path}  ({features_path.stat().st_size / 1024:.0f} KB)")
    print(f"shape {features.shape}  range [{features.min():.4f}, {features.max():.4f}]")


if __name__ == "__main__":
    main()
