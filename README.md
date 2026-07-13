# elsewhere-autopilot

**Channel 2.** Civilization stress tests on one persistent, original,
openly-fictional planet.

> Original speculative documentary. The place is fictional; the principles are real.

Every episode, without exception:

```
the settlement's SYSTEMS  →  the BIOME that shaped them
     →  one STRESS EVENT  →  SURVIVED / ADAPTED / FAILED
```

Terra Incognita (channel 1, `faceless-autopilot`) is untouched by this repo:
separate secrets, separate schedule, separate voice, separate palette, separate
Shorts. That separation is a rule, not an accident — see
[docs/CHANNEL2_PLAN.md](docs/CHANNEL2_PLAN.md) §0-FINAL.

## Where the world lives

| File | What it is |
|---|---|
| `canon/canon.json` | **The world bible.** Planet, physics, atlas, settlements, organisms, verdict record. Nothing contradicts this file. |
| `canon/art_bible.md` | The look. One K-dwarf sun, basalt and ochre, no glass, no HUD. |
| `canon/pending.json` | Canon the pipeline has *proposed*. Never canon until you move it by hand. |
| `pipeline/canon.py` | Canon as executable infrastructure — brief, validate, verdict-steer. |
| `pipeline/canon_check.py` | The gate. Runs **before** TTS, so a canon break costs a retry, not money. |

**The pipeline may propose. Only you canonise.** Every taste decision about what
exists on this planet is permanently yours.

## The three rules that shaped the code

1. **Continuity is enforced, not hoped for.** A weekly AI pipeline *will* drift.
   So the world is injected into every prompt (`canon.brief`), validated
   deterministically before a second of voice is bought (`canon.validate`), and
   entities carry fixed image seeds (`ai_images._canon_seed`) so a species looks
   the same in episode 30 as in episode 1.

2. **The verdict is steered.** Left alone, this format decays into six
   collapses in a row — collapse is the easiest ending to write and the most
   boring to watch twice. `canon.steer_verdict()` reads the recent record and
   *hands the next episode its ending* before a word is written.

3. **The place is fictional; the mechanisms are not.** `canon_check.py` searches
   the real literature for every mechanism in the script. A fabricated mechanism
   is the one unforgivable error on this channel, and it fails the gate.

## First six episodes

All six are stress tests (approved correction 2). Ecology appears *inside* them
as threat, resource or solution — never as its own episode until the promise is
established. `"This Ocean Is One Animal"` is locked until episode 7 and the code
enforces that (`canon.validate` → `ecology_locked`).

Pilot: **"The Underground City That Cooked Itself"** — see [docs/PILOT.md](docs/PILOT.md).
$5 hard budget.

## Setup

Repo secrets required:

| Secret | For |
|---|---|
| `GEMINI_API_KEY` | scripts (free tier), canon/science check, vision QC |
| `ANTHROPIC_API_KEY` | better scripts (optional; falls back to Gemini) |
| `FAL_KEY` | FLUX stills + Wan motion shots — **this channel's main cost** |
| `ELEVENLABS_API_KEY` | the English narrator |
| `ELEVENLABS_VOICE_ID` | **pick the voice once and never change it** |
| `PEXELS_API_KEY` | optional — stock is disabled by default (`ai_images.stock_allowed: false`) |

> ⚠️ The Gemini and Pexels keys previously used by channel 1 were exposed and
> **must be rotated before this repo runs.** Rotating covers both repos at once.

Cadence: one long-form Wednesday, three Shorts Thu/Sat/Sun. Never faster until
ten episodes hold retention.

## Validation gate (before committing to 30 episodes)

Three pilots. Continue only if ≥3 of: browse CTR ≥4.5%, 30s retention ≥65%,
APV ≥45%, subs/1k ≥4 — and the killer signal: **comments asking about the
planet.** If people ask what's in the ocean, the world is working.
