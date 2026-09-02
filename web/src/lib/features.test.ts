/**
 * Golden-vector parity test - TypeScript side.
 *
 * The Python twin is ml/tests/test_golden.py and loads the SAME two fixture
 * files. Together they are the guard against features.py and features.ts
 * drifting apart, which would leave the model training perfectly and
 * predicting nonsense in the browser with no error message.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  BASE_DIMS,
  FEATURE_DIMS,
  SEQUENCE_LENGTH,
  extractFeatures,
  normalizeHand,
  normalizePose,
  type Frame,
} from "./features";

const FIXTURES = join(process.cwd(), "..", "ml", "tests", "fixtures");
const TOLERANCE = 1e-5;

function loadFixtures() {
  const clip = JSON.parse(readFileSync(join(FIXTURES, "golden-clip.json"), "utf8"));
  const expected = JSON.parse(readFileSync(join(FIXTURES, "golden-features.json"), "utf8"));
  return { frames: clip.frames as Frame[], expected: expected.features as number[][] };
}

// --------------------------------------------------------------------------
// The parity test
// --------------------------------------------------------------------------

describe("golden-vector parity with features.py", () => {
  it("reproduces the Python output exactly", () => {
    const { frames, expected } = loadFixtures();
    const actual = extractFeatures(frames);

    expect(expected.length).toBe(SEQUENCE_LENGTH);
    expect(expected[0].length).toBe(FEATURE_DIMS);
    expect(actual.length).toBe(SEQUENCE_LENGTH * FEATURE_DIMS);

    let maxDiff = 0;
    let worst = { frame: -1, column: -1 };

    for (let t = 0; t < SEQUENCE_LENGTH; t++) {
      for (let d = 0; d < FEATURE_DIMS; d++) {
        const diff = Math.abs(actual[t * FEATURE_DIMS + d] - expected[t][d]);
        if (diff > maxDiff) {
          maxDiff = diff;
          worst = { frame: t, column: d };
        }
      }
    }

    expect(
      maxDiff,
      `features.ts drifted from features.py (max diff ${maxDiff.toExponential(2)} ` +
        `at frame ${worst.frame}, column ${worst.column}).\n` +
        "Either you changed the contract on purpose - regenerate with\n" +
        "  python ml/src/make_golden.py\n" +
        "and port the same change to BOTH implementations in one commit -\n" +
        "or you introduced a bug.",
    ).toBeLessThan(TOLERANCE);
  });

  it("uses a fixture that is not trivially all zeros", () => {
    const { expected } = loadFixtures();
    const flat = expected.flat();
    expect(Math.max(...flat.map(Math.abs))).toBeGreaterThan(0.1);
    expect(flat.filter((v) => v !== 0).length).toBeGreaterThan(flat.length * 0.5);
  });
});

// --------------------------------------------------------------------------
// Same behavioural properties the Python suite asserts
// --------------------------------------------------------------------------

function makePose(seed: number): number[][] {
  const pose = Array.from({ length: 33 }, (_, i) => [
    0.5 + Math.sin(seed + i) * 0.05,
    0.5 + Math.cos(seed + i) * 0.05,
    Math.sin(seed * i) * 0.02,
  ]);
  pose[11] = [0.4, 0.4, 0.0];
  pose[12] = [0.6, 0.4, 0.0];
  return pose;
}

function makeHand(seed: number): number[][] {
  const hand = Array.from({ length: 21 }, (_, i) => [
    0.5 + Math.sin(seed + i) * 0.03,
    0.5 + Math.cos(seed + i) * 0.03,
    0.0,
  ]);
  hand[0] = [0.5, 0.5, 0.0];
  return hand;
}

function makeFrames(n: number): Frame[] {
  return Array.from({ length: n }, (_, i) => ({
    pose: makePose(i),
    left_hand: makeHand(100 + i),
    right_hand: makeHand(200 + i),
  }));
}

describe("feature transform behaviour", () => {
  it("always produces a fixed output shape", () => {
    for (const n of [2, 7, 30, 200]) {
      expect(extractFeatures(makeFrames(n)).length).toBe(SEQUENCE_LENGTH * FEATURE_DIMS);
    }
  });

  it("rejects clips shorter than two frames", () => {
    expect(() => extractFeatures([])).toThrow();
    expect(() => extractFeatures(makeFrames(1))).toThrow();
  });

  it("is invariant to camera distance and position", () => {
    // The property that lets a model trained on one setup work on someone
    // else's laptop. If this breaks, the app works only for whoever recorded
    // the training data.
    const frames = makeFrames(24);
    const baseline = extractFeatures(frames);

    for (const [scale, shift] of [
      [2.0, 0.0],
      [0.5, 0.0],
      [1.0, 0.3],
      [1.7, -0.2],
    ]) {
      const moved = frames.map((f) => ({
        pose: f.pose!.map((p) => p.map((v) => v * scale + shift)),
        left_hand: f.left_hand!.map((p) => p.map((v) => v * scale + shift)),
        right_hand: f.right_hand!.map((p) => p.map((v) => v * scale + shift)),
      }));

      const result = extractFeatures(moved);
      let maxDiff = 0;
      for (let i = 0; i < baseline.length; i++) {
        maxDiff = Math.max(maxDiff, Math.abs(baseline[i] - result[i]));
      }
      expect(maxDiff, `changed under scale=${scale} shift=${shift}`).toBeLessThan(1e-4);
    }
  });

  it("puts the wrist at the origin and the shoulders one unit apart", () => {
    const hand = normalizeHand(makeHand(0));
    expect(Math.abs(hand[0])).toBeLessThan(1e-9);

    const pose = normalizePose(makePose(0));
    // Shoulders are at reduced positions 5 and 6.
    const dx = pose[5 * 3] - pose[6 * 3];
    const dy = pose[5 * 3 + 1] - pose[6 * 3 + 1];
    const dz = pose[5 * 3 + 2] - pose[6 * 3 + 2];
    expect(Math.sqrt(dx * dx + dy * dy + dz * dz)).toBeCloseTo(1.0, 9);
  });

  it("does not divide by zero on degenerate frames", () => {
    const zeros = (n: number) => Array.from({ length: n }, () => [0, 0, 0]);
    expect(normalizePose(zeros(33)).every(Number.isFinite)).toBe(true);
    expect(normalizeHand(zeros(21)).every(Number.isFinite)).toBe(true);
  });

  it("flags a missing hand and zero-fills it", () => {
    const frames: Frame[] = Array.from({ length: 5 }, (_, i) => ({
      pose: makePose(i),
      left_hand: null,
      right_hand: makeHand(i),
    }));

    const out = extractFeatures(frames);
    expect(out[BASE_DIMS * 2]).toBe(0); // left presence
    expect(out[BASE_DIMS * 2 + 1]).toBe(1); // right presence

    // The absent hand contributes zeros, not stale coordinates.
    for (let d = 39; d < 39 + 63; d++) expect(out[d]).toBe(0);
  });

  it("reports near-zero velocity for a motionless clip", () => {
    const still: Frame[] = Array.from({ length: 20 }, () => ({
      pose: makePose(0),
      left_hand: makeHand(1),
      right_hand: makeHand(2),
    }));

    const out = extractFeatures(still);
    let maxVelocity = 0;
    for (let t = 0; t < SEQUENCE_LENGTH; t++) {
      for (let d = BASE_DIMS; d < BASE_DIMS * 2; d++) {
        maxVelocity = Math.max(maxVelocity, Math.abs(out[t * FEATURE_DIMS + d]));
      }
    }
    expect(maxVelocity).toBeLessThan(1e-6);
  });

  it("is deterministic", () => {
    const frames = makeFrames(20);
    expect(Array.from(extractFeatures(frames))).toEqual(Array.from(extractFeatures(frames)));
  });
});
