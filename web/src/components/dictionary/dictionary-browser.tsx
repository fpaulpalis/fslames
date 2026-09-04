"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import type { Locale } from "@/i18n/routing";
import {
  SECTIONS,
  SIGNS,
  indexKeys,
  signsForIndexKey,
  signsInGroup,
  sortByGloss,
} from "@/lib/signs";
import { SignList } from "./sign-list";

type Mode = "letter" | "section";

const ALL = "__all__";

/**
 * Section 3 — the browsable index.
 *
 * Two ways in, because the vocabulary answers two different questions. "By
 * letter" is the reference layout: you know the word and want to find it. "By
 * section" follows the taxonomy in seed.csv — Filipino Gestures, Basic Signs,
 * Socializing, Time and Date — which is how the vocabulary is actually taught.
 */
export function DictionaryBrowser() {
  const locale = useLocale() as Locale;
  const t = useTranslations("dictionary");

  const [mode, setMode] = useState<Mode>("letter");
  const [activeKey, setActiveKey] = useState<string>(ALL);

  const keys = indexKeys(locale);
  const visible =
    activeKey === ALL ? sortByGloss(SIGNS, locale) : signsForIndexKey(activeKey, locale);

  return (
    <div className="mx-auto max-w-3xl">
      <h2 className="text-center text-2xl font-bold">{t("title")}</h2>
      <p className="mx-auto mt-2 max-w-xl text-center text-neutral-600">
        {t("intro", { count: SIGNS.length })}
      </p>

      <div className="mt-6 flex justify-center" role="group" aria-label={t("browseLabel")}>
        <div className="inline-flex rounded-lg border border-neutral-300 bg-white p-1">
          {(["letter", "section"] as const).map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={mode === option}
              onClick={() => setMode(option)}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                mode === option
                  ? "bg-neutral-900 text-white"
                  : "text-neutral-600 hover:text-neutral-900"
              }`}
            >
              {t(option === "letter" ? "browseByLetter" : "browseBySection")}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-neutral-200 bg-white">
        {mode === "letter" ? (
          <>
            <div className="flex flex-wrap justify-center gap-1 border-b border-neutral-200 bg-neutral-100 p-3">
              <IndexButton
                label={t("browseAll")}
                active={activeKey === ALL}
                onClick={() => setActiveKey(ALL)}
              />
              {keys.map((key) => (
                <IndexButton
                  key={key}
                  label={key}
                  active={activeKey === key}
                  onClick={() => setActiveKey(key)}
                />
              ))}
            </div>

            <p className="border-b border-neutral-200 bg-neutral-50 px-4 py-2 text-sm font-medium text-neutral-600">
              {t("entries", { count: visible.length })}
            </p>

            {/* Capped height so the sections below stay reachable without a
                long scroll through 136 rows. */}
            <div className="max-h-[26rem] overflow-y-auto">
              <SignList signs={visible} locale={locale} emptyMessage={t("noEntries")} />
            </div>
          </>
        ) : (
          <SectionBrowser locale={locale} />
        )}
      </div>
    </div>
  );
}

function IndexButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-w-8 rounded px-2 py-1 text-sm font-bold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
        active
          ? "bg-blue-600 text-white"
          : "text-blue-700 hover:bg-white hover:text-blue-900"
      }`}
    >
      {label}
    </button>
  );
}

function SectionBrowser({ locale }: { locale: Locale }) {
  const t = useTranslations("dictionary");

  return (
    <div className="divide-y divide-neutral-200">
      {SECTIONS.map((section) => (
        <section key={section.slug}>
          <h3 className="bg-neutral-100 px-4 py-2 text-sm font-bold uppercase tracking-wide text-neutral-700">
            {t(`sections.${section.slug}`)}{" "}
            <span className="font-normal normal-case tracking-normal text-neutral-500">
              {t("entries", { count: section.count })}
            </span>
          </h3>

          {section.groups.length === 0 ? (
            <SignList
              signs={signsInGroup(section.slug, "")}
              locale={locale}
              emptyMessage={t("noEntries")}
            />
          ) : (
            section.groups.map((group) => (
              <div key={group.slug}>
                <h4 className="border-b border-neutral-200 bg-neutral-50 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  {t(`groups.${group.slug}`)} · {t("entries", { count: group.count })}
                </h4>
                <SignList
                  signs={signsInGroup(section.slug, group.slug)}
                  locale={locale}
                  emptyMessage={t("noEntries")}
                />
              </div>
            ))
          )}
        </section>
      ))}
    </div>
  );
}
