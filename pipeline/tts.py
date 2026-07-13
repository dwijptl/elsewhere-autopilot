"""Stage 3 — voiceover.

PRIMARY: ElevenLabs (api.elevenlabs.io) — the channel's English narrator.
The voice comes from the ELEVENLABS_VOICE_ID secret.

PICK THE VOICE ONCE AND NEVER CHANGE IT. On a channel whose entire promise is
"a real documentary from a world that doesn't exist", the narrator IS the
credibility. Changing voices at episode 12 costs more trust than any thumbnail
buys back.

FALLBACK: Kokoro-82M (Apache 2.0, runs free on the runner) with its English
voices — an ElevenLabs outage or empty credits never kills a scheduled run.
Set TTS_NO_FALLBACK=1 to fail hard instead (the Test Voice workflow does).

PRONUNCIATION DICTIONARY: brand/pronunciations.yaml maps terms the voice
mispronounces (English scientific names, units, symbols) to phonetic Hindi
spellings. Applied to TTS text only — captions come from STT of the audio,
so they stay consistent automatically. Add an entry whenever a render
mispronounces something; fail-open if the file is absent.
"""
import base64
import io
import os
import re
import time

import numpy as np
import requests
import soundfile as sf

SARVAM_URL = "https://api.sarvam.ai/text-to-speech"
ELEVEN_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVEN_CHAR_LIMIT = 2400   # chunk below the model limit; sentence-aligned
SARVAM_CHAR_LIMIT = 1800   # API allows 2500 for bulbul:v3 — stay comfortably under
MODEL_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MODEL_FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]
SAMPLE_RATE = 24000

ENGINE_USED = "none"       # run.py reports this in the release notes
_engines: set = set()
_sarvam_chars = 0          # cost telemetry (retained: Sarvam still available)
_eleven_chars = 0          # cost telemetry ($ estimate in usage_summary)
_kokoro = None
FALLBACK_USED = False       # never silently present a fallback run as cloned voice

# Per-scene voice direction: how a human narrator would deliver it.
# pace_mul multiplies cfg tts.speed; pre = seconds of silence BEFORE the
# scene (dramatic beat); temperature = bulbul:v3 expressiveness.
# Channel 2 is a calmer instrument than channel 1. The ranges are tighter and
# the "reveal" beat is longer: this narrator lands a verdict by slowing down and
# leaving a hole in the audio, never by getting louder. "style" is ElevenLabs
# expressiveness — kept low on purpose. Hype is the failure mode.
DELIVERY = {
    "hook":   {"pace_mul": 1.02, "temperature": 0.62, "pre": 0.0,
               "style": 0.22, "stability": 0.40},
    "calm":   {"pace_mul": 1.00, "temperature": 0.55, "pre": 0.0,
               "style": 0.12, "stability": 0.46},
    "reveal": {"pace_mul": 0.90, "temperature": 0.58, "pre": 0.9,
               "style": 0.10, "stability": 0.52},
    "urgent": {"pace_mul": 1.08, "temperature": 0.68, "pre": 0.0,
               "style": 0.28, "stability": 0.38},
    # the SURVIVED / ADAPTED / FAILED card. Flat, quiet, final.
    "verdict": {"pace_mul": 0.86, "temperature": 0.45, "pre": 1.2,
                "style": 0.04, "stability": 0.62},
}

_PRON: dict | None = None


def _apply_pronunciations(text: str) -> str:
    """Replace terms from brand/pronunciations.yaml (longest keys first so
    'Mariana Trench' wins over 'Mariana'). Plain substring replacement keeps
    Devanagari-safe behaviour; fail-open on any problem."""
    global _PRON
    if _PRON is None:
        _PRON = {}
        try:
            import yaml
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "brand", "pronunciations.yaml")
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            _PRON = {str(k): str(v) for k, v in (data.get("terms") or {}).items()
                     if str(k).strip() and str(v).strip()}
            if _PRON:
                print(f"[tts] pronunciation dictionary loaded ({len(_PRON)} terms)")
        except Exception:
            _PRON = {}
    for key in sorted(_PRON, key=len, reverse=True):
        if key in text:
            text = text.replace(key, _PRON[key])
    return text


