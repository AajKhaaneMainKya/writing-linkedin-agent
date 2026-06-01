import os

from skills.common import call_ollama_with_retry, count_words, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "linkedin")


def run(validated_text: str, voice_context: str, model: str, slug: str = "post") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()

    system = (
        "You are distilling a blog post into a LinkedIn post for Rahul.\n\n"
        "Voice rules from CLAUDE.md — follow exactly:\n"
        f"{voice_context}\n\n"
        "LinkedIn FORMAT RULES (non-negotiable):\n"
        "- ~300 words. Hard ceiling at 320.\n"
        "- No hashtags.\n"
        "- No 'link in comments' or 'I wrote a post about X' framing — write it as a standalone piece.\n"
        "- First line must work as a hook without reading the rest. A statement, not a question.\n"
        "- Line breaks used deliberately — not after every sentence, but to pace the reader.\n"
        "- Take a stronger, more direct position than the blog — LinkedIn rewards a sharper opinion.\n"
        "- No 'what do you think?' or any closing question.\n\n"
        "STRUCTURE:\n"
        "Hook (1-2 lines): The most provocative claim from the blog. Statement, not a question.\n\n"
        "The point (3-5 lines): Core argument compressed. Drop the supporting moves, keep the spine.\n\n"
        "One concrete detail (2-3 lines): The single best data point or specific claim from the research.\n\n"
        "Close (2-3 lines): What this means for investors, operators, or builders. No summary.\n\n"
        "STRIP FROM THE BLOG:\n"
        "- All supporting moves beyond the strongest one\n"
        "- Source attributions (unless a named company/person anchors the claim)\n"
        "- The counterargument section (unless it IS the point)\n"
        "- Hedged qualifications — pick a side\n\n"
        "Output only the LinkedIn post. No preamble or commentary."
    )

    prompt = f"Distill this blog post into a LinkedIn post:\n\n{validated_text}"

    post = call_ollama_with_retry(prompt, system=system, label="linkedin", model=model)

    wc = count_words(post)
    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-linkedin.md")
    with open(out_path, "w") as f:
        f.write(post)

    print(f"  LinkedIn post saved → {out_path} ({wc} words)")
    return post
