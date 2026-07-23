# PROJECT LOG — Bharat Ke Rahasya / elsewhere-autopilot

> Session tracker for humans and AI assistants. Read this before changing
> anything. Last updated: **2026-07-22** (Claude session).

## What this is

Channel 2: Hindi **Indian/dharmic mystery investigation documentaries**
(भारत के रहस्य, working name — `config.yaml` → `brand.name`). Rebased
2026-07-22 on channel 1 (`faceless-autopilot`) at its latest state — 30
topic-driven style packs with layout/motion/pacing DNA, seeded per-video
jitter, Hinglish keyword routing, grounded fact-check, Sarvam voice —
then converted to the mystery genre. The prior alien-planet concept
(ELSEWHERE, see old history before this date) was replaced per owner
decision after Studio Trends showed Hindi mystery long-form outperforming
(reference videos: Dwarka 48K / Shambhala 60.8K / Titanic-book 42.9K from
small channels — see docs/MYSTERY_GENRE_STUDY.md).

## Genre conversion (what differs from channel 1)

- `config.yaml`: mystery niche (5 topic families, real-anchor hard rule,
  respect rules), tone, brand BHARAT KE RAHASYA, accent #D8A24A antique
  gold, target 8.5 min (scale after retention data).
- `pipeline/script_gen.py`: INVESTIGATION ENGINE replaces the simulation
  engine — changing_variable is the documented TIMELINE (YEAR); five-act
  skeleton (दावा/स्रोत/इतिहास/सिद्धांत/जो बचा है); THREE REGISTERS always
  labeled (शास्त्र/इतिहास/विज्ञान); RESPECT rules (no mockery, no
  communal/political framing, no invented documents, no conspiracy
  claims); ENDING RULE — factual loops close, the one central mystery may
  stay honestly open. No next-topic tease.
- `pipeline/run.py`: mystery Hindi metadata (description header, tags,
  hashtags, CTA).
- State files reset; channel-1 docs removed.

## Length roadmap (won't-die-mid-run rule)

The owner wants fully-researched complete-package episodes even at 30-60
min. HARD RULE agreed 2026-07-22: a length tier ships only when a run
CANNOT die mid-job. Current tier: **12 min** (proven ~2.5-3h total vs
5.5h job limit on free runners). Next tier (30-60 min) requires
SEGMENTED RENDERING — split the composition into N frame-range chunks,
render each in its own matrix job (each far under the limit), concat
with ffmpeg in a final job. SHIPPED 2026-07-22 as the Make Long Video
workflow: prepare job (checkpoint.pkl before pixels) -> 4 parallel
frame-range chunk jobs (render_chunk.py, h264+PCM mkv) -> finish job
(run_long_finish.py: sample-accurate concat -> final.mp4 -> resumed
finalize). Default 22 min via the `minutes` dispatch input; single-job
Make Video stays the proven path for <=12 min. If a chunk fails,
"Re-run failed jobs" reuses the prepare artifact. Research depth is already unlimited: the
grounded dossier (pipeline/research.py) is built before writing and the
script must cover ALL of it (no-skipping rule) — depth lives inside the
runtime, and runtime grows only with infra.

## Pending — owner actions

1. Set repo secrets (GEMINI, PEXELS, SARVAM; optional FAL, ANTHROPIC).
2. Regenerate `brand/watermark.png` for the new identity
   (`brand/generate_brand.py`) — the copied watermark is channel 1's.
3. Decide final channel name (one line in config) + create the YouTube
   channel with matching handle/branding.
4. First pilot: run `Make Video` manually with a forced topic that has a
   strong documented anchor (e.g. "द्वारका: समुद्र में मिले 5000 साल पुराने
   अवशेष" or "रूपकुंड: कंकालों की झील"). Review with the genre study open.
5. Adjust `Make Video` / `Make Short` cron schedules if both channels
   shouldn't render simultaneously.

## Conventions (inherited from channel 1 — IMPORTANT)

- Every change: syntax-check, push, verify CI green.
- Fail-open philosophy: new features degrade gracefully, never block a
  scheduled render.
- No self-hosted runners / publisher workflows (public repo, secrets).
- New manifest fields: `(x as any)` casts in TSX.
- Respect + three-register rules in scripts are non-negotiable — they are
  the channel's policy shield and its brand.

## 2026-07-23 — Make Long Video run #1 postmortem
Run #1 (सोन भंडार, 22 min) died: prepare hit its 150-min timeout with ZERO
log output. Two stacked causes: (1) stdout was block-buffered, so the killed
job lost every progress line — undiagnosable from CI; (2) Sarvam TTS failing
slowly — synth_scene retried it fresh per scene (4 attempts x 180s timeout
per chunk), so ~30 scenes could burn 4-6h before Kokoro fallback.
Fixes shipped: PYTHONUNBUFFERED=1 in all three video workflows; Sarvam
circuit breaker (2 consecutive scene failures -> Kokoro for the rest of the
run) + chunk timeout 180s->60s; prepare timeout 150->240 min; [stage] t+Nm
elapsed stamps in run.py. Regression test: tests/test_render_guard.py.
NOTE: Sarvam has now failed in runs #9 and #1(long) — check credits/status
at dashboard.sarvam.ai before the next run if the cloned voice matters.

## 2026-07-23 — Long run #2: PIPELINE PROVED, then cost surgery
Run #2 delivered end-to-end: 16.3-min segmented video (25 scenes, 4 chunks
concat'd clean, renderer remotion-segmented) — the architecture works.
Draft flags: Kokoro fallback again (NB: Sarvam STT/align worked 24/25, so
the key is alive — bulbul TTS specifically failing); 5 render-audit shots;
2 story violations; runtime 16.2/22 (Kokoro pace — calibration.json now
carries this run's measured wpm, next budget auto-corrects); fact-check
skipped: fallback model gemini-3-flash 404s on v1beta generateContent and
masked what was likely free-tier quota exhaustion on 2.5-flash.
OWNER DIRECTIVE — cost down: llm.provider now "gemini" (Anthropic dropped
entirely, ANTHROPIC_API_KEY removed from all four workflows); Gemini chain
2.5-flash -> 2.5-flash-lite -> 2.0-flash -> flash-latest (separate free
quota buckets); hero shots kling 2.5-turbo primary + cap $1.20->$0.60;
FLUX schnell primary (dev fallback); gemini-3-* names purged.
Est. per-video spend now: FAL <= ~$0.6 hard-capped, Gemini free tier,
Sarvam ~Rs 54/22-min when its TTS returns. Zero Anthropic.

## 2026-07-23 (later) — Why 16 min instead of 22, fixed three ways
Root cause chain: (1) segmented runs LOST all prepare-side repo state —
calibration.json / styles_used.txt / assets_used.json are written on the
prepare runner but the history commit runs on the finish runner (run #2's
commit had only topics_done + beats). Now: prepare snapshots them into
<outdir>/repo_state/ (rides the artifact), run_long_finish restores before
finalize. (2) Pace was engine-blind: Kokoro ~177 wpm vs Sarvam ~130 — new
tts.preflight() pings Sarvam once (~Rs 0.02) BEFORE the word budget, opens
the breaker immediately if down, and calibration entries now carry engine
so the budget plans at the pace of the voice that will actually speak.
(3) CLAMP 0.25 -> 0.40 (177 is 36% over the configured 130; the old band
made 22-min targets mathematically unreachable on Kokoro).
calibration.json seeded with run #2's measured reality (2860w/971.5s =
176.6 wpm, kokoro). Expected: next Kokoro run ~22 min; first Sarvam run
may drift long once, then self-corrects.
