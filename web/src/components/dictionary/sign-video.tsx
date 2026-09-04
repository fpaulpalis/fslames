"use client";

import { useEffect, useRef } from "react";

/**
 * The reference recording on a sign's entry page.
 *
 * Loops, because a sign lasts about two seconds and nobody catches the movement
 * on one viewing. Muted, because there is no audio track to begin with — and
 * because a muted video is the only kind a browser will let script start.
 *
 * Playback is started from an effect rather than the autoPlay attribute so it
 * can be skipped under prefers-reduced-motion. The video is the content of this
 * page, so it is never hidden from those readers — it just waits for them to
 * press play. If the browser blocks the call anyway, the poster and the controls
 * are already there, so the fallback is the same either way.
 */
export function SignVideo({
  src,
  poster,
  label,
}: {
  src: string;
  poster: string | null;
  label: string;
}) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    void video.play().catch(() => {});
  }, [src]);

  return (
    <video
      ref={ref}
      key={src}
      src={src}
      poster={poster ?? undefined}
      aria-label={label}
      controls
      loop
      muted
      playsInline
      preload="metadata"
      className="mt-8 w-full rounded-xl border border-neutral-200 bg-neutral-900"
    />
  );
}
