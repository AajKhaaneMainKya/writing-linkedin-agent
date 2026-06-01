---
name: research
description: Research a topic for a blog post covering AI, semiconductors, deeptech investments, or strategy. Run this first before drafting. Produces a structured research brief saved to outputs/research/.
invocation: manual
allowed-tools: web_search, bash
---

# Skill: research

## Purpose
Gather 6-8 high-quality sources on the given topic. Produce a structured research brief
that the draft skill will use as raw material. Quality over quantity — one precise claim
with a source beats three vague observations.

## Input
`$ARGUMENTS` — the topic or angle for this piece.
Example: "why TSMC's Arizona expansion changes the foundry calculus for US fabless players"

## Ollama usage in this skill
Use Ollama to summarise long scraped content before adding it to the brief.
Do NOT use Ollama to generate the brief itself — that is Claude Code's job reading this skill.

```python
import requests, os

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
OLLAMA_URL = "http://localhost:11434/api/generate"

def ollama_summarise(text, prompt):
    resp = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": f"{prompt}\n\n{text[:3000]}",
        "stream": False
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"].strip()

# Example: summarise a long scraped page
summary = ollama_summarise(scraped_text,
    "Extract the 3 most specific factual claims from this text. "
    "Return only bullet points with numbers, names, and dates where present."
)
```

If Ollama is not running:
```python
try:
    requests.get("http://localhost:11434", timeout=3)
except Exception:
    print("ERROR: Ollama is not running. Start it with: ollama serve")
    sys.exit(1)
```

## Step 1 — Clarify the angle
Before searching, identify:
- What is the central claim or tension in this topic?
- Who is the primary audience? (investors / builders / operators)
- What would make this piece non-obvious? What's the angle that isn't already everywhere?

Write a one-sentence framing hypothesis. Example:
"The Arizona fabs aren't about supply security — they're about Washington's leverage over TSMC pricing."

## Step 2 — Primary web search
Run 4-6 targeted searches. Cover:

**For AI topics:**
- Latest benchmark / capability news (search: "[topic] 2026")
- Infrastructure or cost angle (search: "[topic] cost infrastructure compute")
- Criticism or limits (search: "[topic] limitations problems criticism")
- Investment or market angle (search: "[topic] funding market size")

**For semiconductor topics:**
- Supply chain or fab angle
- Company-specific moves (TSMC, Intel, Samsung, NVIDIA, Cadence, Synopsys)
- Policy angle (CHIPS Act, export controls, India/Japan/EU incentives)

**For deeptech investment topics:**
- Recent funding rounds or exits
- Investor thesis pieces (a16z, Sequoia, Bessemer, General Catalyst)
- Founder or operator perspective

**For strategy topics:**
- Precedents from adjacent industries
- Contrarian or minority view
- Data point that anchors the argument

## Step 3 — Deep scrape (Playwright fallback)
Use Playwright only if:
- A source is JS-rendered and web search returned a snippet but not full content
- A paywalled summary needs the abstract/intro extracted
- A company blog or investor memo is not indexed

```bash
# Install if needed
pip install playwright --break-system-packages
playwright install chromium

# Scrape a specific URL
python3 - <<'EOF'
from playwright.sync_api import sync_playwright

def scrape(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=15000)
        page.wait_for_load_state("networkidle")
        content = page.inner_text("body")
        browser.close()
        return content[:4000]  # cap at 4000 chars

print(scrape("PASTE_URL_HERE"))
EOF
```

## Step 4 — Evaluate sources
For each source, assess:
- Is this a primary source (company blog, earnings call, research paper) or secondary (journalist summary)?
- Does it contain a specific claim with a number, date, or named entity?
- Is it from the last 6 months? If older, is it foundational?

Discard sources that are: vague, SEO-optimised roundups, PR fluff, or more than 18 months old
unless they contain a landmark data point.

Keep 6-8 sources maximum.

## Step 5 — Build the research brief
Save to `outputs/research/YYYY-MM-DD-[slug]-research.md`

Structure:
```
# Research brief: [topic]
Date: YYYY-MM-DD
Framing hypothesis: [one sentence]

## Key claims
- [Claim 1] — Source: [name + URL]
- [Claim 2] — Source: [name + URL]
- [Claim 3] — Source: [name + URL]
(6-8 total)

## Tensions / contradictions found
- [Any conflicting data points or opposing views]

## Data points worth anchoring on
- [Specific numbers, percentages, dollar figures, dates]

## Angles NOT taken (and why)
- [What the obvious take is, so we consciously avoid it]

## Suggested structure for draft
- Opening hook idea
- Core argument in one sentence
- 3 supporting moves
- Closing provocation
```

## Output
Confirm: `Research brief saved → outputs/research/YYYY-MM-DD-[slug]-research.md`
Print the framing hypothesis and key claims to console for review.
