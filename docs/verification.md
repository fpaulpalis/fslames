# How to verify everything yourself

You should not have to take anyone's word that this works. This page shows you how to
check it, what each check actually proves, and how to confirm the checks are real by
deliberately breaking things.

---

## The one command

```bash
python scripts/verify.py
```

Takes about a minute. Ends with either:

```
  15 passed, 0 failed, 2 skipped
Everything that can be checked right now is working.
```

or a list of what failed. Exit code is 0 on success, 1 on failure — so you can wire it
into CI later without changing anything.

---

## What each check proves

### 1. Project layout
The files exist where the docs say they do. Catches a half-finished checkout.

### 2. Python environments
Both virtualenvs exist and can import their packages. If this fails, you likely haven't
created the venvs yet — the error message tells you the exact command.

### 3. Automated tests

**ml tests (16)** — the landmark → tensor transform. The important ones:

- *Invariance*: scale every coordinate by 2×, or shift the whole body sideways, and the
  output must be **identical to within 1e-5**. This is the property that lets a model
  trained on my camera setup work on yours. If it broke, the app would work for whoever
  recorded the training data and fail for everyone else.
- *Golden parity*: the transform still produces the exact numbers committed in
  `ml/tests/fixtures/`. This is the tripwire for the worst bug in this kind of project —
  see below.
- *Degenerate frames*: coincident shoulders, zero-size hands, missing detections. No
  NaN, no crash, no divide-by-zero.

**api tests (13)** — request validation and error handling. Proves malformed input gets a
clear `422` rather than a confident wrong answer, that a one-handed clip is *accepted*
(most ASL signs are one-handed), and that a missing model returns `503` instead of
crashing.

### 4. Train/serve feature parity
`ml/src/features.py` and `api/app/features.py` are byte-identical.

**Why this check exists:** features are computed in Python during training and in
TypeScript in the browser at inference. If those drift apart even slightly — a reordered
column, a different normalization order — the model trains perfectly and then predicts
nonsense in the browser **with no error message anywhere**. Nothing crashes. You just get
bad predictions and no clue why. This is the single most expensive bug available in this
architecture, and this check plus the golden fixtures is the guard against it.

### 5. Dictionary content
`signs.json` passes validation: unique slugs, both glosses present, no entry where the
Filipino translation is identical to the English (which would mean it was never
translated), no draft entry marked as AI-checkable.

### 6. Model architecture
The transformer builds, runs a forward pass, and gradients flow back to the CLS token.
Reports 2,237,284 parameters. Proves the architecture is wired correctly — not that it
has learned anything.

### 7. ONNX export
Exports the model and then runs **both** PyTorch and ONNX on the same input, at more than
one batch size, asserting they agree to ~1e-7.

The multiple batch sizes matter. An earlier version of the export passed at batch=1 and
failed at batch=3, because `torch.export` silently pins size-1 dimensions. A
single-batch-size check would have shipped that bug to production.

### 8. Live API end-to-end
Boots a real uvicorn server on a free port, then:

- `GET /healthz` returns the model version and the feature contract (`64`, `332`)
- `POST /v1/predict/word` with the committed golden clip returns five ranked candidates
  carrying dictionary slugs and Filipino glosses
- A clip with no hands detected is rejected with `422`

This is the whole pipeline: raw landmarks → normalization → transformer → ranked
predictions → dictionary lookup, over real HTTP.

**The predictions are meaningless right now** — the model is untrained. That is the point
of this stage: it proves the *plumbing* before any training happens, so when predictions
are later wrong you know it is the model and not the wiring. `/healthz` reports
`"trained": false` and the server logs a warning, so this can never be mistaken for a
working model.

### 9. Web frontend

**`npm test` (13 tests)** — two groups:

- *Golden-vector parity*: `features.ts` is loaded against the **same fixture files** the
  Python test uses, asserting agreement to 1e-5. This is the other half of the guard
  described in check 4. With both halves passing, the browser and the training pipeline
  provably compute identical features.
- *Translation completeness*: `en.json` and `fil.json` have identical key sets, no empty
  values, and no Filipino string that is byte-identical to its English counterpart
  (excluding an explicit allow-list for proper nouns). This catches the failure where the
  Filipino toggle silently does nothing on part of the site.

**`npm run typecheck`** — runs `next typegen` first, then `tsc`. The typegen step matters:
Next generates route types, and running `tsc` against a stale set reports errors the real
build does not have.

---

## Prove the checks are real

A test suite that always passes tells you nothing. Break something on purpose:

**Break the feature parity:**
```bash
python -c "p='api/app/features.py';s=open(p).read();open(p,'w').write(s.replace('EPSILON = 1e-6','EPSILON = 1e-3'))"
```
Re-run `python scripts/verify.py` — two independent checks should fail (the byte-identity
check and an api test). Then restore:
```bash
git checkout -- api/app/features.py
```

