import { setRequestLocale } from "next-intl/server";

export default async function Page({ params }: PageProps<"/[locale]/learn">) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="text-3xl font-bold capitalize">learn</h1>
      <p className="mt-2 text-neutral-600">Coming in the next phase.</p>
    </div>
  );
}
