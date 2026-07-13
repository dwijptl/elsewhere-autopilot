# Art bible — ELSEWHERE

The look is the moat. Channel 1 (Terra Incognita) is glass, HUD, navy + amber,
urgent simulation grammar. This channel must never be mistaken for it.

**Grammar: a matte archival engineering dossier.** Field photography from a
survey that actually happened, filed by people who were tired. Not concept art.
Not a game trailer. Not "epic".

## Non-negotiables (every image prompt carries these)

- **Light**: a K-dwarf star. Warm, low-angle, dim — permanent late afternoon
  even at noon. No blue-white sunlight. No white highlights; the brightest
  value in frame is a warm off-white (#F2E6D6), never pure #FFF.
- **Palette**: basalt black, ochre dust, warm paper, oxidised copper. One amber
  accent (#D98A3B) for anything engineered — pipes, lights, system flows. One
  red (#C43B2E) reserved EXCLUSIVELY for the failure path: use it and the
  viewer learns something is about to break.
- **Camera**: documentary lenses. 24mm / 35mm / 85mm, hand-held or tripod,
  eye-level or slightly low. No drone-swoop hero angles. No dutch tilts.
- **Grain**: a real photographic image. Slight sensor noise, slight chromatic
  aberration at the edges, imperfect focus. A too-clean image reads as AI.
- **Scale**: put a human, a doorway or a machine in frame. Awe without a
  reference object is just wallpaper.
- **Restraint**: no lens flares, no volumetric god-rays, no floating particles
  unless dust is the subject, no glowing runes, no chrome.

## Banned (these are the AI-slop tells)

Neon cyan/magenta rim light · symmetrical hero compositions · glossy chrome ·
hexagonal HUD overlays (that's channel 1) · lens flare · "cinematic 8k
hyperrealistic" prompt-speak · creatures with faces staring at camera ·
crowds of identical figures · text rendered inside the image.

## Prompt skeleton

> Documentary field photograph, [SUBJECT], [SETTING on the named region],
> lit by a dim amber K-dwarf sun, low-angle warm light, basalt and ochre
> palette, one human figure for scale, 35mm lens, slight film grain,
> matte contrast, muted, no lens flare, no glossy surfaces.

## Continuity mechanics

- Every canon entity carries a fixed `seed` in `canon/canon.json`. The same
  entity is always generated with the same seed (`ai_images.seed_lock`).
- Recurring subjects also carry a reference image; new shots are generated with
  image-to-image conditioning against it (`ai_images.reference_conditioning`).
- Early organisms deliberately have **no fixed anatomy** (biofilms, swarms,
  colonial mats). An organism with no body plan cannot drift between episodes.
  This is a continuity strategy, not an aesthetic preference.

## Sound (recorded here because it is part of the identity)

Slow synth-orchestral bed, low and unhurried. Room tone and machine hum carry
the scenes — this world is loud with infrastructure. Each recurring entity gets
one motif; the cinder film's is a dry granular shimmer. Music never swells for
a verdict. The verdict lands in near-silence.
