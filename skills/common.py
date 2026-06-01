import glob
import json
import os
import re
import sys
import time

import requests

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "https://ollama-production-9144.up.railway.app")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_ollama():
    try:
        requests.get(OLLAMA_BASE, timeout=3)
    except Exception:
        print("ERROR: Ollama is not running.")
        print("Fix: run `ollama serve` in a separate terminal")
        sys.exit(1)


def call_ollama(prompt: str, system: str = "", timeout: int = 300, model: str = None) -> str:
    mdl = model or OLLAMA_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(2):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json={"model": mdl, "messages": messages, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except requests.exceptions.Timeout:
            if attempt == 0:
                print("  [Ollama] Request timed out, retrying...")
                continue
            raise
    raise RuntimeError("Ollama call failed after retry")


def call_ollama_stream(prompt: str, system: str = "", timeout: int = 600, model: str = None) -> str:
    """Streaming variant of call_ollama — keeps the connection alive chunk by chunk."""
    mdl = model or OLLAMA_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": mdl, "messages": messages, "stream": True},
        stream=True,
        timeout=(10, timeout),
    )
    resp.raise_for_status()

    chunks: list[str] = []
    for raw in resp.iter_lines():
        if not raw:
            continue
        chunk = json.loads(raw)
        token = chunk.get("message", {}).get("content", "")
        if token:
            chunks.append(token)
        if chunk.get("done"):
            break

    return "".join(chunks).strip()


def call_ollama_with_retry(
    prompt: str,
    system: str = "",
    timeout: int = 600,
    model: str = None,
    label: str = "ollama",
    max_retries: int = 3,
    retry_wait: int = 10,
) -> str:
    """call_ollama_stream with retry. Logs each attempt with the caller's label."""
    for attempt in range(max_retries + 1):
        tag = f"attempt {attempt + 1}/{max_retries + 1}"
        print(f"  [{label}] Calling Ollama ({tag}, stream=True, timeout={timeout}s)...")
        try:
            return call_ollama_stream(prompt, system=system, timeout=timeout, model=model)
        except Exception as exc:
            if attempt < max_retries:
                print(f"  [{label}] {tag} failed: {exc}. Retrying in {retry_wait}s...")
                time.sleep(retry_wait)
            else:
                print(f"  [{label}] All {max_retries + 1} attempts failed.")
                raise


def ollama_summarise(text: str, prompt: str, model: str = None, timeout: int = 300) -> str:
    mdl = model or OLLAMA_MODEL
    for attempt in range(2):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": mdl,
                    "prompt": f"{prompt}\n\n{text[:3000]}",
                    "stream": False,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
        except requests.exceptions.Timeout:
            if attempt == 0:
                print("  [Ollama] Summarise timed out, retrying...")
                continue
            raise
    raise RuntimeError("Ollama summarise failed after retry")


def slugify(text: str, max_words: int = 5) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    words = [w for w in text.split() if w][:max_words]
    return "-".join(words)


def today() -> str:
    from datetime import date
    return date.today().strftime("%Y-%m-%d")


def count_words(text: str) -> int:
    text = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"\n---\n##.*", "", text, flags=re.DOTALL)
    return len(text.split())


def strip_front_matter(text: str) -> str:
    return re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL)


def strip_changelogs(text: str) -> str:
    return re.sub(r"\n---\n## (?:Proofread|De-AIify) changes.*", "", text, flags=re.DOTALL)


def find_latest(directory: str, suffix: str) -> str | None:
    files = sorted(glob.glob(os.path.join(directory, f"*{suffix}")))
    return files[-1] if files else None


def extract_slug(filepath: str, stage: str) -> str:
    filename = os.path.basename(filepath)
    # Format: YYYY-MM-DD-{slug}-{stage}.md  (date is 10 chars + 1 dash = 11)
    name = filename[11:]
    suffix = f"-{stage}.md"
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return re.sub(r"\.md$", "", name)


def make_front_matter(slug: str, status: str, word_count: int, topic: str = "AI") -> str:
    title = slug.replace("-", " ").title()
    return (
        f"---\n"
        f"title: {title}\n"
        f"date: {today()}\n"
        f"status: {status}\n"
        f"word_count: {word_count}\n"
        f"topic: {topic}\n"
        f"---\n\n"
    )
