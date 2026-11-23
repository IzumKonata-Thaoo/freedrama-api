"""Pull a FreeDrama session out of a device where the app actually runs.

The app cannot start on an emulator (PairIP), so the practical route is:
log in once on a real phone, connect it, run this, and copy the token into
token.txt. Everything else in this repo then works headlessly.

    python session_pull.py --serial <device>
    python session_pull.py --serial <device> --keep    # keep the dump

Looks in shared_prefs, databases, files and no_backup for a JWT
(`eyJ...`) or an `authorization`/`token` key.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = "com.drama.free"
HERE = Path(__file__).resolve().parent
JWT = re.compile(rb"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
KEYISH = re.compile(rb"(?i)(token|authorization|jwt|access[_-]?token)")


def find_adb() -> str:
    import os

    found = shutil.which("adb")
    if found:
        return found
    guesses = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe",
        Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools/adb.exe",
        Path("C:/Android/Sdk/platform-tools/adb.exe"),
    ]
    for g in guesses:
        if g.is_file():
            return str(g)
    raise SystemExit("adb not found — put it on PATH or set ANDROID_HOME")


def adb(serial, *args, timeout=120):
    return subprocess.run([find_adb(), "-s", serial] + list(args),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    staging = "/data/local/tmp/fd_session"
    print("staging app data on device…")
    r = adb(args.serial, "shell",
            "su -c 'rm -rf %s; mkdir -p %s; cp -r /data/data/%s/. %s/ 2>/dev/null; "
            "chmod -R 777 %s; echo done'" % (staging, staging, PKG, staging, staging))
    if "done" not in r.stdout:
        # no su: try run-as (works only for debuggable builds)
        r = adb(args.serial, "shell",
                "run-as %s sh -c 'cp -r . /sdcard/fd_session' 2>&1" % PKG)
        if r.returncode != 0:
            print("could not read app data (needs root or a debuggable build)")
            print(r.stdout.strip()[:300], r.stderr.strip()[:300])
            sys.exit(1)

    outdir = Path(tempfile.mkdtemp(prefix="fd_session_"))
    print("pulling to %s" % outdir)
    adb(args.serial, "pull", staging, str(outdir))

    found = []
    for f in outdir.rglob("*"):
        if not f.is_file():
            continue
        try:
            data = f.read_bytes()
        except Exception:
            continue
        for m in JWT.finditer(data):
            found.append((f, m.group(0).decode()))

    if not found:
        # fall back to reporting key-ish files so the search can be narrowed
        print("no JWT literal found. files mentioning token/authorization:")
        for f in outdir.rglob("*"):
            if not f.is_file():
                continue
            try:
                data = f.read_bytes()
            except Exception:
                continue
            if KEYISH.search(data) and len(data) < 400_000:
                print("  %s (%d bytes)" % (f.relative_to(outdir), len(data)))
        if not args.keep:
            shutil.rmtree(outdir, ignore_errors=True)
        sys.exit(2)

    best = max(found, key=lambda t: len(t[1]))
    tok_path = HERE / "token.txt"
    tok_path.write_text(best[1], encoding="utf-8")
    print("\nfound %d JWT candidate(s)" % len(found))
    print("wrote %s (from %s)" % (tok_path, best[0].name))

    adb(args.serial, "shell", "su -c 'rm -rf %s'" % staging)
    if not args.keep:
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
