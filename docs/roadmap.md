# Roadmap and status

Last updated: 2026-09-03

---

## Phase 0 — Foundations · ⏳ in progress

| Item | Status |
|---|---|
| Repo structure (`web/` `api/` `ml/` `content/` `docs/` `scripts/`) | ✅ done |
| Git repository initialised | ✅ done (nothing committed yet) |
| `ml/src/features.py` — canonical feature transform | ✅ done, 16 tests passing |
| Golden parity fixtures | ✅ generated |
| `ml/src/model.py` — SignTransformer (2.24M params) | ✅ done, smoke-tested |
| `ml/src/export_onnx.py` — PyTorch → ONNX | ✅ done, verified vs PyTorch |
| `api/` — FastAPI service | ✅ done, 13 tests passing |
| End-to-end prediction through HTTP | ✅ verified with an untrained model |
| `content/` — CSV → validated `signs.json` | ✅ done, 48 seed entries |
| **Node.js 22 installed** | ⛔ **blocking** |
| `web/` scaffolded with `create-next-app` | ⛔ blocked on Node |
| Deployed to Vercel | ⬜ not started |

**Next action:** install Node 22 LTS from [nodejs.org](https://nodejs.org), then scaffold `web/`.

### What "end-to-end verified" means here

An untrained model was exported and served, and a synthetic clip was POSTed to
`/v1/predict/word`, which returned five ranked candidates carrying dictionary slugs and
Filipino glosses. The *plumbing* is proven; the model itself has learned nothing yet.
`/healthz` reports `"trained": false` and the API logs a warning, so this state cannot be
mistaken for a working model.

---

## Phase 1 — Site shell and static pages · ⬜ not started

Header, tab nav (Home / Dictionary / AI / Learn), footer. `next-intl` routing at `/en`
and `/fil`. Home, About, Contact, Privacy. Six terminology pages from one template.
Alphabet guide and the a–z photo grid.

**Done when:** every nav link resolves, and toggling `/en` ↔ `/fil` changes every visible
string with no hardcoded English left behind.

---

## Phase 2 — Dictionary · ⬜ not started

A–Z index, browse-by-letter, full word list, client-side search, and sign entry pages
driven by `content/signs.json`. Media uploaded to Cloudflare R2.

**Done when:** every slug has a reachable page, and searching "hello" and "kumusta" both
find the same entry.

---

## Phase 3 — Letter predictor · ⬜ not started

Build this **before** the word model. Letters are static handshapes: one frame, 21
landmarks, a tiny MLP. No backend, no dataset download, no licensing questions — you
collect the data yourself in an afternoon with a `/dev/capture` route.

⚠️ **J and Z are motion letters** and cannot be classified from a single frame. Handle
them with a short frame buffer and a fingertip trajectory check, or exclude them and say
so in the UI.

**Done when:** all 26 letters classify from your webcam, and DevTools shows **zero**
network requests during prediction.

---

## Phase 4 — Word predictor · ⬜ not started

The longest phase. Download WLASL-100, extract landmarks, train, export, deploy, wire up
`/ai/word`.

Still to write: `extract_landmarks.py`, `dataset.py`, `train.py`, `evaluate.py`.

⚠️ **Attempt the WLASL download in the first week of this phase, not the last.** The
dataset points at third-party URLs and a meaningful fraction are dead. Find out early
whether you need mirrors or a reduced gloss list.

⚠️ **Write `web/src/lib/features.ts` and its parity test BEFORE wiring any UI.** See
[`feature-spec.md`](feature-spec.md).

**Done when:** you sign 10 trained words and at least 7 appear in the top-5, and CORS
works from the deployed Vercel domain rather than only localhost.

---

## Phases 5–7 — Optional

Learn features (quiz, fingerspelling practice) · your own recordings and fine-tuning ·
accounts, only once there is something worth saving.

---

## Known issues and decisions

| Item | Note |
|---|---|
| `api/models/word-v1.onnx` | Currently an **untrained** 8-class smoke model. Do not commit it as if it were real; regenerate or replace before deploy. |
| `wlasl_candidate` in `seed.csv` | A guess. Reconcile against the real `WLASL_v0.3.json` gloss list before trusting it. |
| `params` on all sign entries | Deliberately `null`. Handshape/location/movement were not guessed — wrong articulatory data actively teaches people the wrong thing. Fill in from your own recordings. |
| Python version | 3.14 verified working. The common "you must use 3.11" advice is out of date since mediapipe 1.0. |
| `torch.onnx.export` | Must use `dynamic_shapes` (not `dynamic_axes`) **and** a batch-2 example, or the batch axis silently pins to 1. Already handled in `export_onnx.py`. |
