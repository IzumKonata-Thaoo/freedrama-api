"""One episode, end to end: anonymous auth -> cookie -> ffmpeg.

    python examples/download_one.py 261754 1
    # channel id 261754, episode index 1

Needs ffmpeg on PATH. Run it from the repo root or the src/ dir works too.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import fdapi  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)

    channel_id = sys.argv[1]
    wanted = int(sys.argv[2])

    show = fdapi.channel(channel_id)
    print("show :", show.get("title"))

    episode = None
    page = 1
    while page <= 40 and episode is None:
        doc = fdapi.channel_episodes(channel_id, page, 20)
        for ep in doc.get("episodes") or []:
            if int(ep.get("index") or 0) == wanted:
                episode = ep
                break
        if not doc.get("has_more"):
            break
        page += 1

    if not episode:
        raise SystemExit("episode %d not found" % wanted)

    print("ep   :", episode["title"], "(%ss)" % episode.get("duration_s"))
    url = (episode.get("content") or {}).get("hls_url")
    print("hls  :", url)

    cookies = fdapi.cdn_cookies()
    cookie = fdapi.cookie_header(cookies)

    out = Path("example_%s_%03d.mp4" % (channel_id, wanted))
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-headers", "Cookie: " + cookie + "\r\n",
                    "-i", url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
                    str(out)], check=True)
    print("wrote:", out, "(%.1f MB)" % (out.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