# ── sentence-aware chunking (Hindi danda । + Latin punctuation) ──────────
def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[।.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunks(text: str, limit: int = SARVAM_CHAR_LIMIT) -> list[str]:
    """Greedy multi-sentence chunks under `limit` chars (better prosody than
    per-sentence requests, fewer API calls)."""
    out, cur = [], ""
    for sent in _sentences(text):
        while len(sent) > limit:  # pathological unbroken sentence
            out.append(sent[:limit].strip())
            sent = sent[limit:]
        if cur and len(cur) + 1 + len(sent) > limit:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


# ── Sarvam bulbul:v3 ─────────────────────────────────────────────────────
def _sarvam_lang(code: str) -> str:
    """Map channel language to a Sarvam-supported BCP-47 code.
    Sarvam's enum only knows Indian-market codes: English is 'en-IN',
    not 'en-us'/'en-US'. Anything already regionalised for India passes
    through untouched."""
    c = (code or "").strip()
    if c.lower().startswith("en"):
        return "en-IN"
    return c or "hi-IN"


def _sarvam_request(chunk: str, cfg: dict, api_key: str, speaker: str,
                    dlv: dict) -> np.ndarray:
    t = cfg["tts"]
    base = float(t.get("speed", 1.0)) * dlv.get("pace_mul", 1.0)
    pace = min(max(base, 0.5), 2.0)  # bulbul:v3 range
    body = {
        "text": chunk,
        "target_language_code": _sarvam_lang(cfg["channel"].get("language", "hi-IN")),
        "model": t.get("sarvam_model", "bulbul:v3"),
        "speaker": speaker,
        "pace": round(pace, 3),
        "temperature": dlv.get("temperature", float(t.get("temperature", 0.6))),
        "speech_sample_rate": SAMPLE_RATE,
    }
    headers = {"api-subscription-key": api_key, "Content-Type": "application/json"}
    last = ""
    for attempt in range(4):
        try:
            r = requests.post(SARVAM_URL, json=body, headers=headers, timeout=180)
        except requests.RequestException as e:
            last = str(e)
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            b64 = r.json()["audios"][0]
            data, sr = sf.read(io.BytesIO(base64.b64decode(b64)), dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr != SAMPLE_RATE:  # defensive — we request 24000
                idx = np.linspace(0, len(data) - 1,
                                  int(len(data) * SAMPLE_RATE / sr))
                data = data[idx.astype(int)]
            return np.asarray(data, dtype=np.float32)
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"[tts] sarvam rate-limited, sleeping {wait}s")
            last = r.text[:300]
            time.sleep(wait)
            continue
        if r.status_code == 403:
            raise RuntimeError(
                "Sarvam 403 — check the SARVAM_API_KEY secret and remaining "
                f"credits at dashboard.sarvam.ai. Body: {r.text[:300]}")
        if r.status_code == 422:
            raise RuntimeError(
                "Sarvam 422 — invalid request; usually SARVAM_SPEAKER doesn't "
                f"match bulbul:v3. Body: {r.text[:300]}")
        last = f"HTTP {r.status_code}: {r.text[:300]}"
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Sarvam TTS failed after retries — {last}")


def _synth_sarvam(text: str, cfg: dict, dlv: dict) -> np.ndarray:
    global _sarvam_chars
    api_key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY not set (add it as a repo secret)")
    # Sarvam speaker names are case-sensitive lowercase ('shubh', not 'Shubh')
    # — normalise so a capitalised repo secret doesn't 422 every request.
    speaker = (os.environ.get("SARVAM_SPEAKER", "").strip()
               or cfg["tts"].get("sarvam_speaker", "shubh")).lower()
    pieces = []
    for chunk in _chunks(text):
        pieces.append(_sarvam_request(chunk, cfg, api_key, speaker, dlv))
        _sarvam_chars += len(chunk)
        time.sleep(0.3)  # gentle on rate limits
    if not pieces:
        pieces = [np.zeros(SAMPLE_RATE, dtype=np.float32)]
    return np.concatenate(pieces)


# ── Kokoro-82M fallback (Hindi voices: hf_alpha/hf_beta/hm_omega/hm_psi) ─
def _cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".cache", "kokoro")
    os.makedirs(d, exist_ok=True)
    return d


