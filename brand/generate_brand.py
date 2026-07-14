"""ELSEWHERE brand kit generator (basalt + amber — the dossier identity).

Regenerates every static brand asset deterministically with PIL:
  logo.png (2000x500 transparent)  logo_mark.png (1024)  banner.png (2560x1440)
  avatar.png (800x800)             watermark.png (600, white alpha)
  yt_watermark.png (300, YouTube video watermark)

The mark IS the atlas: a survey ring, deterministic relief contours, and one
amber marker — the same visual language as every episode's locator scene.
NOTHING here is navy or glass; those are channel 1's language and the two
channels must never be confused (config.yaml render note).

Run: python brand/generate_brand.py   (writes into brand/)
Video-side branding lives in remotion/src/styles.ts — the DOSSIER palette
there must match the constants below.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# DOSSIER palette — mirror of remotion/src/styles.ts
BASALT = (28, 24, 20)        # #1C1814 volcanic black, not space black
INK = (42, 36, 30)           # #2A241E panel fill
PAPER = (232, 220, 200)      # #E8DCC8 filed-report off-white
AMBER = (217, 138, 59)       # #D98A3B anything engineered
COPPER = (140, 106, 74)      # #8C6A4A oxidised metal
TEXT = (239, 228, 210)       # #EFE4D2

MARK_SEED = 91177            # same seed as the planet. The brand IS the world.
OUT = os.path.dirname(os.path.abspath(__file__))

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _contour(c: float, r: float, rng: random.Random, steps: int = 140):
    """One wobbly relief ring — the atlas's harmonic-blob language."""
    octaves = [(k + 2, rng.uniform(-0.22, 0.22) / (k + 1) ** 0.75,
                rng.uniform(0, 2 * math.pi)) for k in range(6)]
    pts = []
    for i in range(steps):
        th = 2 * math.pi * i / steps
        wobble = 1.0 + sum(a * math.sin(f * th + ph) for f, a, ph in octaves)
        rr = r * max(0.55, wobble)
        pts.append((c + rr * math.cos(th), c + rr * math.sin(th) * 0.88))
    return pts


