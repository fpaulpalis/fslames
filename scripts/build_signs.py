"""Build and validate the dictionary from content/seed.csv.

    python scripts/build_signs.py            # build + validate
    python scripts/build_signs.py --check    # validate only, write nothing (for CI)

Keeping the dictionary in CSV means you can maintain it in a spreadsheet and
still get schema validation, deterministic output, and a reviewable diff.

Two identical files are written:

  content/signs.json          canonical; read by ml/src/export_onnx.py
  web/src/content/signs.json  the copy Next.js imports

The copy exists because Vercel builds with `web/` as the project root, so an
import that reached up to `../../content` would resolve locally and then fail
in CI. `scripts/verify.py` and `web/src/lib/signs.test.ts` both assert the two
files are byte-identical, so a stale copy is caught rather than deployed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "content" / "seed.csv"
MEDIA_MANIFEST_PATH = REPO_ROOT / "content" / "media.json"
OUTPUT_PATHS = (
    REPO_ROOT / "content" / "signs.json",
    REPO_ROOT / "web" / "src" / "content" / "signs.json",
)

REQUIRED_COLUMNS = {
    "slug", "gloss_en", "gloss_fil", "aliases_en", "aliases_fil",
    "section", "group", "hands", "motion", "same_in_fil",
}

# The taxonomy, in the order the dictionary renders it. A section with an empty
# tuple takes no group. Listing it here rather than deriving it from the CSV
# turns a typo ("colours") into a build failure instead of a silent 1-word
# category that nobody notices until it ships.
#
# Human-readable labels live in web/messages/{en,fil}.json under
# `dictionary.sections` and `dictionary.groups` — add both when you add a key
# here, or web/src/lib/messages.test.ts will fail.
TAXONOMY: dict[str, tuple[str, ...]] = {
    "filipino-gestures": (),
    "basic-signs": ("alphabet", "general", "numbers", "colors"),
    "socializing": (
        "basic-greetings", "introducing", "leave-taking",
        "survival-signs", "wh-questions",
    ),
    "time-and-date": (
        "days-of-the-week", "months-of-the-year", "time-signs", "time-referent",
    ),
}

# "left-right" means the sign is one-handed and works with either hand.
HANDS = {"left-right", "both"}

# Empty is allowed and means "not recorded yet" — see the params note below.
MOTION = {"static", "dynamic", ""}

LOCALES = ("en", "fil")


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


def index_key(gloss: str) -> str:
    """The A-Z browse bucket a gloss falls into: its first character, uppercased.

    Computed per locale and stored, because the Filipino index cannot be derived
    from the English one. "Hello" belongs under H, "Kumusta" under K — filing the
    Filipino entry under H would make browsing in Filipino nonsense.
    """
    return gloss[:1].upper() if gloss else ""


def sort_key(gloss: str) -> tuple[str, str]:
    """Deterministic ordering that keeps accented letters next to their base.

    Plain `.lower()` sorts "Ñ" after "Z" because of its code point. Stripping
    diacritics for the primary key files it beside N, where a reader looks for
    it. The original string breaks ties so the order stays stable.
    """
    folded = unicodedata.normalize("NFKD", gloss)
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return (ascii_only.lower(), gloss.lower())



def load_media() -> dict[str, dict]:
    """Which signs have a recording, from content/media.json.

    Written by scripts/scan_media.py from the files on your disk. Read here
    rather than scanning media/ directly so this build produces identical bytes
    on a machine that has the recordings and on CI, which does not.
    """
    if not MEDIA_MANIFEST_PATH.exists():
        return {}
    document = json.loads(MEDIA_MANIFEST_PATH.read_text(encoding="utf-8"))
    return document.get("entries", {})


def media_for(slug: str, media: dict[str, dict]) -> dict:
    """Bucket-relative paths, or nulls until the sign is recorded.

    Paths are relative on purpose. The origin is NEXT_PUBLIC_MEDIA_BASE_URL at
    render time, so the same signs.json serves local files in dev and R2 in
    production without a rebuild.
    """
    entry = media.get(slug)
    if not entry:
        return {"video": None, "poster": None, "hash": None}
    return {
        "video": entry["video"],
        "poster": entry.get("poster"),
        "hash": entry.get("hash"),
    }


def build_entry(row: dict[str, str], order: int, media: dict[str, dict]) -> dict:
    gloss = {locale: row[f"gloss_{locale}"].strip() for locale in LOCALES}
    motion = row["motion"].strip().lower()

    return {
        "slug": row["slug"].strip(),
        # Position in seed.csv. The A–Z index sorts alphabetically, but browsing
        # a group should read in teaching order — January before April, Monday
        # before Friday, A before Ñ — which is the order the CSV is written in.
        "order": order,
        "gloss": gloss,
        "aliases": {
            locale: split_aliases(row[f"aliases_{locale}"]) for locale in LOCALES
        },
        "index": {locale: index_key(gloss[locale]) for locale in LOCALES},
        "section": row["section"].strip(),
        "group": row["group"].strip(),
        "hands": row["hands"].strip().lower(),
        # null, not a guess. A sign wrongly labelled static teaches a learner to
        # drop the movement that distinguishes it from another sign.
        "motion": motion or None,
        # Null until the recording exists. The UI must handle that.
        "media": media_for(row["slug"].strip(), media),
        # Articulatory detail is left null on purpose — see content/README.md.
        # Guessing how a sign is formed would teach people the wrong thing.
        "params": None,
        "notes": {locale: "" for locale in LOCALES},
        "modelLabel": None,
        "inModel": False,
        "contentStatus": "draft",
    }


def validate(entries: list[dict], rows: list[dict[str, str]]) -> list[str]:
    """Return a list of human-readable problems. Empty means the data is good."""
    problems: list[str] = []

    seen_slugs: dict[str, int] = {}
    seen_en: dict[str, int] = {}

    for i, (entry, row) in enumerate(zip(entries, rows)):
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
        # The slug is a URL segment and a filename-safe id; keep it ASCII so
        # "enye" never has to survive a round trip through URL encoding.
        if slug and not all(c.isascii() and (c.isalnum() or c == "-") for c in slug):
            problems.append(f"{where}: slug must be ASCII letters, digits and hyphens only")

        for locale in LOCALES:
            if not entry["gloss"][locale]:
                problems.append(f"{where}: missing {locale} gloss")

        # A missing translation is the failure mode that would quietly ship an
        # app where the Filipino toggle does nothing on half the dictionary.
        # `same_in_fil` is the explicit opt-out for words that genuinely do not
        # change — the letters of the alphabet, numerals, "FSL", "OK".
        same_flag = row["same_in_fil"].strip().lower() == "yes"
        identical = entry["gloss"]["en"].lower() == entry["gloss"]["fil"].lower()
        if identical and not same_flag:
            problems.append(
                f"{where}: Filipino gloss is identical to English — probably untranslated. "
                "If it is genuinely the same word, set same_in_fil to 'yes'."
            )
        if same_flag and not identical:
            problems.append(
                f"{where}: same_in_fil is 'yes' but the glosses differ — clear the flag"
            )

        english = entry["gloss"]["en"].lower()
        if english in seen_en:
            problems.append(f"{where}: duplicate English gloss '{english}'")
        else:
            seen_en[english] = i

        section, group = entry["section"], entry["group"]
        if section not in TAXONOMY:
            problems.append(
                f"{where}: unknown section '{section}' "
                f"(known: {', '.join(sorted(TAXONOMY))})"
            )
        elif TAXONOMY[section] and group not in TAXONOMY[section]:
            problems.append(
                f"{where}: unknown group '{group}' for section '{section}' "
                f"(known: {', '.join(TAXONOMY[section])})"
            )
        elif not TAXONOMY[section] and group:
            problems.append(f"{where}: section '{section}' takes no group, got '{group}'")

        if entry["hands"] not in HANDS:
            problems.append(
                f"{where}: hands must be one of {sorted(HANDS)}, got '{entry['hands']}'"
            )
        if (entry["motion"] or "") not in MOTION:
            problems.append(
                f"{where}: motion must be 'static', 'dynamic' or empty, "
                f"got '{entry['motion']}'"
            )

        if entry["inModel"] and not entry["modelLabel"]:
            problems.append(f"{where}: inModel is true but modelLabel is null")
        if entry["inModel"] and entry["contentStatus"] != "verified":
            problems.append(f"{where}: only verified entries may be inModel")

    return problems


def build_document(entries: list[dict]) -> dict:
    sections = [
        {
            "slug": section,
            "groups": [
                {
                    "slug": group,
                    "count": sum(
                        1 for e in entries
                        if e["section"] == section and e["group"] == group
                    ),
                }
                for group in groups
            ],
            "count": sum(1 for e in entries if e["section"] == section),
        }
        for section, groups in TAXONOMY.items()
    ]

    return {
        "version": 2,
        "generatedFrom": "content/seed.csv",
        "counts": {
            "total": len(entries),
            "verified": sum(1 for e in entries if e["contentStatus"] == "verified"),
            "withVideo": sum(1 for e in entries if e["media"]["video"]),
            "inModel": sum(1 for e in entries if e["inModel"]),
        },
        "index": {
            locale: sorted(
                {e["index"][locale] for e in entries}, key=sort_key
            )
            for locale in LOCALES
        },
        "sections": sections,
        "signs": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args()

    rows = read_seed(SEED_PATH)
    media = load_media()
    pairs = sorted(
        ((build_entry(row, order, media), row) for order, row in enumerate(rows)),
        key=lambda pair: sort_key(pair[0]["gloss"]["en"]),
    )
    entries = [entry for entry, _ in pairs]
    source_rows = [row for _, row in pairs]

    problems = validate(entries, source_rows)

    # A manifest entry with no matching sign means a slug was renamed or removed
    # after the media was scanned. Left alone, the recording silently stops being
    # reachable from anywhere in the app.
    orphans = sorted(set(media) - {entry["slug"] for entry in entries})
    if orphans:
        problems.append(
            f"content/media.json references {len(orphans)} slug(s) not in seed.csv: "
            f"{', '.join(orphans)} - re-run scripts/scan_media.py"
        )

    if problems:
        print(f"FAILED — {len(problems)} problem(s) in {SEED_PATH.name}:\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    document = build_document(entries)
    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        stale = [
            path for path in OUTPUT_PATHS
            if not path.exists() or path.read_text(encoding="utf-8") != payload
        ]
        if stale:
            print(
                "FAILED — these files are out of date, run scripts/build_signs.py:\n"
                + "\n".join(f"  - {p.relative_to(REPO_ROOT)}" for p in stale),
                file=sys.stderr,
            )
            return 1
        print(f"OK - {len(entries)} entries valid and up to date (nothing written)")
        return 0

    for path in OUTPUT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" because .gitattributes declares these files LF. Without
        # it, write_text on Windows emits CRLF and every rebuild leaves the
        # working tree dirty against what git actually stores.
        path.write_text(payload, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(REPO_ROOT)}")

    counts = document["counts"]
    print(
        f"  {counts['total']} entries · "
        f"{len(document['index']['en'])} index keys (en), "
        f"{len(document['index']['fil'])} (fil) · "
        f"{len(document['sections'])} sections"
    )
    for section in document["sections"]:
        groups = ", ".join(f"{g['slug']} ({g['count']})" for g in section["groups"])
        print(f"  - {section['slug']}: {section['count']}" + (f" — {groups}" if groups else ""))
    print(f"  {counts['verified']} verified, {counts['withVideo']} with video, "
          f"{counts['inModel']} in model")
    print("\nAll entries are drafts with no video and no handshape data — that is expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
