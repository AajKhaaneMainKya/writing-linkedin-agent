#!/usr/bin/env python3
"""Client — submits topic to Railway server, polls progress, saves outputs locally.

Usage:
    python run.py 'your topic here'

Environment variables:
    SERVER_URL  — base URL of the Railway server
"""

import base64
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

SERVER_URL = os.environ.get(
    "SERVER_URL", "https://writing-linkedin-agent-production.up.railway.app"
).rstrip("/")

ROOT = os.path.dirname(os.path.abspath(__file__))

POLL_INTERVAL = 5  # seconds


def save_file(path: str, content: str, encoding: str) -> None:
    full_path = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    if encoding == "base64":
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(content))
    else:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def print_event(entry: dict) -> None:
    kind = entry.get("event", "")

    if kind == "start":
        print(f"\nTopic : {entry['topic']}")
        print(f"Model : {entry['model']}")
        print(f"Slug  : {entry['slug']}")
        print()

    elif kind == "skill_start":
        skill = entry["skill"]
        attempt = entry.get("attempt")
        suffix = f" (attempt {attempt})" if attempt else ""
        print(f"  → {skill}{suffix} …", end="", flush=True)

    elif kind == "skill_done":
        parts = [f"{entry.get('time', '?')}s"]
        if "words" in entry:
            parts.append(f"{entry['words']} words")
        if "score" in entry:
            parts.append(f"score {entry['score']}/100")
        if "passed" in entry:
            parts.append("PASS" if entry["passed"] else "FAIL")
        print(f" done ({', '.join(parts)})")

    elif kind == "retry":
        print(f"\n  Retry {entry['attempt']}/{entry['max']} "
              f"(score {entry['score']}/100)")

    elif kind == "warning":
        print(f"\n  WARNING: {entry['message']}")

    elif kind == "error":
        print(f"\n  ERROR: {entry['message']}")


def submit(topic: str) -> str:
    print(f"Connecting to {SERVER_URL} …")
    try:
        resp = requests.post(
            f"{SERVER_URL}/run",
            json={"topic": topic},
            timeout=15,
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {SERVER_URL}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} — {resp.text[:200]}")
        sys.exit(1)

    job_id = resp.json()["job_id"]
    print(f"\n{'=' * 56}")
    print(f"  JOB ID: {job_id}")
    print(f"{'=' * 56}")
    print(f"\nPolling every {POLL_INTERVAL}s — Ctrl-C to stop watching\n"
          f"(the job keeps running on the server)\n")
    return job_id


def poll(job_id: str) -> dict:
    seen = 0
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            resp = requests.get(f"{SERVER_URL}/status/{job_id}", timeout=15)
        except requests.exceptions.ConnectionError:
            print("  (connection error, retrying…)")
            continue

        if resp.status_code != 200:
            print(f"ERROR: status check failed ({resp.status_code})")
            sys.exit(1)

        data = resp.json()
        log = data.get("log", [])

        for entry in log[seen:]:
            print_event(entry)
        seen = len(log)

        if data["status"] == "done":
            return data
        if data["status"] == "error":
            print(f"\nERROR: {data.get('error', 'unknown error')}")
            sys.exit(1)


def fetch_result(job_id: str) -> dict:
    try:
        resp = requests.get(f"{SERVER_URL}/result/{job_id}", timeout=30)
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to fetch result")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: result fetch failed ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    return resp.json()


def main(topic: str) -> None:
    job_id = submit(topic)

    try:
        poll(job_id)
    except KeyboardInterrupt:
        print(f"\n\nStopped watching. Job is still running on the server.")
        print(f"To fetch results later:\n"
              f"  python run.py --result {job_id}")
        sys.exit(0)

    result = fetch_result(job_id)
    files = result["files"]

    print("\nSaving files locally …")
    for key in ("research", "blog", "linkedin", "pdf"):
        info = files[key]
        save_file(info["path"], info["content"], info["encoding"])
        print(f"  Saved → {info['path']}")

    print(f"\nDone — score {result['score']}/100")
    print(f"  Blog     : {files['blog']['path']} ({result['blog_words']} words)")
    print(f"  LinkedIn : {files['linkedin']['path']} ({result['linkedin_words']} words)")
    print(f"  Research : {files['research']['path']}")
    print(f"  PDF      : {files['pdf']['path']}")


def fetch_and_save(job_id: str) -> None:
    """Called when user runs: python run.py --result <job_id>"""
    print(f"Fetching result for job {job_id} …")
    result = fetch_result(job_id)
    files = result["files"]

    for key in ("research", "blog", "linkedin", "pdf"):
        info = files[key]
        save_file(info["path"], info["content"], info["encoding"])
        print(f"  Saved → {info['path']}")

    print(f"\nDone — score {result['score']}/100")
    print(f"  Blog     : {files['blog']['path']} ({result['blog_words']} words)")
    print(f"  LinkedIn : {files['linkedin']['path']} ({result['linkedin_words']} words)")
    print(f"  Research : {files['research']['path']}")
    print(f"  PDF      : {files['pdf']['path']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run.py 'your topic here'")
        print("  python run.py --result <job_id>   # fetch a completed job")
        sys.exit(1)

    if sys.argv[1] == "--result":
        if len(sys.argv) < 3:
            print("ERROR: --result requires a job_id")
            sys.exit(1)
        fetch_and_save(sys.argv[2])
    else:
        topic = " ".join(sys.argv[1:])
        main(topic)
