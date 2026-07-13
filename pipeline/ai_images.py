"""AI image generation — the channel's "signature shot" engine.

Priority:
  1. FLUX via fal.ai   (FAL_KEY secret set)  — pay-per-image, premium look
  2. Gemini image API  (free tier ~500/day)  — fallback / zero-cost mode
Any failure returns False and the caller falls back to stock — the pipeline
never blocks on this module.

Every prompt gets a STYLE WRAPPER matched to the video's rotating style pack
(documentary / kinetic / editorial / noir) so AI shots feel like one
photographer shot the whole video instead of random AI output.
"""
import base64
import json
import hashlib
import os
import time

import requests

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
FAL_RUN = "https://fal.run/{model}"

# Per-style-pack photographic grammar (matches remotion/src/styles.ts packs)
STYLE_WRAPPERS = {
    "documentary": ("cinematic documentary photography, dramatic natural "
                    "light, atmospheric haze, shot on 35mm film, subtle film "
                    "grain, muted earth tones"),
    "kinetic": ("high-contrast editorial photography, deep shadows, one "
                "strong directional light, bold graphic composition, dark "
                "background, saturated accent colors"),
    "editorial": ("muted editorial palette, soft diffused overcast light, "
                  "minimalist composition with negative space, premium "
                  "printed-magazine look"),
    "noir": ("black and white fine-art photography, hard chiaroscuro "
             "lighting, fog, deep blacks, visible grain, brooding mood"),
    # ELSEWHERE's only pack. Every still on this channel is a field photograph
    # from a survey that happened, filed by someone tired — not concept art.
    # The physics of the light is canon: a K-dwarf sun means the world is lit
    # like a permanent late afternoon, and that is why nothing here is blue.
    "dossier": ("documentary field photograph, dim amber K-dwarf sunlight, "
                "low-angle warm light like a permanent late afternoon, basalt "
                "black and ochre dust palette, oxidised copper accents, matte "
                "contrast, 35mm lens, handheld, slight film grain, slight "
                "chromatic aberration, muted and desaturated, archival"),
}
COMMON_SUFFIX = ", photorealistic, high detail, no text, no watermark, no borders"

# The AI-slop tells. Negative-prompted on every single image, because one
# neon-rimmed chrome hero shot undoes ten episodes of earned credibility.
DOSSIER_NEGATIVE = (", no lens flare, no god rays, no volumetric light beams, "
                    "no glossy chrome, no neon rim light, no cyan or magenta "
                    "lighting, no blue-white sunlight, no HUD overlay, no "
                    "symmetrical hero composition, no creature facing camera, "
                    "not concept art, not a game render, not epic")


def _style_wrapper(cfg: dict) -> str:
    pack = str(cfg.get("render", {}).get("style_pack", "documentary"))
    wrapper = STYLE_WRAPPERS.get(pack, STYLE_WRAPPERS["documentary"])
    if pack == "dossier":
        wrapper += DOSSIER_NEGATIVE
    return wrapper


def _download(url: str, out_path: str) -> bool:
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return os.path.getsize(out_path) > 20_000


# ── FLUX via fal.ai ──────────────────────────────────────────────────────
def _canon_seed(prompt: str, cfg: dict) -> int | None:
    """Species/settlement visual continuity — the hardest technical problem in
    an AI-rendered persistent world, and the one that killed nobody's channel
    only because nobody tried this weekly.

    Every canon entity carries a fixed `seed` in canon/canon.json. If a prompt
    names that entity, we generate with ITS seed, every time, forever. Same
    seed + same style wrapper = the same creature in episode 1 and episode 30.
    Prompts that name no canon entity get a stable seed derived from the prompt
    text, so a re-run of the same episode reproduces the same images rather
    than quietly redesigning the world.
    """
    if not cfg.get("ai_images", {}).get("seed_lock", False):
        return None
    try:
        import canon as canon_mod
        world = canon_mod.load(".")
    except Exception:
        return None
    low = prompt.lower()
    for entity in (world.get("organisms", []) + world.get("settlements", [])):
        names = [entity.get("name", ""), entity.get("common_name", "")]
        if any(n and n.lower() in low for n in names) and entity.get("seed"):
            return int(entity["seed"])
    return int(hashlib.sha1(low.encode()).hexdigest()[:8], 16) % 2_000_000_000


