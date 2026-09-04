"use client";

import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";

import type { Locale } from "@/i18n/routing";
import { searchSigns } from "@/lib/signs";
import { SignList } from "./sign-list";

/**
 * Section 1 — the search box at the top of the dictionary.
 *
 * Filtering happens in the browser against the imported dataset: 136 entries is
 * far too small to justify a round trip per keystroke, and results appear as
 * the reader types rather than after a submit.
 *
 * It is still a real <form> that submits to /dictionary?q=…, so the home page's
 * search box lands here with its query intact and the page keeps working
 * before hydration.
 */
export function SignSearch() {
  const locale = useLocale() as Locale;
  const t = useTranslations("dictionary");
  const searchParams = useSearchParams();

  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const results = useMemo(() => searchSigns(query, locale), [query, locale]);

  const trimmed = query.trim();

  return (
    <div className="mx-auto max-w-2xl">
      <h2 className="text-center text-2xl font-bold">{t("searchTitle")}</h2>
      <p className="mt-2 text-center text-neutral-600">{t("searchHelp")}</p>

      <form
        // Only reached before hydration, so it needs the locale prefix that
        // <Link> would normally add.
        action={`/${locale}/dictionary`}
        role="search"
        // Wraps because a third control (Clear) appears once there is a query,
        // and input + Search + Clear do not fit on one line at 375px.
        className="mt-6 flex flex-wrap gap-2"
        onSubmit={(event) => {
          // Already filtered live; submitting would only reload the same page.
          event.preventDefault();
        }}
      >
        <label htmlFor="q" className="sr-only">
          {t("searchLabel")}
        </label>
        <input
          id="q"
          name="q"
          type="search"
          value={query}
          autoComplete="off"
          placeholder={t("searchPlaceholder")}
          onChange={(event) => setQuery(event.target.value)}
          className="min-w-0 flex-1 basis-full rounded-md border border-neutral-300 bg-white px-4 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:basis-auto"
        />
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-5 py-2 font-medium text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          {t("searchButton")}
        </button>
        {trimmed !== "" && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="rounded-md border border-neutral-300 bg-white px-4 py-2 font-medium text-neutral-700 transition hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            {t("searchClear")}
          </button>
        )}
      </form>

      <p className="mt-3 text-center text-sm text-neutral-500">{t("searchBilingual")}</p>

      {/* aria-live so a screen reader hears the count change while typing. */}
      <div aria-live="polite" className="mt-6">
        {trimmed === "" ? null : results.length === 0 ? (
          <div className="rounded-xl border border-neutral-200 bg-white px-4 py-6 text-center">
            <p className="font-medium">{t("searchEmpty")}</p>
            <p className="mt-1 text-sm text-neutral-500">{t("searchEmptyHelp")}</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
            <p className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-sm font-medium text-neutral-600">
              {t("entries", { count: results.length })}
            </p>
            <div className="max-h-96 overflow-y-auto">
              <SignList signs={results} locale={locale} emptyMessage={t("searchEmpty")} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
