"""Verify the whole project from a single command.

    python scripts/verify.py

Runs every automated check there is and prints a report. Each check says what
it PROVES, so a green run tells you something specific rather than just
"tests passed".

Uses only the standard library, so it runs on any Python without setup.
Exit code 0 means everything that can be checked right now is working.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ML_PY = REPO / "ml" / ".venv" / "Scripts" / "python.exe"
API_PY = REPO / "api" / ".venv" / "Scripts" / "python.exe"

if os.name != "nt":  # macOS / Linux layout
    ML_PY = REPO / "ml" / ".venv" / "bin" / "python"
    API_PY = REPO / "api" / ".venv" / "bin" / "python"

results: list[tuple[str, str, str]] = []   # (status, name, detail)

# This script prints output captured from other programs, which may contain
# any character. Windows consoles frequently report a cp1252 stdout, where a
# single em-dash in a subprocess's output would otherwise crash the whole run
# with UnicodeEncodeError. Ask for UTF-8, and sanitize as a fallback for
# terminals that refuse it.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except (AttributeError, OSError):
    pass


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def safe(text: str) -> str:
    """Drop characters the active console cannot render, rather than crashing."""
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    symbol = {"PASS": "  OK  ", "FAIL": " FAIL ", "SKIP": " SKIP "}[status]
    print(safe(f"[{symbol}] {name}"))
    if detail:
        for line in detail.splitlines():
            print(safe(f"          {line}"))


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 300):
    """Run a command, returning (ok, combined_output)."""
    # Force UTF-8 in every child process. Without this, any subprocess that
    # prints a non-ASCII character (torch's exporter prints emoji) dies with
    # UnicodeEncodeError on a cp1252 console, and the traceback points at the
    # library rather than at the encoding.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return False, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_layout() -> None:
    section("1. Project layout")
    expected = [
        "ml/src/features.py", "ml/src/model.py", "ml/src/export_onnx.py",
        "api/app/main.py", "api/Dockerfile",
        "content/signs.json", "scripts/build_signs.py",
        "ml/tests/fixtures/golden-clip.json",
    ]
    missing = [p for p in expected if not (REPO / p).exists()]
    if missing:
        record("FAIL", "expected files present", "missing: " + ", ".join(missing))
    else:
        record("PASS", "expected files present",
               f"{len(expected)} key files found")


def check_environments() -> bool:
    section("2. Python environments")
    ok = True

    for label, python, packages in (
        ("ml", ML_PY, ["torch", "numpy", "onnx", "onnxruntime", "onnxscript", "pytest"]),
        ("api", API_PY, ["fastapi", "numpy", "onnxruntime", "pytest"]),
    ):
        if not python.exists():
            record("FAIL", f"{label} virtualenv exists",
                   f"not found at {python.relative_to(REPO)}\n"
                   f"create it:  cd {label} && python -m venv .venv && "
                   f".venv\\Scripts\\pip install -r requirements.txt")
            ok = False
            continue

        code = "import importlib;" + "".join(
            f"importlib.import_module('{p}');" for p in packages
        ) + "print('ok')"
        good, out = run([str(python), "-c", code])
        if good:
            record("PASS", f"{label} virtualenv has its packages",
                   ", ".join(packages))
        else:
            record("FAIL", f"{label} virtualenv has its packages", out.strip()[-300:])
            ok = False

    return ok


def check_tests() -> None:
    section("3. Automated tests")

    if ML_PY.exists():
        good, out = run([str(ML_PY), "-m", "pytest", "ml/tests/", "-q", "--no-header"])
        summary = next((l for l in reversed(out.splitlines()) if "passed" in l or "failed" in l), "")
        record("PASS" if good else "FAIL",
               "ml tests (feature transform + golden parity)", summary.strip())
    else:
        record("SKIP", "ml tests", "ml virtualenv missing")

    if API_PY.exists():
        good, out = run([str(API_PY), "-m", "pytest", "api/tests/", "-q", "--no-header"])
        summary = next((l for l in reversed(out.splitlines()) if "passed" in l or "failed" in l), "")
        record("PASS" if good else "FAIL",
               "api tests (validation + error handling)", summary.strip())
    else:
        record("SKIP", "api tests", "api virtualenv missing")


def check_feature_copies() -> None:
    section("4. Train/serve feature parity")

    a = REPO / "ml" / "src" / "features.py"
    b = REPO / "api" / "app" / "features.py"
    if a.read_bytes() == b.read_bytes():
        record("PASS", "ml and api feature code are byte-identical",
               "the model will see the same numbers in training and in production")
    else:
        record("FAIL", "ml and api feature code are byte-identical",
               "they have DIVERGED - copy ml/src/features.py over api/app/features.py")


def check_content() -> None:
    section("5. Dictionary content")
    good, out = run([sys.executable, "scripts/build_signs.py", "--check"])
    record("PASS" if good else "FAIL", "signs.json passes validation",
           out.strip().splitlines()[-1] if out.strip() else "")


def check_model() -> None:
    section("6. Model architecture")
    if not ML_PY.exists():
        record("SKIP", "model smoke test", "ml virtualenv missing")
        return

    good, out = run([str(ML_PY), "src/model.py"], cwd=REPO / "ml")
    detail = "\n".join(l for l in out.splitlines() if "parameters" in l or "logits" in l)
    record("PASS" if good and "smoke test passed" in out else "FAIL",
           "transformer builds, runs, and backpropagates", detail)


def check_export() -> None:
    section("7. ONNX export")
    if not ML_PY.exists():
        record("SKIP", "onnx export", "ml virtualenv missing")
        return

    good, out = run(
        [str(ML_PY), "src/export_onnx.py", "--random", "--num-classes", "8"],
        cwd=REPO / "ml", timeout=600,
    )
    diffs = [l.strip() for l in out.splitlines() if "max |torch - onnx|" in l]
    if good and len(diffs) >= 2:
        record("PASS", "exported ONNX matches PyTorch at several batch sizes",
               "\n".join(diffs))
    else:
        record("FAIL", "exported ONNX matches PyTorch at several batch sizes",
               out.strip()[-400:])


def check_live_api() -> None:
    section("8. Live API end-to-end")
    if not API_PY.exists():
        record("SKIP", "live API", "api virtualenv missing")
        return

    model = REPO / "api" / "models" / "word-v1.onnx"
    if not model.exists():
        record("SKIP", "live API", "no model exported yet")
        return

    port = free_port()
    proc = subprocess.Popen(
        [str(API_PY), "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=str(REPO / "api"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    try:
        base = f"http://127.0.0.1:{port}"
        health = None
        for _ in range(40):                      # up to ~20s for startup
            try:
                with urllib.request.urlopen(f"{base}/healthz", timeout=2) as r:
                    health = json.loads(r.read())
                    break
            except (urllib.error.URLError, ConnectionResetError, TimeoutError):
                time.sleep(0.5)

        if health is None:
            record("FAIL", "API starts and answers /healthz", "server never became ready")
            return

        record("PASS", "API starts and answers /healthz",
               f"model_version={health['model_version']}  classes={health['num_classes']}  "
               f"trained={health['trained']}\n"
               f"sequence_length={health['sequence_length']}  feature_dims={health['feature_dims']}")

        if not health["trained"]:
            record("PASS", "API flags the untrained model honestly",
                   "predictions below are random by design - this checks the plumbing")

        # Real prediction through HTTP, using the committed golden clip.
        clip = (REPO / "ml" / "tests" / "fixtures" / "golden-clip.json").read_bytes()
        request = urllib.request.Request(
            f"{base}/v1/predict/word", data=clip,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as r:
            body = json.loads(r.read())

        preds = body["predictions"]
        total = sum(p["confidence"] for p in preds)
        lines = [f"{i + 1}. {p['label']:10} {p['gloss_fil']:12} {p['confidence']:.3f}"
                 for i, p in enumerate(preds)]
        record("PASS", "landmarks -> features -> model -> ranked predictions",
               "\n".join(lines) + f"\n(top-5 confidence sums to {total:.3f})")

        # Bad input must be refused clearly, not answered with nonsense.
        bad = json.dumps({"frames": [{"pose": None, "left_hand": None,
                                      "right_hand": None}] * 5, "fps": 30}).encode()
        request = urllib.request.Request(
            f"{base}/v1/predict/word", data=bad,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=20)
            record("FAIL", "API rejects a clip with no hands", "it accepted it")
        except urllib.error.HTTPError as exc:
            record("PASS" if exc.code == 422 else "FAIL",
                   "API rejects a clip with no hands",
                   f"HTTP {exc.code} (422 expected)")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_web() -> None:
    section("9. Web frontend")
    web = REPO / "web"

    if not (web / "package.json").exists():
        record("SKIP", "web frontend", "not scaffolded yet (needs Node.js installed)")
        return
    if not (web / "node_modules").exists():
        record("FAIL", "web dependencies installed", "run: cd web && npm install")
        return

    npm = "npm.cmd" if os.name == "nt" else "npm"

    # The TypeScript half of the golden-vector parity guard lives here. Until
    # this passes, features.ts and features.py could silently disagree.
    good, out = run([npm, "test"], cwd=web, timeout=600)
    summary = next((l.strip() for l in out.splitlines() if "Tests " in l), "")
    record("PASS" if good else "FAIL",
           "web tests (feature parity + translation completeness)",
           summary or out.strip()[-300:])

    # `next typegen` first: route types are generated, and a stale set makes
    # tsc report errors that the real build does not have.
    good, out = run([npm, "run", "typecheck"], cwd=web, timeout=600)
    record("PASS" if good else "FAIL", "web typechecks",
           "" if good else out.strip()[-400:])


def check_not_yet_possible() -> None:
    section("10. Not testable yet")

    docker, _ = run(["docker", "--version"], timeout=30)
    record("SKIP", "docker image build",
           "Docker installed - try: docker build -t fslames-api ./api" if docker
           else "Docker not installed (only needed to deploy)")

    record("SKIP", "model accuracy",
           "no trained model exists yet - that is Phase 4")


# --------------------------------------------------------------------------

def main() -> int:
    print("=" * 68)
    print("  FSLAMES - full verification")
    print("=" * 68)

    check_layout()
    environments_ok = check_environments()
    check_tests()
    check_feature_copies()
    check_content()
    if environments_ok:
        check_model()
        check_export()
        check_live_api()
    check_web()
    check_not_yet_possible()

    passed = sum(1 for s, _, _ in results if s == "PASS")
    failed = sum(1 for s, _, _ in results if s == "FAIL")
    skipped = sum(1 for s, _, _ in results if s == "SKIP")

    print("\n" + "=" * 68)
    print(f"  {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 68)

    if failed:
        print("\nFailed checks:")
        for status, name, _ in results:
            if status == "FAIL":
                print(f"  - {name}")
        print("\nSee docs/verification.md for what each check means.")
        return 1

    print("\nEverything that can be checked right now is working.")
    print("That proves the plumbing, not that the app is finished -")
    print("see docs/roadmap.md for what is actually built.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
