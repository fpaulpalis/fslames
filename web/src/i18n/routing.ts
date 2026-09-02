import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // "fil" is the ISO code for Filipino. "tl" would mean Tagalog specifically,
  // which is narrower than what this app targets.
  locales: ["en", "fil"],
  defaultLocale: "en",
});

export type Locale = (typeof routing.locales)[number];
