"""Research dossier — the investigation happens BEFORE the script.

One grounded Gemini pass (Google Search tools, same mechanism as
factcheck.py) assembles the complete documented record for a mystery topic
into a five-act dossier. generate_script() then writes FROM the dossier
with a no-skipping rule, so the script's depth is bounded by research, not
by what one generation pass happens to remember.

Fail-open: any error returns {} and the pipeline proceeds exactly as
before (the script prompt simply has no dossier block).
"""
import json

import factcheck


DOSSIER_PROMPT = """You are the research lead for a Hindi mystery
documentary channel (भारत के रहस्य). Build the COMPLETE research dossier
for this investigation topic using web search. Be exhaustive — the
scriptwriter will only use what you collect.

TOPIC: {topic}

Return ONLY valid JSON with this exact shape:
{{
  "anchor": "the ONE real, documented, checkable anomaly that makes this topic legitimate (excavation, expedition, dated text, declassified file) — 2-3 sentences with names and dates",
  "dawa": "the central claim/question of the investigation, one Hindi sentence",
  "srot": ["4-8 items: what the texts/legends ACTUALLY say — name the text, the passage's content, and its approximate date; quote or paraphrase accurately, never invent"],
  "itihas": [{{"year": 1938, "event": "the documented event — expedition, excavation, publication, court case — with named people/institutions"}}],
  "siddhant": ["2-4 competing explanations INCLUDING the mainstream skeptical/scientific one, each 1-3 sentences, each attributed (who holds this view)"],
  "jo_bacha": ["2-4 precisely-stated open questions that remain genuinely unanswered by the documented record"],
  "key_numbers": [{{"value": 5000, "unit": "साल", "what": "what this number measures and its source"}}],
  "confidence_notes": ["claims popularly repeated about this topic that are NOT supported by the documented record — the script must avoid or explicitly debunk these"]
}}

Rules: every itihas item needs a real year; every srot item names its text;
nothing invented; where sources disagree, say so inside the item. The
skeptical explanation is mandatory in siddhant."""


def build_dossier(topic: str, cfg: dict, api_key: str) -> dict:
    """Grounded five-act research dossier for the topic. {} on any failure."""
    try:
        dossier, urls = factcheck._grounded_json(
            DOSSIER_PROMPT.format(topic=topic), cfg, api_key)
        if not isinstance(dossier, dict) or not dossier.get("itihas"):
            print("[research] dossier empty/malformed — proceeding without")
            return {}
        dossier["sources"] = urls[:20]
        acts = {k: len(dossier.get(k) or []) for k in
                ("srot", "itihas", "siddhant", "jo_bacha")}
        print(f"[research] dossier built: {acts}, {len(urls)} sources")
        return dossier
    except Exception as exc:
        print(f"[research] dossier failed ({exc}) — proceeding without")
        return {}


def prompt_block(dossier: dict) -> str:
    """The block generate_script() injects into the writing prompt."""
    if not dossier:
        return ""
    return f"""
RESEARCH DOSSIER (the complete documented record — this is your ONLY
source of facts. NO-SKIPPING RULE: every act below must appear in the
script — the anchor, every srot item, the itihas timeline, every
siddhant theory, every jo_bacha question. If material is rich, compress
LANGUAGE, never drop an act or a documented item. Never add facts that
are not in the dossier; confidence_notes lists popular claims you must
avoid or explicitly debunk):
{json.dumps(dossier, ensure_ascii=False, indent=1)}
"""
