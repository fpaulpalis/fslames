"""Scan the local media/ folder and write content/media.json.

    python scripts/scan_media.py            # rewrite the manifest
    python scripts/scan_media.py --check    # report drift, write nothing (for CI)

Recordings are large binaries that never enter git — `*.mp4` is gitignored and
they live in Cloudflare R2. But `signs.json` has to know which signs have a
video, and it must produce identical bytes on every machine including CI, where
`media/` does not exist.

This script is the bridge. You run it after adding recordings; it reads the
files that are on your disk right now and writes a small committed manifest.
`build_signs.py` then reads the manifest, never the files. So the build is
deterministic everywhere, and the filesystem stays the source of truth for
"does this sign have a video yet".

Layout it expects, mirroring the R2 bucket exactly so `rclone sync media/
r2:<bucket>/` is the whole upload step:

    media/video/<slug>.mp4
    media/poster/<slug>.jpg      optional

The filename IS the link. `media/video/hello.mp4` attaches to the sign whose
slug is `hello`; there is no column to keep in sync and no way to point a video
at the wrong entry. A file whose name matches no slug is reported as an error
rather than ignored, because a typo would otherwise fail silently — the sign
just quietly keeps its "no video yet" placeholder.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "content" / "seed.csv"
MEDIA_DIR = REPO_ROOT / "media"
MANIFEST_PATH = REPO_ROOT / "content" / "media.json"

VIDEO_SUFFIX = ".mp4"
POSTER_SUFFIX = ".jpg"


def read_slugs() -> list[str]:
    """Slugs from seed.csv, not signs.json — signs.json depends on this manifest."""
    raw = SEED_PATH.read_text(encoding="utf-8-sig")
    body = "\n".join(
        line for line in raw.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return [row["slug"].strip() for row in csv.DictReader(io.StringIO(body))]


def short_hash(path: Path) -> str:
    """First 8 hex of the file's sha256.

    This ends up on the URL as ?v=<hash>. R2 sits behind a CDN with a long TTL,
    so without it re-recording a sign leaves every visitor — and your own hard
    refresh — watching the old take with no indication anything changed.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:8]


def scan(slugs: list[str]) -> tuple[dict, list[str]]:
    known = set(slugs)
    entries: dict[str, dict] = {}
    problems: list[str] = []

    video_dir = MEDIA_DIR / "video"
    poster_dir = MEDIA_DIR / "poster"

    for directory, suffix in ((video_dir, VIDEO_SUFFIX), (poster_dir, POSTER_SUFFIX)):
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() != suffix:
                problems.append(
                    f"{path.relative_to(REPO_ROOT)}: expected a {suffix} file here"
                )
                continue
            if path.stem not in known:
                problems.append(
                    f"{path.relative_to(REPO_ROOT)}: '{path.stem}' matches no slug in seed.csv"
                )

    # Iterate slugs, not files, so the manifest is ordered by the vocabulary
    # rather than by whatever order the filesystem hands back.
    for slug in slugs:
        video = video_dir / f"{slug}{VIDEO_SUFFIX}"
        if not video.is_file():
            continue

        poster = poster_dir / f"{slug}{POSTER_SUFFIX}"
        entries[slug] = {
            "video": f"video/{slug}{VIDEO_SUFFIX}",
            "poster": f"poster/{slug}{POSTER_SUFFIX}" if poster.is_file() else None,
            "hash": short_hash(video),
            "bytes": video.stat().st_size,
        }

    document = {
        "version": 1,
        "generatedFrom": "media/",
        "counts": {
            "video": len(entries),
            "poster": sum(1 for e in entries.values() if e["poster"]),
            "vocabulary": len(slugs),
        },
        "entries": entries,
    }
    return document, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = parser.parse_args()

    slugs = read_slugs()

    if not MEDIA_DIR.exists():
        # The normal state on CI and on a fresh clone. The committed manifest is
        # already correct; rewriting it from an absent folder would wipe it.
        print(f"no {MEDIA_DIR.relative_to(REPO_ROOT)}/ folder - leaving the manifest alone")
        return 0

    document, problems = scan(slugs)
    if problems:
        print(f"FAILED - {len(problems)} problem(s):\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    payload = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    current = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else None

    if args.check:
        if current != payload:
            print(
                "FAILED - content/media.json is out of date, run scripts/scan_media.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK - manifest matches media/ ({document['counts']['video']} videos)")
        return 0

    MANIFEST_PATH.write_text(payload, encoding="utf-8", newline="\n")

    counts = document["counts"]
    missing = counts["vocabulary"] - counts["video"]
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    print(f"  {counts['video']} of {counts['vocabulary']} signs have a video"
          f" ({counts['poster']} with a poster)")
    if missing:
        print(f"  {missing} still to record")
    print("\nnext:  python scripts/build_signs.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
