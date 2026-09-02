/**
 * Canonical landmark -> model-input transform. TypeScript port.
 *
 * ==========================================================================
 *  THIS IS A PORT OF ml/src/features.py. THE TWO MUST AGREE EXACTLY.
 *  Verified by src/lib/features.test.ts against the same golden fixtures the
 *  Python test uses. If they drift, the model trains fine and then predicts
 *  garbage in the browser with NO error message anywhere.
 *  See docs/feature-spec.md before changing anything here.
 * ==========================================================================
 *
 * Why hands and body are normalized separately: a sign is defined by WHERE the
 * hand is and WHAT SHAPE it makes. Pose is normalized against the shoulders
 * (and includes both wrists, so it encodes location); hands are normalized
 * against their own wrist (so they encode handshape independent of arm
 * position). Both survive, and the result is invariant to camera distance.
 */

// --------------------------------------------------------------------------
// Landmark indices
// --------------------------------------------------------------------------

/**
 * 13 upper-body points kept from the 33 MediaPipe Pose returns. Legs and fine
 * facial landmarks carry no signing information and only add noise.
 */
export const POSE_INDICES = [0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24] as const;

const RAW_LEFT_SHOULDER = 11;
const RAW_RIGHT_SHOULDER = 12;

const HAND_WRIST = 0;
const HAND_MCP_INDICES = [5, 9, 13, 17] as const;

// --------------------------------------------------------------------------
// Tensor shape contract
// --------------------------------------------------------------------------

export const NUM_POSE = POSE_INDICES.length; // 13
export const NUM_HAND = 21;

export const POSE_DIMS = NUM_POSE * 3; // 39
export const HAND_DIMS = NUM_HAND * 3; // 63
export const BASE_DIMS = POSE_DIMS + 2 * HAND_DIMS; // 165
export const PRESENCE_DIMS = 2;
export const FEATURE_DIMS = BASE_DIMS * 2 + PRESENCE_DIMS; // 332

export const SEQUENCE_LENGTH = 64;

const EPSILON = 1e-6;

// --------------------------------------------------------------------------
// Types - the wire format, identical to the API request body
// --------------------------------------------------------------------------

export type LandmarkList = number[][] | null;

export interface Frame {
  pose?: LandmarkList;
  left_hand?: LandmarkList;
  right_hand?: LandmarkList;
}

// --------------------------------------------------------------------------
// Normalization
// --------------------------------------------------------------------------

/** (33, 3) raw pose -> (13, 3) shoulder-normalized, flattened to 39 numbers. */
export function normalizePose(pose33: number[][]): Float64Array {
  const left = pose33[RAW_LEFT_SHOULDER];
  const right = pose33[RAW_RIGHT_SHOULDER];

  const ox = (left[0] + right[0]) / 2;
  const oy = (left[1] + right[1]) / 2;
  const oz = (left[2] + right[2]) / 2;

  const dx = left[0] - right[0];
  const dy = left[1] - right[1];
  const dz = left[2] - right[2];
  let scale = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (scale < EPSILON) scale = 1.0; // degenerate frame: signer turned sideways

  const out = new Float64Array(POSE_DIMS);
  for (let i = 0; i < NUM_POSE; i++) {
    const p = pose33[POSE_INDICES[i]];
    out[i * 3] = (p[0] - ox) / scale;
    out[i * 3 + 1] = (p[1] - oy) / scale;
    out[i * 3 + 2] = (p[2] - oz) / scale;
  }
  return out;
}

/** (21, 3) raw hand -> wrist-normalized, flattened to 63 numbers. */
export function normalizeHand(hand21: number[][]): Float64Array {
  const wrist = hand21[HAND_WRIST];

  let sum = 0;
  for (const index of HAND_MCP_INDICES) {
    const p = hand21[index];
    const cx = p[0] - wrist[0];
    const cy = p[1] - wrist[1];
    const cz = p[2] - wrist[2];
    sum += Math.sqrt(cx * cx + cy * cy + cz * cz);
  }
  let span = sum / HAND_MCP_INDICES.length;
  if (span < EPSILON) span = 1.0;

  const out = new Float64Array(HAND_DIMS);
  for (let i = 0; i < NUM_HAND; i++) {
    const p = hand21[i];
    out[i * 3] = (p[0] - wrist[0]) / span;
    out[i * 3 + 1] = (p[1] - wrist[1]) / span;
    out[i * 3 + 2] = (p[2] - wrist[2]) / span;
  }
  return out;
}

// --------------------------------------------------------------------------
// Assembly
// --------------------------------------------------------------------------

