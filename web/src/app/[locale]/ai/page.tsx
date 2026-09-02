import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";

export default async function AiPage({ params }: PageProps<"/[locale]/ai">) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <AiContent />;
}

function AiContent() {
  const t = useTranslations("ai");

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <span className="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-800">
        {t("badge")}
      </span>

      <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">{t("title")}</h1>
      <p className="mt-4 max-w-2xl text-neutral-600">{t("intro")}</p>

      <div className="mt-10 grid gap-6 sm:grid-cols-2">
        <article className="rounded-xl border border-neutral-200 bg-emerald-50/40 p-6">
          <h2 className="text-xl font-bold">{t("wordTitle")}</h2>
          <p className="mt-2 text-sm text-neutral-600">{t("wordBody")}</p>
          <button
            type="button"
            disabled
            className="mt-6 w-full cursor-not-allowed rounded-md bg-emerald-700/50 px-4 py-2.5 font-medium text-white"
          >
            {t("wordCta")}
          </button>
        </article>

        <article className="rounded-xl border border-neutral-200 p-6">
          <h2 className="text-xl font-bold">{t("letterTitle")}</h2>
          <p className="mt-2 text-sm text-neutral-600">{t("letterBody")}</p>
          <button
            type="button"
            disabled
            className="mt-6 w-full cursor-not-allowed rounded-md bg-neutral-900/50 px-4 py-2.5 font-medium text-white"
          >
            {t("letterCta")}
          </button>
        </article>
      </div>
    </div>
  );
}
