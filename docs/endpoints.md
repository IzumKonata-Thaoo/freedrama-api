# Endpoints

Base: `https://api.kukufm.com` · every call needs `Authorization: Bearer <token>`
(see [authentication](authentication.md)). All endpoints are `GET` unless noted.

---

## `GET /api/v3/home/all/`

The home feed. Sections carry `uri` pointers like
`app://kukufm/show/{slug}/`.

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
  "total_pages": …,
  "nav_bar_items": [ … ],
  "metadata": {}
}
```

The `metadata.styled_tropes[].uri` values are themselves working API calls — the
feed hands you the browse queries.

## `GET /api/v2.3/home/all/`

Same shape, but banner items carry `item_id` — **the numeric channel id**, which
is what the episode endpoint needs. Prefer this one for building a catalogue.

```json
{ "items": [ { "banners": [ { "item_id": 261754,
  "uri": "app://kukufm/show/mr-idiot-hero-husband/" } ] } ] }
```

## `GET /api/v3/home/category_more_shows`

| Query | Notes |
|---|---|
| `category` | genre slug (`romance`, `action-1`) or a trope name (`Blackmail`) |
| `show_category` | trope-style filter, used by the feed's own links |
| `page` | 1-based |
| `size` | page size |
| `selected_tab` | `popular` |
| `item_type` | `trope` when filtering by trope |

```json
{
  "items": [ { "view_type": "grid_single_show", "type": "groups",
    "items": [ { "uri": "app://kukufm/show/the-sea-kings-bride/",
                 "slug": "the-sea-kings-bride", "image": "…" } ] } ],
  "has_more": true, "next_page_num": 2, "total_pages": 12
}
```

---

## `GET /api/v1/genres`

```json
{ "genre": [ { "id": 82, "title": "Action", "slug": "action-1",
  "uri": "app://app/genres/action-1", "web_uri": "/genres/action-1",
  "icon": "https://images.cdn.kukufm.com/…" } ] }
```

36 genres. `/api/v2/genres` and `/api/v3/genres` return the same list.

## `GET /api/v1/languages`

```json
{ "languages": [ { "id": 1, "title": "हिंदी", "title_secondary": "Hindi",
  "slug": "hindi", "color": "#FD6233" } ] }
```

---

## `GET /api/v1/genres/{genre_slug}/shows`

Shows inside a genre.

| Query | Notes |
|---|---|
| `page` | 1-based |

```json
{
  "genre": { "id": 82, "title": "ऐक्शन", "slug": "action-1" },
  "cu_shows": [
    {
      "id": 283463,
      "slug": "mera-pati-sniper-no1",
      "title": "Mera Pati Sniper No.1",
      "image": "…",
      "language": "hindi",
      "published_on": "2026-10-08T07:12:51+00:00",
      "status": "live",
      "n_listens": 10762499,
      "is_premium": true,
      "is_fictional": true,
      "duration_s": 21815,
      "n_episodes": 190,
      "uri": "app://kukufm/show/mera-pati-sniper-no1/",
      "web_uri": "/show/mera-pati-sniper-no1"
    }
  ],
  "has_next": true
}
```

---

## `GET /api/v1.0/channels/{channel_id}/`

Show detail. `channel.id` is the id the episode endpoint wants.

```json
{ "channel": { "id": 261754, "slug": "mr-idiot-hero-husband",
  "title": "Mr. Idiot, Hero Husband", "image": "…", … } }
```

`/api/v2/channels/{id}/` returns the same object.

## `GET /api/v2.3/channels/{channel_id}/episodes/`

**The episode list.**

| Query | Default | Notes |
|---|---|---|
| `page` | 1 | |
| `page_size` | 10 | 20 works |

```json
{
  "show": { "id": 261754, "slug": "mr-idiot-hero-husband",
            "title": "Mr. Idiot, Hero Husband", "image": "…" },
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
      "n_likes": 89531,
      "n_comments": 4,
      "published_on": "…",
      "content": {
        "url": "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "hls_url": "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "video_hls_url": "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
        "premium_audio_url": "https://d1l07mcd18xic4.cloudfront.net/audio/<uuid>.m3u8",
        "duration": 173,
        "sprite_sheet_key": "https://d1l07mcd18xic4.cloudfront.net/episode_video_scrubbing/…jpg"
      },
      "has_srt": false,
      "can_download": true
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

The `content` block is the whole media pipeline in one object: video HLS, a
separate premium audio HLS, and a sprite sheet for scrubbing.

## `GET /api/v2/episodes/{episode_id}/`

Single episode, same object shape. Use it when a list entry has no `content`.

## `GET /api/v1.0/episodes/{episode_id}/comments/`

Comments for an episode (paginated).

---

## `GET /api/v3/search/?q=&page=`

| Query | Notes |
|---|---|
| `q` | free text |
| `page` | 1-based |

```json
{
  "languages": [ { "is_selected": true, "id": 1, "slug": "hindi" } ],
  "items": [
    {
      "metadata": { … },
      "show": { "id": 274536, "slug": "eternal-love-1",
                "title": "Eternal Love", "n_episodes": 76,
                "is_premium": true, "is_reel": true },
      "view_type": "…",
      "slug": "eternal-love-1"
    }
  ]
}
```

`q` is mandatory: omitting it returns `{"code":"SEARCH_QUERY"}`.

---

## `GET /api/v2.0/content-types/`

```json
{ "content_types": [ { "id": 18, "title": "Learning", "slug": "learning",
  "uri": "app://kukufm/content-types/learning" } ] }
```

Pairs with `/api/v2.0/content-types/{slug}/shows/?page=&page_size=&lang=`.

---

## Identifier map

```text
home feed          -> item_id  = channel id
genre browse       -> cu_show slug  (needs slug_mapper for some routes)
channel id         -> /api/v2.3/channels/{id}/episodes/
episode id         -> content.hls_url
```

`/api/v1.0/utility/slug_mapper/?item_type=show&slug=<slug>` maps a show slug to
its id. `item_type=channel` uses the same route with a different validator.

## Route-shape rule

| Response | Meaning |
|---|---|
| `{"error": "No matching url pattern found"}` | route absent |
| `{"error_code": "INVALID_…"}` | route present, argument wrong |
| `401 "Login required"` | route present, token missing |
| Spring `"No static resource …"` | v3 prefix present, sub-path absent |
