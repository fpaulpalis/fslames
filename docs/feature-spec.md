# Feature specification

The exact contract between MediaPipe landmarks and model input. This document is the
reference for porting `ml/src/features.py` to `web/src/lib/features.ts`.

**Status:** implemented and verified in Python (`ml/tests/` — 16 tests passing).
TypeScript port not yet written.

---

## Wire format

Both the browser and the training pipeline produce this shape. It is also the JSON body
of `POST /v1/predict/word`.

```jsonc
{
  "fps": 30,
  "frames": [
    {
      "pose":       [[x, y, z], ...],  // 33 entries, or null if not detected
      "left_hand":  [[x, y, z], ...],  // 21 entries, or null
      "right_hand": [[x, y, z], ...]   // 21 entries, or null
    }
    // 2..300 frames
  ]
}
```

Coordinates are MediaPipe's normalized output: `x`/`y` roughly in `[0, 1]` relative to the
image, `z` a relative depth. Values slightly outside `[0, 1]` are normal near frame edges
and must not be clamped or rejected.

---

## Output tensor

`(64, 332)` float32.

| Columns | Count | Contents |
|---|---|---|
| `0 .. 38` | 39 | Pose: 13 points × (x, y, z), shoulder-normalized |
| `39 .. 101` | 63 | Left hand: 21 points × (x, y, z), wrist-normalized |
| `102 .. 164` | 63 | Right hand: 21 points × (x, y, z), wrist-normalized |
| `165 .. 329` | 165 | Velocity — frame-to-frame delta of columns 0–164 |
| `330` | 1 | Left-hand presence (1.0 detected, 0.0 not) |
| `331` | 1 | Right-hand presence |

**Column order is part of the contract.** Reordering these silently destroys a trained
model's accuracy without raising any error.

---

## Retained pose points

From MediaPipe's 33, we keep 13. Legs and fine facial landmarks carry no signing
information and only add noise.

| Position in output | Raw MediaPipe index | Point |
|---|---|---|
| 0 | 0 | nose |
| 1, 2 | 2, 5 | left eye, right eye |
| 3, 4 | 7, 8 | left ear, right ear |
| 5, 6 | 11, 12 | left shoulder, right shoulder |
| 7, 8 | 13, 14 | left elbow, right elbow |
| 9, 10 | 15, 16 | left wrist, right wrist |
| 11, 12 | 23, 24 | left hip, right hip |

---

## Normalization

### Why hands and body are normalized separately

A sign is defined by **where** the hand is *and* **what shape** it makes. Normalizing
everything one way destroys one of those.

- **Pose** is normalized against the shoulders. Because the pose includes both wrists,
  this is what encodes hand **location** (forehead vs. chest).
- **Hands** are normalized against their own wrist. This is what encodes **handshape**,
  independent of where the arm happens to be.

Both pieces survive, and the result is invariant to camera distance and framing.

### Pose

```
origin = (raw[11] + raw[12]) / 2          # midpoint between shoulders
scale  = ‖raw[11] − raw[12]‖              # shoulder width
if scale < 1e-6: scale = 1.0              # signer turned fully sideways
output = (raw[POSE_INDICES] − origin) / scale
```

### Hand

```
origin = raw[0]                            # wrist
centred = raw − origin
scale = mean(‖centred[i]‖ for i in [5, 9, 13, 17])   # wrist-to-knuckle distance
if scale < 1e-6: scale = 1.0
output = centred / scale
```

### Missing detections

| Case | Handling |
|---|---|
| Hand not detected | Zero-fill its 63 columns, presence flag `0.0` |
| Pose not detected | **Carry forward** the previous frame's normalized pose |
| Pose missing on frame 0 | Zeros until the first successful detection |

Carry-forward is used for pose because dropped detections mid-clip are common, and
holding the last known body position damages a motion model far less than injecting a
block of zeros that reads as a violent jump.

---

## Pipeline order

This order is **load-bearing** and must be identical in both languages:

1. **Normalize and assemble** → `(N, 167)` — pose, hands, presence flags
2. **Resample to 64 frames** → `(64, 167)` — linear interpolation over frame index
3. **Append velocity** → `(64, 332)` — difference of the 165 base columns

Resampling *before* differencing means velocity is always measured over a uniform time
step, so a 15fps phone and a 60fps webcam produce comparable numbers. Doing it the other
way round makes velocity depend on the recording device.

Presence flags are interpolated along with everything else, producing fractional values
in `[0, 1]`. This is intentional — treat it as a soft confidence.

Velocity on frame 0 is zero.

---

## Verified properties

`ml/tests/test_features.py` asserts all of these:

- Output is always exactly `(64, 332)` float32, for any input from 2 to 300 frames
- **Invariant to camera distance and position** — scaling or translating every landmark
  leaves the output unchanged to within `1e-5`. This is the property that lets a model
  trained on one setup work on someone else's laptop.
- **Not** invariant to rotation. Deliberate: orientation is linguistically meaningful.
- No NaN or infinity, including on degenerate frames (coincident shoulders, zero-size hand)
- A motionless clip produces near-zero velocity
- Deterministic — same input, byte-identical output

---

## Porting to TypeScript

`web/src/lib/features.ts` must reproduce this exactly. Notes for the port:

- The Python uses only elementary numpy (`interp`, `norm`, `mean`, slicing). Every
  operation maps to a plain loop; no linear-algebra library is needed.
- `np.interp` is straightforward linear interpolation with endpoint clamping. Match the
  endpoint behaviour: position 0 maps to source frame 0, and the last output frame maps
  to source frame `N-1` exactly.
- Accumulate in `Float64Array` and cast to `Float32Array` only at the very end, matching
  Python's `float64` intermediate and `float32` output.
- Use the **MediaPipe Tasks API** on both sides (`@mediapipe/tasks-vision` in the browser,
  `mediapipe.tasks.python.vision` in `ml/`). Mixing the modern Tasks API with the legacy
  `Holistic` solution gives different landmark ordering and coordinate conventions.

### The parity test

Then make `web/src/lib/features.test.ts` load the same two fixtures the Python test uses:

- `ml/tests/fixtures/golden-clip.json` — a 37-frame synthetic clip that deliberately
  exercises the missing-pose and missing-hand branches
- `ml/tests/fixtures/golden-features.json` — the expected `(64, 332)` output

Assert `max |actual − expected| < 1e-5`. Run it in CI on every push.

If you change the feature contract, regenerate with `python ml/src/make_golden.py` and
update **both** implementations in the same commit. `api/tests/test_api.py` additionally
asserts that `ml/src/features.py` and `api/app/features.py` are byte-identical.
