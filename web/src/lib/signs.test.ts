/**
 * Dictionary data guards.
 *
 * scripts/build_signs.py already validates the CSV. These tests cover the seam
 * the Python side cannot see: that the copy Next.js imports is the same file,
 * that every taxonomy key has a label in both locales, and that search behaves
 * the way the roadmap says it must.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import en from "../../messages/en.json";
import fil from "../../messages/fil.json";
import {
  SECTIONS,
  SIGNS,
  fold,
  getSign,
  indexKeys,
  searchSigns,
  signsForIndexKey,
  signsInGroup,
} from "./signs";

const read = (relative: string) =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");

describe("generated data", () => {
  it("is a byte-identical copy of the canonical content/signs.json", () => {
    // Vercel builds with web/ as the project root, so the web app cannot import
    // ../../content. build_signs.py writes both; this catches the copy going
    // stale, which would otherwise ship a dictionary that disagrees with the
    // labels baked into the model.
    expect(read("../content/signs.json")).toEqual(read("../../../content/signs.json"));
  });

  it("has unique slugs", () => {
    const slugs = SIGNS.map((sign) => sign.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("has a URL-safe slug for every sign", () => {
    const bad = SIGNS.filter((sign) => !/^[a-z0-9-]+$/.test(sign.slug));
    expect(bad.map((sign) => sign.slug)).toEqual([]);
  });

  it("resolves every slug through getSign", () => {
    const missing = SIGNS.filter((sign) => getSign(sign.slug) === undefined);
    expect(missing).toEqual([]);
  });

  it("files every sign under an index key that the browser offers", () => {
    for (const locale of ["en", "fil"] as const) {
      const offered = new Set(indexKeys(locale));
      const orphans = SIGNS.filter((sign) => !offered.has(sign.index[locale]));
      expect(orphans.map((sign) => sign.slug), `orphans in ${locale}`).toEqual([]);
    }
  });

  it("reaches every sign by browsing letters", () => {
    for (const locale of ["en", "fil"] as const) {
      const reachable = indexKeys(locale).flatMap((key) => signsForIndexKey(key, locale));
      expect(reachable.length, `via letters in ${locale}`).toBe(SIGNS.length);
    }
  });

  it("reaches every sign by browsing sections", () => {
    const reachable = SECTIONS.flatMap((section) =>
      section.groups.length === 0
        ? signsInGroup(section.slug, "")
        : section.groups.flatMap((group) => signsInGroup(section.slug, group.slug)),
    );
    expect(reachable.length).toBe(SIGNS.length);
  });
});

describe("taxonomy labels", () => {
  // A section with no label renders its raw slug, which looks like a bug and
  // reads like one. Catch it here rather than in a screenshot.
  const sectionSlugs = [...new Set(SIGNS.map((sign) => sign.section))];
  const groupSlugs = [...new Set(SIGNS.map((sign) => sign.group))].filter(Boolean);

  for (const [name, messages] of [["en", en], ["fil", fil]] as const) {
    it(`covers every section and group in messages/${name}.json`, () => {
      const sections = messages.dictionary.sections as Record<string, string>;
      const groups = messages.dictionary.groups as Record<string, string>;

      expect(sectionSlugs.filter((slug) => !sections[slug])).toEqual([]);
      expect(groupSlugs.filter((slug) => !groups[slug])).toEqual([]);
    });
  }

  it("has no label for a section or group that no sign uses", () => {
    const unused = Object.keys(en.dictionary.groups).filter(
      (slug) => !groupSlugs.includes(slug),
    );
    expect(unused).toEqual([]);
  });
});

describe("fold", () => {
  it("ignores case, punctuation and diacritics", () => {
    expect(fold("Don't Know")).toBe("dontknow");
    expect(fold("Ano?")).toBe("ano");
    expect(fold("Ñ")).toBe("n");
    expect(fold("Good Morning")).toBe("goodmorning");
  });
});

describe("searchSigns", () => {
  it("finds the same entry from either language", () => {
    // The Phase 2 acceptance criterion, straight from docs/roadmap.md.
    expect(searchSigns("hello", "en")[0].slug).toBe("hello");
    expect(searchSigns("kumusta", "en")[0].slug).toBe("hello");
    expect(searchSigns("kumusta", "fil")[0].slug).toBe("hello");
  });

  it("ranks an exact gloss above a partial one", () => {
    const results = searchSigns("see you", "en").map((sign) => sign.slug);
    expect(results[0]).toBe("see-you");
    expect(results).toContain("see-you-later");
  });

  it("matches through aliases", () => {
    expect(searchSigns("goodbye", "en")[0].slug).toBe("bye");
    expect(searchSigns("dalawa", "fil")[0].slug).toBe("number-2");
  });

  it("ranks a gloss match above an alias match", () => {
    // "isa" is an alias of the numeral 1, but it also sits inside the gloss
    // "No (Disagree)". The word someone can actually see wins.
    const results = searchSigns("isa", "fil").map((sign) => sign.slug);
    expect(results.indexOf("no")).toBeLessThan(results.indexOf("number-1"));
  });

  it("tolerates punctuation the reader will not type", () => {
    expect(searchSigns("dont know", "en")[0].slug).toBe("dont-know");
    expect(searchSigns("whats", "en")).toEqual([]);
    expect(searchSigns("what", "en").map((s) => s.slug)).toContain("what");
  });

  it("returns nothing for an empty query rather than everything", () => {
    expect(searchSigns("", "en")).toEqual([]);
    expect(searchSigns("   ", "en")).toEqual([]);
  });
});
