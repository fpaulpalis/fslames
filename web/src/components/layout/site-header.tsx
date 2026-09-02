import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { LocaleToggle } from "./locale-toggle";

export function SiteHeader() {
  const t = useTranslations("site");

  return (
    <header className="bg-neutral-900 text-white">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link
          href="/"
          className="text-lg font-bold tracking-tight focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
        >
          {t("name")}
        </Link>
        <LocaleToggle />
      </div>
    </header>
  );
}
