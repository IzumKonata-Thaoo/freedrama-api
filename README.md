<p align="center">
  <img src="assets/logo.png" width="132" alt="FreeDrama logo">
</p>

<h1 align="center">FreeDrama API</h1>

<p align="center">
  <b>Unofficial API reference and downloader for FreeDrama — a rebrand of Kuku TV.</b><br>
  <sub>No app. No emulator. No frida. One anonymous Firebase token is the whole key.</sub>
</p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-2ea44f">
  <img alt="status" src="https://img.shields.io/badge/status-working-brightgreen">
  <img alt="auth" src="https://img.shields.io/badge/auth-firebase%20anonymous-orange">
  <img alt="drm" src="https://img.shields.io/badge/DRM-none-lightgrey">
  <img alt="catalogue" src="https://img.shields.io/badge/catalogue-323%20shows-blueviolet">
</p>

---

```text
$ python fdgrab.py discover
catalog: 323 shows (323 with channel ids)

$ python fdgrab.py get 261754 --eps 1-2 --workers 2
Mr. Idiot, Hero Husband: 2 episode(s), 2 worker(s)
  [1/2] E001_Ep 1 - Janamdin Par Talaak.mp4      37.2 MB
  [2/2] E002_Ep 2 - Biwi Kaun Hai.mp4            44.9 MB
Mr. Idiot, Hero Husband: 2/2 in 93s
```

---

## Contents

