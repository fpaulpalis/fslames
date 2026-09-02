"""Request and response models — the contract between browser and API.

The browser sends *landmarks*, never video. A three-second clip is roughly
200 KB of coordinates here versus several megabytes of encoded video, and the
server never receives anything that identifies the person signing.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

# A landmark is [x, y, z]. Guard rails are loose on purpose: MediaPipe returns
# x/y roughly in [0, 1] but z is a relative depth that can fall outside it, and
# hands near the frame edge can produce slightly negative coordinates.
Landmark = Annotated[list[float], Field(min_length=3, max_length=3)]

MAX_FRAMES = 300  # ~10 seconds at 30fps; anything longer is not a single sign


class Frame(BaseModel):
    """One video frame's worth of detections. Any field may be null."""

    pose: list[Landmark] | None = Field(default=None)
    left_hand: list[Landmark] | None = Field(default=None)
    right_hand: list[Landmark] | None = Field(default=None)

    @field_validator("pose")
    @classmethod
    def _check_pose(cls, v):
        if v is not None and len(v) != 33:
            raise ValueError(f"pose must have 33 landmarks, got {len(v)}")
        return v

    @field_validator("left_hand", "right_hand")
    @classmethod
    def _check_hand(cls, v):
        if v is not None and len(v) != 21:
            raise ValueError(f"hand must have 21 landmarks, got {len(v)}")
        return v


class PredictRequest(BaseModel):
    frames: list[Frame] = Field(min_length=2, max_length=MAX_FRAMES)
    fps: float = Field(default=30.0, gt=0, le=240)

    @field_validator("frames")
    @classmethod
    def _needs_a_hand(cls, frames):
        """Reject clips where no hand was ever detected.

        This is almost always a camera or lighting problem rather than a
        genuine attempt at a sign, and a clear 422 is far more useful to the
        user than five confident-looking predictions derived from nothing.
        """
        if not any(f.left_hand or f.right_hand for f in frames):
            raise ValueError(
                "no hands detected in any frame — check lighting and that your "
                "hands are inside the camera frame"
            )
        return frames


class Prediction(BaseModel):
    """One candidate sign. `slug` links straight back to the dictionary entry."""

    label: str                  # the model's class name, e.g. "HELLO"
    slug: str                   # dictionary slug, e.g. "hello"
    gloss_en: str
    gloss_fil: str
    confidence: float


class PredictResponse(BaseModel):
    predictions: list[Prediction]
    model_version: str
    # False when served by a --random smoke model. The UI must not present
    # these as real results — show a clear "test model" banner instead.
    trained: bool = True


class HealthResponse(BaseModel):
    status: str
    model_version: str
    trained: bool
    num_classes: int
    sequence_length: int
    feature_dims: int
