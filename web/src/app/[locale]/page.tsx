import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { SignSearch } from "@/components/dictionary/sign-search";

export default async function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HomeContent />;
}

function HomeContent() {
  const t = useTranslations("home");

  return (
    <div>
      <section className="bg-gradient-to-br from-amber-600 to-orange-700 px-4 py-20 text-center text-white">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("welcome")}</h1>
      </section>

      {/* The same component the dictionary uses, so the two search boxes cannot
          drift apart. Submitting here carries the query to /dictionary, where
          it seeds the identical box with the identical results. */}
      <section className="border-b border-neutral-200 bg-neutral-50 px-4 py-12">
        <Suspense fallback={<div className="mx-auto h-64 max-w-2xl" />}>
          <SignSearch />
        </Suspense>
      </section>

      <section className="px-4 py-12">
        <div className="mx-auto max-w-2xl text-center">
          <Link
            href="/ai"
            className="inline-block rounded-md bg-neutral-900 px-6 py-3 font-medium text-white transition hover:bg-neutral-700"
          >
            {t("practiceCta")}
          </Link>
        </div>
      </section>
    </div>
  );
}