def _ensure_model() -> tuple[str, str]:
    paths = []
    for name in MODEL_FILES:
        path = os.path.join(_cache_dir(), name)
        if not os.path.exists(path) or os.path.getsize(path) < 1_000_000:
            print(f"[tts] downloading {name} ...")
            with requests.get(f"{MODEL_BASE}/{name}", stream=True, timeout=1200) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 22):
                        f.write(chunk)
        paths.append(path)
    return paths[0], paths[1]


def _engine():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        model, voices = _ensure_model()
        _kokoro = Kokoro(model, voices)
    return _kokoro


def _kokoro_lang(cfg: dict) -> str:
    lang = str(cfg["channel"].get("language", "en-us")).lower()
    if lang.startswith("hi"):
        return "hi"
    return "en-us" if lang.startswith("en") else lang


def _synth_kokoro(text: str, cfg: dict) -> np.ndarray:
    k = _engine()
    voice = cfg["tts"].get("voice", "am_michael")
    try:
        available = set(k.get_voices())
        if voice not in available:
            english = sorted(v for v in available if v.startswith(("am_", "af_",
                                                                  "bm_", "bf_")))
            fallback = english[0] if english else sorted(available)[0]
            print(f"[tts] voice '{voice}' not found, using '{fallback}'")
            voice = fallback
    except Exception:
        pass

    speed = float(cfg["tts"].get("speed", 1.0))
    lang = _kokoro_lang(cfg)
    gap = np.zeros(int(0.25 * SAMPLE_RATE), dtype=np.float32)
    chunks = []
    for sent in _sentences(text):
        samples, sr = k.create(sent, voice=voice, speed=speed, lang=lang)
        chunks.append(np.asarray(samples, dtype=np.float32))
        chunks.append(gap)
    if not chunks:
        chunks = [np.zeros(SAMPLE_RATE, dtype=np.float32)]
    return np.concatenate(chunks)


# ── ElevenLabs (primary: the English narrator) ───────────────────────────
def _eleven_request(chunk: str, cfg: dict, api_key: str, voice_id: str,
                    dlv: dict) -> np.ndarray:
    t = cfg["tts"]
    body = {
        "text": chunk,
        "model_id": t.get("elevenlabs_model", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": float(dlv.get("stability", t.get("stability", 0.42))),
            "similarity_boost": float(t.get("similarity", 0.80)),
            "style": float(dlv.get("style", t.get("style", 0.15))),
            "use_speaker_boost": bool(t.get("speaker_boost", True)),
            "speed": float(t.get("speed", 1.0)) * float(dlv.get("pace_mul", 1.0)),
        },
    }
    headers = {"xi-api-key": api_key, "accept": "audio/mpeg",
               "content-type": "application/json"}
    url = f"{ELEVEN_URL}/{voice_id}"
    for attempt in range(4):
        r = requests.post(url, json=body, headers=headers, timeout=180)
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"[tts] elevenlabs rate-limited, sleeping {wait}s")
            time.sleep(wait)
            continue
        if r.status_code == 401:
            raise RuntimeError("ELEVENLABS_API_KEY rejected (401). Check the "
                               "secret and the account's character balance.")
        if r.status_code >= 400:
            raise RuntimeError(f"elevenlabs {r.status_code}: {r.text[:300]}")
        audio, sr = sf.read(io.BytesIO(r.content), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            idx = np.linspace(0, len(audio) - 1,
                              int(len(audio) * SAMPLE_RATE / sr))
            audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)
        return audio
    raise RuntimeError("elevenlabs failed after retries")


def _synth_eleven(text: str, cfg: dict, dlv: dict) -> np.ndarray:
    global _eleven_chars
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY missing")
    voice_id = (os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
                or cfg["tts"].get("elevenlabs_voice", "").strip())
    if not voice_id:
        raise RuntimeError(
            "No ElevenLabs voice selected. Set the ELEVENLABS_VOICE_ID secret. "
            "Pick the voice ONCE — it is the channel's face.")
    pieces = []
    for chunk in _chunks(text, ELEVEN_CHAR_LIMIT):
        pieces.append(_eleven_request(chunk, cfg, api_key, voice_id, dlv))
        _eleven_chars += len(chunk)
    gap = np.zeros(int(0.18 * SAMPLE_RATE), dtype=np.float32)
    out: list = []
    for p in pieces:
        out += [p, gap]
    return np.concatenate(out) if out else np.zeros(SAMPLE_RATE, dtype=np.float32)