def draw_mark(size: int, ring=None, contour=None, marker=None,
              bg=None) -> Image.Image:
    """The mark: a survey ring + relief contours + one amber marker.

    Reads at 32px as a coin with a dot; at 800px as a map of somewhere you
    have not been yet. Deterministic — the same hills every time, because on
    this channel even the logo is canon.
    """
    ring = ring or PAPER
    contour = contour or COPPER
    marker = marker or AMBER
    img = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r = size / 2, size * 0.44
    w = max(int(size * 0.030), 3)

    # survey ring with a deliberate gap — the unrevealed part of the atlas
    d.arc([c - r, c - r, c + r, c + r], start=305, end=250, fill=ring, width=w)
    # graticule ticks at the cardinal points
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        x1 = c + (r - w * 2.2) * math.cos(a)
        y1 = c + (r - w * 2.2) * math.sin(a)
        x2 = c + (r + w * 0.4) * math.cos(a)
        y2 = c + (r + w * 0.4) * math.sin(a)
        d.line([(x1, y1), (x2, y2)], fill=ring, width=max(w // 2, 2))

    # relief contours — three nested rings, offset from centre like a real
    # highland, clipped to the survey ring
    rng = random.Random(MARK_SEED)
    ox, oy = c - size * 0.055, c + size * 0.035
    clip = Image.new("L", (size, size), 0)
    ImageDraw.Draw(clip).ellipse(
        [c - r + w, c - r + w, c + r - w, c + r - w], fill=255)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    if isinstance(contour, tuple) and len(contour) == 3:
        contour = contour + (255,)
    for ring_scale in (0.72, 0.47, 0.25):
        pts = _contour(0, r * ring_scale, rng)
        shifted = [(x + ox, y + oy) for x, y in pts]
        dl.line(shifted + [shifted[0]], fill=contour,
                width=max(w // 2, 2), joint="curve")
    img.paste(layer, (0, 0), Image.composite(
        layer.split()[3], Image.new("L", (size, size), 0), clip))

    # the marker — one settlement, located
    mr = size * 0.052
    mx, my = c + size * 0.13, c - size * 0.10
    d.ellipse([mx - mr * 2.1, my - mr * 2.1, mx + mr * 2.1, my + mr * 2.1],
              outline=marker, width=max(w // 2, 2))
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=marker)
    return img


def vertical_gradient(w: int, h: int, top, bottom) -> Image.Image:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def add_grid(img: Image.Image, alpha=14, step=110) -> None:
    """Faint survey graticule."""
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for x in range(0, w, step):
        d.line([(x, 0), (x, h)], fill=PAPER + (alpha,))
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=PAPER + (alpha,))


def wordmark(d: ImageDraw.ImageDraw, xy, size: int, spacing: int = None,
             fill=TEXT):
    x, y = xy
    f1 = font(size)
    spacing = spacing if spacing is not None else int(size * 0.30)
    for ch in "ELSEWHERE":
        d.text((x, y), ch, font=f1, fill=fill)
        x += d.textlength(ch, font=f1) + spacing
    return x


def make_logo():
    img = Image.new("RGBA", (2000, 500), (0, 0, 0, 0))
    mark = draw_mark(420)
    img.paste(mark, (30, 40), mark)
    d = ImageDraw.Draw(img)
    end_x = wordmark(d, (520, 140), 138)
    d.rectangle([524, 320, end_x - 40, 330], fill=AMBER)
    f2 = font(40)
    d.text((524, 358), "THE PLACE IS FICTIONAL. THE PRINCIPLES ARE REAL.",
           font=f2, fill=COPPER)
    img.save(os.path.join(OUT, "logo.png"))


def make_logo_mark():
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    grad = vertical_gradient(1024, 1024, INK, BASALT).convert("RGBA")
    m = Image.new("L", (1024, 1024), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, 1024, 1024], radius=180, fill=255)
    img.paste(grad, (0, 0), m)
    add_grid(img, alpha=12, step=128)
    mark = draw_mark(760)
    img.paste(mark, (132, 132), mark)
    img.save(os.path.join(OUT, "logo_mark.png"))


def make_banner():
    W, H = 2560, 1440
    img = vertical_gradient(W, H, INK, BASALT).convert("RGBA")
    add_grid(img, alpha=10, step=120)
    # low warm horizon glow — the K-dwarf afternoon
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([W * 0.12, H * 0.55, W * 0.88, H * 1.20],
                                 fill=AMBER + (40,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(130)))
    d = ImageDraw.Draw(img, "RGBA")
    # safe area (1546x423 centred) content only
    cx, cy = W // 2, H // 2
    mark = draw_mark(230)
    img.paste(mark, (cx - 115, cy - 200), mark)
    d = ImageDraw.Draw(img, "RGBA")
    f1 = font(96)
    text = "ELSEWHERE"
    spacing = 30
    total = sum(d.textlength(ch, font=f1) + spacing for ch in text) - spacing
    x = cx - total / 2
    for ch in text:
        d.text((x, cy + 48), ch, font=f1, fill=TEXT)
        x += d.textlength(ch, font=f1) + spacing
    d.rectangle([cx - 170, cy + 172, cx + 170, cy + 180], fill=AMBER)
    f2 = font(36)
    sub = "CASE FILES FROM A WORLD THAT NEVER WAS · WEEKLY"
    d.text((cx - d.textlength(sub, font=f2) / 2, cy + 204), sub, font=f2,
           fill=COPPER + (255,))
    img.convert("RGB").save(os.path.join(OUT, "banner.png"))


def make_avatar():
    S = 800
    img = vertical_gradient(S, S, INK, BASALT).convert("RGBA")
    add_grid(img, alpha=12, step=100)
    d = ImageDraw.Draw(img)
    ring_w = 14
    d.ellipse([ring_w, ring_w, S - ring_w, S - ring_w], outline=AMBER,
              width=ring_w)
    mark = draw_mark(500)
    img.paste(mark, (150, 90), mark)
    d = ImageDraw.Draw(img)
    f = font(58)
    text = "ELSEWHERE"
    spacing = 10
    total = sum(d.textlength(ch, font=f) + spacing for ch in text) - spacing
    x = (S - total) / 2
    for ch in text:
        d.text((x, S - 165), ch, font=f, fill=TEXT)
        x += d.textlength(ch, font=f) + spacing
    img.convert("RGB").save(os.path.join(OUT, "avatar.png"))


def make_watermarks():
    # in-video corner watermark: white mark, transparent bg
    mark = draw_mark(600, ring=(255, 255, 255, 235),
                     contour=(255, 255, 255, 160),
                     marker=(255, 255, 255, 235))
    mark.save(os.path.join(OUT, "watermark.png"))
    # YouTube "video watermark" (branding setting): amber on basalt disc
    S = 300
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, S, S], fill=INK + (255,))
    d.ellipse([6, 6, S - 6, S - 6], outline=AMBER, width=8)
    m = draw_mark(210)
    img.paste(m, (45, 45), m)
    img.save(os.path.join(OUT, "yt_watermark.png"))


if __name__ == "__main__":
    make_logo()
    make_logo_mark()
    make_banner()
    make_avatar()
    make_watermarks()
    print("ELSEWHERE brand kit written to", OUT)
