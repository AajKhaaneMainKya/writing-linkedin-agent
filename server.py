#!/usr/bin/env python3
"""Server — runs on Railway.

Endpoints:
    GET  /health  — liveness check
    POST /run     — runs the full pipeline, streams progress via Server-Sent Events

SSE event schema (one JSON object per data: line):
    {"event": "start",        "topic": str, "slug": str, "model": str}
    {"event": "skill_start",  "skill": str, "attempt"?: int}
    {"event": "skill_done",   "skill": str, "time": float, "words"?: int, "score"?: int, "passed"?: bool}
    {"event": "retry",        "attempt": int, "max": int, "score": int}
    {"event": "warning",      "message": str}
    {"event": "file",         "path": str, "content": str, "encoding": "utf-8"|"base64"}
    {"event": "complete",     "score": int, "blog_words": int, "linkedin_words": int,
                               "research_file": str, "blog_file": str,
                               "linkedin_file": str, "pdf_file": str}
    {"event": "error",        "message": str, "detail"?: str}

Environment variables:
    PORT              — HTTP port (Railway sets this automatically)
    OLLAMA_BASE_URL   — Ollama server URL (defaults to Railway-hosted instance)
    OLLAMA_MODEL      — model name (default: mistral)
"""

import base64
import json
import os
import queue
import sys
import threading
import time
import traceback

from flask import Flask, Response, request, stream_with_context

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

from skills.common import (
    OLLAMA_MODEL,
    count_words,
    make_front_matter,
    slugify,
    today,
)
import skills.research as research_skill
import skills.draft as draft_skill
import skills.proofread as proofread_skill
import skills.de_aify as de_aify_skill
import skills.validate as validate_skill
import skills.linkedin_distill as linkedin_skill
import skills.export_pdf as pdf_skill

app = Flask(__name__)

BLOG_DIR = os.path.join(ROOT, "outputs", "blog")
RESEARCH_DIR = os.path.join(ROOT, "outputs", "research")
LINKEDIN_DIR = os.path.join(ROOT, "outputs", "linkedin")
PDF_DIR = os.path.join(ROOT, "outputs", "pdf")

