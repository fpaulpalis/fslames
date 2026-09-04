/**
 * Turning a sign's stored media paths into URLs the browser can fetch.
 *
 * `signs.json` stores bucket-relative paths ("video/hello.mp4"), never absolute
 * URLs. The origin is decided here, at render time, so the same generated data
 * serves local files during development and Cloudflare R2 in production without
 * regenerating anything.
 *
 * Set NEXT_PUBLIC_MEDIA_BASE_URL to the bucket's public origin. It falls back to
 * /media, which resolves to web/public/media/ — drop recordings there to preview
 * without R2 at all.
 */

import type { Sign } from "./signs";

const BASE = (process.env.NEXT_PUBLIC_MEDIA_BASE_URL ?? "/media").replace(/\/+$/, "");

export interface SignMedia {
  video: string;
  poster: string | null;
}

/**
 * Absolute (or root-relative) URLs for a sign, or null when it has no recording.
 *
 * The `?v=` is the first 8 hex of the file's sha256, from scan_media.py. R2 sits
 * behind a CDN with a long TTL, so without it a re-recorded sign keeps serving
 * the old take to everyone who has already seen it — including you, past a hard
 * refresh — with nothing to indicate the file changed.
 */
export function resolveMedia(sign: Sign): SignMedia | null {
  const { video, poster, hash } = sign.media;
  if (!video) return null;

  const version = hash ? `?v=${hash}` : "";
  return {
    video: `${BASE}/${video}${version}`,
    poster: poster ? `${BASE}/${poster}${version}` : null,
  };
}

export function hasMedia(sign: Sign): boolean {
  return sign.media.video !== null;
}
