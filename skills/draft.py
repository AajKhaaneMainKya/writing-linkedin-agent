import os

from skills.common import call_ollama, count_words, make_front_matter, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "blog")

STRUCTURE = """
STRUCTURE TO FOLLOW (950-1050 words total):

Opening (100-150 words):
- Start with a specific concrete observation — a number, a moment, a contradiction
- NOT a question. NOT "In recent years". NOT "The world is changing."
- The first sentence must make someone want to read the second.

Core argument (200-250 words):
- State what you actually think — the non-obvious take
- Anchor with one strong data point from the research
- Opinions stated plainly, not hedged

Supporting move 1 (150-200 words):
- First layer of evidence, grounded in a source from the research brief

Supporting move 2 (150-200 words):
- Different angle — technical / commercial / political

Supporting move 3 or counterargument (150-200 words):
- Third supporting point OR steelman the opposing view and knock it down

Closing (100-150 words):
- No summary. No "in conclusion." No bullet-point recap.
- End with: a forward-looking implication, OR something the piece leaves open
  (stated as a statement, not a question), OR what you'd do differently if running the company/fund/team
"""


def run(research_brief: str, voice_context: str, model: str, slug: str = "draft") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    system = (
        "You are ghostwriting a blog post for Rahul.\n\n"
        "Voice rules — follow these exactly:\n"
        f"{voice_context}\n\n"
        f"{STRUCTURE}\n\n"
        "Output only the article, starting with the title as # Heading. "
        "No preamble. No commentary before or after the article."
    )

    print("  [draft] Calling Ollama to generate draft...")
    draft_text = call_ollama(research_brief, system=system, timeout=300, model=model)

    wc = count_words(draft_text)
    fm = make_front_matter(slug, "draft", wc)

    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-draft.md")
    with open(out_path, "w") as f:
        f.write(fm + draft_text)

    print(f"  Draft saved → {out_path} ({wc} words)")
    return draft_text