def _flux(prompt: str, out_path: str, cfg: dict, aspect: str) -> bool:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        return False
    aicfg = cfg.get("ai_images", {})
    portrait = "9:16" in aspect or "vertical" in aspect or "tall" in aspect
    sizes = [
        {"width": 1080, "height": 1920} if portrait
        else {"width": 1920, "height": 1080},
        "portrait_16_9" if portrait else "landscape_16_9",  # enum fallback
    ]
    models = [aicfg.get("flux_model", "fal-ai/flux/dev"),
              aicfg.get("flux_fallback", "fal-ai/flux/schnell")]
    full_prompt = f"{prompt.strip()}. {_style_wrapper(cfg)}{COMMON_SUFFIX}"
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}

    for model in models:
        for size in sizes:
            body = {"prompt": full_prompt, "image_size": size, "num_images": 1,
                    "output_format": "jpeg", "enable_safety_checker": True}
            seed = _canon_seed(prompt, cfg)
            if seed is not None:
                body["seed"] = seed
            try:
                r = requests.post(FAL_RUN.format(model=model), json=body,
                                  headers=headers, timeout=300)
                if r.status_code == 422:
                    continue  # size rejected -> try enum size
                if r.status_code in (401, 403):
                    print(f"[ai-img] fal auth failed — check FAL_KEY: {r.text[:200]}")
                    return False
                if r.status_code == 429:
                    time.sleep(20)
                    continue
                r.raise_for_status()
                images = r.json().get("images") or []
                if images and images[0].get("url"):
                    if _download(images[0]["url"], out_path):
                        print(f"[ai-img] FLUX ({model}): {prompt[:60]}...")
                        return True
            except (requests.RequestException, KeyError, ValueError) as e:
                print(f"[ai-img] fal {model} failed: {e}")
                break  # network/model issue -> next model
    return False


# ── Gemini image API (free fallback) ─────────────────────────────────────
def _gemini_image(prompt: str, out_path: str, api_key: str, cfg: dict,
                  aspect: str) -> bool:
    aicfg = cfg.get("ai_images", {})
    models = [aicfg.get("model", "gemini-2.5-flash-image")] + list(
        aicfg.get("fallback_models", []))
    suffix = (f". {_style_wrapper(cfg)}, {aspect} composition{COMMON_SUFFIX}")
    body = {
        "contents": [{"parts": [{"text": prompt.strip() + suffix}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    for model in models:
        url = f"{API_BASE}/{model}:generateContent?key={api_key}"
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, timeout=180)
                if r.status_code == 429:
                    time.sleep(25 * (attempt + 1))
                    continue
                if r.status_code in (400, 404):
                    break  # model gone/renamed -> next model
                r.raise_for_status()
                data = r.json()
                parts = data["candidates"][0]["content"]["parts"]
                for p in parts:
                    inline = p.get("inlineData") or p.get("inline_data")
                    if inline and inline.get("data"):
                        with open(out_path, "wb") as f:
                            f.write(base64.b64decode(inline["data"]))
                        if os.path.getsize(out_path) > 20_000:
                            print(f"[ai-img] gemini ({model}): {prompt[:60]}...")
                            return True
                break  # no image part -> next model
            except (requests.RequestException, KeyError, IndexError,
                    json.JSONDecodeError) as e:
                print(f"[ai-img] {model} attempt {attempt + 1} failed: {e}")
                time.sleep(5)
    return False


# ── public API (signature unchanged — assets.py keeps working) ──────────
def generate(prompt: str, out_path: str, api_key: str, cfg: dict,
             aspect: str = "16:9 wide") -> bool:
    aicfg = cfg.get("ai_images", {})
    if not aicfg.get("enabled", True):
        return False
    if _flux(prompt, out_path, cfg, aspect):
        return True
    if _gemini_image(prompt, out_path, api_key, cfg, aspect):
        return True
    print("[ai-img] all providers failed — falling back to stock")
    return False
