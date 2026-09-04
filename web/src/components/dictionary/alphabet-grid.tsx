import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { signsInGroup } from "@/lib/signs";

/**
 * Section 2 — the manual alphabet, in Filipino order (… M, N, Ñ, Ng, O …).
 *
 * The reference layout shows a photo per letter. There are no photos yet and
 * `media.video` is null on every entry, so each tile shows the letter itself
 * plus the two facts the dataset does record: one hand or two, and whether the
 * letter has movement. J, Ñ and Z are the dynamic ones — exactly the letters a
 * single-frame classifier will not be able to tell apart, which is worth having
 * visible before Phase 3 starts.
 */
export function AlphabetGrid({ locale }: { locale: Locale }) {
  const t = useTranslations("dictionary");
  const letters = signsInGroup("basic-signs", "alphabet");

  return (
    <div className="mx-auto max-w-4xl">
      <h2 className="text-center text-2xl font-bold">{t("alphabetTitle")}</h2>
      <p className="mx-auto mt-2 max-w-xl text-center text-neutral-600">
        {t("alphabetHelp")}
      </p>

      <ul className="mt-8 grid grid-cols-4 gap-3 sm:grid-cols-6 md:grid-cols-7">
        {letters.map((sign) => (
          <li key={sign.slug}>
            <Link
              href={`/dictionary/${sign.slug}`}
              className="flex aspect-square flex-col items-center justify-center gap-1.5 rounded-lg border border-neutral-200 bg-white transition hover:border-neutral-400 hover:bg-neutral-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              <span className="text-2xl font-bold">{sign.gloss[locale]}</span>
              {/* Only the exceptions earn a chip: 27 of the 28 letters are
                  one-handed, and only J, Ñ and Z carry movement. */}
              <span className="flex flex-wrap justify-center gap-1">
                {sign.hands === "both" && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-900">
                    {t("handsShort.both")}
                  </span>
                )}
                {sign.motion === "dynamic" && (
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-800">
                    {t("motion.dynamic")}
                  </span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
