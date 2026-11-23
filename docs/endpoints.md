# Endpoints

Base: `https://api.kukufm.com`
Auth: `Authorization: Bearer <firebase-or-account-token>` on **every** call.
Headers: see [authentication](authentication.md#2-the-header-scheme-matters).

Everything is `GET`. All ids are integers, all slugs are lowercase-hyphenated.

| # | Endpoint | Purpose |
|---|---|---|
| 1 | `/api/v3/home/all/` | home rails |
| 2 | `/api/v2.3/home/all/` | home rails with channel ids |
| 3 | `/api/v3/home/category_more_shows` | browse by category / trope |
| 4 | `/api/v1/genres` | genre list |
| 5 | `/api/v1/languages` | language list |
| 6 | `/api/v1/genres/{genre}/shows` | shows in a genre |
| 7 | `/api/v2.0/content-types/` | content type list |
| 8 | `/api/v2.0/content-types/{type}/shows/` | shows of a type (**series** = dramas) |
| 9 | `/api/v1.0/channels/{id}/` | show detail |
| 10 | `/api/v2.3/channels/{id}/episodes/` | **episode list** |
| 11 | `/api/v2/episodes/{id}/` | single episode |
| 12 | `/api/v3/search/` | search |
| 13 | `/api/v1.0/utility/slug_mapper/` | slug → id |
| 14 | `/api/v1.0/utility/refresh-cloudfront-cookie/` | **CDN cookie** |

---

## 1 · `GET /api/v3/home/all/`

| Param | Type | Default | Verified behaviour |
|---|---|---|---|
| `page` | int | 1 | page 2 returns a different rail set (9 sections); page 1 returns the full layout |

```json
{
  "items": [
    {
      "slug": "banner",
      "view_type": "banner",
      "type": "banner",
      "title": "Banner",
      "is_active": true,
      "items": [
        {
          "uri": "app://kukufm/show/love-ki-century/",
          "image": "https://images.cdn.kukufm.com/…",
          "slug": "love-ki-century",
          "metadata": {
            "cta_text": "Start Free Trial",
            "epi_info_text": "762 Eps",
            "styled_tropes": [
              { "tropes": [ { "text": "Whodunit" } ],
                "uri": "/api/v3/home/category_more_shows?size=10&show_category=Whodunit&selected_tab=popular&item_type=trope" }
            ]
          }
        }
      ]
    }
  ],
  "has_more": true,
  "next_page_num": 2,
  "total_pages": 3,
  "nav_bar_items": [ { "title": "All", "slug": "all", "is_selected": true } ],
  "metadata": {}
}
```

Section `type` values seen: `banner`, `groups`, plus horizontal carousels.
Every show reference is a `uri` of the form `app://kukufm/show/{slug}/`.

## 2 · `GET /api/v2.3/home/all/`

Same rails, but banner entries use `banners[]` and each carries **`item_id`**,
the numeric channel id:

```json
{ "items": [ { "slug": "banner", "banners": [
  { "item_id": 261754, "uri": "app://kukufm/show/mr-idiot-hero-husband/" } ] } ] }
```

| Param | Verified behaviour |
|---|---|
| `page` | accepted but only page 1 has data (`page=2` → `items: []`) |

Use this one when you need ids without a second lookup.

## 3 · `GET /api/v3/home/category_more_shows`

| Param | Type | Default | Required | Notes |
|---|---|---|---|---|
| `category` | string | — | yes* | genre slug (`romance`, `action-1`) **or** a trope name (`Blackmail`) |
| `page` | int | 1 | no | 1-based |
| `size` | int | 10 | no | page size |
| `selected_tab` | string | `popular` | no | feed uses `popular` |
| `item_type` | string | — | when using `show_category` | `trope` |
| `show_category` | string | — | no | trope filter, as emitted by the feed's own links |

\* `category` is what the endpoint validates; the feed's generated links pass
`show_category` + `item_type` instead and both work.

```json
{
  "items": [ { "view_type": "grid_single_show", "type": "groups", "title": "",
    "items": [ { "uri": "app://kukufm/show/the-sea-kings-bride/",
                 "slug": "the-sea-kings-bride", "image": "…" } ] } ],
  "has_more": true, "next_page_num": 2, "total_pages": 12,
  "nav_bar_items": [ … ], "metadata": {}
}
```

## 4 · `GET /api/v1/genres`

No params. 36 entries.

```json
{ "genre": [ { "id": 82, "title": "Action", "slug": "action-1",
  "uri": "app://app/genres/action-1", "web_uri": "/genres/action-1",
  "icon": "https://images.cdn.kukufm.com/…",
  "icon_sizes": { "16": "…" } } ] }
```

`/api/v2/genres` and `/api/v3/genres` return the identical document.

## 5 · `GET /api/v1/languages`

No params.

```json
{ "languages": [ { "id": 1, "title": "हिंदी", "title_secondary": "Hindi",
  "slug": "hindi", "color": "#FD6233", "image": "…" } ] }
```

## 6 · `GET /api/v1/genres/{genre_slug}/shows`

| Param | Type | Default | Verified behaviour |
|---|---|---|---|
| `page` | int | 1 | 10 shows per page; `has_next` stays true past page 4 |
| `lang` | string | — | accepted, no observable effect on the page |

```json
{
  "genre": { "id": 82, "title": "ऐक्शन", "slug": "action-1" },
  "cu_shows": [
    { "id": 283463, "slug": "mera-pati-sniper-no1", "title": "Mera Pati Sniper No.1",
      "image": "…", "language": "hindi",
      "published_on": "2026-10-08T07:12:51+00:00", "status": "live",
      "n_listens": 10762499, "is_premium": true, "is_fictional": true,
      "duration_s": 21815, "n_episodes": 190,
      "uri": "app://kukufm/show/mera-pati-sniper-no1/",
      "web_uri": "/show/mera-pati-sniper-no1" }
  ],
  "has_next": true
}
```

## 7 · `GET /api/v2.0/content-types/`

```json
{ "content_types": [
  { "id": 18, "title": "Learning", "slug": "learning", "uri": "app://kukufm/content-types/learning" }
] }
```

Full list: `learning, kuku-upskill, entertainment, movie, novel, quiz, series,
bytes, podcast, story, audio-book, book-summary, news, course, poems-shayari`.

**`series` is the drama catalogue.** `movie` and `entertainment` return empty
lists on this app.

## 8 · `GET /api/v2.0/content-types/{type_slug}/shows/`

| Param | Type | Default | Verified behaviour |
|---|---|---|---|
| `page` | int | 1 | 20 shows per page, `has_next` paginates |
| `page_size` | int | 20 | honoured |
| `lang` | string | `english` | accepted |

Invalid slug → `404 {"error_code":"INVALID_CONTENT_TYPE"}`.

```json
{ "content_type": { "slug": "series", "title": "Series" },
  "shows": [ { "id": 276857, "slug": "billionaire-waiter", "title": "Billionaire Waiter",
               "n_episodes": 80, "is_premium": true, "image": "…" } ],
  "has_next": true, "has_more": true }
```

## 9 · `GET /api/v1.0/channels/{channel_id}/`

```json
{ "channel": { "id": 261754, "slug": "mr-idiot-hero-husband",
  "title": "Mr. Idiot, Hero Husband", "language": "hindi",
  "is_premium": true, "image": "…", "n_episodes": 94 } }
```

`/api/v2/channels/{id}/` returns the same object under the same key.

## 10 · `GET /api/v2.3/channels/{channel_id}/episodes/`  ⭐

| Param | Type | Default | Verified behaviour |
|---|---|---|---|
| `page` | int | 1 | 1-based |
| `page_size` | int | 10 | 10 / 20 / 50 / 100 all honoured; 100 returns the whole 94-episode show in one call |

```json
{
  "show":   { "id": 261754, "slug": "mr-idiot-hero-husband", "title": "Mr. Idiot, Hero Husband" },
  "episodes": [
    {
      "id": 970769,
      "slug": "episode-1-934",
      "title": "Ep 1 - Janamdin Par Talaak?",
      "index": 1,
      "duration_s": 173,
      "is_premium": true,
      "is_locked": false,
      "is_play_locked": false,
      "show_id": 261754,
      "season_no": 1,
      "season_index": 1,
      "season_n_episodes": 94,
      "n_likes": 89531,
      "n_comments": 4,
      "n_plays": null,
      "published_on": "…",
      "has_srt": false,
      "can_download": true,
      "content": {
        "url":               "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "hls_url":           "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "video_hls_url":     "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "premium_audio_url": "https://d1l07mcd18xic4.cloudfront.net/audio/<uuid>.m3u8",
        "duration": 173,
        "sprite_sheet_key":  "https://d1l07mcd18xic4.cloudfront.net/episode_video_scrubbing/…jpg"
      }
    }
  ],
  "has_more": true,
  "n_episodes": 94,
  "n_pages": 10,
  "page": 1,
  "reminder": null,
  "support_sticker": null
}
```

## 11 · `GET /api/v2/episodes/{episode_id}/`

Same episode object, wrapped in `{"episode": {...}}`. Use it when a list entry
has no `content` block (it happens on pages 2+ of some shows).

## 12 · `GET /api/v3/search/`

| Param | Type | Default | Required | Verified behaviour |
|---|---|---|---|---|
| `q` | string | — | **yes** | missing → `{"code":"SEARCH_QUERY"}` |
| `page` | int | 1 | no | |
| `lang` | string | — | no | accepted, count unchanged |
| `type` | string | — | no | accepted, count unchanged |

```json
{
  "languages": [ { "is_selected": true, "id": 1, "slug": "hindi" } ],
  "items": [ { "metadata": { … },
    "show": { "id": 274536, "slug": "eternal-love-1", "title": "Eternal Love",
              "n_episodes": 76, "is_premium": true, "is_reel": true },
    "view_type": "…", "slug": "eternal-love-1" } ]
}
```

`show.is_reel: true` marks the short-drama (TV) items.

## 13 · `GET /api/v1.0/utility/slug_mapper/`

| Param | Type | Required | Notes |
|---|---|---|---|
| `item_type` | string | yes | `show` (validates as `cu_show`), `channel`, … |
| `slug` | string | yes | the slug to resolve |

Resolves to the numeric id when the slug belongs to the type you asked for;
otherwise `404 INVALID_PARAM "Invalid cu_show <slug>"`.

## 14 · `GET /api/v1.0/utility/refresh-cloudfront-cookie/`  ⭐

No params. Returns the CDN credentials:

```json
{ "cookies": { "CloudFront-Policy": "eyJ…", "CloudFront-Signature": "G9Ov…",
               "CloudFront-Key-Pair-Id": "K2…" } }
```

Decoded policy:

```json
{"Statement":[{"Resource":"https://media.cdn.kukufm.com/*",
  "Condition":{"DateLessThan":{"AWS:EpochTime":1795435178}},
  "CustomData":{"user_id":415123744}}]}
```

Bound to the user id, ~1 hour. Send as one `Cookie` header.

---

## Identifier map

```text
home feed (v2.3)      item_id                → channel id
content-types/series  shows[].id             → channel id
genres/{slug}/shows   cu_shows[].id          → channel id
channel id            → /api/v2.3/channels/{id}/episodes/
episode id            → content.hls_url
```

## Route-shape rule

| Response | Meaning |
|---|---|
| `{"error": "No matching url pattern found"}` | route does not exist |
| `{"error_code": "INVALID_…"}` | route exists, argument wrong |
| `401 "Login required to access this resource"` | route exists, token missing |
| `401 "Invalid user"` | token present but wrong scheme (`jwt` instead of `Bearer`) |
| Spring `"No static resource api/v3/…"` | v3 prefix exists, sub-path does not |
