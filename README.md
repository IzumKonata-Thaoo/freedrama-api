# FreeDrama API

**Unofficial documentation and downloader for FreeDrama (`com.drama.free`) — a rebrand of Kuku TV (`com.vlv.aravali`).**

No app, no emulator, no frida. The API accepts a **Firebase anonymous token**, and the app ships the Google API key that mints one. Media is HLS behind CloudFront signed cookies that the same API hands out for free.

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-2ea44f">
  <img alt="status" src="https://img.shields.io/badge/status-working-brightgreen">
  <img alt="auth" src="https://img.shields.io/badge/auth-firebase%20anonymous-orange">
  <img alt="drm" src="https://img.shields.io/badge/DRM-none-lightgrey">
</p>

---

## Table of contents

- [Why this works](#why-this-works)
- [Install](#install)
- [Quickstart](#quickstart)
- [CLI reference](#cli-reference)
- [Output layout](#output-layout)
- [API at a glance](#api-at-a-glance)
- [Media pipeline](#media-pipeline)
- [Documentation](#documentation)
- [Notes](#notes)

---

## Why this works

Three measured facts:

1. **Auth is anonymous-capable.** The app ships a Google API key in
   `resources.arsc` and the Firebase project allows anonymous sign-in, so
   `accounts:signUp` returns a usable ID token with no account at all.
2. **The API takes it as `Bearer`.** `Authorization: Bearer <firebase-id-token>`
   is accepted on content routes. (`jwt <token>` is rejected with
   `"Invalid user"` — the scheme matters.)
3. **The CDN cookie is free.** `GET /api/v1.0/utility/refresh-cloudfront-cookie/`
   returns `CloudFront-Policy / -Signature / -Key-Pair-Id` for that user, and
   `media.cdn.kukufm.com` serves HLS once they are sent. No DRM, no Widevine.

Everything below follows from those three.

## Install

```bash
git clone https://github.com/IzumKonata-Thaoo/freedrama-api.git
cd freedrama-api

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Only external dependency: **ffmpeg** on `PATH`. The Python side is stdlib only.

## Quickstart

```bash
cd src
python fdapi.py
```

```text
auth: anonymous firebase
genres: 36 -> ['action-1', 'billionaire', 'business', 'career', 'comedy']
shows in action-1: 10 (has_next=True)
  first: Mera Pati Sniper No.1 | id 283463 | eps 190 | premium True
languages: ['hindi', 'english']
```

```bash
python fdgrab.py catalog
```

```text
catalog: 22 shows (22 with channel ids) -> catalog.json
  mr-idiot-hero-husband                          261754
  my-handsome-bodyguard-1                        262136
  study-god                                      261836
  ...
```

```bash
python fdgrab.py index 262136
python fdgrab.py get 262136 --eps 1-2
```

```text
My Handsome Bodyguard: 93 episodes (api says 93)
[1/2] My Handsome Bodyguard\E001_Ep 1 - Mithaai Ki Dukaan Todi.mp4  40.6 MB  78.3s
[2/2] My Handsome Bodyguard\E002_Ep 2 - Bachcha Dekhkar Call Kati.mp4  26.1 MB  41.4s
downloaded 2/2 for My Handsome Bodyguard
```

Verified output: **H.264 + AAC, 173.0 s and 127.9 s, 0 decode errors**.

## CLI reference

| Command | What it does |
|---|---|
| `python fdapi.py` | auth + genre + show smoke test |
| `python fdgrab.py catalog` | shows from the home feed, with channel ids |
| `python fdgrab.py index <channel>` | full episode list for one show (auto-paginates) |
| `python fdgrab.py index-all` | every show in the catalog |
| `python fdgrab.py get <channel>` | download a whole show |
| `python fdgrab.py get <channel> --eps 1-5` | episode range |
| `python fdgrab.py get <channel> --limit 3` | first N |
| `python fdgrab.py get <channel> --force` | re-download |
| `python fdgrab.py status` | what is on disk, grouped by show |
| `python probe.py` | map unknown routes (404 vs 401 vs 200) |

`<channel>` accepts either a numeric id or a show slug; slugs are resolved through
`/api/v1.0/utility/slug_mapper/`.

## Output layout

```text
out/
├── Mr. Idiot, Hero Husband/
│   ├── E001_Ep 1 - Janamdin Par Talaak?.mp4
│   └── E002_...
└── My Handsome Bodyguard/
    ├── E001_Ep 1 - Mithaai Ki Dukaan Todi.mp4
    └── E002_Ep 2 - Bachcha Dekhkar Call Kati.mp4
```

State lives in `state/<channel>.json`, so re-running `get` only fetches the gaps.
The CDN cookie is cached for 20 minutes and refreshed transparently.

## API at a glance

Base: `https://api.kukufm.com` · `Authorization: Bearer <firebase-id-token>`

| Method | Endpoint | Returns |
|---|---|---|
| `POST` | `identitytoolkit…/accounts:signUp?key=` | anonymous Firebase ID token |
| `GET` | `/api/v1.0/utility/refresh-cloudfront-cookie/` | **CloudFront signed cookies** |
| `GET` | `/api/v3/home/all/` | home rails |
| `GET` | `/api/v2.3/home/all/` | home rails with `item_id` |
| `GET` | `/api/v1/genres` · `/api/v1/languages` | taxonomies |
| `GET` | `/api/v1/genres/{slug}/shows` | shows in a genre |
| `GET` | `/api/v3/home/category_more_shows?category=` | browse by category/trope |
| `GET` | `/api/v1.0/channels/{id}/` | show detail |
| `GET` | `/api/v2.3/channels/{id}/episodes/?page=&page_size=` | **episode list** |
| `GET` | `/api/v2/episodes/{id}/` | single episode |
| `GET` | `/api/v3/search/?q=&page=` | search |
| `GET` | `/api/v2.0/content-types/` | content types |

Full schemas: [`docs/endpoints.md`](docs/endpoints.md).

## Media pipeline

```text
episode.content.hls_url
  -> https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8
       ├── audio group: original-audio-1/2.m3u8, ad-master-2.m3u8
       └── variants (up to 1080x1920) -> segments
```

Without the cookie it is `403`. With it:

```bash
ffmpeg -headers "Cookie: CloudFront-Policy=…; CloudFront-Signature=…; CloudFront-Key-Pair-Id=…" \
       -i "<hls_url>" -c copy -bsf:a aac_adtstoasc out.mp4
```

## Documentation

| File | Contents |
|---|---|
| [`docs/authentication.md`](docs/authentication.md) | Firebase anonymous auth, Bearer vs jwt, CDN cookies |
| [`docs/endpoints.md`](docs/endpoints.md) | every endpoint, parameters, response shapes |
| [`docs/media.md`](docs/media.md) | HLS layout, audio groups, ffmpeg recipe |

## Notes

- **Premium content is reachable with the anonymous token.** Every episode we
  tested returned a manifest and a cookie, including `is_premium: true` shows.
  That is a property of the API, not something this repo adds.
- The Firebase ID token expires in ~1 hour; `fdapi.py` caches it and refreshes it
  with the refresh token automatically.
- The CDN cookie expires in ~1 hour too; `fdgrab.py` refreshes it every 20 min.
- Content belongs to its respective owners. This repository documents and
  automates access; it does not grant rights to redistribute anything.
- If you *do* have a real account token, drop it in `src/token.txt` and it takes
  priority over the anonymous one.

## License

MIT — see [LICENSE](LICENSE).
