# Rahul — Content Pipeline Context

## Who I am
PM background, MBA from BITSoM. Writing about AI, semiconductors, deeptech investments, and strategy.
Audience: founders, investors, operators, and people building in the space.
Tone: practitioner writing for other practitioners. Not a journalist, not an academic.

## Writing rules (non-negotiable)
- First person, direct voice
- No em dashes — use commas, periods, or restructure
- No AI-isms: never use "delve", "it's worth noting", "in conclusion", "leverage" (as a verb), "transformative", "nuanced", "at its core", "game-changer", "deep dive", "unpack", "underscore", "paradigm"
- No corporate filler: no "synergies", "ecosystem" (unless quoting), "scalable solutions"
- No LinkedIn guru language: no "hot take:", no "unpopular opinion:", no "here's what nobody talks about"
- No bullet-point summaries at the end of articles
- No rhetorical questions used as transitions ("So what does this mean?")
- Short sentences preferred. Paragraphs max 3-4 lines.
- Opinions are stated as opinions, not dressed up as facts
- Numbers and specifics over vague claims

## Topics I write about
- AI/ML — practical applications, infrastructure, limits of current systems
- Semiconductors — design tools, fab economics, supply chain strategy
- Deeptech investment — what gets funded, what doesn't, why
- Strategy — product thinking, market structure, competitive dynamics

## Infrastructure (non-negotiable)
- LLM inference: Ollama only. No OpenAI, no Anthropic API, no cloud inference.
- Default model: `mistral` (good balance of speed and quality on consumer hardware)
- Ollama base URL: `http://localhost:11434`
- All LLM calls go through `http://localhost:11434/api/generate` or `/api/chat`
- If Ollama is not running, print a clear error and exit — do not silently fail
- Model can be overridden via env var: `OLLAMA_MODEL=llama3 claude ...`

## Output format
- Blog post: ~1000 words, markdown, saved to outputs/blog/
- LinkedIn post: ~300 words, distilled from blog, saved to outputs/linkedin/
- PDF: exported from blog markdown, saved to outputs/pdf/

## File naming
YYYY-MM-DD-slug.md / .pdf
