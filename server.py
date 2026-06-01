#!/usr/bin/env python3
"""Server — runs on Railway.

Endpoints:
    GET  /health            — liveness check
    POST /run               — enqueue topic, returns {"job_id": "uuid"} immediately
    GET  /status/<job_id>   — current progress (skill running, log of completed steps)
    GET  /result/<job_id>   — all outputs when done (text files + PDF as base64)

Environment variables:
    PORT              — HTTP port (Railway sets this automatically)
    OLLAMA_BASE_URL   — Ollama server URL
    OLLAMA_MODEL      — model name (default: mistral)
"""

import base64
import json
import os
import sys
import threading
import time
import traceback
import uuid

from flask import Flask, Response, request

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

# Use /data if a persistent volume is mounted there, otherwise fall back to local
_DATA = "/data" if os.path.isdir("/data") else ROOT
BLOG_DIR     = os.path.join(_DATA, "outputs", "blog")
RESEARCH_DIR = os.path.join(_DATA, "outputs", "research")
LINKEDIN_DIR = os.path.join(_DATA, "outputs", "linkedin")
PDF_DIR      = os.path.join(_DATA, "outputs", "pdf")

for _d in [BLOG_DIR, RESEARCH_DIR, LINKEDIN_DIR, PDF_DIR]:
    os.makedirs(_d, exist_ok=True)

# ── Job store ─────────────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job(topic: str, model: str) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "queued",
            "topic": topic,
            "model": model,
            "slug": None,
            "current_skill": None,
            "log": [],
            "result": None,
            "error": None,
            "detail": None,
        }
    return job_id


def _log(job: dict, entry: dict) -> None:
    with _jobs_lock:
        job["log"].append(entry)


def _set_skill(job: dict, skill: str | None) -> None:
    with _jobs_lock:
        job["current_skill"] = skill


# ── Pipeline worker (runs in a background thread) ─────────────────────────────

