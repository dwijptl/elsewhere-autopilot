# Build Verification — elsewhere-autopilot vs approved plan

Date: 2026-07-13 · Audited against `docs/CHANNEL2_PLAN.md` §0-FINAL (the
approved consensus verdict + Dwij's three corrections). Every item below is
verified in code, with evidence, not by re-reading the docs.

Test suite: **63 passed, 0 failed** (`python -m pytest tests/`).

## Approved spec vs implementation

| # | Approved item (§0-FINAL) | Status | Evidence |
|---|--------------------------|--------|----------|
| 1 | Format spine: Civilization Stress Test — systems → biome → stress event → SURVIVED/ADAPTED/FAILED | ✅ | `script_gen.py` episode prompt; verdict vocabulary enforced in `canon.py` gate; rendered by `remotion/src/dossier.tsx` verdict card |
| 2 | Verdict mix kept honest (imported outcome-ratio tracking) | ✅ | `canon.py:125 steer_verdict()` — reads the record, hands the next episode its ending, refuses 3 identical verdicts in a row; wired at `script_gen.py:560,698` |
| 3 | Correction 1: one continuity, not a hard one-planet rule | ✅ | `config.yaml:30-33` (`continuity: "one atlas, one timeline, one physics — the planet is season 1"`) |
| 4 | Correction 2: first SIX videos all stress-test; ecology locked until then | ✅ | `config.yaml:50 ecology_episode_unlocks_after: 6`; enforced deterministically in `canon.py:214-221` (`ecology_locked` rule) |
| 5 | Correction 3: viewer canon = polls on creator-designed options only; permission + license before using submissions | ✅ | `config.yaml:38 viewer_canon: "polls_on_creator_options_only"` |
| 6 | Planet name NEVER in the title | ✅ | `canon.py:169-173` (`planet_name_in_title` rule, regex, deterministic fail); reinforced in the script prompt (`script_gen.py:719`) |
| 7 | Truth label: "The place is fictional; the principles are real" | ✅ | present in `config.yaml`, `script_gen.py`, `canon_check.py` (goes in every description) |
| 8 | Teased regions cannot host an episode | ✅ | `canon.py:70,210` (teased-only regions excluded + gate rule); `atlasgen.py:157` refuses to locate on unrevealed regions |
| 9 | Canon validated BEFORE money is spent (pre-TTS) | ✅ | `run.py:307` — `canon_check.check_script()` runs before TTS/assets; gate mode in config |
| 10 | Pipeline proposes canon, only Dwij canonises | ✅ | `run.py:308-309` — proposals go to `canon/pending.json`, never `canon.json` |
| 11 | Species/entity visual consistency | ✅ | fixed image seeds stored per entity in `canon/canon.json` (e.g. `"seed": 40117`), reused by `ai_images.py` |
| 12 | Pilot: "The Underground City That Cooked Itself" — desert biome, dust/organism ecology, first FAILED verdict, ocean tease | ✅ | `docs/PILOT.md`; used as the title model in the script prompt |
| 13 | Separate repo, own schedules/secrets/canon/style pack | ✅ | this repo; workflows reference only its own secrets; `cross_post_to_channel_1: false` (90-day non-cannibalization, `config.yaml:172-173`) |
| 14 | NO glass-HUD language (channel 1's identity) | ✅ | dossier style pack (`remotion/src/dossier.tsx`); legacy `glass`/`map` names survive only as internal contract keys, translated at the normalize boundary |
| 15 | AI-first assets, stock demoted to reference | ✅ | `assets.py` inverted priority; `ai_images_max` / `ai_images_max_flux` budgets in `config.yaml:169-170` |

## TTS decision (2026-07-13): Sarvam bulbul:v3, speaker `shubh`

Applied today, after the initial push:

- `config.yaml` — `tts.engine: "sarvam"`, `sarvam_model: "bulbul:v3"`,
  `sarvam_speaker: "shubh"`. ElevenLabs kept as dormant alternative; Kokoro
  remains the free offline fallback so a run never dies.
- **Bug fixed:** `tts.py` passed the channel language `en-us` straight to
  Sarvam, whose enum only accepts `en-IN` for English (channel 1 never hit
  this — it sent `hi-IN`). New `_sarvam_lang()` maps `en-*` → `en-IN`.
  Without this, the first pilot run would have 422'd on every scene.
- **Hardening:** Sarvam speaker names are case-sensitive lowercase per their
  docs. The `SARVAM_SPEAKER` env/secret is now lowercased defensively, so a
  secret saved as `Shubh` still works. Verify the secret value anyway.
- 2 new tests cover both (`tests/test_tts.py`), suite now 63.

## Known gaps (deliberate, tracked)

1. ~~Wan motion stage not wired to fal~~ **CLOSED 2026-07-13** —
   `pipeline/wan_motion.py`: Wan-2.1 i2v via the fal queue API. Hard cap
   `motion.max_per_video` (2), submit-all-then-poll, 81-frame billing floor,
   canon seed reuse, and fail-open at every step (a failed shot leaves the
   still+parallax; the run never dies). Motion shot replaces its source
   still in place so visual-beat bindings survive. 7 tests. The $5 pilot is
   now runnable end to end.
2. ~~Planet name "Kelvara" is PROVISIONAL~~ **CONFIRMED by Dwij 2026-07-13**
   — Kelvara is canon.
3. **Key rotation** for the previously exposed Gemini/Pexels keys — rotate,
   then update secrets in BOTH repos.
4. `ELEVENLABS_*` secrets now optional (engine is Sarvam); harmless if set.