**Break the normalization:**
```bash
python -c "p='ml/src/features.py';s=open(p).read();open(p,'w').write(s.replace('/ scale','/ 1.0'))"
```
The invariance test and the golden parity test should both fail. Restore the same way.

**Break the TypeScript port** (the most important one):
```bash
python -c "p='web/src/lib/features.ts';s=open(p).read();open(p,'w').write(s.replace('[5, 9, 13, 17]','[5, 9, 13, 18]'))"
```
That changes a single landmark index by one. Run `cd web && npm test` — the parity test
should fail and name the exact frame and column where the two implementations diverge.
Restore with `git checkout -- web/src/lib/features.ts`.

**Break the dictionary:** add a row to `content/seed.csv` with a slug that already exists,
then run `python scripts/build_signs.py --check`.

If any of those *pass*, the check is not doing its job and you should tell me.

---

## Poke at it by hand

Start the API yourself:

```bash
cd api
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

### Easiest: the browser

Open **http://localhost:8000/docs**.

FastAPI generates an interactive explorer from the code itself. You can read the request
schema, hit **Try it out**, edit the JSON, and fire real requests from the page. No shell
quoting, no curl. This is the best way to get a feel for the API, and it stays in sync
with the code automatically because it is generated from it.

### From PowerShell

⚠️ **`curl` in PowerShell is not curl.** It is an alias for `Invoke-WebRequest`, which
takes completely different flags. And PowerShell 5.1 strips double quotes when passing
arguments to real `.exe`s, so JSON on the command line needs backslash escaping. Both of
these produce baffling errors. Use PowerShell's own command instead:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/healthz
```

Send the golden clip through the whole pipeline:

```powershell
Invoke-RestMethod -Uri http://localhost:8000/v1/predict/word -Method Post -ContentType "application/json" -Body (Get-Content ml/tests/fixtures/golden-clip.json -Raw)
```

Confirm bad input gives a clean error rather than a stack trace:

```powershell
try { Invoke-RestMethod -Uri http://localhost:8000/v1/predict/word -Method Post -ContentType "application/json" -Body '{"frames":[],"fps":30}' } catch { $_.ErrorDetails.Message }
```

Expected: `422` with `"List should have at least 2 items"` — the schema rejecting a clip
too short to be a sign.

### From Git Bash

You have Git Bash installed, and normal curl syntax works there:

```bash
curl -s http://localhost:8000/healthz

curl -s -X POST http://localhost:8000/v1/predict/word -H 'Content-Type: application/json' --data-binary '@ml/tests/fixtures/golden-clip.json'

curl -s -X POST http://localhost:8000/v1/predict/word -H 'Content-Type: application/json' -d '{"frames":[],"fps":30}'
```

---

## Look at the data

```bash
python -c "import json;d=json.load(open('content/signs.json',encoding='utf-8'));print(d['counts']);print(d['signs'][0])"
```

Every entry has `params: null` and `contentStatus: \"draft\"`. That is deliberate, not
unfinished work — handshape and movement descriptions were left empty rather than guessed,
because a confidently wrong description of how to form a sign teaches people the wrong
thing. See [`../content/README.md`](../content/README.md).

---

## What is NOT tested yet, and why

| Not covered | Why |
|---|---|
| **Docker image** | Docker not installed. Once it is: `docker build -t strongasl-api ./api` |
| **Model accuracy** | No trained model exists. Phase 4 |
| **Deployment** | Nothing deployed yet |
| **Visual appearance** | Tests confirm strings translate and pages build; they do not confirm the design looks right. Run `cd web && npm run dev` and look |

Green here means **the plumbing is correct**. It does not mean the app works — there is no
app yet, and no model that has learned anything. Those are honestly different claims and
the report is written to keep them apart.

---

## Troubleshooting

**`python: command not found`** — try `py` instead of `python` on Windows.

**A virtualenv check fails** — recreate it:
```bash
cd ml
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Note `ml/requirements.txt` installs the full CUDA build of PyTorch (~2.5 GB). For
CPU-only work, which is all this needs until training:
```bash
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**The live API check is skipped** — no model has been exported. Generate a smoke model:
```bash
cd ml
.venv\Scripts\python src/export_onnx.py --random --num-classes 8
```

**A port is already in use** — the script picks a free port automatically. If it still
fails, something is blocking loopback connections, usually a firewall or VPN.

**`UnicodeEncodeError` running something by hand** — Windows consoles often report
`cp1252`, and several tools here print non-ASCII (PyTorch's ONNX exporter prints emoji).
`verify.py` sets `PYTHONIOENCODING=utf-8` for everything it launches, and `export_onnx.py`
forces UTF-8 on its own streams, so this should not happen. If you hit it in a script that
predates those fixes, prefix the command:

```bash
PYTHONIOENCODING=utf-8 python the-script.py
```

**`tsc` reports errors but `npm run build` passes** — your route types are stale. Run
`npm run typecheck`, which does `next typegen` first.