def pipeline_worker(job_id: str, topic: str, model: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job["status"] = "running"

    def log(entry: dict) -> None:
        _log(job, entry)

    try:
        with open(os.path.join(ROOT, "CLAUDE.md")) as f:
            voice = f.read()

        date_str = today()
        slug = slugify(topic)

        with _jobs_lock:
            job["slug"] = slug

        log({"event": "start", "topic": topic, "slug": slug, "model": model})

        # ── 1. Research ───────────────────────────────────────────────────────
        t0 = time.time()
        _set_skill(job, "research")
        log({"event": "skill_start", "skill": "research"})
        brief = research_skill.run(topic, voice, model, slug=slug)
        log({"event": "skill_done", "skill": "research",
             "time": round(time.time() - t0, 1), "words": count_words(brief)})

        research_filename = f"{date_str}-{slug}-research.md"
        research_path = os.path.join(RESEARCH_DIR, research_filename)
        with open(research_path, "w") as f:
            f.write(brief)

        # ── 2-5. Draft → Proofread → De-AIify → Validate (with retry) ────────
        MAX_RETRIES = 2
        validated_text = clean_text = ""
        score = 0
        passed = False
        notes_str = ""

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                log({"event": "retry", "attempt": attempt,
                     "max": MAX_RETRIES, "score": score})

            brief_input = brief
            if attempt > 0 and notes_str:
                brief_input = (
                    f"{brief}\n\n---\nREDRAFT NOTES:\n{notes_str}\n"
                    "Address each issue in the new draft. "
                    "Your previous attempt was too short. This attempt must be longer and more detailed. "
                    "Do not summarise — expand."
                )

            t0 = time.time()
            _set_skill(job, "draft")
            log({"event": "skill_start", "skill": "draft", "attempt": attempt})
            draft_text = draft_skill.run(brief_input, voice, model, slug=slug)
            draft_wc = count_words(draft_text)
            log({"event": "skill_done", "skill": "draft",
                 "time": round(time.time() - t0, 1), "words": draft_wc})

            if draft_wc < 800:
                wc_msg = f"Draft too short ({draft_wc} words), retrying..."
                print(f"  [server] {wc_msg}")
                log({"event": "warning", "message": wc_msg})
                t0 = time.time()
                _set_skill(job, "draft")
                log({"event": "skill_start", "skill": "draft", "attempt": "wc-expand"})
                expanded_input = (
                    brief_input
                    + f"\n\n---\nYour previous draft was only {draft_wc} words. "
                    "This attempt must be longer and more detailed. "
                    "Do not summarise — expand every section with specific data, examples, and analysis."
                )
                draft_text = draft_skill.run(expanded_input, voice, model, slug=slug)
                log({"event": "skill_done", "skill": "draft",
                     "time": round(time.time() - t0, 1), "words": count_words(draft_text)})

            t0 = time.time()
            _set_skill(job, "proofread")
            log({"event": "skill_start", "skill": "proofread"})
            proofed = proofread_skill.run(draft_text, voice, model, slug=slug)
            log({"event": "skill_done", "skill": "proofread",
                 "time": round(time.time() - t0, 1), "words": count_words(proofed)})

            t0 = time.time()
            _set_skill(job, "de-aify")
            log({"event": "skill_start", "skill": "de-aify"})
            clean_text = de_aify_skill.run(proofed, voice, model, slug=slug)
            log({"event": "skill_done", "skill": "de-aify",
                 "time": round(time.time() - t0, 1), "words": count_words(clean_text)})

            t0 = time.time()
            _set_skill(job, "validate")
            log({"event": "skill_start", "skill": "validate"})
            score, passed, notes_str, validated_text = validate_skill.run(
                clean_text, voice, model, slug=slug
            )
            log({"event": "skill_done", "skill": "validate",
                 "time": round(time.time() - t0, 1), "score": score, "passed": passed})

            if passed:
                break

        if not passed:
            validated_text = clean_text
            log({"event": "warning",
                 "message": (f"Validation failed after {MAX_RETRIES} retries "
                             f"(score {score}/100). Using best attempt.")})

        blog_content = (
            make_front_matter(slug, "validated", count_words(validated_text))
            + validated_text
        )
        blog_filename = f"{date_str}-{slug}-validated.md"
        blog_path = os.path.join(BLOG_DIR, blog_filename)
        with open(blog_path, "w") as f:
            f.write(blog_content)

        # ── 6a. LinkedIn ──────────────────────────────────────────────────────
        t0 = time.time()
        _set_skill(job, "linkedin-distill")
        log({"event": "skill_start", "skill": "linkedin-distill"})
        li_post = linkedin_skill.run(validated_text, voice, model, slug=slug)
        log({"event": "skill_done", "skill": "linkedin-distill",
             "time": round(time.time() - t0, 1), "words": count_words(li_post)})

        li_filename = f"{date_str}-{slug}-linkedin.md"
        li_path = os.path.join(LINKEDIN_DIR, li_filename)
        with open(li_path, "w") as f:
            f.write(li_post)

        # ── 6b. PDF ───────────────────────────────────────────────────────────
        t0 = time.time()
        _set_skill(job, "export-pdf")
        log({"event": "skill_start", "skill": "export-pdf"})
        skill_pdf_path = pdf_skill.run(validated_text, voice, model, slug=slug)
        with open(skill_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        log({"event": "skill_done", "skill": "export-pdf",
             "time": round(time.time() - t0, 1)})

        pdf_filename = f"{date_str}-{slug}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # ── Store result ──────────────────────────────────────────────────────
        result = {
            "score": score,
            "blog_words": count_words(validated_text),
            "linkedin_words": count_words(li_post),
            "files": {
                "research": {
                    "path": f"outputs/research/{research_filename}",
                    "content": brief,
                    "encoding": "utf-8",
                },
                "blog": {
                    "path": f"outputs/blog/{blog_filename}",
                    "content": blog_content,
                    "encoding": "utf-8",
                },
                "linkedin": {
                    "path": f"outputs/linkedin/{li_filename}",
                    "content": li_post,
                    "encoding": "utf-8",
                },
                "pdf": {
                    "path": f"outputs/pdf/{pdf_filename}",
                    "content": base64.b64encode(pdf_bytes).decode(),
                    "encoding": "base64",
                },
            },
        }

        log({"event": "complete", "score": score,
             "blog_words": count_words(validated_text),
             "linkedin_words": count_words(li_post)})

        with _jobs_lock:
            job["status"] = "done"
            job["current_skill"] = None
            job["result"] = result

    except Exception as exc:
        with _jobs_lock:
            job["status"] = "error"
            job["current_skill"] = None
            job["error"] = str(exc)
            job["detail"] = traceback.format_exc()
        log({"event": "error", "message": str(exc)})


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
    job_id = _new_job(topic, model)
    threading.Thread(
        target=pipeline_worker, args=(job_id, topic, model), daemon=True
    ).start()
    return {"job_id": job_id}


@app.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {"error": "job not found"}, 404
    return {
        "job_id": job_id,
        "status": job["status"],
        "topic": job["topic"],
        "slug": job["slug"],
        "model": job["model"],
        "current_skill": job["current_skill"],
        "log": list(job["log"]),
        "error": job.get("error"),
    }


@app.route("/result/<job_id>")
def result(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {"error": "job not found"}, 404
    if job["status"] != "done":
        return {"error": f"job is {job['status']}", "status": job["status"]}, 409
    return {"job_id": job_id, **job["result"]}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
