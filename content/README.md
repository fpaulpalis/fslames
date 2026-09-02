# Content — the canonical sign dataset

`signs.json` is the single source of truth for the dictionary. It lives at the repo
root rather than inside `web/` because **two** consumers need it:

- `web/` renders every dictionary page from it
- `ml/` uses it to build `word-v1.labels.json`, so a model prediction can be turned
  straight back into a dictionary entry with a Filipino gloss and a video

## Schema

| Field | Type | Notes |
|---|---|---|
| `slug` | string | URL segment, kebab-case, unique. `/en/dictionary/sign/<slug>` |
| `gloss.en` / `gloss.fil` | string | The word label in each language |
| `aliases.en` / `aliases.fil` | string[] | Extra search terms; may be empty |
| `letter` | string | Bucket for the A–Z browse index |
| `category` | string | Loose grouping (`greetings`, `family`, `colors`, …) |
| `media.video` | string \| null | Path inside the R2 bucket. `null` until recorded |
| `media.poster` | string \| null | Still frame for the video player |
| `params` | object \| null | Handshape / location / movement breakdown |
| `notes.en` / `notes.fil` | string | Short description shown on the entry page |
| `modelLabel` | string \| null | Class name in the classifier. `null` if not modelled |
| `inModel` | boolean | Whether the AI can currently check this sign |
| `contentStatus` | `"draft"` \| `"verified"` | See below |

## ⚠️ `contentStatus` — read this before shipping

Seeded entries are marked **`"draft"`**. A draft entry has a trustworthy English word
and Filipino translation, but its `params` (handshape, location, movement) are `null`
and it has no video.

**Those articulatory details were deliberately left empty rather than guessed.** This is
a tool people will use to learn a language; a confidently wrong description of how to
form a sign is worse than no description at all. Fill them in from your own recordings
or a source you trust, then flip `contentStatus` to `"verified"`.

Suggested rule: the dictionary can display draft entries, but the UI should only show
the handshape/location/movement breakdown for `verified` ones, and only `verified`
entries should be eligible for `inModel: true`.

## Workflow

Maintain the data in a spreadsheet, export CSV, and regenerate:

```bash
npm run content:build     # CSV -> signs.json, validated with Zod
npm run content:check     # validate without writing
```

Validation enforces: unique slugs, non-empty glosses in both languages, `letter`
matching the first character of `gloss.en`, and `inModel` entries having a `modelLabel`.

## Seed vocabulary

The ~36 seeded words were chosen to overlap with the **WLASL-100** gloss list, so the
first trained model and the first dictionary entries cover the same words. Words with
no clean WLASL counterpart are still included — they just start with `inModel: false`.