for _d in [BLOG_DIR, RESEARCH_DIR, LINKEDIN_DIR, PDF_DIR]:
    os.makedirs(_d, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def read_file(path: str) -> tuple[str, str]:
    """Return (content, encoding). PDFs are base64-encoded."""
    if path.endswith(".pdf"):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode(), "base64"
    with open(path) as f:
        return f.read(), "utf-8"


# ── Pipeline worker (runs in a thread) ────────────────────────────────────────

def pipeline_worker(topic: str, model: str, q: queue.Queue) -> None:
    """Runs the full pipeline and puts SSE event dicts into q.
    Puts None as a sentinel when finished (pass or error)."""

    def emit(data: dict) -> None:
        q.put(data)

    try:
        with open(os.path.join(ROOT, "CLAUDE.md")) as f:
            voice = f.read()

        date_str = today()
        slug = slugify(topic)

        emit({"event": "start", "topic": topic, "slug": slug, "model": model})

        # ── 1. Research ───────────────────────────────────────────────────────
        t0 = time.time()
        emit({"event": "skill_start", "skill": "research"})
        brief = research_skill.run(topic, voice, model, slug=slug)
        research_path = os.path.join(RESEARCH_DIR, f"{date_str}-{slug}-research.md")
        emit({
            "event": "skill_done", "skill": "research",
            "time": round(time.time() - t0, 1),
            "words": count_words(brief),
        })
        content, enc = read_file(research_path)
        emit({"event": "file",
              "path": f"outputs/research/{date_str}-{slug}-research.md",
              "content": content, "encoding": enc})

        # ── 2-5. Draft → Proofread → De-AIify → Validate (with retry) ────────
        MAX_RETRIES = 2
        validated_text = clean_text = ""
        score = 0
        passed = False
        notes_str = ""

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                emit({"event": "retry", "attempt": attempt,
                      "max": MAX_RETRIES, "score": score})

            brief_input = brief
            if attempt > 0 and notes_str:
                brief_input = (
                    f"{brief}\n\n---\nREDRAFT NOTES:\n{notes_str}\n"
                    "Address each issue in the new draft."
                )

            t0 = time.time()
            emit({"event": "skill_start", "skill": "draft", "attempt": attempt})
            draft_text = draft_skill.run(brief_input, voice, model, slug=slug)
            emit({"event": "skill_done", "skill": "draft",
                  "time": round(time.time() - t0, 1),
                  "words": count_words(draft_text)})

            t0 = time.time()
            emit({"event": "skill_start", "skill": "proofread"})
            proofed = proofread_skill.run(draft_text, voice, model, slug=slug)
            emit({"event": "skill_done", "skill": "proofread",
                  "time": round(time.time() - t0, 1),
                  "words": count_words(proofed)})

            t0 = time.time()
            emit({"event": "skill_start", "skill": "de-aify"})
            clean_text = de_aify_skill.run(proofed, voice, model, slug=slug)
            emit({"event": "skill_done", "skill": "de-aify",
                  "time": round(time.time() - t0, 1),
                  "words": count_words(clean_text)})

            t0 = time.time()
            emit({"event": "skill_start", "skill": "validate"})
            score, passed, notes_str, validated_text = validate_skill.run(
                clean_text, voice, model, slug=slug
            )
            emit({"event": "skill_done", "skill": "validate",
                  "time": round(time.time() - t0, 1),
                  "score": score, "passed": passed})

            if passed:
                break

        validated_path = os.path.join(BLOG_DIR, f"{date_str}-{slug}-validated.md")
        if not passed:
            validated_text = clean_text
            with open(validated_path, "w") as f:
                f.write(
                    make_front_matter(slug, "validated-forced", count_words(clean_text))
                    + clean_text
                )
            emit({"event": "warning",
                  "message": (f"Validation failed after {MAX_RETRIES} retries "
                              f"(score {score}/100). Using best attempt.")})

        content, enc = read_file(validated_path)
        emit({"event": "file",
              "path": f"outputs/blog/{date_str}-{slug}-validated.md",
              "content": content, "encoding": enc})

        # ── 6a. LinkedIn ──────────────────────────────────────────────────────
        t0 = time.time()
        emit({"event": "skill_start", "skill": "linkedin-distill"})
        li_post = linkedin_skill.run(validated_text, voice, model, slug=slug)
        li_path = os.path.join(LINKEDIN_DIR, f"{date_str}-{slug}-linkedin.md")
        emit({"event": "skill_done", "skill": "linkedin-distill",
              "time": round(time.time() - t0, 1),
              "words": count_words(li_post)})
        content, enc = read_file(li_path)
        emit({"event": "file",
              "path": f"outputs/linkedin/{date_str}-{slug}-linkedin.md",
              "content": content, "encoding": enc})

        # ── 6b. PDF ───────────────────────────────────────────────────────────
        t0 = time.time()
        emit({"event": "skill_start", "skill": "export-pdf"})
        pdf_path = pdf_skill.run(validated_text, voice, model, slug=slug)
        emit({"event": "skill_done", "skill": "export-pdf",
              "time": round(time.time() - t0, 1)})
        content, enc = read_file(pdf_path)
        emit({"event": "file",
              "path": f"outputs/pdf/{date_str}-{slug}.pdf",
              "content": content, "encoding": enc})

        # ── Done ──────────────────────────────────────────────────────────────
        emit({
            "event": "complete",
            "score": score,
            "blog_words": count_words(validated_text),
            "linkedin_words": count_words(li_post),
            "research_file": f"outputs/research/{date_str}-{slug}-research.md",
            "blog_file":     f"outputs/blog/{date_str}-{slug}-validated.md",
            "linkedin_file": f"outputs/linkedin/{date_str}-{slug}-linkedin.md",
            "pdf_file":      f"outputs/pdf/{date_str}-{slug}.pdf",
        })

    except Exception as exc:
        emit({"event": "error", "message": str(exc),
              "detail": traceback.format_exc()})

    finally:
        q.put(None)  # sentinel — tells the generator to close the stream


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.route("/run", methods=["POST"])
def run():
    body = request.get_json(force=True, silent=True) or {}
    topic = (body.get("topic") or "").strip()
    if not topic:
        return {"error": "missing 'topic' in request body"}, 400

    model = body.get("model", OLLAMA_MODEL)
    q: queue.Queue = queue.Queue()

    threading.Thread(
        target=pipeline_worker, args=(topic, model, q), daemon=True
    ).start()

    def generate():
        while True:
            try:
                item = q.get(timeout=600)   # 10 min max between events
            except queue.Empty:
                yield sse({"event": "error",
                           "message": "Pipeline timed out between events"})
                break
            if item is None:
                break
            yield sse(item)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
