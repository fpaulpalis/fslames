"""Unit tests for the canonical feature transform.

Run with pytest, or directly:  py -3.11 ml/tests/test_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features import (  # noqa: E402
    BASE_DIMS,
    FEATURE_DIMS,
    SEQUENCE_LENGTH,
    build_base_features,
    extract_features,
    normalize_hand,
    normalize_pose,
    resample_sequence,
)

RNG = np.random.default_rng(1234)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def make_pose(seed: int = 0) -> list[list[float]]:
    """A plausible 33-point pose with shoulders one unit apart."""
    rng = np.random.default_rng(seed)
    pose = rng.normal(0.5, 0.05, size=(33, 3))
    pose[11] = [0.4, 0.4, 0.0]   # left shoulder
    pose[12] = [0.6, 0.4, 0.0]   # right shoulder
    return pose.tolist()


def make_hand(seed: int = 0) -> list[list[float]]:
    rng = np.random.default_rng(seed)
    hand = rng.normal(0.5, 0.03, size=(21, 3))
    hand[0] = [0.5, 0.5, 0.0]    # wrist
    return hand.tolist()


def make_frames(n: int = 30, *, left: bool = True, right: bool = True) -> list[dict]:
    return [
        {
            "pose": make_pose(i),
            "left_hand": make_hand(100 + i) if left else None,
            "right_hand": make_hand(200 + i) if right else None,
        }
        for i in range(n)
    ]


def transform(frames: list[dict], *, scale: float, shift: float) -> list[dict]:
    """Apply a global similarity transform to every landmark in every frame."""
    out = []
    for f in frames:
        moved = {}
        for key, value in f.items():
            if value is None:
                moved[key] = None
            else:
                moved[key] = (np.asarray(value) * scale + shift).tolist()
        out.append(moved)
    return out


# --------------------------------------------------------------------------
# Shape contract
# --------------------------------------------------------------------------

def test_output_shape_is_fixed():
    for n_frames in (2, 7, 30, 200):
        feats = extract_features(make_frames(n_frames))
        assert feats.shape == (SEQUENCE_LENGTH, FEATURE_DIMS)
        assert feats.dtype == np.float32


def test_rejects_too_short_sequences():
    for bad in ([], make_frames(1)):
        try:
            extract_features(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for < 2 frames")


def test_no_nans_or_infs():
    feats = extract_features(make_frames(30))
    assert np.isfinite(feats).all()


# --------------------------------------------------------------------------
# Normalization behaviour
# --------------------------------------------------------------------------

def test_pose_normalization_centres_and_scales():
    pose = np.asarray(make_pose(0))
    norm = normalize_pose(pose)
    # Shoulders sit at reduced positions 5 and 6, one unit apart, centred on origin.
    assert np.allclose((norm[5] + norm[6]) / 2, 0.0, atol=1e-9)
    assert np.isclose(np.linalg.norm(norm[5] - norm[6]), 1.0, atol=1e-9)


def test_hand_normalization_puts_wrist_at_origin():
    hand = np.asarray(make_hand(0))
    assert np.allclose(normalize_hand(hand)[0], 0.0, atol=1e-9)


def test_degenerate_pose_does_not_divide_by_zero():
    pose = np.zeros((33, 3))          # shoulders coincide -> scale 0
    assert np.isfinite(normalize_pose(pose)).all()


def test_degenerate_hand_does_not_divide_by_zero():
    assert np.isfinite(normalize_hand(np.zeros((21, 3)))).all()


# --------------------------------------------------------------------------
# Invariances — the whole point of the normalization
# --------------------------------------------------------------------------

def test_invariant_to_distance_and_position():
    """Sitting closer, further, or off-centre must not change the features.

    This is the property that lets a model trained on one camera setup work
    on somebody else's laptop.
    """
    frames = make_frames(24)
    baseline = extract_features(frames)

    for scale, shift in ((2.0, 0.0), (0.5, 0.0), (1.0, 0.3), (1.7, -0.2)):
        moved = extract_features(transform(frames, scale=scale, shift=shift))
        assert np.allclose(baseline, moved, atol=1e-5), (
            f"features changed under scale={scale} shift={shift}; "
            "normalization is not doing its job"
        )


# --------------------------------------------------------------------------
# Presence flags
# --------------------------------------------------------------------------

def test_presence_flags_track_detected_hands():
    both = build_base_features(make_frames(5))
    assert np.allclose(both[:, BASE_DIMS], 1.0)
    assert np.allclose(both[:, BASE_DIMS + 1], 1.0)

    right_only = build_base_features(make_frames(5, left=False))
    assert np.allclose(right_only[:, BASE_DIMS], 0.0)
    assert np.allclose(right_only[:, BASE_DIMS + 1], 1.0)
    # A missing hand must contribute zeros, not stale or garbage coordinates.
    assert np.allclose(right_only[:, 39:39 + 63], 0.0)


def test_missing_pose_carries_forward():
    frames = make_frames(4)
    frames[2]["pose"] = None
    base = build_base_features(frames)
    assert np.allclose(base[2, :39], base[1, :39])


# --------------------------------------------------------------------------
# Resampling and velocity
# --------------------------------------------------------------------------

def test_resample_preserves_endpoints():
    seq = np.linspace(0, 1, 10).reshape(10, 1)
    out = resample_sequence(seq, 64)
    assert out.shape == (64, 1)
    assert np.isclose(out[0, 0], 0.0)
    assert np.isclose(out[-1, 0], 1.0)


def test_velocity_block_is_the_difference_of_the_base_block():
    feats = extract_features(make_frames(30)).astype(np.float64)
    base = feats[:, :BASE_DIMS]
    velocity = feats[:, BASE_DIMS:BASE_DIMS * 2]
    assert np.allclose(velocity[0], 0.0)
    assert np.allclose(velocity[1:], base[1:] - base[:-1], atol=1e-5)


def test_a_still_clip_has_near_zero_velocity():
    """A hand held motionless should produce almost no velocity signal."""
    static = [{"pose": make_pose(0), "left_hand": make_hand(1), "right_hand": make_hand(2)}] * 20
    feats = extract_features(static)
    assert np.abs(feats[:, BASE_DIMS:BASE_DIMS * 2]).max() < 1e-6


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_deterministic():
    frames = make_frames(20)
    assert np.array_equal(extract_features(frames), extract_features(frames))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
