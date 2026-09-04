/**
 * Read access to the dictionary.
 *
 * The data is generated — edit `content/seed.csv` at the repo root and run
 * `python scripts/build_signs.py`, which writes both `content/signs.json` and
 * the copy imported here. Never hand-edit the JSON; the next build overwrites it.
 *
 * Everything below is a pure function over that import, so the dictionary page
 * stays a static server component and the search box can call the same helpers
 * on the client without a round trip.
 */

import document from "../content/signs.json";
import type { Locale } from "@/i18n/routing";

// --------------------------------------------------------------------------
// Types — mirror the shape scripts/build_signs.py emits
// --------------------------------------------------------------------------

/** "left-right" is one-handed and works with either hand. */
export type Hands = "left-right" | "both";

/** null means nobody has confirmed it yet, not that the sign is static. */
export type Motion = "static" | "dynamic" | null;

export interface Sign {
  slug: string;
  /** Position in seed.csv — teaching order, not alphabetical. */
  order: number;
  gloss: Record<Locale, string>;
  aliases: Record<Locale, string[]>;
  /** A–Z browse bucket, per locale. "Hello" is under H, "Kumusta" under K. */
  index: Record<Locale, string>;
  section: string;
  /** "" for sections that have no subsections. */
  group: string;
  hands: Hands;
  motion: Motion;
  media: { video: string | null; poster: string | null };
  params: Record<string, unknown> | null;
  notes: Record<Locale, string>;
  modelLabel: string | null;
  inModel: boolean;
  contentStatus: "draft" | "verified";
}

export interface SectionSummary {
  slug: string;
  groups: { slug: string; count: number }[];
  count: number;
}

export const SIGNS = document.signs as Sign[];
export const SECTIONS = document.sections as SectionSummary[];
export const SIGN_COUNT = SIGNS.length;

// --------------------------------------------------------------------------
// Lookup
// --------------------------------------------------------------------------

const BY_SLUG = new Map(SIGNS.map((sign) => [sign.slug, sign]));

export function getSign(slug: string): Sign | undefined {
  return BY_SLUG.get(slug);
}

/** Every A–Z (and 0–9) bucket that has at least one entry, in display order. */
export function indexKeys(locale: Locale): string[] {
  return document.index[locale];
}

export function signsForIndexKey(key: string, locale: Locale): Sign[] {
  return sortByGloss(
    SIGNS.filter((sign) => sign.index[locale] === key),
    locale,
  );
}

/**
 * Teaching order, not alphabetical — January before April, A before Ñ. Change
 * the order by moving rows in seed.csv.
 */
export function signsInGroup(section: string, group: string): Sign[] {
  return SIGNS.filter(
    (sign) => sign.section === section && sign.group === group,
  ).sort((a, b) => a.order - b.order);
}

/**
 * Alphabetical by the gloss the reader can actually see. Sorting the Filipino
 * list by the English gloss would put "Kumusta" between "Good Noon" and "Hi".
 */
export function sortByGloss(signs: Sign[], locale: Locale): Sign[] {
  return [...signs].sort((a, b) =>
    a.gloss[locale].localeCompare(b.gloss[locale], locale, { numeric: true }),
  );
}

// --------------------------------------------------------------------------
// Search
// --------------------------------------------------------------------------

/**
 * Reduce a string to bare letters and digits so near-misses still match:
 * "dont know" finds "Don't Know", "ano" finds "Ano?", "n" finds "Ñ".
 */
export function fold(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]/gu, "");
}

// Precomputed so typing in the search box does not re-normalize 136 entries per
// keystroke. Both locales are always searched: a learner who has the site in
// Filipino still knows the English word half the time, and vice versa.
const HAYSTACK: { sign: Sign; gloss: string[]; alias: string[] }[] = SIGNS.map(
  (sign) => ({
    sign,
    gloss: [fold(sign.gloss.en), fold(sign.gloss.fil)],
    alias: [...sign.aliases.en, ...sign.aliases.fil].map(fold),
  }),
);

/**
 * Ranked: exact gloss, then gloss prefix, then anywhere in a gloss, then
 * aliases. Ties break alphabetically in the reader's locale.
 */
export function searchSigns(query: string, locale: Locale): Sign[] {
  const needle = fold(query);
  if (!needle) return [];

  const scored: { sign: Sign; score: number }[] = [];

  for (const entry of HAYSTACK) {
    let score = Infinity;

    for (const gloss of entry.gloss) {
      if (gloss === needle) score = Math.min(score, 0);
      else if (gloss.startsWith(needle)) score = Math.min(score, 1);
      else if (gloss.includes(needle)) score = Math.min(score, 2);
    }

    if (score === Infinity) {
      for (const alias of entry.alias) {
        if (alias.startsWith(needle)) score = Math.min(score, 3);
        else if (alias.includes(needle)) score = Math.min(score, 4);
      }
    }

    if (score !== Infinity) scored.push({ sign: entry.sign, score });
  }

  return scored
    .sort(
      (a, b) =>
        a.score - b.score ||
        a.sign.gloss[locale].localeCompare(b.sign.gloss[locale], locale, {
          numeric: true,
        }),
    )
    .map((entry) => entry.sign);
}
