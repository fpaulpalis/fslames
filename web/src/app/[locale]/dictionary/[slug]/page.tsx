import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";
import { SIGNS, getSign, type Sign } from "@/lib/signs";

// One page per sign, prerendered at build time. The parent [locale] segment
// already generates the locales, so this only supplies the slugs.
export function generateStaticParams() {
  return SIGNS.map((sign) => ({ slug: sign.slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/dictionary/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const sign = getSign(slug);
  if (!sign) return {};
  return { title: sign.gloss[locale as Locale] };
}

export default async function SignPage({
  params,
}: PageProps<"/[locale]/dictionary/[slug]">) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const sign = getSign(slug);
  if (!sign) notFound();

  const t = await getTranslations({ locale, namespace: "dictionary" });
  const current = locale as Locale;
  const other = routing.locales.find((l) => l !== current) ?? routing.defaultLocale;

  const aliases = sign.aliases[current];

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link
        href="/dictionary"
        className="text-sm font-medium text-blue-700 underline underline-offset-2 hover:text-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        ← {t("backToDictionary")}
      </Link>

      <p className="mt-6 text-sm font-medium uppercase tracking-wide text-neutral-500">
        {t(`sections.${sign.section}`)}
        {sign.group && <> · {t(`groups.${sign.group}`)}</>}
      </p>

      <h1 className="mt-1 text-4xl font-bold tracking-tight">{sign.gloss[current]}</h1>

      <p className="mt-2 text-lg text-neutral-600">
        <span className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          {t("glossOther")}:
        </span>{" "}
        {sign.gloss[other]}
      </p>

      {aliases.length > 0 && (
        <p className="mt-1 text-sm text-neutral-500">
          {t("alsoCalled")}: {aliases.join(", ")}
        </p>
      )}

      <dl className="mt-8 grid gap-4 sm:grid-cols-2">
        <Fact label={t("handsLabel")} value={t(`hands.${sign.hands}`)} />
        <Fact
          label={t("motionLabel")}
          value={sign.motion ? t(`motion.${sign.motion}`) : t("motion.unknown")}
          muted={sign.motion === null}
        />
      </dl>

      <MediaPlaceholder sign={sign} pending={t("mediaPending")} help={t("mediaPendingHelp")} />

      <section className="mt-8">
        <h2 className="text-xl font-bold">{t("formationTitle")}</h2>
        {/* params is null on every entry by design — see content/README.md.
            Saying so is the point: a learner should not read an empty panel as
            "this sign has no particular handshape". */}
        <p className="mt-2 rounded-lg border border-dashed border-neutral-300 bg-neutral-50 p-4 text-sm text-neutral-600">
          {sign.params ? JSON.stringify(sign.params) : t("formationPending")}
        </p>
      </section>
    </div>
  );
}

function Fact({
  label,
  value,
  muted = false,
}: {
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <dt className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </dt>
      <dd className={`mt-1 font-medium ${muted ? "text-neutral-400" : ""}`}>{value}</dd>
    </div>
  );
}

function MediaPlaceholder({
  sign,
  pending,
  help,
}: {
  sign: Sign;
  pending: string;
  help: string;
}) {
  if (sign.media.video) {
    return (
      <video
        className="mt-8 w-full rounded-xl border border-neutral-200"
        controls
        playsInline
        poster={sign.media.poster ?? undefined}
        src={sign.media.video}
      />
    );
  }

  return (
    <div className="mt-8 flex aspect-video flex-col items-center justify-center rounded-xl border border-dashed border-neutral-300 bg-neutral-50 p-6 text-center">
      <p className="font-medium text-neutral-700">{pending}</p>
      <p className="mt-1 max-w-sm text-sm text-neutral-500">{help}</p>
    </div>
  );
}
