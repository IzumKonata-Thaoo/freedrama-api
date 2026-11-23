"""FreeDrama / Kuku TV API client.

Auth, as measured:

  * `Authorization: Bearer <firebase-id-token>`  -> accepted
  * `Authorization: jwt    <firebase-id-token>`  -> "Invalid user"

The Firebase ID token can be minted by anyone: the app ships a Google API key in
`resources.arsc` and Firebase **anonymous auth is enabled** on the project, so
`accounts:signUp` hands back a token with no account at all.

Premium playback may still need a real account; browsing does not.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.kukufm.com"
HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "token.txt"          # a real account JWT, if you have one
FB_FILE = HERE / "firebase_token.json"   # cached anonymous Firebase token

FIREBASE_KEY = "AIzaSyCKncphbcD-b6vIRNByOnfnQlI1kqnNqNg"

UA = "free-drama-android/6.2.0"
BASE_HEADERS = {
    "User-Agent": UA,
    "package-name": "com.drama.free",
    "build-number": "6020000",
    "install-source": "google_play",
    "Accept": "application/json",
    "Accept-Language": "en",
}


# ------------------------------------------------------------------ firebase
def firebase_anonymous(force: bool = False) -> dict:
    """Mint (or reuse) a Firebase anonymous ID token."""
    if not force and FB_FILE.exists():
        try:
            doc = json.loads(FB_FILE.read_text(encoding="utf-8"))
            if doc.get("expires_at", 0) - 60 > time.time():
                return doc
        except Exception:
            pass

    url = ("https://identitytoolkit.googleapis.com/v1/accounts:signUp?key="
           + FIREBASE_KEY)
    req = urllib.request.Request(
        url, data=json.dumps({"returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())

    doc = {
        "id_token": d["idToken"],
        "refresh_token": d.get("refreshToken"),
        "local_id": d.get("localId"),
        "expires_at": time.time() + int(d.get("expiresIn", 3600)),
    }
    FB_FILE.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def _refresh_firebase(refresh_token: str) -> dict:
    url = ("https://securetoken.googleapis.com/v1/token?key=" + FIREBASE_KEY)
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    doc = {
        "id_token": d["id_token"],
        "refresh_token": d.get("refresh_token"),
        "local_id": d.get("user_id"),
        "expires_at": time.time() + int(d.get("expires_in", 3600)),
    }
    FB_FILE.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def auth_headers() -> dict:
    """Real account token wins; otherwise fall back to a fresh anonymous one."""
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return {"Authorization": "Bearer " + t}

    doc = firebase_anonymous()
    if doc.get("expires_at", 0) - 60 <= time.time() and doc.get("refresh_token"):
        try:
            doc = _refresh_firebase(doc["refresh_token"])
        except Exception:
            doc = firebase_anonymous(force=True)
    return {"Authorization": "Bearer " + doc["id_token"]}


def headers() -> dict:
    h = dict(BASE_HEADERS)
    h.update(auth_headers())
    return h


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__("HTTP %d: %s" % (status, body[:180]))


def get(path: str, params: dict | None = None, timeout: int = 30):
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"_raw": body.decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode("utf-8", "replace"))


# ------------------------------------------------------------------ endpoints
def genres() -> list[dict]:
    return get("/api/v1/genres").get("genre") or []


def languages() -> list[dict]:
    return get("/api/v1/languages").get("languages") or []


def shows_by_genre(slug: str, page: int = 1, **extra) -> dict:
    params = {"page": page}
    params.update(extra)
    return get("/api/v1/genres/%s/shows" % slug, params)


def shows(genre: str | None = None, **extra) -> dict:
    params = {}
    if genre:
        params["genre"] = genre
    params.update(extra)
    return get("/api/v1/shows", params or None)


def search(q: str, page: int = 1, **extra) -> dict:
    params = {"q": q, "page": page}
    params.update(extra)
    return get("/api/v3/search/", params)


def content(slug_or_id) -> dict:
    return get("/api/v1/content/%s" % slug_or_id)


def parts(slug_or_id, **extra) -> dict:
    return get("/api/v1/content/%s/parts" % slug_or_id, extra or None)


def home_all() -> dict:
    return get("/api/v3/home/all/")


def category_more(category: str, page: int = 1, size: int = 10,
                  selected_tab: str = "popular", item_type: str | None = None) -> dict:
    params = {"category": category, "page": page, "size": size,
              "selected_tab": selected_tab}
    if item_type:
        params["item_type"] = item_type
    return get("/api/v3/home/category_more_shows", params)


def channel(channel_id) -> dict:
    return get("/api/v1.0/channels/%s/" % channel_id).get("channel") or {}


def channel_episodes(channel_id, page: int = 1, page_size: int = 10) -> dict:
    return get("/api/v2.3/channels/%s/episodes/" % channel_id,
               {"page": page, "page_size": page_size})


def cdn_cookies() -> dict:
    """CloudFront signed cookies; media.cdn.kukufm.com 403s without them."""
    return get("/api/v1.0/utility/refresh-cloudfront-cookie/").get("cookies") or {}


def cookie_header(cookies: dict) -> str:
    return "; ".join("%s=%s" % (k, v) for k, v in cookies.items())



# ------------------------------------------------------------------ utilities
MEDIA_HINTS = (".m3u8", ".mpd", ".mp4", "/hls/", "/dash/")


def find_media(obj, out=None, depth: int = 0):
    out = out if out is not None else []
    if depth > 14:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                if any(x in v.lower() for x in MEDIA_HINTS):
                    out.append({k: v})
            else:
                find_media(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            find_media(v, out, depth + 1)
    return out


if __name__ == "__main__":
    who = "account token" if TOKEN_FILE.exists() else "anonymous firebase"
    print("auth:", who)
    g = genres()
    print("genres:", len(g), "->", [x["slug"] for x in g[:5]])
    if g:
        d = shows_by_genre(g[0]["slug"])
        rows = d.get("cu_shows") or []
        print("shows in %s: %d (has_next=%s)" % (g[0]["slug"], len(rows), d.get("has_next")))
        if rows:
            s = rows[0]
            print("  first:", s.get("title"), "| id", s.get("id"),
                  "| eps", s.get("n_episodes"), "| premium", s.get("is_premium"))
    print("languages:", [x.get("slug") for x in languages()[:5]])
