#!/usr/bin/env python3
"""Content pipeline — topic → blog post + LinkedIn post + PDF via Ollama.

Usage:
    python pipeline.py "your topic here"
    python pipeline.py --skill research "your topic"
    python pipeline.py --skill validate
    OLLAMA_MODEL=llama3 python pipeline.py "your topic"
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


# ── Dependency bootstrap ───────────────────────────────────────────────────────
# Runs before any third-party import. If a required package is missing, installs
# from requirements.txt then re-execs this process so the original command works
# exactly as typed — no manual pip step needed.
def _ensure_deps() -> None:
    _required = [
        ("requests",  "requests"),
        ("bs4",       "beautifulsoup4"),
        ("reportlab", "reportlab"),
        ("dotenv",    "python-dotenv"),
    ]
    missing = [pkg for import_name, pkg in _required if not _can_import(import_name)]
    if not missing:
        return

    req = os.path.join(ROOT, "requirements.txt")
    print(f"Installing missing packages: {', '.join(missing)}")
    import subprocess
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", req, "--break-system-packages"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("Done. Starting pipeline...\n")
    # Replace this process with a fresh one — all packages now importable.
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


_ensure_deps()
# ── End bootstrap ─────────────────────────────────────────────────────────────


import argparse  # noqa: E402  (stdlib, but placed after bootstrap for clarity)
import time      # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from skills.common import (
    OLLAMA_MODEL,
    check_ollama,
    count_words,
    extract_slug,
    find_latest,
    make_front_matter,
    slugify,
    strip_changelogs,
    strip_front_matter,
    today,
)
import skills.research as research
import skills.draft as draft
import skills.proofread as proofread
import skills.de_aify as de_aify
import skills.validate as validate
import skills.linkedin_distill as linkedin_distill
import skills.export_pdf as export_pdf

BLOG_DIR = os.path.join(ROOT, "outputs", "blog")
RESEARCH_DIR = os.path.join(ROOT, "outputs", "research")
LINKEDIN_DIR = os.path.join(ROOT, "outputs", "linkedin")
PDF_DIR = os.path.join(ROOT, "outputs", "pdf")
CLAUDE_MD = os.path.join(ROOT, "CLAUDE.md")


def rel(path: str) -> str:
    """Return path relative to project root for clean summary output."""
    return os.path.relpath(path, ROOT)


def load_voice_context() -> str:
    with open(CLAUDE_MD, "r") as f:
        return f.read()


def run_full_pipeline(topic: str, model: str) -> None:
    t_start = time.time()
    date_str = today()
    slug = slugify(topic)
    voice = load_voice_context()

    print(f"\n=== Content Pipeline ===")
    print(f"Topic : {topic}")
    print(f"Model : {model}")
    print(f"Slug  : {slug}\n")

    # Step 1 — Research
    print("[1/6] Research")
    research_brief = research.run(topic, voice, model, slug=slug)
    research_path = os.path.join(RESEARCH_DIR, f"{date_str}-{slug}-research.md")

    # Steps 2–5 — Draft → Proofread → De-AIify → Validate with retry loop
    MAX_RETRIES = 2
    validated_text = ""
    clean_text = ""
    score = 0
    passed = False
    notes_str = ""

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            print(f"\n--- Retry {attempt}/{MAX_RETRIES}: redrafting with validator notes ---")

        print(f"\n[2/6] Draft{'  (retry)' if attempt > 0 else ''}")
        brief_input = research_brief
        if attempt > 0 and notes_str:
            brief_input = (
                f"{research_brief}\n\n"
                f"---\nREDRAFT NOTES FROM PREVIOUS ATTEMPT:\n{notes_str}\n"
                "Address each issue above in the new draft."
            )
        draft_text = draft.run(brief_input, voice, model, slug=slug)

        print("\n[3/6] Proofread")
        proofed_text = proofread.run(draft_text, voice, model, slug=slug)

        print("\n[4/6] De-AIify")
        clean_text = de_aify.run(proofed_text, voice, model, slug=slug)

        print("\n[5/6] Validate")
        score, passed, notes_str, validated_text = validate.run(clean_text, voice, model, slug=slug)

        if passed:
            break
        if attempt < MAX_RETRIES:
            print(f"\n  Score {score}/100 — retrying with notes...")

    validated_path = os.path.join(BLOG_DIR, f"{date_str}-{slug}-validated.md")

    # Force-save if still failing after all retries
    if not passed:
        print(f"\nWARNING: Validation failed after {MAX_RETRIES} retries (score {score}/100).")
        print("Saving best attempt and continuing to outputs...")
        validated_text = clean_text
        with open(validated_path, "w") as f:
            f.write(make_front_matter(slug, "validated-forced", count_words(clean_text)) + clean_text)

    wc = count_words(validated_text)

    # Step 6a — LinkedIn distill
    print("\n[6a/6] LinkedIn distill")
    linkedin_post = linkedin_distill.run(validated_text, voice, model, slug=slug)
    linkedin_wc = count_words(linkedin_post)
    linkedin_path = os.path.join(LINKEDIN_DIR, f"{date_str}-{slug}-linkedin.md")

    # Step 6b — PDF export
    print("\n[6b/6] PDF export")
    pdf_path = export_pdf.run(validated_text, voice, model, slug=slug)

    elapsed = int(time.time() - t_start)
    mins, secs = divmod(elapsed, 60)

    print(f"\n{'=' * 52}")
    print(f"✓ Research brief  → {rel(research_path)}")
    print(f"✓ Blog post       → {rel(validated_path)} ({wc} words)")
    print(f"✓ LinkedIn post   → {rel(linkedin_path)} ({linkedin_wc} words)")
    print(f"✓ PDF             → {rel(pdf_path)}")
    print(f"Validation score  → {score}/100")
    print(f"Total time        → {mins}m {secs}s")


def run_single_skill(skill_name: str, topic: str | None, model: str) -> None:
    voice = load_voice_context()

    if skill_name == "research":
        if not topic:
            print("ERROR: --skill research requires a topic argument")
            sys.exit(1)
        slug = slugify(topic)
        research.run(topic, voice, model, slug=slug)

    elif skill_name == "draft":
        path = find_latest(RESEARCH_DIR, "*-research.md")
        if not path:
            print("ERROR: No research brief in outputs/research/. Run research skill first.")
            sys.exit(1)
        slug = extract_slug(path, "research")
        with open(path) as f:
            brief = f.read()
        draft.run(brief, voice, model, slug=slug)

    elif skill_name == "proofread":
        path = find_latest(BLOG_DIR, "*-draft.md")
        if not path:
            print("ERROR: No draft file in outputs/blog/")
            sys.exit(1)
        slug = extract_slug(path, "draft")
        text = strip_front_matter(open(path).read())
        proofread.run(text, voice, model, slug=slug)

    elif skill_name in ("de-aify", "de_aify"):
        path = find_latest(BLOG_DIR, "*-proofed.md")
        if not path:
            print("ERROR: No proofed file in outputs/blog/")
            sys.exit(1)
        slug = extract_slug(path, "proofed")
        text = strip_changelogs(strip_front_matter(open(path).read()))
        de_aify.run(text, voice, model, slug=slug)

    elif skill_name == "validate":
        path = find_latest(BLOG_DIR, "*-deaified.md")
        if not path:
            print("ERROR: No deaified file in outputs/blog/")
            sys.exit(1)
        slug = extract_slug(path, "deaified")
        text = strip_changelogs(strip_front_matter(open(path).read()))
        validate.run(text, voice, model, slug=slug)

    elif skill_name in ("linkedin", "linkedin-distill"):
        path = find_latest(BLOG_DIR, "*-validated.md")
        if not path:
            print("ERROR: No validated file in outputs/blog/")
            sys.exit(1)
        slug = extract_slug(path, "validated")
        text = strip_front_matter(open(path).read())
        linkedin_distill.run(text, voice, model, slug=slug)

    elif skill_name in ("export-pdf", "pdf"):
        path = find_latest(BLOG_DIR, "*-validated.md")
        if not path:
            print("ERROR: No validated file in outputs/blog/")
            sys.exit(1)
        slug = extract_slug(path, "validated")
        text = strip_front_matter(open(path).read())
        export_pdf.run(text, voice, model, slug=slug)

    else:
        print(f"ERROR: Unknown skill '{skill_name}'")
        print("Available: research, draft, proofread, de-aify, validate, linkedin, export-pdf")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content pipeline — blog + LinkedIn + PDF from a topic via Ollama"
    )
    parser.add_argument("topic", nargs="?", help="Topic to write about")
    parser.add_argument(
        "--skill",
        metavar="SKILL",
        help="Run one skill only: research, draft, proofread, de-aify, validate, linkedin, export-pdf",
    )
    parser.add_argument("--model", default=None, help="Override Ollama model (default: mistral)")
    args = parser.parse_args()

    model = args.model or OLLAMA_MODEL

    check_ollama()

    if args.skill:
        run_single_skill(args.skill, args.topic, model)
    else:
        if not args.topic:
            parser.error("A topic is required for the full pipeline")
        run_full_pipeline(args.topic, model)


if __name__ == "__main__":
    main()
