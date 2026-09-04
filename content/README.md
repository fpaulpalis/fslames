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

The duplicate exists because Vercel builds with `web/` as the project root, so an import
reaching up to `../../content` resolves locally and then fails in CI. `--check`,
`scripts/verify.py` and `web/src/lib/signs.test.ts` all assert the two files match, so a
stale copy fails the build instead of shipping.

### Per-locale index

Each entry carries `index.en` and `index.fil`, because the Filipino browse cannot be
derived from the English one — "Hello" belongs under H and "Kumusta" under K. Filing the
Filipino entry under H would make browsing in Filipino nonsense.

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
