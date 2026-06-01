import os

from skills.common import call_ollama, count_words, make_front_matter, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "blog")

SYSTEM = """You are a copy editor doing a grammar and flow pass only. NOT a rewrite.

Fix:
- Grammatical errors (subject-verb agreement, tense consistency, missing articles)
- Punctuation (missing commas, double spaces, inconsistent quote marks)
- Sentence flow — if a sentence is hard to parse on first read, simplify the structure
- Abrupt or missing transitions between paragraphs
- Same word repeated within 2 sentences (unless deliberate for emphasis)

Do NOT touch:
- Sentence length — if it's short and punchy, keep it short
- Word choice — do not replace words with "better" synonyms
- Structure — do not reorder paragraphs or merge sections
- Opinions — do not soften or qualify
- Contractions — keep them
- Opening and closing lines — these are the most intentional; leave them alone

Return the result in this exact format with no extra text:

[ARTICLE]
(the full corrected article)

[CHANGES]
- change description 1
- change description 2
- Total: N changes"""


def run(draft_text: str, voice_context: str, model: str, slug: str = "draft") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    prompt = f"Proofread this article:\n\n{draft_text}"

    print("  [proofread] Calling Ollama...")
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
    fm = make_front_matter(slug, "proofed", wc)
    n = changes.count("\n-") + (1 if changes.startswith("-") else 0)

    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-proofed.md")
    with open(out_path, "w") as f:
        f.write(fm + article + f"\n\n---\n## Proofread changes\n{changes}\n")

    print(f"  Proofread complete → {out_path} ({n} changes)")
    return article
