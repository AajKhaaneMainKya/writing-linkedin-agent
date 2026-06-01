# Content Pipeline — Build Spec for Claude Code

## What this is
An end-to-end automated content pipeline that takes a topic as input and produces:
1. A ~1000 word blog post (markdown + PDF)
2. A ~300 word LinkedIn post distilled from the blog

All LLM inference runs locally via **Ollama**. No external API keys required.

---

## Stack
- **LLM inference**: Ollama (local) — default model: `mistral`
- **Web research**: Python `requests` + `BeautifulSoup` for scraping; DuckDuckGo search API (no key needed) for discovery
- **Deep scraping fallback**: Playwright (Chromium, headless)
- **PDF export**: `reportlab`
- **Orchestration**: Single Python script `pipeline.py` that calls each skill in sequence
- **Language**: Python 3.10+

---

## Folder structure to build
```
content-pipeline/
├── README.md                          ← this file
├── CLAUDE.md                          ← voice rules, always loaded by pipeline
├── pipeline.py                        ← main orchestrator, runs all skills in order
├── requirements.txt                   ← all pip dependencies
├── .env.example                       ← environment variable template
├── .claude/
│   └── skills/
│       ├── research.md
│       ├── draft.md
│       ├── proofread.md
│       ├── de-aify.md
│       ├── validate.md
│       ├── linkedin-distill.md
│       └── export-pdf.md
├── outputs/
│   ├── research/                      ← research briefs
│   ├── blog/                          ← draft → proofed → deaified → validated
│   ├── linkedin/                      ← linkedin posts
│   └── pdf/                           ← final PDFs
└── skills/
    ├── research.py
    ├── draft.py
    ├── proofread.py
    ├── de_aify.py
    ├── validate.py
    ├── linkedin_distill.py
    └── export_pdf.py
```

---

## How it runs

Start Ollama once (keep this running in the background):
```bash
ollama serve
```

Then give it a topic:
```bash
python pipeline.py "why TSMC's Arizona fabs change foundry economics for fabless players"
```

That's the only command you need. The pipeline handles everything else.

---

## Debug commands (for development only)
```bash
# Run a single skill in isolation
python pipeline.py --skill research "your topic"
python pipeline.py --skill validate

# Use a different model
OLLAMA_MODEL=llama3 python pipeline.py "your topic"
```

---

## Prerequisites

### 1. Install Ollama
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a model
```bash
ollama pull mistral        # recommended default (~4GB)
ollama pull phi3           # lighter, good for 8GB RAM
ollama pull llama3         # better quality if you have 16GB+
```

### 3. Start Ollama
```bash
ollama serve
# Runs on http://localhost:11434 by default
```

### 4. Install Python dependencies
```bash
pip install -r requirements.txt --break-system-packages
```

### 5. Install Playwright (for deep scraping fallback)
```bash
pip install playwright --break-system-packages
playwright install chromium
```

---

## requirements.txt to generate
```
requests>=2.31.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
reportlab>=4.0.0
python-dotenv>=1.0.0
markdown>=3.5.0
```

---

## pipeline.py — what to build

The orchestrator should:

1. **Check Ollama is running** before anything else. Print clear error and exit if not.
2. **Load CLAUDE.md** into memory as `voice_context` — passed to every skill that calls Ollama.
3. **Run skills in sequence**, passing outputs between them:
   ```
   research(topic) → research_brief
   draft(research_brief, voice_context) → draft_text
   proofread(draft_text, voice_context) → proofed_text
   de_aify(proofed_text, voice_context) → clean_text
   validate(clean_text, voice_context) → (score, pass/fail, notes)
   ```
4. **Validation gate**: if score < 75, print redraft notes and loop back to draft (max 2 retries).
5. **On pass**: run linkedin_distill and export_pdf in parallel (or sequence is fine).
6. **Print a summary** at the end:
   ```
   ✓ Research brief  → outputs/research/2026-05-31-tsmc-arizona-research.md
   ✓ Blog post       → outputs/blog/2026-05-31-tsmc-arizona-validated.md (1024 words)
   ✓ LinkedIn post   → outputs/linkedin/2026-05-31-tsmc-arizona-linkedin.md (298 words)
   ✓ PDF             → outputs/pdf/2026-05-31-tsmc-arizona.pdf
   Validation score  → 84/100
   Total time        → 3m 12s
   ```

---

## Each skill as a Python module

Each file in `skills/` should:
- Read its corresponding SKILL.md from `.claude/skills/[name]/SKILL.md` for reference
- Implement a single function: `run(input, voice_context, model) -> output`
- Handle Ollama errors gracefully — retry once on timeout, then raise
- Write its output file to the correct `outputs/` subdirectory
- Return the output text for the next skill to consume

---

## Ollama call pattern (consistent across all skills)
```python
import requests, os, sys

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")

def check_ollama():
    try:
        r = requests.get(OLLAMA_BASE, timeout=3)
    except Exception:
        print("ERROR: Ollama is not running.")
        print("Fix: run `ollama serve` in a separate terminal")
        sys.exit(1)

def call_ollama(prompt: str, system: str = "", timeout: int = 120) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()
```

---

## Web search in research.py (no API key needed)
```python
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

def ddg_search(query: str, max_results: int = 6) -> list[dict]:
    """DuckDuckGo HTML scrape — no API key required."""
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for r in soup.select(".result__body")[:max_results]:
        title = r.select_one(".result__title")
        snippet = r.select_one(".result__snippet")
        link = r.select_one(".result__url")
        if title and snippet:
            results.append({
                "title": title.get_text(strip=True),
                "snippet": snippet.get_text(strip=True),
                "url": link.get_text(strip=True) if link else ""
            })
    return results
```

---

## .env.example
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OUTPUT_DIR=outputs
```

---

## Notes for Claude Code
- Read every skill file in `.claude/skills/` before writing any Python — they are named `research.md`, `draft.md`, `proofread.md`, `de-aify.md`, `validate.md`, `linkedin-distill.md`, `export-pdf.md`
- The CLAUDE.md voice rules must be injected into the system prompt for every Ollama call that generates or edits text
- Do not add any external LLM API calls — Ollama only
- Validate that `ollama serve` is running at startup
- All outputs go to `outputs/` subdirectories with date-prefixed filenames
- The pipeline should be runnable with a single command from the project root
