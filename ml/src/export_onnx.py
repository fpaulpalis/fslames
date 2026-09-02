"""Export a trained checkpoint to ONNX for the inference API.

    python src/export_onnx.py --checkpoint runs/word-v1/best.pt
    python src/export_onnx.py --random --num-classes 5      # untrained smoke model

The --random mode exists on purpose. It lets you build, deploy, and load-test
the entire serving path — Docker image, Render service, CORS, the browser
client — before you have spent a single hour training. Wiring problems are
much easier to debug when you are not also wondering whether the model is any
good. The exported labels are obviously fake, so nobody can mistake its
predictions for real ones.

Writes two files next to each other:
    api/models/word-v1.onnx
    api/models/word-v1.labels.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from features import FEATURE_DIMS, SEQUENCE_LENGTH
from model import ModelConfig, SignTransformer

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "api" / "models"

# torch >= 2.9 implements opset 18+. Requesting 17 triggers a lossy fallback
# conversion through the ONNX C API, which we do not want in a shipped model.
OPSET = 18


def load_signs() -> dict[str, dict]:
    """Index content/signs.json by uppercase gloss, for label enrichment."""
    path = REPO_ROOT / "content" / "signs.json"
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    return {entry["gloss"]["en"].upper(): entry for entry in document["signs"]}


def build_labels(class_names: list[str]) -> list[dict]:
    """Attach dictionary metadata to each model class.

    This is the seam that turns a bare prediction ("HELLO") into something the
    UI can render: a Filipino gloss and a link to the dictionary entry. Doing
    it at export time means the API needs no dictionary lookup at runtime.
    """
    signs = load_signs()
    labels = []

    for name in class_names:
        entry = signs.get(name.upper())
        if entry:
            labels.append(
                {
                    "label": name,
                    "slug": entry["slug"],
                    "gloss_en": entry["gloss"]["en"],
                    "gloss_fil": entry["gloss"]["fil"],
                }
            )
        else:
            # The model knows a word the dictionary does not. Export anyway so
            # the mismatch is visible in the labels file rather than crashing.
            labels.append(
                {
                    "label": name,
                    "slug": name.lower().replace(" ", "-"),
                    "gloss_en": name.lower(),
                    "gloss_fil": "",
                }
            )

    missing = [x["label"] for x in labels if not x["gloss_fil"]]
    if missing:
        print(f"  WARNING: {len(missing)} class(es) have no Filipino gloss: {missing[:8]}")
        print("           Add them to content/seed.csv and rebuild before shipping.")

    return labels


def export(
    model: SignTransformer,
    class_names: list[str],
    out_dir: Path,
    model_version: str,
    trained: bool = True,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"{model_version}.onnx"
    labels_path = out_dir / f"{model_version}.labels.json"

    model.eval()

    # Batch size 2, not 1, and this matters: torch.export SPECIALIZES
    # dimensions of size 1. Exporting with a batch-1 example silently pins the
    # batch axis to 1 no matter what dynamic_shapes says, and every batched
    # request then fails at inference with an opaque Reshape error.
    example = torch.randn(2, SEQUENCE_LENGTH, FEATURE_DIMS)

    # Only the batch axis varies. Sequence length and feature width stay fixed
    # by the feature contract, so the API can detect a mismatched model at
    # startup instead of mid-request.
    #
    # NOTE: this must be `dynamic_shapes`, not the older `dynamic_axes`. Since
    # torch 2.9 the dynamo exporter is the default and it silently IGNORES
    # dynamic_axes — the graph then hardcodes batch=1 and every multi-item
    # batch fails with a Reshape error at inference time. verify() below
    # catches that, which is why it tests more than one batch size.
    dynamic_shapes = {"x": {0: torch.export.Dim("batch", min=1, max=256)}}

    torch.onnx.export(
        model,
        (example,),
        str(model_path),
        input_names=["features"],
        output_names=["logits"],
        dynamic_shapes=dynamic_shapes,
        opset_version=OPSET,
        do_constant_folding=True,
        # Keep the weights inside the .onnx file. By default the exporter
        # spills them to a sibling word-v1.onnx.data, and two files that must
        # travel together is an easy thing to get wrong in a Docker COPY or a
        # .gitignore rule. At ~9 MB a single self-contained file is fine.
        external_data=False,
    )

    labels_path.write_text(
        json.dumps(
            {
                "model_version": model_version,
                # Travels with the model so the API can refuse to present an
                # untrained smoke model's output as a real prediction.
                "trained": trained,
                "num_classes": len(class_names),
                "sequence_length": SEQUENCE_LENGTH,
                "feature_dims": FEATURE_DIMS,
                "labels": build_labels(class_names),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return model_path, labels_path


def verify(model: SignTransformer, model_path: Path, tolerance: float = 1e-4) -> None:
    """Confirm the ONNX graph agrees with PyTorch before we ship it.

    Export can silently change behaviour — a traced control-flow branch, an op
    approximated differently. Catching it here costs seconds; catching it after
    deploy costs an afternoon of blaming the training data.
    """
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    rng = np.random.default_rng(0)
    for batch_size in (1, 3):
        sample = rng.normal(size=(batch_size, SEQUENCE_LENGTH, FEATURE_DIMS)).astype(np.float32)

        with torch.no_grad():
            torch_out = model(torch.from_numpy(sample)).numpy()
        onnx_out = session.run(None, {input_name: sample})[0]

        diff = float(np.abs(torch_out - onnx_out).max())
        if diff >= tolerance:
            raise SystemExit(
                f"ONNX output diverges from PyTorch by {diff:.2e} at batch={batch_size}. "
                "Do not ship this model."
            )
        print(f"  batch={batch_size}: max |torch - onnx| = {diff:.2e}  OK")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, help="path to a trained .pt checkpoint")
    parser.add_argument("--random", action="store_true", help="export an untrained model")
    parser.add_argument("--num-classes", type=int, default=5, help="classes for --random")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model-version", default="word-v1")
    args = parser.parse_args()

    if args.random:
        # Borrow real words from the dictionary so the smoke model produces
        # labels that at least render correctly in the UI.
        signs = load_signs()
        pool = sorted(signs.keys())[: args.num_classes]
        class_names = pool or [f"CLASS_{i}" for i in range(args.num_classes)]

        config = ModelConfig(num_classes=len(class_names))
        model = SignTransformer(config)
        print(f"Exporting an UNTRAINED model with {len(class_names)} classes.")
        print("Its predictions are meaningless — this is for testing the pipeline only.\n")

    elif args.checkpoint:
        if not args.checkpoint.exists():
            raise SystemExit(f"checkpoint not found: {args.checkpoint}")
        payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        config = ModelConfig(**payload["config"])
        model = SignTransformer(config)
        model.load_state_dict(payload["state_dict"])
        class_names = payload["class_names"]
        print(f"Loaded {args.checkpoint} ({len(class_names)} classes)\n")

    else:
        raise SystemExit("pass either --checkpoint <path> or --random")

    model_path, labels_path = export(
        model, class_names, args.out_dir, args.model_version, trained=not args.random
    )
    print(f"wrote {model_path}  ({model_path.stat().st_size / 1e6:.1f} MB)")
    print(f"wrote {labels_path}")

    print("\nVerifying ONNX matches PyTorch:")
    verify(model, model_path)
    print("\nDone. Restart the API to pick up the new model.")


if __name__ == "__main__":
    main()
