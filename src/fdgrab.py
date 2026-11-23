"""fdgrab — FreeDrama / Kuku TV downloader.

    python fdgrab.py discover                # catalog: series + home rails
    python fdgrab.py discover --genres       # + every genre (slow, thorough)
    python fdgrab.py index <show>            # episode list for one show
    python fdgrab.py index-all               # every show in the catalog
    python fdgrab.py info <show>             # show details, no download
    python fdgrab.py get <show> --eps 1-5    # download a range
    python fdgrab.py get <show> --all        # the whole show
    python fdgrab.py get-all --limit-shows 3 # batch, first N shows
    python fdgrab.py search "love"           # search and print ids
    python fdgrab.py status                  # what is on disk

<show> is a numeric channel id or a show slug.

Media is HLS behind CloudFront signed cookies; the cookie is fetched once and
refreshed every 20 minutes. State lives in state/<channel>.json so re-running only
fetches the gaps.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import threading
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
COOKIE_TTL = 20 * 60
_cookie = {"ts": 0.0, "header": "", "lock": threading.Lock()}


# ------------------------------------------------------------------ helpers
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
    with _cookie["lock"]:
        if time.time() - _cookie["ts"] < COOKIE_TTL and _cookie["header"]:
            return _cookie["header"]
        header = fdapi.cookie_header(fdapi.cdn_cookies())
        _cookie.update({"ts": time.time(), "header": header})
        return header


def resolve_channel(ref):
    """Accept a numeric id or a slug; slugs go through the API where possible."""
    if str(ref).isdigit():
        return int(ref)
    cat = load_json(CATALOG, [])
    for row in cat:
        if row.get("slug") == ref and row.get("id"):
            return int(row["id"])
    try:
        d = fdapi.slug_map(ref, "show")
        for key in ("id", "item_id", "channel_id"):
            if isinstance(d, dict) and d.get(key):
                return int(d[key])
    except fdapi.ApiError:
        pass
    raise SystemExit("cannot resolve show %r — try a numeric channel id" % ref)


# ------------------------------------------------------------------ discovery
def _add(rows: dict, refs):
    for r in refs:
        if not r.get("slug"):
            continue
        cur = rows.get(r["slug"])
        if cur is None:
            rows[r["slug"]] = r
        elif not cur.get("id") and r.get("id"):
            rows[r["slug"]] = r


def cmd_discover(args) -> None:
    rows: dict[str, dict] = {}

    print("home rails…")
    for page in range(1, 4):
        try:
            _add(rows, fdapi.walk_shows(fdapi.home_ids(page)))
            _add(rows, fdapi.walk_shows(fdapi.home(page)))
        except fdapi.ApiError as e:
            print("  page %d: %s" % (page, e.status))
            break

    print("series content type…")
    for page in range(1, 31):
        try:
            d = fdapi.content_type_shows("series", page, 20)
        except fdapi.ApiError as e:
            print("  page %d: %s" % (page, e.status))
            break
        shows = d.get("shows") or []
        for s in shows:
            _add(rows, [{"slug": s.get("slug"), "id": s.get("id"),
                         "title": s.get("title"), "image": s.get("image"),
                         "episodes": s.get("n_episodes")}])
        if not d.get("has_next") or not shows:
            break

    if args.genres:
        print("every genre…")
        for g in fdapi.genres():
            for page in range(1, args.max_pages + 1):
                try:
                    d = fdapi.genre_shows(g["slug"], page)
                except fdapi.ApiError:
                    break
                shows = d.get("cu_shows") or []
                for s in shows:
                    _add(rows, [{"slug": s.get("slug"), "id": s.get("id"),
                                 "title": s.get("title"), "image": s.get("image"),
                                 "episodes": s.get("n_episodes")}])
                if not d.get("has_next") or not shows:
                    break

    out = sorted(rows.values(), key=lambda r: (r.get("title") or r["slug"]).lower())
    save_json(CATALOG, out)
    with_id = sum(1 for r in out if r.get("id"))
    print("\ncatalog: %d shows (%d with channel ids) -> %s"
          % (len(out), with_id, CATALOG))
    for r in out[:15]:
        print("  %-44s %-8s %s" % ((r.get("title") or r["slug"])[:44],
                                   r.get("id") or "?", r["slug"]))


# ------------------------------------------------------------------ indexing
def index_show(ref, page_size: int = 100) -> dict:
    cid = resolve_channel(ref)
    first = fdapi.channel_episodes(cid, 1, page_size)
    show = first.get("show") or {}
    title = show.get("title") or str(cid)

    rows, page = [], 1
    while page <= 60:
        d = fdapi.channel_episodes(cid, page, page_size)
        eps = d.get("episodes") or []
        if not eps:
            break
        for e in eps:
            rows.append({
                "channel_id": cid,
                "show": title,
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
    doc[str(cid)] = {"show": title, "n": first.get("n_episodes"), "episodes": rows}
    save_json(EPISODES, doc)
    print("%-46s %3d episodes" % (title[:46], len(rows)))
    return {"id": cid, "show": title, "n": len(rows)}


def cmd_index(args) -> None:
    index_show(args.show)


def cmd_index_all(args) -> None:
    cat = load_json(CATALOG, [])
    if not cat:
        print("catalog empty — run: python fdgrab.py discover")
        return
    if args.limit_shows:
        cat = cat[: args.limit_shows]
    total = 0
    for r in cat:
        try:
            info = index_show(r.get("id") or r["slug"])
            total += info["n"]
        except Exception as e:  # noqa: BLE001
            print("  ! %s: %s" % (r.get("slug"), e))
    print("indexed %d episodes across %d shows" % (total, len(cat)))


# ------------------------------------------------------------------ info
def cmd_info(args) -> None:
    cid = resolve_channel(args.show)
    ch = fdapi.channel(cid)
    d = fdapi.channel_episodes(cid, 1, 5)
    print("title      :", ch.get("title"))
    print("channel id :", cid)
    print("slug       :", ch.get("slug"))
    print("language   :", ch.get("language"))
    print("premium    :", ch.get("is_premium"))
    print("episodes   :", d.get("n_episodes"))
    print("image      :", ch.get("image"))
    eps = d.get("episodes") or []
    for e in eps[:5]:
        print("   E%03d  %-46s %4ss" % (e.get("index") or 0,
                                        (e.get("title") or "")[:46],
                                        e.get("duration_s") or 0))


# ------------------------------------------------------------------ download
def state_path(cid) -> Path:
    return STATE / ("%s.json" % cid)


def episode_url(ep: dict) -> str | None:
    url = ep.get("hls")
    if url:
        return url
    try:
        d = fdapi.episode(ep["id"])
        return ((d.get("content") or {}).get("hls_url"))
    except Exception:
        return None


def download(ep: dict, show: str) -> tuple[str, Path | None]:
    folder = OUT / slugify(show)
    folder.mkdir(parents=True, exist_ok=True)
    name = "E%03d_%s.mp4" % (int(ep.get("index") or 0), slugify(ep.get("title") or ""))
    dest = folder / name
    if dest.exists() and dest.stat().st_size > 200_000:
        return ep["id"], dest

    url = episode_url(ep)
    if not url:
        return ep["id"], None

    tmp = dest.with_suffix(".part.mp4")
    cmd = [FFMPEG, "-y", "-v", "error",
           "-headers", "Cookie: " + cookie_header() + "\r\n",
           "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if tmp.exists() and tmp.stat().st_size > 100_000:
        tmp.replace(dest)
        return ep["id"], dest
    print("   ! ffmpeg ep %s: %s" % (ep.get("id"), (r.stderr or "")[-160:]))
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    return ep["id"], None


def parse_range(spec, rows):
    if not spec:
        return rows
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", spec.strip())
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return [r for r in rows if lo <= int(r.get("index") or 0) <= hi]
    want = {int(x) for x in re.split(r"[,\s]+", spec.strip()) if x.isdigit()}
    return [r for r in rows if int(r.get("index") or 0) in want]


def grab(ref, eps=None, limit=None, all_eps=False, workers=3, force=False) -> int:
    cid = resolve_channel(ref)
    doc = load_json(EPISODES, {})
    if str(cid) not in doc:
        index_show(cid)
        doc = load_json(EPISODES, {})
    pack = doc.get(str(cid)) or {}
    rows = pack.get("episodes") or []
    if all_eps:
        pass
    elif eps:
        rows = parse_range(eps, rows)
    if limit:
        rows = rows[:limit]

    st = load_json(state_path(cid), {"done": []})
    done = set(st.get("done") or [])
    todo = [r for r in rows if force or r["id"] not in done]
    if not todo:
        print("%s: nothing to do" % pack.get("show"))
        return 0

    show = pack.get("show") or str(cid)
    print("%s: %d episode(s), %d worker(s)" % (show, len(todo), workers))
    ok = 0
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(download, ep, show): ep for ep in todo}
        for fut in concurrent.futures.as_completed(futures):
            ep = futures[fut]
            try:
                eid, path = fut.result()
            except Exception as e:  # noqa: BLE001
                print("   ! %s: %s" % (ep.get("title"), e))
                continue
            if path:
                ok += 1
                done.add(eid)
                st["done"] = sorted(done)
                save_json(state_path(cid), st)
                print("  [%d/%d] %-52s %6.1f MB" % (
                    ok, len(todo), path.name[:52], path.stat().st_size / 1e6))
    print("%s: %d/%d in %.0fs" % (show, ok, len(todo), time.time() - t0))
    return ok


def cmd_get(args) -> None:
    grab(args.show, args.eps, args.limit, args.all, args.workers, args.force)


def cmd_get_all(args) -> None:
    cat = load_json(CATALOG, [])
    if not cat:
        print("catalog empty — run: python fdgrab.py discover")
        return
    if args.limit_shows:
        cat = cat[: args.limit_shows]
    total = 0
    for r in cat:
        try:
            total += grab(r.get("id") or r["slug"], None, args.limit, args.all,
                          args.workers, args.force)
        except SystemExit:
            continue
        except Exception as e:  # noqa: BLE001
            print("  ! %s: %s" % (r.get("slug"), e))
    print("downloaded %d episode(s) across %d show(s)" % (total, len(cat)))


# ------------------------------------------------------------------ misc
def cmd_search(args) -> None:
    d = fdapi.search(args.query, args.page)
    items = d.get("items") or []
    print("%d result(s) for %r" % (len(items), args.query))
    for it in items:
        sh = it.get("show") or {}
        print("  %-8s %-44s %3s eps  premium=%s" % (
            sh.get("id"), (sh.get("title") or "")[:44],
            sh.get("n_episodes"), sh.get("is_premium")))


def cmd_status(args) -> None:
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
    p = argparse.ArgumentParser(prog="fdgrab", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="build the show catalog")
    d.add_argument("--genres", action="store_true", help="also walk every genre")
    d.add_argument("--max-pages", type=int, default=8)
    d.set_defaults(fn=cmd_discover)

    i = sub.add_parser("index", help="episode list for one show")
    i.add_argument("show")
    i.set_defaults(fn=cmd_index)

    ia = sub.add_parser("index-all", help="episode lists for the whole catalog")
    ia.add_argument("--limit-shows", type=int)
    ia.set_defaults(fn=cmd_index_all)

    inf = sub.add_parser("info", help="show details")
    inf.add_argument("show")
    inf.set_defaults(fn=cmd_info)

    g = sub.add_parser("get", help="download one show")
    g.add_argument("show")
    g.add_argument("--eps", help="1-5 or 1,3,7")
    g.add_argument("--all", action="store_true", help="every episode")
    g.add_argument("--limit", type=int)
    g.add_argument("--workers", type=int, default=3)
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_get)

    ga = sub.add_parser("get-all", help="download every show in the catalog")
    ga.add_argument("--limit-shows", type=int)
    ga.add_argument("--limit", type=int, help="episodes per show")
    ga.add_argument("--all", action="store_true")
    ga.add_argument("--workers", type=int, default=3)
    ga.add_argument("--force", action="store_true")
    ga.set_defaults(fn=cmd_get_all)

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--page", type=int, default=1)
    s.set_defaults(fn=cmd_search)

    st = sub.add_parser("status")
    st.set_defaults(fn=cmd_status)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
