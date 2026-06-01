#!/usr/bin/env python3
"""Client — sends topic to Railway server, streams progress, saves outputs locally.

Usage:
    python run.py 'your topic here'

Environment variables:
    SERVER_URL  — base URL of the Railway server (default: https://writing-linkedin-agent.up.railway.app)
"""

import base64
import json
import os
import sys

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)

SERVER_URL = os.environ.get(
    "SERVER_URL", "https://writing-linkedin-agent.up.railway.app"
).rstrip("/")

ROOT = os.path.dirname(os.path.abspath(__file__))


def save_file(path: str, content: str, encoding: str) -> None:
    full_path = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    if encoding == "base64":
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(content))
    else:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def stream_run(topic: str) -> None:
    url = f"{SERVER_URL}/run"
    print(f"Connecting to {SERVER_URL} …")

    try:
        resp = requests.post(
            url,
            json={"topic": topic},
            stream=True,
            timeout=(10, 600),
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {SERVER_URL}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: Server returned {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)

    for raw_line in resp.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if not line.startswith("data: "):
            continue

        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue

        kind = event.get("event", "")

        if kind == "start":
            print(f"\nTopic : {event['topic']}")
            print(f"Model : {event['model']}")
            print(f"Slug  : {event['slug']}")
            print()

        elif kind == "skill_start":
            skill = event["skill"]
            attempt = event.get("attempt")
            suffix = f" (attempt {attempt})" if attempt else ""
            print(f"  → {skill}{suffix} …", end="", flush=True)

        elif kind == "skill_done":
            parts = [f"{event.get('time', '?')}s"]
            if "words" in event:
                parts.append(f"{event['words']} words")
            if "score" in event:
                parts.append(f"score {event['score']}/100")
            if "passed" in event:
                parts.append("PASS" if event["passed"] else "FAIL")
            print(f" done ({', '.join(parts)})")

        elif kind == "retry":
            print(f"\n  ↺ Retry {event['attempt']}/{event['max']} "
                  f"(score {event['score']}/100)")

        elif kind == "warning":
            print(f"\n  ⚠ {event['message']}")

        elif kind == "file":
            path = event["path"]
            save_file(path, event["content"], event["encoding"])
            print(f"  ✓ saved → {path}")

        elif kind == "complete":
            print(f"\nDone — score {event['score']}/100")
            print(f"  Blog      : {event['blog_file']} ({event['blog_words']} words)")
            print(f"  LinkedIn  : {event['linkedin_file']} ({event['linkedin_words']} words)")
            print(f"  Research  : {event['research_file']}")
            print(f"  PDF       : {event['pdf_file']}")

        elif kind == "error":
            print(f"\nERROR: {event['message']}")
            detail = event.get("detail", "")
            if detail:
                print(detail)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run.py 'your topic here'")
        sys.exit(1)

    topic = " ".join(sys.argv[1:])
    stream_run(topic)
