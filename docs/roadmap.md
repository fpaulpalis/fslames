# Roadmap and status

Last updated: 2026-09-04

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
| Node.js 22 installed | ✅ done (v22.23.2) |
| `web/` scaffolded (Next 16 + Tailwind 4 + next-intl) | ✅ done |
| `web/src/lib/features.ts` + golden parity test | ✅ done, 13 tests passing |
| `scripts/verify.py` covers everything above | ✅ done, 15 checks |
| Deployed to Vercel | ⬜ not started |

**Next action:** deploy `web/` to Vercel to close out Phase 0, then build the
dictionary pages in Phase 2.

### What "end-to-end verified" means here

An untrained model was exported and served, and a synthetic clip was POSTed to
`/v1/predict/word`, which returned five ranked candidates carrying dictionary slugs and
Filipino glosses. The *plumbing* is proven; the model itself has learned nothing yet.
`/healthz` reports `"trained": false` and the API logs a warning, so this state cannot be
mistaken for a working model.

---

## Phase 1 — Site shell and static pages · ⏳ in progress

Done: header with locale toggle, tab nav (Home / Dictionary / AI / Learn), `next-intl`
routing at `/en` and `/fil`, home page, AI hub page. Both locales prerender statically.

Remaining: footer, About, Contact, Privacy, and the six terminology pages from one
template. The alphabet grid moved into Phase 2 and now lives on `/dictionary` — it is
built from the 28 alphabet entries in `seed.csv`, so it stays a letter grid rather than a
photo grid until the recordings exist.

**Done when:** every nav link resolves, and toggling `/en` ↔ `/fil` changes every visible
string with no hardcoded English left behind.

---

## Phase 2 — Dictionary · ⏳ in progress

| Item | Status |
|---|---|
| FSL vocabulary — 136 signs across 4 sections | ✅ done, replaces the 48 ASL seed words |
| Per-locale A–Z index (`index.en` / `index.fil`) | ✅ done |
| `/dictionary` — search, alphabet, index, in that order | ✅ done |
| Client-side bilingual search | ✅ done, 15 tests |
| Sign entry pages | ✅ done, 272 prerendered (136 × 2 locales) |
| Media uploaded to Cloudflare R2 | ⬜ not started — `media.video` is null on all 136 |
| Handshape / location / movement (`params`) | ⬜ not started — deliberately null, see content/README.md |

**Done when:** every slug has a reachable page, and searching "hello" and "kumusta" both
find the same entry. ✅ Both are covered by `web/src/lib/signs.test.ts`.

**Next action:** record the reference videos. Every entry currently renders an honest
"no reference video yet" placeholder, which is the last thing between this and a
dictionary someone can actually learn from.

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

✅ `web/src/lib/features.ts` and its parity test are already done — verified to reproduce
the Python output exactly against the shared golden fixtures.

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
| `wlasl_candidate` in `seed.csv` | **Removed in Phase 2.** The column flagged overlap with the ASL WLASL-100 gloss list. The vocabulary is now FSL-specific — Filipino gestures, Filipino month names, Ñ and Ng — so ASL overlap no longer says anything useful about it. Phase 4 needs a fresh answer to "what can we actually train on", not a resurrected column. |
| `params` on all sign entries | Deliberately `null`. Handshape/location/movement were not guessed — wrong articulatory data actively teaches people the wrong thing. Fill in from your own recordings. `motion` is empty for the same reason on everything outside the alphabet and numbers. |
| Filipino glosses | Written to get the bilingual UI working, **not reviewed by a Deaf FSL user**. `content/README.md` lists the specific judgement calls to check first. |
| Two copies of `signs.json` | `content/signs.json` and `web/src/content/signs.json` are written together and asserted byte-identical. Vercel builds with `web/` as the project root, so the web app cannot import `../../content`. |
| Python version | 3.14 verified working. The common "you must use 3.11" advice is out of date since mediapipe 1.0. |
| `torch.onnx.export` | Must use `dynamic_shapes` (not `dynamic_axes`) **and** a batch-2 example, or the batch axis silently pins to 1. Already handled in `export_onnx.py`. |
| Console encoding on Windows | `torch.onnx.export` prints emoji. On a cp1252 console (Git Bash, several Windows terminals) that raises `UnicodeEncodeError` and kills the export mid-run, with a traceback pointing at torch internals. Fixed by forcing UTF-8 stdout in `export_onnx.py` and setting `PYTHONIOENCODING` for subprocesses in `verify.py`. |
| Dark mode | `web/src/app/globals.css` declares `color-scheme: light`. The scaffold's default dark block only flipped two variables while every section sets its own surface colour, producing a broken half-dark page. Real dark mode needs surfaces tokenised first. |