# ── public API ───────────────────────────────────────────────────────────
def synth_scene(text: str, wav_path: str, cfg: dict,
                delivery: str = "calm", tail_seconds: float = 0.35) -> float:
    """Synthesize one scene's narration to wav_path. Returns duration (s).
    delivery: hook | calm | reveal | urgent (per-scene voice direction)."""
    global ENGINE_USED, FALLBACK_USED
    text = _apply_pronunciations(text)
    dlv = DELIVERY.get(str(delivery).lower().strip(), DELIVERY["calm"])
    engine = str(cfg.get("tts", {}).get("engine", "elevenlabs")).lower()
    audio = None
    if engine == "elevenlabs":
        try:
            audio = _synth_eleven(text, cfg, dlv)
            _engines.add("elevenlabs:" +
                         cfg["tts"].get("elevenlabs_model", "eleven_multilingual_v2"))
        except Exception as e:
            if os.environ.get("TTS_NO_FALLBACK", "").strip() == "1":
                raise
            FALLBACK_USED = True
            print(f"[tts] ELEVENLABS FAILED -> Kokoro fallback. Reason: {e}")
    elif engine == "sarvam":
        try:
            audio = _synth_sarvam(text, cfg, dlv)
            _engines.add("sarvam:" + cfg["tts"].get("sarvam_model", "bulbul:v3"))
        except Exception as e:
            if os.environ.get("TTS_NO_FALLBACK", "").strip() == "1":
                raise
            FALLBACK_USED = True
            print(f"[tts] SARVAM FAILED -> Kokoro fallback. Reason: {e}")
    if audio is None:
        kcfg = dict(cfg)
        kcfg["tts"] = dict(cfg["tts"])
        kcfg["tts"]["speed"] = float(cfg["tts"].get("speed", 1.0)) * dlv["pace_mul"]
        audio = _synth_kokoro(text, kcfg)
        _engines.add("kokoro-82m")
    ENGINE_USED = " + ".join(sorted(_engines))

    # dramatic beat before reveals + configurable breath before the next scene
    pre = np.zeros(int(dlv.get("pre", 0.0) * SAMPLE_RATE), dtype=np.float32)
    tail = max(0.0, min(float(tail_seconds), 2.0))
    audio = np.concatenate(
        [pre, audio, np.zeros(int(tail * SAMPLE_RATE), dtype=np.float32)])
    peak = float(np.max(np.abs(audio))) or 1.0  # normalize to healthy loudness
    audio = audio * (0.89 / peak)
    sf.write(wav_path, audio, SAMPLE_RATE)
    return len(audio) / SAMPLE_RATE


def fallback_used() -> bool:
    """Whether this run used a non-primary voice after a Sarvam failure."""
    return FALLBACK_USED


def reset_run_state() -> None:
    """Reset module telemetry when a process intentionally runs more than once."""
    global ENGINE_USED, FALLBACK_USED, _sarvam_chars, _eleven_chars
    ENGINE_USED = "none"
    FALLBACK_USED = False
    _sarvam_chars = 0
    _eleven_chars = 0
    _engines.clear()


def usage_summary() -> str:
    if _eleven_chars <= 0 and _sarvam_chars <= 0:
        return f"engines: {ENGINE_USED} · 0 paid characters ($0)"
    parts = [f"engines: {ENGINE_USED}"]
    if _eleven_chars:
        # Creator tier ≈ $0.00018/char at 100k chars for $22 — the pilot budgets
        # $0.50 of voice, which is ~2,700 characters. Check your plan.
        dollars = _eleven_chars * 0.00018
        parts.append(f"elevenlabs chars: {_eleven_chars:,} (≈ ${dollars:.2f})")
    if _sarvam_chars:
        parts.append(f"sarvam chars: {_sarvam_chars:,}")
    return " · ".join(parts)
