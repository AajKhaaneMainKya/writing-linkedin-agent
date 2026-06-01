import os
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from skills.common import ollama_summarise, slugify, today

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "research")


def ddg_search(query: str, max_results: int = 6) -> list[dict]:
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result__body")[:max_results]:
            title_el = r.select_one(".result__title")
            snippet_el = r.select_one(".result__snippet")
            if not (title_el and snippet_el):
                continue

            # Get the real URL from the DDG redirect link
            link_el = r.select_one("a.result__a") or r.select_one(".result__title a")
            actual_url = ""
            if link_el:
                href = link_el.get("href", "")
                if "uddg=" in href:
                    try:
                        qs = parse_qs(urlparse(href).query)
                        actual_url = unquote(qs.get("uddg", [""])[0])
                    except Exception:
                        pass
                elif href.startswith("http"):
                    actual_url = href

            # Fallback: display URL text (will be prefixed with https:// on scrape)
            if not actual_url:
                url_el = r.select_one(".result__url")
                if url_el:
                    actual_url = url_el.get_text(strip=True)

            results.append({
                "title": title_el.get_text(strip=True),
                "snippet": snippet_el.get_text(strip=True),
                "url": actual_url,
            })
        return results
    except Exception as e:
        print(f"  [search] DuckDuckGo failed for '{query[:50]}': {e}")
        return []


def scrape_url(url: str, timeout: int = 10) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=timeout)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:5000]
    except Exception:
        return ""


def scrape_url_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_load_state("networkidle")
            content = page.inner_text("body")
            browser.close()
            return content[:4000]
    except Exception:
        return ""


def detect_topic_type(topic: str) -> str:
    t = topic.lower()
    if any(w in t for w in [
        "chip", "tsmc", "semiconductor", "fab", "foundry", "nvidia", "intel",
        "amd", "arm", "eda", "cadence", "synopsys", "wafer", "node", "lithography",
        "asic", "fabless",
    ]):
        return "semiconductor"
    if any(w in t for w in [
        "fund", "invest", "vc", "startup", "raise", "round", "exit", "portfolio",
        "deeptech", "deep tech", "venture", "capital",
    ]):
        return "deeptech"
    if any(w in t for w in [
        "strategy", "market", "product", "competi", "pricing", "moat",
        "operator", "business model", "distribution", "go-to-market",
    ]):
        return "strategy"
    return "ai"


def _count_bullet_points(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("-"))


def _priority_queries(topic: str) -> list[str]:
    return [
        f"{topic} TechCrunch analysis report",
        f"{topic} Reuters Bloomberg market data statistics",
        f"{topic} a16z Sequoia investment memo thesis",
        f"{topic} IEEE Spectrum technical research",
        f"{topic} earnings revenue forecast analyst",
        f"{topic} investor relations annual report figures",
    ]


def build_search_queries(topic: str, topic_type: str) -> list[str]:
    base = [topic, f"{topic} 2026"]
    if topic_type == "semiconductor":
        extra = [
            f"{topic} supply chain fab economics",
            f"{topic} TSMC Intel Samsung CHIPS Act",
            f"{topic} fabless foundry cost analysis",
        ]
    elif topic_type == "deeptech":
        extra = [
            f"{topic} funding round 2026",
            f"{topic} investor thesis venture capital",
            f"{topic} startup founder perspective",
        ]
    elif topic_type == "strategy":
        extra = [
            f"{topic} market structure competitive dynamics",
            f"{topic} product strategy case study",
            f"{topic} contrarian view criticism",
        ]
    else:
        extra = [
            f"{topic} cost infrastructure compute",
            f"{topic} limitations problems criticism",
            f"{topic} funding market size 2026",
        ]
    return (base + extra)[:6]


