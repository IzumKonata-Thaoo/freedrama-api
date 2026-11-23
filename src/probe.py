"""Endpoint discovery harness.

The Kuku API answers three distinguishable ways, which is what makes probing
useful instead of guesswork:

  404 {"error": "No matching url pattern found"}   -> route does not exist
  401 {"message": "Authentication failed..."}      -> route exists, needs JWT
  200 {...}                                        -> route exists and is open

Run it with a token to map the authenticated surface in one pass.

    set FD_TOKEN=...            (or write token.txt)
    python probe.py
    python probe.py --path /api/v1/shows --path /api/v1/shows/x/episodes
"""
from __future__ import annotations

import argparse
import json
import sys

import fdapi

# Shapes worth testing. Placeholders are filled from --arg or from the first
# search hit, so the probe adapts instead of hardcoding ids.
CANDIDATES = [
    "/api/v1/shows",
    "/api/v1/shows/{slug}",
    "/api/v1/shows/{id}",
    "/api/v1/shows/{slug}/episodes",
    "/api/v1/shows/{id}/episodes",
    "/api/v1/shows/{slug}/parts",
    "/api/v3/shows",
    "/api/v3/shows/{slug}",
    "/api/v3/shows/{id}/episodes",
    "/api/v1/content/{slug}",
    "/api/v1/content/{slug}/parts",
    "/api/v1/content/{id}",
    "/api/v1/content/{id}/parts",
    "/api/v3/home",
    "/api/v1/home",
    "/api/v1/me",
    "/api/v1/users/me",
    "/api/v1/user/profile",
    "/api/v1/library",
    "/api/v1/watchlist",
    "/api/v1/recently_played",
    "/api/v1/episodes/{id}",
    "/api/v1/episodes/{id}/playback",
    "/api/v1/playback/{id}",
    "/api/v1/media/{id}",
]


def classify(err_or_doc) -> str:
    if isinstance(err_or_doc, fdapi.ApiError):
        if err_or_doc.status == 404:
            return "404 route missing"
        if err_or_doc.status == 401:
            return "401 needs token"
        return "HTTP %d" % err_or_doc.status
    return "200 OK"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", help="extra path template")
    ap.add_argument("--slug")
    ap.add_argument("--id")
    args = ap.parse_args()

    slug, cid = args.slug, args.id
    if not slug:
        try:
            doc = fdapi.search("love")
            first = (doc.get("items") or [{}])[0].get("show") or {}
            slug, cid = first.get("slug"), first.get("id")
        except Exception as e:  # noqa: BLE001
            print("could not derive ids for probing:", e)

    print("token: %s | sample slug=%s id=%s\n"
          % ("yes" if fdapi.token() else "no", slug, cid))

    paths = list(CANDIDATES) + (args.path or [])
    hits = []
    for tmpl in paths:
        p = tmpl.format(slug=slug or "x", id=cid or 0)
        try:
            doc = fdapi.get(p)
            state = "200 OK"
            extra = ""
            keys = list(doc.keys())[:8] if isinstance(doc, dict) else type(doc).__name__
            extra = str(keys)
            if isinstance(doc, dict):
                media = fdapi.find_media(doc)
                if media:
                    extra += "  MEDIA:%s" % json.dumps(media[:2])[:160]
            hits.append((p, state, extra))
            print("%-46s %-16s %s" % (p, state, extra))
        except fdapi.ApiError as e:
            print("%-46s %-16s %s" % (p, classify(e), e.body[:90]))
        except Exception as e:  # noqa: BLE001
            print("%-46s %-16s %s" % (p, "error", str(e)[:80]))

    live = [h for h in hits if h[1] == "200 OK"]
    print("\n%d reachable route(s)" % len(live))
    for p, _, extra in live:
        print("  %s  %s" % (p, extra[:120]))


if __name__ == "__main__":
    sys.exit(main())
