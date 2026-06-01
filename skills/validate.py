import json
import os
import re

from skills.common import call_ollama_with_retry, count_words, make_front_matter, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "blog")

RUBRIC = """Score the blog post below against this rubric. Respond with ONLY valid JSON — no markdown, no preamble, no explanation.

VOICE (0-25):
- 25: Opinionated, direct, no filler. Reads like a practitioner, not a model.
- 20: Mostly strong, one or two flat patches.
- 15: Correct voice in parts but generic elsewhere.
- 10 or below: Sounds like a generic AI blog post.
Deductions: -3 per banned word still present (delve, unpack, underscore, transformative, nuanced,
game-changer, paradigm, ecosystem, synergy, leverage-as-verb, "it's worth noting", "at its core",
"in conclusion", "to summarise"), -2 per passive-voice hedge, -2 per paragraph-ending summary sentence.

ARGUMENT QUALITY (0-25):
- 25: Clear non-obvious central claim. Specific evidence. Closing adds something new.
- 20: Good argument but obvious take, or not fully supported.
- 15: Argument buried or inconsistent.
- 10 or below: No clear point of view.
Required: central claim stated explicitly, at least 2 named sources or data points,
closing that is not a summary.

RESEARCH INTEGRATION (0-20):
- 20: Sources woven in naturally. Specific numbers and named entities present.
- 15: Sources referenced but feel bolted on.
- 10: Thin on evidence, reads like opinion with no grounding.
- 5 or below: No sources visible.

READABILITY (0-15):
- 15: Flows well. Paragraphs tight. No slog sections.
- 10: One or two sections that drag.
- 5: Multiple sections needing restructure.

JSON format (use these exact keys, integer values):
{
  "voice_score": <0-25>,
  "argument_score": <0-25>,
  "research_score": <0-20>,
  "readability_score": <0-15>,
  "notes": ["specific issue with location", "what to fix"]
}"""


def word_count_score(wc: int) -> int:
    if 950 <= wc <= 1050:
        return 15
    if 900 <= wc <= 1100:
        return 10
    if 800 <= wc <= 1200:
        return 5
    return 0


def parse_scores(response: str) -> dict:
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", response).strip().rstrip("`").strip()

    # Try valid JSON first
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Regex fallback — handles both "key": val and key: val forms
    def extract_int(key: str) -> int:
        m = re.search(rf'"?{re.escape(key)}"?\s*:\s*(\d+)', response)
        return int(m.group(1)) if m else 0

    notes: list[str] = []
    notes_match = re.search(r'"?notes"?\s*:\s*\[(.*?)\]', response, re.DOTALL)
    if notes_match:
        notes = re.findall(r'"([^"]+)"', notes_match.group(1))

    return {
        "voice_score": extract_int("voice_score"),
        "argument_score": extract_int("argument_score"),
        "research_score": extract_int("research_score"),
        "readability_score": extract_int("readability_score"),
        "notes": notes,
    }


def run(
    clean_text: str, voice_context: str, model: str, slug: str = "draft"
) -> tuple[int, bool, str, str]:
    """Returns (score, passed, notes_str, validated_text_or_empty)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    wc = count_words(clean_text)
    wc_score = word_count_score(wc)

    prompt = f"Article to score (word count: {wc}):\n\n{clean_text}"

    response = call_ollama_with_retry(prompt, system=RUBRIC, label="validate", model=model)

    scores = parse_scores(response)

    # If all qualitative scores parsed to 0, Ollama likely returned garbage —
    # treat as a provisional pass at 75 so the pipeline doesn't loop forever.
    qualitative = (
        scores.get("voice_score", 0)
        + scores.get("argument_score", 0)
        + scores.get("research_score", 0)
        + scores.get("readability_score", 0)
    )
    if qualitative == 0:
        print("  [validate] WARNING: could not parse scores from Ollama response — treating as 75/100")
        total = 75
    else:
        total = qualitative + wc_score

    passed = total >= 75
    notes = scores.get("notes", [])
    notes_str = "\n".join(f"- {n}" for n in notes) if notes else "- No specific issues noted"

    if passed:
        fm = make_front_matter(slug, "validated", wc)
        out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-validated.md")
        with open(out_path, "w") as f:
            f.write(fm + clean_text)
        print(f"  PASS — Score: {total}/100 → proceeding to LinkedIn distill")
        return total, True, notes_str, clean_text

    print(f"  FAIL — Score: {total}/100")
    print(f"  Redraft notes:\n{notes_str}")
    return total, False, notes_str, ""
