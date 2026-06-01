import os

from skills.common import call_ollama, count_words, make_front_matter, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "blog")

BANNED_WORDS = (
    "delve, unpack, underscore, leverage (as a verb), transformative, nuanced, "
    "game-changer, paradigm, ecosystem (unless quoting), synergy, synergies, seamless, "
    "robust, cutting-edge, groundbreaking, revolutionary, unprecedented, holistic, pivotal, "
    "it's worth noting, at its core, in essence, when it comes to, the fact that, "
    "in conclusion, to summarise, in today's [anything], the [noun] landscape"
)

BANNED_PATTERNS = (
    '- "It\'s important to..." → just say the thing\n'
    '- "This [noun] highlights/underscores/demonstrates..." → say what it means directly\n'
    '- "One thing that stands out is..." → cut the preamble\n'
    "- Paragraph-ending sentence that summarises what was just said → delete it\n"
    "- Two sentences where sentence 2 restates sentence 1 → delete sentence 2\n"
    '- "Not only X, but also Y" → simplify\n'
    "- Passive voice used to avoid taking a position → active voice, own the claim\n"
    '- Tricolon filler ("speed, scale, and efficiency") → cut or make specific\n'
    '- Transition sentence that only says "now let\'s look at X" → delete, just start X'
)

SYSTEM = f"""You are editing a blog post to remove AI-generated language patterns.

BANNED WORDS AND PHRASES — rewrite any sentence containing these:
{BANNED_WORDS}

BANNED SENTENCE PATTERNS — fix these:
{BANNED_PATTERNS}

PRESERVE:
- Short, punchy sentences that state something plainly
- Specific numbers and named entities
- Contractions and colloquial phrasing
- Any sentence that sounds like something a practitioner would say out loud to a peer

Return the result in this exact format with no extra text:

[ARTICLE]
(the corrected article)

[CHANGES]
- description of rewrite 1
- description of rewrite 2
- Total: N rewrites"""


def run(proofed_text: str, voice_context: str, model: str, slug: str = "draft") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    prompt = f"Remove AI language patterns from this article:\n\n{proofed_text}"

    print("  [de-aify] Calling Ollama...")
    result = call_ollama(prompt, system=SYSTEM, timeout=300, model=model)

    if "[ARTICLE]" in result and "[CHANGES]" in result:
        article = result.split("[ARTICLE]")[1].split("[CHANGES]")[0].strip()
        changes = result.split("[CHANGES]")[1].strip()
    elif "[CHANGES]" in result:
        parts = result.split("[CHANGES]")
        article = parts[0].strip()
        changes = parts[1].strip()
    else:
        article = result
        changes = "- No changes logged"

    wc = count_words(article)
    fm = make_front_matter(slug, "deaified", wc)
    n = changes.count("\n-") + (1 if changes.startswith("-") else 0)

    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-deaified.md")
    with open(out_path, "w") as f:
        f.write(fm + article + f"\n\n---\n## De-AIify changes\n{changes}\n")

    print(f"  De-AIify complete → {out_path} ({n} rewrites)")
    return article
