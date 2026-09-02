/**
 * Message-file guards.
 *
 * Catches the failure mode where the Filipino toggle silently does nothing on
 * part of the site because a key was added to en.json and forgotten in
 * fil.json. Eyeballing screenshots does not scale to a 40-page site.
 */

import { describe, expect, it } from "vitest";

import en from "../../messages/en.json";
import fil from "../../messages/fil.json";

type Messages = Record<string, unknown>;

function flatten(obj: Messages, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, flatten(value as Messages, path));
    } else {
      out[path] = String(value);
    }
  }
  return out;
}

const flatEn = flatten(en as Messages);
const flatFil = flatten(fil as Messages);

/**
 * Keys that legitimately read the same in both languages: proper nouns,
 * borrowed words, and the brand name. Anything NOT listed here that is
 * identical in both files is almost certainly an untranslated string.
 */
const ALLOWED_IDENTICAL = new Set([
  "site.name",
  "nav.home",
  "nav.ai",
  "ai.title",
]);

describe("translation files", () => {
  it("have exactly the same keys", () => {
    const missingInFil = Object.keys(flatEn).filter((k) => !(k in flatFil));
    const missingInEn = Object.keys(flatFil).filter((k) => !(k in flatEn));

    expect(missingInFil, `missing from messages/fil.json: ${missingInFil.join(", ")}`).toEqual([]);
    expect(missingInEn, `missing from messages/en.json: ${missingInEn.join(", ")}`).toEqual([]);
  });

  it("have no empty values", () => {
    for (const [file, flat] of [["en", flatEn], ["fil", flatFil]] as const) {
      const empty = Object.entries(flat)
        .filter(([, v]) => v.trim() === "")
        .map(([k]) => k);
      expect(empty, `empty values in messages/${file}.json`).toEqual([]);
    }
  });

  it("have no untranslated Filipino strings", () => {
    const suspicious = Object.keys(flatEn).filter(
      (key) =>
        !ALLOWED_IDENTICAL.has(key) &&
        key in flatFil &&
        flatEn[key].trim().toLowerCase() === flatFil[key].trim().toLowerCase(),
    );

    expect(
      suspicious,
      `identical in both locales - probably untranslated: ${suspicious.join(", ")}.\n` +
        "If a value is genuinely the same in Filipino, add its key to ALLOWED_IDENTICAL.",
    ).toEqual([]);
  });
});
