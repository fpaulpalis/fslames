"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";

type Tab = { href: "/" | "/dictionary" | "/ai" | "/learn"; key: string; icon: React.ReactNode };

const icon = (d: string) => (
  <svg
    aria-hidden="true"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="h-6 w-6"
    dangerouslySetInnerHTML={{ __html: d }}
  />
);

const TABS: Tab[] = [
  { href: "/", key: "home", icon: icon('<path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>') },
  { href: "/dictionary", key: "dictionary", icon: icon('<path d="M2 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H2z"/><path d="M22 4h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8z"/>') },
  { href: "/ai", key: "ai", icon: icon('<rect x="4" y="8" width="16" height="11" rx="2"/><path d="M12 8V5"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/>') },
  { href: "/learn", key: "learn", icon: icon('<path d="m2 8 10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/>') },
];

export function TabNav() {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="border-b border-neutral-200 bg-neutral-50">
      <ul className="mx-auto flex max-w-3xl items-stretch justify-between px-2">
        {TABS.map((tab) => {
          const active =
            tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);

          return (
            <li key={tab.key} className="flex-1">
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center gap-1 border-b-2 px-2 py-3 text-sm transition ${
                  active
                    ? "border-neutral-900 font-semibold text-neutral-900"
                    : "border-transparent text-neutral-600 hover:text-neutral-900"
                }`}
              >
                {tab.icon}
                <span>{t(tab.key)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
