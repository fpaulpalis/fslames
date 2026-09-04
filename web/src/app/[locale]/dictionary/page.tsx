import { Suspense } from "react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";

import type { Locale } from "@/i18n/routing";
import { AlphabetGrid } from "@/components/dictionary/alphabet-grid";
import { DictionaryBrowser } from "@/components/dictionary/dictionary-browser";
import { SignSearch } from "@/components/dictionary/sign-search";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/dictionary">): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "dictionary" });
  return { title: t("title") };
}

/**
 * Three stacked sections, in this order: search, alphabet, then the index.
 * Search comes first because it is what someone who already knows the word
 * wants; browsing is for everyone else.
 *
 * Backgrounds alternate neutral-50 / white the same way the home page does, so
 * the section boundaries read the same across the site.
 */
export default async function DictionaryPage({
  params,
}: PageProps<"/[locale]/dictionary">) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "dictionary" });

  return (
    <div>
      {/* The page's own title is carried by the third section's heading, so
          this exists only to give assistive tech a single top-level label. */}
      <h1 className="sr-only">{t("title")}</h1>

      <section className="border-b border-neutral-200 bg-neutral-50 px-4 py-12">
        {/* SignSearch reads ?q= so the home page's search box lands here with
            its query. useSearchParams needs a Suspense boundary to keep the
            rest of the page statically rendered. */}
        <Suspense fallback={<div className="mx-auto h-64 max-w-2xl" />}>
          <SignSearch />
        </Suspense>
      </section>

      <section className="border-b border-neutral-200 px-4 py-12">
        <AlphabetGrid locale={locale as Locale} />
      </section>

      <section className="bg-neutral-50 px-4 py-12">
        <DictionaryBrowser />
      </section>
    </div>
  );
}
