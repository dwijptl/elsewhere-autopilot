# Pilot — "The Underground City That Cooked Itself"

$5 hard budget. One 6–7 minute episode + 3 Shorts from the same assets.

## What this episode is secretly doing

It looks like one self-contained disaster. It is actually four jobs at once:

1. **Establishes the format** — systems → biome → stress → verdict. The first
   FAILED verdict sets the stakes so that a later SURVIVED means something.
2. **Establishes the planet without announcing it.** The atlas locator, the
   K-dwarf light, the 31-hour day and the thin-air cooling penalty all land as
   *engineering constraints*, not as worldbuilding exposition. The viewer learns
   the physics because the physics is what kills the city.
3. **Plants the ocean.** The closing shot glimpses the Slow Sea and the thing in
   it that "seems to know the tide before the tide arrives." That single line is
   the seed for episode 7 — and the comment-section bait that tells us whether
   the world is working at all.
4. **Avoids the one technical trap.** The antagonist is a *biofilm* — no face,
   no anatomy, no body plan. Nothing to keep visually consistent across
   episodes. Continuity risk on the pilot: near zero, by design.

The planet's name is **never in the title.** The title sells the premise; the
episode builds the IP.

## The case

**Tehlmark Deep** (SET-01), 9,400 people, cut vertically into the basalt of the
Cinder Shelf to escape a surface that cooks through a 31-hour day.

| System | How it works | Runs at |
|---|---|---|
| COOLING | closed groundwater loop, waste heat dumped to an aquifer 500 m down | 31 °C at level 9 |
| POWER | geothermal, tapped from the same basalt | 40 MW |
| WATER | drinking supply, filtered — **from the cooling aquifer** | 1.4 ML/day |
| AIR | passive stack ventilation, driven by the day/night surface swing | — |
| FOOD | fungal galleries on level 9, fed on surface dust organics | — |

**The hidden dependency:** cooling, power and drinking water all terminate in
one aquifer. Nobody drew those three on the same diagram.

This is drawn — literally — in the schematic scene, and never pointed at. The
`<Schematic>` component renders a shared dependency as one amber node with two
lines running into it (`remotion/src/dossier.tsx`). The audience sees it before
the narrator says it. That half-second is the whole format.

**The stress event:** the cinder film (ORG-01) — a real-physics chemolithotroph
that eats iron and sulphur in volcanic dust and thrives at 45–70 °C, which is
*exactly* the temperature band a heat exchanger operates in. It colonises the
exchanger surfaces. Conductivity halves over 60 days.

**The cascade** (each step caused by the last, not merely after it):

1. Exchanger conductivity falls 340 → 160 W/m²K.
2. Waste heat backs up; the aquifer warms.
3. Warmer aquifer = worse cooling *and* worse drinking water — the same water.
4. Cooling demand rises, so geothermal draw rises, so waste heat rises.
5. The loop is now feeding itself. The city's power source has become its oven.
6. Level 9 (food) passes 45 °C — the fungal galleries die, and the film's ideal
   temperature band arrives *inside the city*.

**Verdict: FAILED.** Sealed, not destroyed — Tehlmark Deep remains available for
a return episode, which is worth more than a ruin.

**The engineers were not stupid.** Tapping geothermal power from the rock you
are hiding inside is *elegant*: it is the cheapest heat sink and the cheapest
power source on the plateau. Write at least one scene that makes the audience
agree with the decision that kills the city. That is the difference between a
stress test and a disaster video — and it is what the comments will argue about.

## Budget ($5 hard cap)

| Item | Count | Cost |
|---|---|---|
| FLUX stills (dev) + retries | 12–16 | ~$1.25 |
| Wan motion shots | 1–2 | $1.50–2.25 |
| ElevenLabs narration | ~1,000 words | ~$0.50 |
| Retry reserve | — | $1.00 |
| **Total** | | **≤ $5.00** |

Spend the motion shots on the cascade's turning point and the closing ocean
glimpse. Never on an establishing shot — a still with a slow push does that job
for free.

## Targets (from the plan, unchanged)

Browse CTR ≥ 4.5% · 30s retention ≥ 65% · APV ≥ 45% · subs/1k ≥ 4

**The killer signal:** comments asking about the planet or the next biome. Not
"great video" — *"what's in the ocean?"* Retention without world-curiosity means
we made a good disaster video and no IP, and that is a pivot, not a win.

## Unused assets

Roll into episode 2. Nothing generated for the Cinder Shelf is wasted — the
region persists, and so does everything shot in it.
