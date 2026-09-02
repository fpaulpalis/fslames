# Strong ASL — Filipino Edition

A bilingual (English / Filipino) American Sign Language learning app: a searchable sign
dictionary, alphabet and fingerspelling lessons, and a camera-based AI practice tool that
tells you which sign you just made.

Signs are **ASL**. The interface and the word labels are available in **English and Filipino**.

## Repository layout

```
strong-asl-fil/
├─ web/    Next.js frontend                → deploys to Vercel
├─ api/    FastAPI inference service       → deploys to Render (Docker)
├─ ml/     PyTorch training pipeline       → runs locally / on Colab, never deployed
└─ docs/   design notes and decisions
```

Each folder runs independently. You can develop `web/` without `api/` or `ml/` running.

## The core idea

> **Video never leaves the browser. Only coordinates do.**

The browser uses MediaPipe to turn your webcam feed into 21 hand landmarks and a body pose,
per frame. Letters are classified right there in the browser. Words send ~64 frames of
*coordinates* (a small JSON) to the Python API, which runs a transformer and returns the
five most likely signs.

This means the server never sees video, never needs a GPU, and never stores anything
personal — and letter practice works with no network at all.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 22 LTS | Next.js 16 requires Node 20.9+ |
| Python | 3.12+ (3.14 verified) | Verified by dependency resolution on 2026-09-03 |
| Docker | latest | Only needed to build the API image for deploy |

> **On Python versions:** older guides for this stack insist on Python 3.11, because
> MediaPipe used to ship version-specific wheels that lagged new releases. As of
> **mediapipe 1.0** the wheels are version-agnostic (`py3-none-win_amd64`) and
> **torch 2.14** ships cp314 builds, so the full training stack resolves cleanly on
> Python 3.14. If you hit a wheel problem on a future Python release, dropping to
> 3.12 is the escape hatch — nothing in this repo depends on a 3.13+ language feature.

## Quick start

```bash
# Frontend
cd web
npm install
npm run dev          # http://localhost:3000
```

```bash
# Inference API
cd api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Training pipeline
cd ml
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/model.py          # smoke-test the architecture
python -m pytest tests/      # verify the feature contract
```

## ⚠️ The one rule that matters

`ml/src/features.py` is the **single source of truth** for how landmarks become model input.

It is duplicated in two places that must stay byte-identical in behaviour:

- `api/app/features.py` — a literal copy
- `web/src/lib/features.ts` — a line-by-line port

If these ever drift, the model will train perfectly and predict garbage in the browser,
**with no error message**. The golden-vector parity test (`ml/tests/`, `api/tests/`,
`web/src/lib/features.test.ts`) exists to catch exactly this. Run it before trusting any
prediction result.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — how the pieces fit together
- [`docs/feature-spec.md`](docs/feature-spec.md) — the exact landmark → tensor contract
- [`docs/roadmap.md`](docs/roadmap.md) — build phases and current status
