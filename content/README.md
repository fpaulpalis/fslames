# Content — the canonical sign dataset

`seed.csv` is the source of truth. `signs.json` is generated from it and **must not be
hand-edited** — the next build overwrites your changes.

```bash
python scripts/build_signs.py            # CSV -> JSON, validated
python scripts/build_signs.py --check    # validate only, write nothing (for CI)
```

## Adding, removing or renaming a word

**One file: `content/seed.csv`.** Add a row, delete a row, edit a cell, then run the
build. Everything downstream follows — the A–Z index, the search box, the section
browse, the per-sign page at `/en/dictionary/<slug>`, and the labels baked into the
model at export time.

```csv
slug,gloss_en,gloss_fil,aliases_en,aliases_fil,section,group,hands,motion,same_in_fil
water,Water,Tubig,,inumin,basic-signs,general,left-right,,
```

Two things that are **not** just a CSV edit:

| What you want | Also edit |
|---|---|
| A new **section** or **group** | `TAXONOMY` in `scripts/build_signs.py`, then add a label to `dictionary.sections` / `dictionary.groups` in **both** `web/messages/en.json` and `web/messages/fil.json` |
| A **reference video** | nothing here — drop the file in `media/video/<slug>.mp4` and run `scripts/scan_media.py`, see [Reference recordings](#reference-recordings) |
| A new **field** on every sign | `build_entry` and `validate` in the build script, the `Sign` type in `web/src/lib/signs.ts`, and wherever it should render |

⚠️ **`slug` is a permalink.** Renaming one breaks every link already shared and every
bookmark. Prefer adding an alias over renaming a slug.

## Columns

| Column | Notes |
|---|---|
| `slug` | URL segment. Lowercase ASCII, digits, hyphens. Unique. |
| `gloss_en` / `gloss_fil` | The label shown in each locale. Both required. |
| `aliases_en` / `aliases_fil` | Extra search terms, `|`-separated. Searched in both locales regardless of which one the reader is using. |
| `section` | `filipino-gestures`, `basic-signs`, `socializing`, `time-and-date` |
| `group` | Subsection — see `TAXONOMY`. Empty for `filipino-gestures`. |
| `hands` | `left-right` (one-handed, either hand) or `both` |
| `motion` | `static`, `dynamic`, or empty when nobody has confirmed it |
| `same_in_fil` | `yes` only when the word is genuinely identical in both languages |

Row order in the CSV is the **teaching order**: it is what the section browse uses, which
is why the months read January → December rather than alphabetically. The A–Z index sorts
alphabetically on its own, so you never have to keep the file sorted.

## Generated output

The build writes the same bytes to two paths:

| Path | Read by |
|---|---|
| `content/signs.json` | `ml/src/export_onnx.py`, to turn a prediction into a dictionary entry |
| `web/src/content/signs.json` | Next.js, which imports it directly |

`content/media.json` is generated too, but by a different script and on a different
schedule — see [Reference recordings](#reference-recordings). It is an *input* to this
build, not an output of it.

The duplicate exists because Vercel builds with `web/` as the project root, so an import
reaching up to `../../content` resolves locally and then fails in CI. `--check`,
`scripts/verify.py` and `web/src/lib/signs.test.ts` all assert the two files match, so a
stale copy fails the build instead of shipping.

### Per-locale index

Each entry carries `index.en` and `index.fil`, because the Filipino browse cannot be
derived from the English one — "Hello" belongs under H and "Kumusta" under K. Filing the
Filipino entry under H would make browsing in Filipino nonsense.

## Reference recordings

Videos never enter git — `*.mp4` is gitignored and 136 clips would sit in history
forever. They live in Cloudflare R2. `content/media.json` is the small committed record
of which signs have one, so `signs.json` builds to identical bytes on your machine and on
CI, where `media/` does not exist.

### The filename is the link

```
media/video/<slug>.mp4       media/video/hello.mp4  ->  the sign with slug "hello"
media/poster/<slug>.jpg      optional still frame
```

There is no column to keep in sync and no way to point a recording at the wrong entry.
A file whose name matches no slug is a **build error**, not a warning — a typo would
otherwise fail silently, leaving that sign quietly stuck on its placeholder.

The layout mirrors the bucket exactly, so uploading is one command with no path
rewriting.

### Adding recordings

```bash
# 1. drop the files into media/video/ (and media/poster/ if you have stills)
python scripts/scan_media.py      # -> content/media.json
python scripts/build_signs.py     # -> signs.json, now with media paths

# 2. upload. The bucket mirrors media/ one-for-one.
rclone sync media/ r2:<bucket>/

# 3. point the app at the bucket (web/.env.local)
NEXT_PUBLIC_MEDIA_BASE_URL=https://media.example.com
```

To preview without R2 at all, copy `media/` to `web/public/media/` and leave
`NEXT_PUBLIC_MEDIA_BASE_URL` unset — it falls back to `/media`.

No posters? A `<video>` shows its own first frame once metadata loads, so posters are
optional. To batch-generate them from the recordings:

```bash
for f in media/video/*.mp4; do
  ffmpeg -i "$f" -vf "select=eq(n\,0)" -q:v 3 "media/poster/$(basename "${f%.mp4}").jpg"
done
```

### Re-recording a sign

Replace the file, re-run both scripts, re-upload. `scan_media.py` hashes each video and
`signs.json` carries the first 8 hex as `media.hash`, which the app appends as `?v=`.
Without it R2's CDN would keep serving the old take to everyone who had already seen it —
including you, past a hard refresh — with nothing to suggest the file had changed.

### What to record

The dictionary assumes these; changing them later means re-recording, not re-encoding.

| | |
|---|---|
| Aspect | **16:9 landscape**. The player and the placeholder both reserve `aspect-video`; a portrait clip letterboxes into black bars. |
| Framing | Head to waist, centred, with **both hands in frame even for one-handed signs** — the resting hand is part of the sign. |
| Background | Plain and unpatterned, contrasting with the signer's skin tone and clothing. |
| Duration | 2–4 seconds. The sign only, no lead-in and no "and now the sign for…". |
| Start/end | Begin and end in the same neutral rest position. The player **loops**, so a clip that ends mid-movement jumps visibly on every repeat. |
| Codec | H.264 in MP4, `-movflags +faststart` so playback begins before the file finishes downloading. |
| Resolution | 720p is plenty. 136 clips at ~500 KB is ~70 MB total; 1080p triples that for detail nobody needs. |
| Audio | **Strip it.** There is no audio content, and a silent track is bytes that buy nothing. |

A reasonable encode of an existing take:

```bash
ffmpeg -i raw.mov -an -vf "scale=-2:720" -c:v libx264 -crf 23   -movflags +faststart media/video/hello.mp4
```

### Two things worth doing in the same session

`params` (handshape, location, movement) and the `motion` column are blank for most signs
because they were never confirmed. You are the only person who can fill them in, and the
recording session is when you will know the answers. See below.

## ⚠️ `contentStatus` — read this before shipping

Every entry is **`"draft"`**. A draft has a word and a translation, but its `params`
(handshape, location, movement) are `null` and it has no video.

**Those articulatory details were deliberately left empty rather than guessed.** This is a
tool people will use to learn a language; a confidently wrong description of how to form a
sign is worse than no description at all. `motion` is left empty for the same reason
wherever it was not stated — a sign wrongly labelled static teaches a learner to drop the
movement that distinguishes it from another sign.

Fill them in from your own recordings or a source you trust, then flip `contentStatus` to
`"verified"`. The UI shows draft entries but says plainly that the formation is not
recorded, and only `verified` entries should ever be `inModel: true`.

### The Filipino glosses are drafts too

They were written to get the bilingual UI working end to end and have **not** been
reviewed by a Deaf FSL user. A few are known judgement calls worth checking first:

- **Good Evening** and **Good Night** are both *Magandang Gabi*; the farewell is
  currently disambiguated as *Magandang Gabi (Paalam)*.
- **Sunday** and **Week** are both *Linggo*; Week is currently *Linggo (Sanlinggo)*.
- The Filipino gestures (**Ano?**, **Ewan**, **Sana**) are flagged `same_in_fil` because
  they are Filipino words already, so the English column repeats them.

## Vocabulary

136 signs across four sections:

| Section | Signs |
|---|---|
| Filipino Gestures | 7 |
| Basic Signs — alphabet 28, general 4, numbers 10, colors 13 | 55 |
| Socializing — greetings 9, introducing 5, leave-taking 6, survival 14, WH 5 | 39 |
| Time and Date — days 7, months 12, time 12, referent 4 | 35 |

The alphabet is the Filipino manual alphabet: 26 Latin letters plus **Ñ** and **Ng**, in
Filipino order (… M, N, Ñ, Ng, O …). **J, Ñ and Z are dynamic** — they carry movement and
cannot be classified from a single frame, which matters for the Phase 3 letter predictor.