function checkShape(landmarks: LandmarkList | undefined, expected: number): number[][] | null {
  if (landmarks === null || landmarks === undefined) return null;
  if (landmarks.length !== expected) {
    throw new Error(`expected ${expected} landmarks, got ${landmarks.length}`);
  }
  return landmarks;
}

/** frames -> (N, BASE_DIMS + PRESENCE_DIMS), flat and row-major. */
export function buildBaseFeatures(frames: Frame[]): Float64Array {
  const rowWidth = BASE_DIMS + PRESENCE_DIMS;
  const out = new Float64Array(frames.length * rowWidth);

  // A dropped pose detection mid-clip is common. Holding the previous value
  // damages a motion model far less than injecting a block of zeros, which
  // would read as a violent jump.
  let lastPose: Float64Array | null = null;

  for (let i = 0; i < frames.length; i++) {
    const frame = frames[i];
    const base = i * rowWidth;

    const pose = checkShape(frame.pose, 33);
    if (pose !== null) lastPose = normalizePose(pose);
    if (lastPose !== null) out.set(lastPose, base);
    // else: leave zeros until the first successful detection

    const left = checkShape(frame.left_hand, NUM_HAND);
    if (left !== null) {
      out.set(normalizeHand(left), base + POSE_DIMS);
      out[base + BASE_DIMS] = 1.0;
    }

    const right = checkShape(frame.right_hand, NUM_HAND);
    if (right !== null) {
      out.set(normalizeHand(right), base + POSE_DIMS + HAND_DIMS);
      out[base + BASE_DIMS + 1] = 1.0;
    }
  }

  return out;
}

/**
 * Linearly resample (numFrames, width) to (targetLength, width) along time.
 * Matches numpy.interp, including its clamping behaviour at both endpoints.
 */
export function resampleSequence(
  seq: Float64Array,
  numFrames: number,
  width: number,
  targetLength: number = SEQUENCE_LENGTH,
): Float64Array {
  if (numFrames === 0) throw new Error("cannot resample an empty sequence");

  const out = new Float64Array(targetLength * width);

  if (numFrames === 1) {
    for (let t = 0; t < targetLength; t++) out.set(seq.subarray(0, width), t * width);
    return out;
  }

  for (let t = 0; t < targetLength; t++) {
    // Equivalent to np.linspace(0, numFrames - 1, targetLength)
    const position = (t * (numFrames - 1)) / (targetLength - 1);

    let lower = Math.floor(position);
    if (lower >= numFrames - 1) lower = numFrames - 2;
    const frac = position - lower;

    const a = lower * width;
    const b = (lower + 1) * width;
    const dst = t * width;

    for (let d = 0; d < width; d++) {
      out[dst + d] = seq[a + d] + frac * (seq[b + d] - seq[a + d]);
    }
  }

  return out;
}

/**
 * (T, BASE+PRESENCE) -> (T, FEATURE_DIMS).
 * Column order is [base | velocity | presence] and is part of the contract.
 */
export function addVelocity(seq: Float64Array, targetLength: number): Float32Array {
  const inWidth = BASE_DIMS + PRESENCE_DIMS;
  const out = new Float32Array(targetLength * FEATURE_DIMS);

  for (let t = 0; t < targetLength; t++) {
    const src = t * inWidth;
    const dst = t * FEATURE_DIMS;

    for (let d = 0; d < BASE_DIMS; d++) {
      out[dst + d] = seq[src + d];
      // Velocity on the first frame is zero.
      out[dst + BASE_DIMS + d] = t === 0 ? 0 : seq[src + d] - seq[src - inWidth + d];
    }

    out[dst + BASE_DIMS * 2] = seq[src + BASE_DIMS];
    out[dst + BASE_DIMS * 2 + 1] = seq[src + BASE_DIMS + 1];
  }

  return out;
}

/**
 * Top-level entry point: wire-format frames -> (targetLength, FEATURE_DIMS),
 * returned flat and row-major.
 *
 * The order is load-bearing and must match features.py:
 *   1. normalize + assemble   2. resample   3. append velocity
 *
 * Resampling BEFORE differencing means velocity is always measured over a
 * uniform time step, so a 15fps phone and a 60fps webcam produce comparable
 * numbers.
 */
export function extractFeatures(
  frames: Frame[],
  targetLength: number = SEQUENCE_LENGTH,
): Float32Array {
  if (frames.length < 2) {
    throw new Error("need at least 2 frames to extract features");
  }

  const base = buildBaseFeatures(frames);
  const resampled = resampleSequence(
    base,
    frames.length,
    BASE_DIMS + PRESENCE_DIMS,
    targetLength,
  );
  return addVelocity(resampled, targetLength);
}
