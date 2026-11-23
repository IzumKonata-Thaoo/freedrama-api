# Media

Streams are HLS on `media.cdn.kukufm.com`, fronted by CloudFront with **signed
cookies**. Without the cookie every request is `403`; with it, plain HLS.

## Where the URL comes from

The episode object carries it:

```json
"content": {
  "url":              "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
  "hls_url":          "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
  "video_hls_url":    "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8",
  "premium_audio_url":"https://d1l07mcd18xic4.cloudfront.net/audio/<uuid>.m3u8",
  "duration": 173,
  "sprite_sheet_key": "https://d1l07mcd18xic4.cloudfront.net/episode_video_scrubbing/…jpg"
}
```

Three of the fields point at the same master playlist. `premium_audio_url` is an
**audio-only** rendition on a different CloudFront distribution.

## Manifest

`master-with-ad-v2.m3u8`:

```m3u8
#EXTM3U
#EXT-X-VERSION:3

#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Original",DEFAULT=YES,AUTOSELECT=YES,LANGUAGE="hi",CHANNELS="2",URI="original-audio-2.m3u8"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Hindi (Audio Description)",DEFAULT=NO,AUTOSELECT=NO,LANGUAGE="hi-ad",CHANNELS="2",CHARACTERISTICS="public.accessibility.describes-video",URI="ad-master-2.m3u8"

#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Original",DEFAULT=YES,AUTOSELECT=YES,LANGUAGE="hi",CHANNELS="2",URI="original-audio-1.m3u8"
…
```

Audio is a **separate rendition group**, as with most modern HLS. Anything that
concatenates video segments and stops there produces a silent file.

## Downloading

The cookie is the whole trick:

```bash
# 1. get the cookie (one API call)
curl -s -H "Authorization: Bearer $TOKEN" \
     https://api.kukufm.com/api/v1.0/utility/refresh-cloudfront-cookie/
```

```bash
# 2. hand it to ffmpeg
ffmpeg -headers "Cookie: CloudFront-Policy=…; CloudFront-Signature=…; CloudFront-Key-Pair-Id=…" \
       -i "https://media.cdn.kukufm.com/video-episode/<uuid>/master-with-ad-v2.m3u8" \
       -c copy -bsf:a aac_adtstoasc out.mp4
```

`fdgrab.py` does exactly this, caching the cookie for 20 minutes and refreshing it
when it ages out.

## Verified output

| episode | duration | size | codec |
|---|---|---|---|
| Mr. Idiot, Hero Husband — Ep 1 | 174.4 s | 35.5 MB | h264 720×1280 + aac |
| My Handsome Bodyguard — Ep 1 | 173.0 s | 38.8 MB | h264 1080×1920 + aac |
| My Handsome Bodyguard — Ep 2 | 127.9 s | 24.9 MB | h264 720×1280 + aac |

The 1080p rung exists on some episodes and not others — the master playlist picks
per encode, so resolution varies per episode.

## Notes

- `master-with-ad-v2` is the ad-stitched ladder; the same episode is served whole,
  the name just reflects how it was packaged.
- Some segments log `Packet corrupt` in the muxer while remuxing. The output still
  decodes clean; it comes from ad-boundary discontinuities in the ladder.
- The CloudFront policy is bound to the requesting user id and expires within the
  hour. Re-fetch it rather than reusing an old one.
- The sprite sheet (`sprite_sheet_key`) and its metadata JSON are also signed;
  they are useful for chapter thumbnails if you want them.
