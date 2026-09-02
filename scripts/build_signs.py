"""Build and validate content/signs.json from content/seed.csv.

    python scripts/build_signs.py            # build + validate
    python scripts/build_signs.py --check    # validate only, write nothing (for CI)

Keeping the dictionary in CSV means you can maintain it in a spreadsheet and
still get schema validation, deterministic output, and a reviewable diff.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "content" / "seed.csv"
OUTPUT_PATH = REPO_ROOT / "content" / "signs.json"

REQUIRED_COLUMNS = {
    "slug", "gloss_en", "gloss_fil", "aliases_en",
    "aliases_fil", "category", "wlasl_candidate",
}


def read_seed(path: Path) -> list[dict[str, str]]:
    """Read the CSV, ignoring blank lines and '#' comments.

    Reads as utf-8-sig because Excel saves CSV with a UTF-8 BOM by default.
    Without this the first column name parses as '\\ufeffslug' and every row
    fails validation with a baffling "missing column: slug".
    """
    raw = path.read_text(encoding="utf-8-sig")
    body = "\n".join(
        line for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    rows = list(csv.DictReader(io.StringIO(body)))

    if not rows:
        raise SystemExit(f"{path} contains no data rows")

    missing = REQUIRED_COLUMNS - set(rows[0].keys())
    if missing:
        raise SystemExit(f"{path} is missing columns: {sorted(missing)}")

    return rows


def split_aliases(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def build_entry(row: dict[str, str]) -> dict:
    gloss_en = row["gloss_en"].strip()

    return {
        "slug": row["slug"].strip(),
        "gloss": {"en": gloss_en, "fil": row["gloss_fil"].strip()},
        "aliases": {
            "en": split_aliases(row["aliases_en"]),
            "fil": split_aliases(row["aliases_fil"]),
        },
        "letter": gloss_en[0].upper(),
        "category": row["category"].strip(),
        # No media until it is actually recorded. The UI must handle null.
        "media": {"video": None, "poster": None},
        # Articulatory detail is left null on purpose — see content/README.md.
        # Guessing how a sign is formed would teach people the wrong thing.
        "params": None,
        "notes": {"en": "", "fil": ""},
        "modelLabel": None,
        "inModel": False,
        "wlaslCandidate": row["wlasl_candidate"].strip().lower() == "yes",
        "contentStatus": "draft",
    }


def validate(entries: list[dict]) -> list[str]:
    """Return a list of human-readable problems. Empty means the data is good."""
    problems: list[str] = []

    seen_slugs: dict[str, int] = {}
    seen_en: dict[str, int] = {}

    for i, entry in enumerate(entries):
        where = f"row {i + 1} ({entry['slug'] or '<no slug>'})"

        slug = entry["slug"]
        if not slug:
            problems.append(f"{where}: empty slug")
        elif slug in seen_slugs:
            problems.append(f"{where}: duplicate slug, first seen at row {seen_slugs[slug] + 1}")
        else:
            seen_slugs[slug] = i

        if slug and slug != slug.lower():
            problems.append(f"{where}: slug must be lowercase")
        if " " in slug:
            problems.append(f"{where}: slug must not contain spaces (use hyphens)")

        if not entry["gloss"]["en"]:
            problems.append(f"{where}: missing English gloss")
        if not entry["gloss"]["fil"]:
            problems.append(f"{where}: missing Filipino gloss")

        # A missing translation is the failure mode that would quietly ship an
        # app where the Filipino toggle does nothing on half the dictionary.
        if entry["gloss"]["en"].lower() == entry["gloss"]["fil"].lower():
            problems.append(
                f"{where}: Filipino gloss is identical to English — probably untranslated"
            )

        english = entry["gloss"]["en"].lower()
        if english in seen_en:
            problems.append(f"{where}: duplicate English gloss '{english}'")
        else:
            seen_en[english] = i

        if entry["inModel"] and not entry["modelLabel"]:
            problems.append(f"{where}: inModel is true but modelLabel is null")
        if entry["inModel"] and entry["contentStatus"] != "verified":
            problems.append(f"{where}: only verified entries may be inModel")

        if not entry["category"]:
            problems.append(f"{where}: missing category")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    rows = read_seed(SEED_PATH)
    entries = [build_entry(row) for row in rows]
    entries.sort(key=lambda e: e["gloss"]["en"].lower())

    problems = validate(entries)
    if problems:
        print(f"FAILED — {len(problems)} problem(s) in {SEED_PATH.name}:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    letters = sorted({e["letter"] for e in entries})
    categories = sorted({e["category"] for e in entries})

    document = {
        "version": 1,
        "generatedFrom": "content/seed.csv",
        "counts": {
            "total": len(entries),
            "verified": sum(1 for e in entries if e["contentStatus"] == "verified"),
            "withVideo": sum(1 for e in entries if e["media"]["video"]),
            "inModel": sum(1 for e in entries if e["inModel"]),
            "wlaslCandidates": sum(1 for e in entries if e["wlaslCandidate"]),
        },
        "letters": letters,
        "categories": categories,
        "signs": entries,
    }

    if args.check:
        print(f"OK — {len(entries)} entries valid (nothing written)")
        return 0

    OUTPUT_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    counts = document["counts"]
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {counts['total']} entries across {len(letters)} letters, {len(categories)} categories")
    print(f"  {counts['wlaslCandidates']} flagged as possible WLASL-100 words")
    print(f"  {counts['verified']} verified, {counts['withVideo']} with video, {counts['inModel']} in model")
    print("\nAll entries are drafts with no video and no handshape data — that is expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
