import os

from skills.common import call_ollama_with_retry, count_words, make_front_matter, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "blog")

INSTRUCTIONS = (
    "FORMAT: Write in continuous prose only. No structural labels, no section headers, "
    "no 'Reason 1:', no 'Counterargument:', no numbered points. Paragraph after paragraph.\n\n"
    "SHAPE OF THE PIECE (in prose, not labelled):\n"
    "Open with a specific concrete observation — a number, a moment, a contradiction. "
    "NOT a question. NOT 'In recent years'. The first sentence must make someone want to read the second.\n"
    "Then state the core argument — the non-obvious take — anchored with one strong data point from the research. "
    "Then three supporting moves: first a layer of evidence from the sources; then a different angle "
    "(technical, commercial, or political); then either a third supporting point or steelman the opposing view "
    "and knock it down. Close without a summary. No 'in conclusion.' End with a forward-looking implication "
    "or something the piece leaves deliberately open — stated as a statement, not a question.\n\n"
    "WORD COUNT (non-negotiable):\n"
    "You must write a minimum of 1000 words. Count your words as you write. "
    "Do not stop before 1000 words. If you finish a thought early, go deeper — add specific examples, "
    "historical context, company names, dollar figures, market dynamics. Keep writing until you hit 1000 words."
)


def run(research_brief: str, voice_context: str, model: str, slug: str = "draft") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    system = (
        "You are ghostwriting a blog post for Rahul.\n\n"
        "Voice rules — follow these exactly:\n"
        f"{voice_context}\n\n"
        f"{INSTRUCTIONS}\n\n"
        "Output only the article, starting with the title as # Heading. "
        "No preamble. No commentary before or after the article."
    )

    draft_text = call_ollama_with_retry(research_brief, system=system, label="draft", model=model)

    wc = count_words(draft_text)
    fm = make_front_matter(slug, "draft", wc)

    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-draft.md")
    with open(out_path, "w") as f:
        f.write(fm + draft_text)

    print(f"  Draft saved → {out_path} ({wc} words)")
    return draft_text
