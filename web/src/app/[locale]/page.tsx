import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";

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

      <section className="border-b border-neutral-200 bg-neutral-50 px-4 py-12">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-2xl font-bold">{t("searchTitle")}</h2>
          <p className="mt-2 text-neutral-600">{t("searchHelp")}</p>

          <form action="/dictionary" className="mt-6 flex gap-2">
            <label htmlFor="q" className="sr-only">
              {t("searchTitle")}
            </label>
            <input
              id="q"
              name="q"
              type="search"
              placeholder={t("searchPlaceholder")}
              className="flex-1 rounded-md border border-neutral-300 px-4 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            />
            <button
              type="submit"
              className="rounded-md bg-blue-600 px-5 py-2 font-medium text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              {t("searchButton")}
            </button>
          </form>
        </div>
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
