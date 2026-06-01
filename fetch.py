#!/usr/bin/env python3
"""Retrieve outputs for a completed job by ID.

Usage:
    python fetch.py <job_id>                 # fetch all outputs
    python fetch.py <job_id> --type blog
    python fetch.py <job_id> --type linkedin
    python fetch.py <job_id> --type research
    python fetch.py <job_id> --type pdf

Environment variables:
    SERVER_URL  — base URL of the Railway server
"""

import base64
import os
import sys

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

SERVER_URL = os.environ.get(
    "SERVER_URL", "https://writing-linkedin-agent-production.up.railway.app"
).rstrip("/")

ROOT = os.path.dirname(os.path.abspath(__file__))

VALID_TYPES = ("blog", "linkedin", "research", "pdf")


def save_file(path: str, content: str, encoding: str) -> str:
    full_path = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    if encoding == "base64":
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(content))
    else:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return full_path


def fetch_result(job_id: str) -> dict:
    url = f"{SERVER_URL}/result/{job_id}"
    print(f"Fetching {url} …")
    try:
        resp = requests.get(url, timeout=30)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {SERVER_URL}")
        sys.exit(1)

    if resp.status_code == 404:
        print(f"ERROR: Job '{job_id}' not found — it may have expired or never existed.")
        sys.exit(1)

    if resp.status_code == 409:
        data = resp.json()
        print(f"ERROR: Job is '{data.get('status', 'not done')}' — results not available yet.")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)

    return resp.json()


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python fetch.py <job_id>")
        print("  python fetch.py <job_id> --type blog|linkedin|research|pdf")
        sys.exit(1)

    job_id = args[0]
    output_type: str | None = None

    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 >= len(args):
            print("ERROR: --type requires a value: blog, linkedin, research, or pdf")
            sys.exit(1)
        output_type = args[idx + 1]
        if output_type not in VALID_TYPES:
            print(f"ERROR: unknown type '{output_type}'. Choose from: {', '.join(VALID_TYPES)}")
            sys.exit(1)

    result = fetch_result(job_id)
    files = result.get("files", {})

    if not files:
        print("ERROR: No files in result.")
        sys.exit(1)

    keys = [output_type] if output_type else list(VALID_TYPES)
    saved: list[str] = []

    for key in keys:
        info = files.get(key)
        if not info:
            print(f"  (no '{key}' output in result)")
            continue
        full_path = save_file(info["path"], info["content"], info["encoding"])
        saved.append(full_path)
        print(f"  Saved → {info['path']}")

    if saved:
        print(f"\n{len(saved)} file(s) saved.")
        if result.get("score") is not None:
            print(f"Score    : {result['score']}/100")
        if result.get("blog_words"):
            print(f"Blog     : {result['blog_words']} words")
        if result.get("linkedin_words"):
            print(f"LinkedIn : {result['linkedin_words']} words")


if __name__ == "__main__":
    main()
