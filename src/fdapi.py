"""fdapi — FreeDrama / Kuku TV API client.

    import fdapi
    fdapi.channel_episodes(261754, page=1, page_size=20)

Auth
----
`Authorization: Bearer <firebase-id-token>`. The Firebase project allows
anonymous sign-in and the app ships its API key, so a token can be minted with no
account at all. `token.txt` (a real account token) overrides it when present.

Media
-----
`media.cdn.kukufm.com` is behind CloudFront signed cookies; `cdn_cookies()`
returns them, `cookie_header()` flattens them for ffmpeg.
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
TOKEN_FILE = HERE / "token.txt"            # real account token, optional
FB_FILE = HERE / "firebase_token.json"     # cached anonymous token

FIREBASE_KEY = "AIzaSyCKncphbcD-b6vIRNByOnfnQlI1kqnNqNg"

DEFAULT_HEADERS = {
    "User-Agent": "free-drama-android/6.2.0",
    "package-name": "com.drama.free",
    "build-number": "6020000",
    "install-source": "google_play",
    "Accept": "application/json",
    "Accept-Language": "en",
}


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__("HTTP %d: %s" % (status, body[:200]))


# ------------------------------------------------------------------ firebase
def firebase_anonymous(force: bool = False) -> dict:
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
    body = urllib.parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token}).encode()
    req = urllib.request.Request(
        "https://securetoken.googleapis.com/v1/token?key=" + FIREBASE_KEY,
        data=body,
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


def token() -> str:
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return t
    doc = firebase_anonymous()
    if doc.get("expires_at", 0) - 60 <= time.time() and doc.get("refresh_token"):
        try:
            return _refresh_firebase(doc["refresh_token"])["id_token"]
        except Exception:
            return firebase_anonymous(force=True)["id_token"]
    return doc["id_token"]


def auth_mode() -> str:
    if TOKEN_FILE.exists() and TOKEN_FILE.read_text(encoding="utf-8").strip():
        return "account"
    return "anonymous"


# ------------------------------------------------------------------ transport
def get(path: str, params: dict | None = None, timeout: int = 30,
        retries: int = 3):
    url = path if path.startswith("http") else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            **DEFAULT_HEADERS, "Authorization": "Bearer " + token()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"_raw": body.decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            err = ApiError(e.code, e.read().decode("utf-8", "replace"))
            if e.code in (401, 403, 404):
                raise err
            last = err
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(0.6 * (2 ** attempt))
    raise RuntimeError("GET %s failed: %s" % (url, last))


# ------------------------------------------------------------------ endpoints
def home(page: int = 1) -> dict:
    """Home rails (v3 layout)."""
    return get("/api/v3/home/all/", {"page": page})


def home_ids(page: int = 1) -> dict:
    """Same rails, but banners carry `item_id` = channel id (v2.3)."""
    return get("/api/v2.3/home/all/", {"page": page})


def category_more(category: str, page: int = 1, size: int = 10,
                  selected_tab: str = "popular",
                  item_type: str | None = None) -> dict:
    params = {"category": category, "page": page, "size": size,
              "selected_tab": selected_tab}
    if item_type:
        params["item_type"] = item_type
    return get("/api/v3/home/category_more_shows", params)


def genres() -> list[dict]:
    return get("/api/v1/genres").get("genre") or []


def languages() -> list[dict]:
    return get("/api/v1/languages").get("languages") or []


def genre_shows(slug: str, page: int = 1, lang: str | None = None) -> dict:
    params = {"page": page}
    if lang:
        params["lang"] = lang
    return get("/api/v1/genres/%s/shows" % slug, params)


def content_types() -> list[dict]:
    return get("/api/v2.0/content-types/").get("content_types") or []


def content_type_shows(slug: str, page: int = 1, page_size: int = 20,
                       lang: str = "english") -> dict:
    return get("/api/v2.0/content-types/%s/shows/" % slug,
               {"page": page, "page_size": page_size, "lang": lang})


def channel(channel_id) -> dict:
    return get("/api/v1.0/channels/%s/" % channel_id).get("channel") or {}


def channel_episodes(channel_id, page: int = 1, page_size: int = 20) -> dict:
    return get("/api/v2.3/channels/%s/episodes/" % channel_id,
               {"page": page, "page_size": page_size})


def episode(episode_id) -> dict:
    d = get("/api/v2/episodes/%s/" % episode_id)
    return d.get("episode") or d


def search(q: str, page: int = 1, **extra) -> dict:
    params = {"q": q, "page": page}
    params.update(extra)
    return get("/api/v3/search/", params)


def slug_map(slug: str, item_type: str = "show") -> dict:
    return get("/api/v1.0/utility/slug_mapper/",
               {"item_type": item_type, "slug": slug})


# ------------------------------------------------------------------ media bits
def cdn_cookies() -> dict:
    return get("/api/v1.0/utility/refresh-cloudfront-cookie/").get("cookies") or {}


def cookie_header(cookies: dict) -> str:
    return "; ".join("%s=%s" % (k, v) for k, v in cookies.items())


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


def walk_shows(obj, out=None):
    """Every show reference in a feed payload: {slug, id?, title?, image?}."""
    out = out if out is not None else []
    if isinstance(obj, dict):
        uri = obj.get("uri")
        if isinstance(uri, str) and "kukufm/show/" in uri:
            out.append({
                "slug": uri.rstrip("/").split("/")[-1],
                "id": obj.get("item_id") or obj.get("id"),
                "title": obj.get("title") or obj.get("name"),
                "image": obj.get("image"),
            })
        for v in obj.values():
            walk_shows(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_shows(v, out)
    return out


if __name__ == "__main__":
    print("auth:", auth_mode())
    g = genres()
    print("genres:", len(g), [x["slug"] for x in g[:6]])
    print("content types:", [x["slug"] for x in content_types()])
    d = channel_episodes(261754, 1, 3)
    eps = d.get("episodes") or []
    print("channel 261754:", (d.get("show") or {}).get("title"),
          "| eps", d.get("n_episodes"), "| returned", len(eps))
    if eps:
        print("  first:", eps[0]["title"],
              "| hls:", bool((eps[0].get("content") or {}).get("hls_url")))
    print("search 'love':", len(search("love").get("items") or []), "items")
