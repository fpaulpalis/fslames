import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import type { Sign } from "@/lib/signs";

/**
 * A row per sign, in the order it is handed in. Callers decide the order —
 * alphabetical for the A–Z index, teaching order for a group.
 *
 * Deliberately a plain component with no state so both the server-rendered
 * section browse and the client-side search can render identical rows.
 */
export function SignList({
  signs,
  locale,
  emptyMessage,
}: {
  signs: Sign[];
  locale: Locale;
  emptyMessage: string;
}) {
  if (signs.length === 0) {
    return <p className="px-4 py-6 text-sm text-neutral-500">{emptyMessage}</p>;
  }

  return (
    <ul className="divide-y divide-neutral-200">
      {signs.map((sign) => (
        <li key={sign.slug}>
          <Link
            href={`/dictionary/${sign.slug}`}
            className="flex items-center justify-between gap-3 px-4 py-3 transition hover:bg-neutral-50 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600"
          >
            <span className="font-medium text-blue-700 underline underline-offset-2">
              {sign.gloss[locale]}
            </span>
            {/* Only two-handed signs are chipped. Marking all 136 rows would put
                "Left or right hand" on 100 of them, which reads as decoration
                and hides the 36 that actually need both hands. */}
            {sign.hands === "both" && <HandsBadge hands={sign.hands} />}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/**
 * Whether the sign needs one hand or two. Shown on every row because it is the
 * one articulatory detail the vocabulary list actually records — handshape,
 * location and movement are still null. See content/README.md.
 */
export function HandsBadge({ hands }: { hands: Sign["hands"] }) {
  const t = useTranslations("dictionary");

  return (
    <span
      className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
        hands === "both"
          ? "bg-amber-100 text-amber-900"
          : "bg-neutral-100 text-neutral-700"
      }`}
    >
      {t(`hands.${hands}`)}
    </span>
  );
}
