"""FreeDrama / Kuku TV downloader.

    python fdgrab.py catalog              # channels + episode counts -> catalog.json
    python fdgrab.py index <channel_id>   # episode list for one channel
    python fdgrab.py index-all
    python fdgrab.py get <channel_id> [--eps 1-5] [--limit 3]
    python fdgrab.py status

Media is HLS on `media.cdn.kukufm.com`, behind CloudFront signed cookies that the
API hands out per session. ffmpeg pulls the manifest and the segments once the
cookie header is passed with `-headers`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import fdapi

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
STATE = ROOT / "state"
CATALOG = ROOT / "catalog.json"
EPISODES = ROOT / "episodes.json"
for d in (OUT, STATE):
    d.mkdir(exist_ok=True)

FFMPEG = "ffmpeg"
COOKIE_TTL = 20 * 60          # refresh the CDN cookie every 20 minutes
_cookie_cache: dict = {"ts": 0.0, "header": ""}


def slugify(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|\r\n\t]+", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:70] or "untitled"


def load_json(p: Path, default):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(p: Path, obj) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def cookie_header() -> str:
    if time.time() - _cookie_cache["ts"] < COOKIE_TTL and _cookie_cache["header"]:
        return _cookie_cache["header"]
    header = fdapi.cookie_header(fdapi.cdn_cookies())
    _cookie_cache.update({"ts": time.time(), "header": header})
    return header


# ------------------------------------------------------------------ catalog
def walk_shows(obj, out=None):
    """Collect {slug, title?, id} show refs from any home-feed shape."""
    out = out if out is not None else []
    if isinstance(obj, dict):
        uri = obj.get("uri")
        if isinstance(uri, str) and "kukufm/show/" in uri:
            slug = uri.rstrip("/").split("/")[-1]
            out.append({
                "slug": slug,
                "title": obj.get("title") or obj.get("name"),
                "id": obj.get("item_id") or obj.get("id"),
                "image": obj.get("image"),
            })
        for v in obj.values():
            walk_shows(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_shows(v, out)
    return out


def resolve_channel(slug_or_id):
    """The home feed gives slugs; episode lists need numeric channel ids."""
    if str(slug_or_id).isdigit():
        return int(slug_or_id)
    d = fdapi.get("/api/v1.0/utility/slug_mapper/",
                  {"item_type": "show", "slug": slug_or_id})
    for key in ("id", "item_id", "channel_id"):
        if isinstance(d, dict) and d.get(key):
            return int(d[key])
    if isinstance(d, dict) and isinstance(d.get("channel"), dict):
        return int(d["channel"]["id"])
    raise RuntimeError("cannot resolve channel for %r: %s" % (slug_or_id, str(d)[:200]))


def cmd_catalog(_args) -> None:
    # v2.3 carries item_id (channel id); v3 only carries slugs.
    refs = walk_shows(fdapi.get("/api/v2.3/home/all/"))
    if not any(r.get("id") for r in refs):
        refs = walk_shows(fdapi.home_all())
    seen, rows = set(), []
    for r in refs:
        if not r["slug"] or r["slug"] in seen:
            continue
        seen.add(r["slug"])
        rows.append(r)
    save_json(CATALOG, rows)
    print("catalog: %d shows (%d with channel ids) -> %s"
          % (len(rows), sum(1 for r in rows if r.get("id")), CATALOG))
    for r in rows[:12]:
        print("  %-46s %s" % (r["slug"][:46], r.get("id") or ""))


def cmd_index(args) -> None:
    cid = resolve_channel(args.channel)
    first = fdapi.channel_episodes(cid, 1, 20)
    show = first.get("show") or {}
    total = first.get("n_episodes") or 0
    rows, page = [], 1
    while page <= 60:
        d = fdapi.channel_episodes(cid, page, 20)
        eps = d.get("episodes") or []
        if not eps:
            break
        for e in eps:
            rows.append({
                "channel_id": cid,
                "show": show.get("title"),
                "id": e.get("id"),
                "slug": e.get("slug"),
                "title": e.get("title"),
                "index": e.get("index"),
                "duration": e.get("duration_s"),
                "is_premium": e.get("is_premium"),
                "is_locked": e.get("is_locked"),
                "hls": (e.get("content") or {}).get("hls_url"),
            })
        if not d.get("has_more"):
            break
        page += 1
    doc = load_json(EPISODES, {})
    doc[str(cid)] = {"show": show.get("title"), "n": total, "episodes": rows}
    save_json(EPISODES, doc)
    print("%s: %d episodes (api says %d)" % (show.get("title"), len(rows), total))


def cmd_index_all(_args) -> None:
    cat = load_json(CATALOG, [])
    for r in cat:
        try:
            cmd_index(argparse.Namespace(channel=r["id"] or r["slug"]))
        except Exception as e:  # noqa: BLE001
            print("  ! %s: %s" % (r["slug"], e))


# ------------------------------------------------------------------ download
def state_path(cid) -> Path:
    return STATE / ("%s.json" % cid)


def download(ep: dict, show_title: str) -> Path | None:
    folder = OUT / slugify(show_title or str(ep["channel_id"]))
    folder.mkdir(parents=True, exist_ok=True)
    name = "E%03d_%s.mp4" % (int(ep.get("index") or 0), slugify(ep.get("title") or ""))
    dest = folder / name
    if dest.exists() and dest.stat().st_size > 200_000:
        return dest

    url = ep.get("hls")
    if not url:
        # the list is a summary; the per-episode call carries the manifest
        try:
            d = fdapi.get("/api/v2/episodes/%s/" % ep["id"])
            url = ((d.get("episode") or d).get("content") or {}).get("hls_url")
        except Exception:
            url = None
    if not url:
        print("  ! no hls for ep %s" % ep.get("id"))
        return None

    tmp = dest.with_suffix(".part.mp4")
    cmd = [FFMPEG, "-y", "-v", "error",
           "-headers", "Cookie: " + cookie_header() + "\r\n",
           "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if tmp.exists() and tmp.stat().st_size > 100_000:
        tmp.replace(dest)
        return dest
    print("  ! ffmpeg failed ep %s: %s" % (ep.get("id"), (r.stderr or "")[-200:]))
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    return None


def parse_range(spec, rows):
    if not spec:
        return rows
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", spec.strip())
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return [r for r in rows if lo <= int(r.get("index") or 0) <= hi]
    want = {int(x) for x in re.split(r"[,\s]+", spec.strip()) if x.isdigit()}
    return [r for r in rows if int(r.get("index") or 0) in want]


def cmd_get(args) -> None:
    cid = resolve_channel(args.channel)
    doc = load_json(EPISODES, {})
    if str(cid) not in doc:
        cmd_index(argparse.Namespace(channel=cid))
        doc = load_json(EPISODES, {})
    pack = doc.get(str(cid)) or {}
    rows = parse_range(args.eps, pack.get("episodes") or [])
    if args.limit:
        rows = rows[: args.limit]

    st = load_json(state_path(cid), {"done": []})
    done = set(st.get("done") or [])
    ok = 0
    for i, ep in enumerate(rows, 1):
        if ep["id"] in done and not args.force:
            continue
        t0 = time.time()
        p = download(ep, pack.get("show") or str(cid))
        if p:
            ok += 1
            done.add(ep["id"])
            st["done"] = sorted(done)
            save_json(state_path(cid), st)
            print("[%d/%d] %s  %.1f MB  %.1fs" % (
                i, len(rows), p.relative_to(OUT), p.stat().st_size / 1e6,
                time.time() - t0))
    print("downloaded %d/%d for %s" % (ok, len(rows), pack.get("show")))


def cmd_status(_args) -> None:
    files = list(OUT.rglob("*.mp4"))
    total = sum(f.stat().st_size for f in files)
    print("%d episodes on disk, %.2f GB" % (len(files), total / 1e9))
    seen: dict[str, int] = {}
    for f in files:
        key = "/".join(f.relative_to(OUT).parts[:-1])
        seen[key] = seen.get(key, 0) + 1
    for k in sorted(seen):
        print("  %-56s %3d eps" % (k, seen[k]))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog").set_defaults(fn=cmd_catalog)
    i = sub.add_parser("index"); i.add_argument("channel"); i.set_defaults(fn=cmd_index)
    sub.add_parser("index-all").set_defaults(fn=cmd_index_all)
    g = sub.add_parser("get"); g.add_argument("channel")
    g.add_argument("--eps"); g.add_argument("--limit", type=int)
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_get)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