- [What this gives you](#what-this-gives-you)
- [Why it works](#why-it-works)
- [Install](#install)
- [Quickstart](#quickstart)
- [Commands](#commands)
- [Output layout](#output-layout)
- [How the pipeline fits together](#how-the-pipeline-fits-together)
- [API surface](#api-surface)
- [Documentation](#documentation)
- [Notes](#notes)

---

## What this gives you

| | |
|---|---|
| **Catalogue** | 323 shows in the `series` content type, plus every genre and home rail |
| **Episodes** | 76–190 in the shows sampled, each with its own signed HLS manifest |
| **Quality** | up to 1080×1920, H.264 + AAC |
| **Auth** | Firebase anonymous token — no account, no OTP, no app |
| **DRM** | none; the only gate is a CloudFront cookie the API hands out |
| **Resume** | per-show state file; re-running only fetches what is missing |
| **Concurrency** | `--workers N` episodes in parallel, one shared cookie |

## Why it works

Three measured facts, nothing assumed:

<table>
<tr><td width="34"><b>1</b></td><td>

**The app ships a Firebase key.** `AIzaSyCKncphbcD-b6vIRNByOnfnQlI1kqnNqNg`, in
`resources.arsc`. The Firebase project allows **anonymous sign-in**, so
`accounts:signUp` returns a real ID token with no account.

</td></tr>
<tr><td><b>2</b></td><td>

**The API accepts it as `Bearer`.** `Authorization: Bearer <firebase-id-token>`
works. The app's own `jwt <token>` scheme rejects it with `"Invalid user"` — the
scheme is the detail that matters.

</td></tr>
<tr><td><b>3</b></td><td>

**The CDN cookie is free.** `GET /api/v1.0/utility/refresh-cloudfront-cookie/`
returns `CloudFront-Policy / -Signature / -Key-Pair-Id` for that user, and
`media.cdn.kukufm.com` serves plain HLS once they ride along.

</td></tr>
</table>

## Install

```bash
git clone https://github.com/IzumKonata-Thaoo/freedrama-api.git
cd freedrama-api
```

The Python side is **stdlib only** — no `pip install` needed. You do need ffmpeg:

```bash
ffmpeg -version        # winget install Gyan.FFmpeg | brew install ffmpeg | apt install ffmpeg
```

## Quickstart

```bash
cd src
python fdapi.py
```

```text
auth: anonymous
genres: 36 ['action-1', 'billionaire', 'business', 'career', 'comedy', 'crime']
content types: ['learning', 'kuku-upskill', 'entertainment', 'movie', 'novel',
                'quiz', 'series', 'bytes', 'podcast', 'story', 'audio-book', …]
channel 261754: Mr. Idiot, Hero Husband | eps 94 | returned 3
  first: Ep 1 - Janamdin Par Talaak? | hls: True
search 'love': 41 items
```

```bash
python fdgrab.py discover          # 323 shows -> catalog.json
python fdgrab.py info 261754       # show details
python fdgrab.py get 261754 --all  # download the whole show
```

Want the full sweep? `discover --genres` walks all 36 genres as well, then
`index-all` and `get-all` do the rest.

## Commands

| Command | What it does |
|---|---|
| `python fdgrab.py discover` | build `catalog.json` from series + home rails |
| `python fdgrab.py discover --genres` | also walk every genre (thorough, slower) |
| `python fdgrab.py info <show>` | title, id, language, episode count, first episodes |
| `python fdgrab.py index <show>` | full episode list for one show |
| `python fdgrab.py index-all` | episode lists for the whole catalogue |
| `python fdgrab.py get <show> --eps 1-5` | download a range |
| `python fdgrab.py get <show> --all` | the whole show |
| `python fdgrab.py get <show> --limit 3` | first N episodes |
| `python fdgrab.py get <show> --workers 4` | parallel downloads |
| `python fdgrab.py get-all --limit-shows 3` | batch across the catalogue |
| `python fdgrab.py search "love"` | search and print channel ids |
| `python fdgrab.py status` | what is on disk, per show |

`<show>` takes a numeric channel id or a slug. Slugs are resolved through the
catalogue first, then `/api/v1.0/utility/slug_mapper/`.

## Output layout

```text
out/
└── Mr. Idiot, Hero Husband/
    ├── E001_Ep 1 - Janamdin Par Talaak.mp4     37.2 MB
    └── E002_Ep 2 - Biwi Kaun Hai.mp4           44.9 MB

state/261754.json        downloaded episode ids
catalog.json             shows
episodes.json            per-show episode lists
```

Re-running `get` is free — it reads `state/` and skips what is already there.

## How the pipeline fits together

```mermaid
flowchart LR
    A[Firebase<br/>anonymous sign-up] -->|idToken| B[API<br/>api.kukufm.com]
    B -->|Bearer| C[catalog<br/>323 shows]
    C --> D[channels/id<br/>episodes]
    D --> E[content.hls_url]
    B -->|cookie endpoint| F[CloudFront<br/>signed cookies]
    F --> G[media.cdn.kukufm.com]
    E --> G
    G -->|HLS| H[ffmpeg -c copy]
    H --> I[.mp4]
```

The token expires in an hour and is refreshed with its refresh token. The cookie
is bound to the user id and cached for 20 minutes by the tool.

## API surface

Base `https://api.kukufm.com` · `Authorization: Bearer <token>`

| Endpoint | Purpose |
|---|---|
| `POST identitytoolkit…/accounts:signUp?key=` | anonymous Firebase token |
| `GET /api/v3/home/all/` | home rails |
| `GET /api/v2.3/home/all/` | home rails with `item_id` |
| `GET /api/v3/home/category_more_shows` | browse by category or trope |
| `GET /api/v1/genres` · `/api/v1/languages` | taxonomies |
| `GET /api/v1/genres/{slug}/shows` | shows in a genre |
| `GET /api/v2.0/content-types/` | content types |
| `GET /api/v2.0/content-types/{slug}/shows/` | shows of a type (**series** = dramas) |
| `GET /api/v1.0/channels/{id}/` | show detail |
| `GET /api/v2.3/channels/{id}/episodes/` | **episode list** |
| `GET /api/v2/episodes/{id}/` | single episode |
| `GET /api/v3/search/` | search |
| `GET /api/v1.0/utility/slug_mapper/` | slug → id |
| `GET /api/v1.0/utility/refresh-cloudfront-cookie/` | **CDN cookie** |

Every parameter, every response field, and the route-shape rules that let you
probe the API yourself: **[`docs/endpoints.md`](docs/endpoints.md)**.

## Documentation

| File | Contents |
|---|---|
| [`docs/authentication.md`](docs/authentication.md) | anonymous Firebase, Bearer vs jwt, CDN cookies, failure modes |
| [`docs/endpoints.md`](docs/endpoints.md) | 14 endpoints, full parameter tables, response schemas |
| [`docs/media.md`](docs/media.md) | HLS layout, audio groups, ffmpeg recipe, verified output |

## Notes

- **Premium is reachable with the anonymous token.** Every episode sampled —
  including `is_premium: true` shows — returned a manifest and a cookie. That is
  a property of the API, not something this repo adds.
- A real account token in `src/token.txt` takes priority over the anonymous one.
- `master-with-ad-v2.m3u8` is the ad-stitched ladder; the ffmpeg muxer prints a
  few `Packet corrupt` lines at ad boundaries and the output still decodes clean.
- Content belongs to its respective owners. This repository documents and
  automates access; it does not grant rights to redistribute anything.

## License

MIT — see [LICENSE](LICENSE). Logo © its owner, included for identification only.
