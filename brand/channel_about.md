# ELSEWHERE — channel setup kit

Everything needed to create the YouTube channel. Files in this folder:

| File | Where it goes |
|---|---|
| `avatar.png` (800×800) | Channel profile picture |
| `banner.png` (2560×1440, safe-area centred) | Channel banner |
| `yt_watermark.png` (300×300) | Studio → Customisation → Branding → Video watermark |
| `watermark.png` | used automatically by the render pipeline |
| `logo.png` / `logo_mark.png` | thumbnails, end cards, socials |

## Handle candidates (check availability, in order)

1. `@ElsewhereCaseFiles`
2. `@ElsewhereAtlas`
3. `@TheElsewhereSurvey`

(`@Elsewhere` alone will be taken; the qualifier also helps search.)

## Channel description (paste into About)

> Civilization stress tests from a planet that never was.
>
> Every episode is one case file: a settlement on the planet Kelvara, the
> systems that kept it alive, one stress event, and a verdict —
> SURVIVED, ADAPTED, or FAILED.
>
> The place is fictional; the principles are real. Every mechanism in every
> episode is built on real engineering and real biology you can go and look
> up. New case files weekly.

## Channel settings

- Language: **English**. Audience: not made for kids.
- Keywords: `speculative documentary, worldbuilding, engineering failures,
  hard science fiction, alien planet, stress test, case file, atlas`
- Upload defaults → description must START with the truth label:
  `Original speculative documentary. The place is fictional; the principles are real.`
- Publish window: **15:00–17:00 UTC** (US morning + EU evening — English
  channel; channel 1's IST logic does not apply).
- Do NOT cross-post Shorts to channel 1 for 90 days (config
  `cross_post_to_channel_1: false`).

## Brand rules (one-look discipline)

- Palette: basalt `#1C1814`, paper `#E8DCC8`, amber `#D98A3B`, copper
  `#8C6A4A`. The red `#C43B2E` appears ONLY on the failure path — never in
  branding, never in thumbnails.
- No navy, no glass/HUD — that's Terra Incognita's language.
- The mark is the atlas: survey ring, relief contours, one located marker.
  Regenerate any asset with `python brand/generate_brand.py`.
