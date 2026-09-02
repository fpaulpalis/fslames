"""
Canonical landmark -> model-input transform.

============================================================================
  THIS FILE IS THE SINGLE SOURCE OF TRUTH.
  It is duplicated at:
      api/app/features.py      (literal copy)
      web/src/lib/features.ts  (line-by-line TypeScript port)
  If those drift from this file, the model trains fine and predicts garbage
  in the browser with NO error message. See ml/tests/test_golden.py.
============================================================================

Design note: why hands and body are normalized separately
---------------------------------------------------------
A sign is defined by *where* the hand is (forehead vs. chest) AND *what shape*
it makes. If we normalized everything against the hand's own wrist we would
destroy location; if we normalized everything against the shoulders we would
lose handshape detail at low resolution.

So we split the job:
  * POSE landmarks are normalized against the shoulders. Because the pose
    includes both wrists, this is what encodes WHERE the hands are.
  * HAND landmarks are normalized against their own wrist and hand span.
    This is what encodes the HANDSHAPE, independent of arm position.

The result is invariant to how far the signer sits from the camera and where
they stand in frame, while keeping both pieces of linguistic information.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

# --------------------------------------------------------------------------
# Landmark indices
# --------------------------------------------------------------------------

# MediaPipe Pose returns 33 landmarks. We keep 13 upper-body points; legs and
# fine facial points carry no signing information and only add noise.
#   0 nose | 2 left eye | 5 right eye | 7 left ear | 8 right ear
#   11/12 shoulders | 13/14 elbows | 15/16 wrists | 23/24 hips
POSE_INDICES: tuple[int, ...] = (0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24)

# Index of the shoulders *within the raw 33-point array*.
RAW_LEFT_SHOULDER = 11
RAW_RIGHT_SHOULDER = 12

# Mirror pairs, expressed as positions *within the reduced 13-point array*.
# Used by the horizontal-flip augmentation. Nose (position 0) has no partner.
POSE_MIRROR_PAIRS: tuple[tuple[int, int], ...] = (
    (1, 2),    # eyes
    (3, 4),    # ears
    (5, 6),    # shoulders
    (7, 8),    # elbows
    (9, 10),   # wrists
    (11, 12),  # hips
)

# MediaPipe Hand returns 21 landmarks. Index 0 is the wrist; 5/9/13/17 are the
# knuckles (MCP joints) of index/middle/ring/pinky.
HAND_WRIST = 0
HAND_MCP_INDICES: tuple[int, ...] = (5, 9, 13, 17)

# --------------------------------------------------------------------------
# Tensor shape contract
# --------------------------------------------------------------------------

NUM_POSE = len(POSE_INDICES)   # 13
NUM_HAND = 21

POSE_DIMS = NUM_POSE * 3       # 39
HAND_DIMS = NUM_HAND * 3       # 63
BASE_DIMS = POSE_DIMS + 2 * HAND_DIMS  # 165  (pose + left hand + right hand)
PRESENCE_DIMS = 2              # was a left / right hand detected this frame
FEATURE_DIMS = BASE_DIMS * 2 + PRESENCE_DIMS  # 332  (base + velocity + presence)

SEQUENCE_LENGTH = 64           # every clip is resampled to exactly this many frames

EPSILON = 1e-6                 # guards against divide-by-zero on degenerate frames


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def _landmarks_to_array(landmarks: Any, expected: int) -> np.ndarray | None:
    """Convert one frame's landmark list into an (expected, 3) array.

    Returns None when the detector found nothing, which the caller turns into
    a zero block plus a presence flag of 0.
    """
    if landmarks is None:
        return None
    arr = np.asarray(landmarks, dtype=np.float64)
    if arr.shape != (expected, 3):
        raise ValueError(f"expected landmark shape ({expected}, 3), got {arr.shape}")
    return arr


def parse_sequence(frames: Sequence[dict]) -> tuple[list, list, list]:
    """Split the wire format into three per-frame lists.

    Each frame is a dict shaped like:
        {"pose": [[x,y,z] * 33] | None,
         "left_hand":  [[x,y,z] * 21] | None,
         "right_hand": [[x,y,z] * 21] | None}
    """
    poses, lefts, rights = [], [], []
    for frame in frames:
        poses.append(_landmarks_to_array(frame.get("pose"), 33))
        lefts.append(_landmarks_to_array(frame.get("left_hand"), NUM_HAND))
        rights.append(_landmarks_to_array(frame.get("right_hand"), NUM_HAND))
    return poses, lefts, rights


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

def normalize_pose(pose33: np.ndarray) -> np.ndarray:
    """(33, 3) raw pose -> (13, 3) shoulder-normalized pose.

    Origin becomes the midpoint between the shoulders; one unit becomes the
    shoulder width. This is what makes the model indifferent to how far the
    signer sits from the camera.
    """
    left_shoulder = pose33[RAW_LEFT_SHOULDER]
    right_shoulder = pose33[RAW_RIGHT_SHOULDER]

    origin = (left_shoulder + right_shoulder) / 2.0
    scale = float(np.linalg.norm(left_shoulder - right_shoulder))
    if scale < EPSILON:
        scale = 1.0  # degenerate frame (signer turned fully sideways)

    return (pose33[list(POSE_INDICES)] - origin) / scale


def normalize_hand(hand21: np.ndarray) -> np.ndarray:
    """(21, 3) raw hand -> (21, 3) wrist-normalized hand.

    Origin becomes the wrist; one unit becomes the mean wrist-to-knuckle
    distance. Strips away *where* the hand is so the model sees only its shape.
    Location is preserved separately by the pose wrists.
    """
    wrist = hand21[HAND_WRIST]
    centred = hand21 - wrist

    span = float(np.mean(np.linalg.norm(centred[list(HAND_MCP_INDICES)], axis=1)))
    if span < EPSILON:
        span = 1.0

    return centred / span


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build_base_features(frames: Sequence[dict]) -> np.ndarray:
    """Wire-format frames -> (num_frames, BASE_DIMS + PRESENCE_DIMS) array.

    When the pose is missing for a frame we carry forward the last good one.
    A dropped detection mid-clip is common and holding the previous value is
    far less damaging to a motion model than injecting a block of zeros.
    """
    poses, lefts, rights = parse_sequence(frames)
    num_frames = len(frames)

    out = np.zeros((num_frames, BASE_DIMS + PRESENCE_DIMS), dtype=np.float64)
    last_pose: np.ndarray | None = None

    for i in range(num_frames):
        if poses[i] is not None:
            last_pose = normalize_pose(poses[i])
        pose_block = last_pose if last_pose is not None else np.zeros((NUM_POSE, 3))

        left_present = lefts[i] is not None
        right_present = rights[i] is not None

        left_block = normalize_hand(lefts[i]) if left_present else np.zeros((NUM_HAND, 3))
        right_block = normalize_hand(rights[i]) if right_present else np.zeros((NUM_HAND, 3))

        out[i, :POSE_DIMS] = pose_block.reshape(-1)
        out[i, POSE_DIMS:POSE_DIMS + HAND_DIMS] = left_block.reshape(-1)
        out[i, POSE_DIMS + HAND_DIMS:BASE_DIMS] = right_block.reshape(-1)
        out[i, BASE_DIMS] = 1.0 if left_present else 0.0
        out[i, BASE_DIMS + 1] = 1.0 if right_present else 0.0

    return out


def resample_sequence(seq: np.ndarray, target_length: int = SEQUENCE_LENGTH) -> np.ndarray:
    """Linearly resample (N, D) to (target_length, D) along time.

    Signs recorded at different speeds or frame rates must land on the same
    tensor shape. Interpolating presence flags yields fractional values in
    [0, 1]; that is intentional and treated as a soft confidence.
    """
    num_frames, dims = seq.shape
    if num_frames == 0:
        raise ValueError("cannot resample an empty sequence")
    if num_frames == 1:
        return np.repeat(seq, target_length, axis=0)

    source_positions = np.arange(num_frames, dtype=np.float64)
    target_positions = np.linspace(0.0, num_frames - 1.0, target_length, dtype=np.float64)

    out = np.zeros((target_length, dims), dtype=np.float64)
    for d in range(dims):
        out[:, d] = np.interp(target_positions, source_positions, seq[:, d])
    return out


def add_velocity(seq: np.ndarray) -> np.ndarray:
    """(T, BASE+PRESENCE) -> (T, FEATURE_DIMS) by appending frame-to-frame deltas.

    Movement is a core parameter of a sign — "MOTHER" and "FATHER" share a
    handshape and differ mainly in where they land, while many pairs differ
    only in motion. Explicit velocity saves the model from having to infer it.

    Velocity is computed on the base dims only (not presence) and the first
    frame's velocity is zero. Column order is [base | velocity | presence].
    """
    base = seq[:, :BASE_DIMS]
    presence = seq[:, BASE_DIMS:]

    velocity = np.zeros_like(base)
    velocity[1:] = base[1:] - base[:-1]

    return np.concatenate([base, velocity, presence], axis=1)


def extract_features(
    frames: Sequence[dict],
    target_length: int = SEQUENCE_LENGTH,
) -> np.ndarray:
    """Top-level entry point: wire-format frames -> (target_length, FEATURE_DIMS).

    Order matters and must be identical in the TypeScript port:
        1. normalize + assemble   2. resample   3. append velocity

    Resampling BEFORE differencing means velocity is always measured over a
    uniform time step, so a 15fps phone and a 60fps webcam produce comparable
    numbers.
    """
    if len(frames) < 2:
        raise ValueError("need at least 2 frames to extract features")

    base = build_base_features(frames)
    resampled = resample_sequence(base, target_length)
    features = add_velocity(resampled)

    assert features.shape == (target_length, FEATURE_DIMS), (
        f"feature contract violated: got {features.shape}, "
        f"expected ({target_length}, {FEATURE_DIMS})"
    )
    return features.astype(np.float32)