def run(topic: str, voice_context: str, model: str, slug: str = None) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = today()
    if not slug:
        slug = slugify(topic)

    topic_type = detect_topic_type(topic)
    queries = build_search_queries(topic, topic_type)

    print(f"  [research] Topic type: {topic_type}")
    print(f"  [research] Running {len(queries)} searches...")

    seen_urls: set[str] = set()
    all_sources = []
    for q in queries:
        for r in ddg_search(q, max_results=4):
            url = r["url"]
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_sources.append(r)

    to_scrape = all_sources[:10]
    print(f"  [research] Scraping {len(to_scrape)} sources...")

    enriched = []
    for src in to_scrape:
        url = src["url"]
        text = scrape_url(url)
        if not text:
            text = scrape_url_playwright(url)

        if text:
            claims = ollama_summarise(
                text,
                "Extract the 3 most specific factual claims from this text. "
                "Return only bullet points with numbers, names, and dates where present. "
                "If there are no specific claims, return 'No specific claims.'",
                model=model,
            )
        else:
            claims = src.get("snippet", "")

        enriched.append({"title": src["title"], "url": url, "claims": claims})
        print(f"  [research]   {src['title'][:65]}")

    good = [
        s for s in enriched
        if len(s["claims"]) > 50 and "No specific claims" not in s["claims"]
    ]
    if len(good) < 4:
        good = enriched
    good = good[:8]

    sources_block = "\n\n".join(
        f"Source: {s['title']}\nURL: {s['url']}\nClaims:\n{s['claims']}"
        for s in good
    )

    framing = ollama_summarise(
        sources_block,
        f"Topic: {topic}\n\n"
        "Write ONE sentence framing hypothesis — the non-obvious angle that distinguishes this "
        "piece from the generic take. Just the sentence, no preamble.",
        model=model,
    )

    key_claims_lines = "\n".join(
        f"- {s['claims'].split(chr(10))[0][:200]} — Source: {s['title']} ({s['url']})"
        for s in good
    )

    tensions = ollama_summarise(
        sources_block,
        "Identify any contradictions, competing claims, or unresolved tensions between these sources. "
        "List as bullet points. If none, note the main area of uncertainty or debate.",
        model=model,
    )

    data_points = ollama_summarise(
        sources_block,
        "List ONLY specific numbers, percentages, dollar figures, dates, and named entities "
        "from these sources. Aim for at least 8 bullet points. No vague claims.",
        model=model,
    )

    # Second search pass if fewer than 8 concrete data points found
    if _count_bullet_points(data_points) < 8:
        print(f"  [research] Only {_count_bullet_points(data_points)} data points — running priority source pass...")
        for q in _priority_queries(topic)[:4]:
            for r in ddg_search(q, max_results=3):
                url = r["url"]
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    text = scrape_url(url) or scrape_url_playwright(url)
                    if text:
                        claims = ollama_summarise(
                            text,
                            "Extract the 3 most specific factual claims from this text. "
                            "Return only bullet points with numbers, names, and dates where present. "
                            "If there are no specific claims, return 'No specific claims.'",
                            model=model,
                        )
                    else:
                        claims = r.get("snippet", "")
                    if claims and "No specific claims" not in claims:
                        enriched.append({"title": r["title"], "url": url, "claims": claims})
                        print(f"  [research] (priority)  {r['title'][:65]}")

        extended_block = "\n\n".join(
            f"Source: {s['title']}\nURL: {s['url']}\nClaims:\n{s['claims']}"
            for s in enriched
        )
        data_points = ollama_summarise(
            extended_block,
            "List ONLY specific numbers, percentages, dollar figures, dates, and named entities. "
            "Aim for at least 8 bullet points. No vague claims.",
            model=model,
        )
        print(f"  [research] After priority pass: {_count_bullet_points(data_points)} data points")

    structure = ollama_summarise(
        sources_block,
        f"Topic: {topic}\n\nSuggest a structure for a 1000-word blog post:\n"
        "- Opening hook idea (one sentence — concrete observation, not a question)\n"
        "- Core argument in one sentence (non-obvious claim)\n"
        "- Supporting move 1 (one line)\n"
        "- Supporting move 2 (one line)\n"
        "- Supporting move 3 or counterargument (one line)\n"
        "- Closing provocation (one sentence)\n"
        "Be specific to the sources above.",
        model=model,
    )

    brief = (
        f"# Research brief: {topic}\n"
        f"Date: {date_str}\n"
        f"Framing hypothesis: {framing}\n\n"
        f"## Key claims\n{key_claims_lines}\n\n"
        f"## Tensions / contradictions found\n{tensions}\n\n"
        f"## Data points worth anchoring on\n{data_points}\n\n"
        f"## Angles NOT taken (and why)\n"
        f"- The obvious take: a general overview of {topic} — avoided in favour of the framing hypothesis above\n\n"
        f"## Suggested structure for draft\n{structure}\n"
    )

    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}-research.md")
    with open(out_path, "w") as f:
        f.write(brief)

    print(f"\n  Framing: {framing}")
    print(f"  Research brief saved → {out_path}")
    return brief
