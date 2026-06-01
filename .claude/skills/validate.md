---
name: validate
description: Score the blog post against quality criteria. Pass (score ≥ 75) moves to export. Fail routes back to draft with specific notes.
invocation: manual
allowed-tools: read_file, write_file
---

# Skill: validate

## Purpose
Quality gate before the piece gets exported and published.
Produces a score and a pass/fail decision. If it fails, returns specific notes
for the draft skill to act on — not vague feedback.

## Input
Read: `outputs/blog/[latest]-deaified.md`
Read: `CLAUDE.md`

## Scoring rubric (100 points total)

### Voice (25 points)
- 25: Reads unmistakably like Rahul. Opinionated, direct, no filler.
- 20: Mostly his voice, one or two flat patches.
- 15: Correct voice in parts but generic in others.
- 10 or below: Sounds like a generic AI blog post.

Check for: banned words still present (-3 each), passive-voice hedging (-2 each),
summary sentence at end of paragraphs (-2 each)

### Argument quality (25 points)
- 25: Clear non-obvious central claim. Supported by specific evidence. Conclusion is earned.
- 20: Good argument but obvious take, or claim not fully supported.
- 15: Argument exists but is buried or inconsistent.
- 10 or below: No clear point of view.

Check for: central claim stated explicitly (required), at least 2 named sources or data points,
closing that adds something rather than summarising

### Research integration (20 points)
- 20: Sources are woven in naturally. Specific numbers and named entities present.
- 15: Sources referenced but not integrated — feels like a list report.
- 10: Thin on evidence, reads like opinion with no grounding.
- 5 or below: No sources visible.

### Readability (15 points)
- 15: Flows well. Paragraphs are tight. No slog sections.
- 10: One or two sections that drag or are hard to follow.
- 5: Multiple sections that need restructuring.

### Word count (15 points)
- 15: 950-1050 words
- 10: 900-1100 words
- 5: 800-1200 words
- 0: Outside 800-1200

## Pass threshold
Score ≥ 75 → pass, proceed to LinkedIn distill then PDF export
Score < 75 → fail, return to draft with notes

## Output on pass
Save validation report to: `outputs/blog/YYYY-MM-DD-[slug]-validated.md`
Update front matter status: `validated`
Print: `PASS — Score: [n]/100 → proceeding to LinkedIn distill`

## Output on fail
Print: `FAIL — Score: [n]/100`
Print specific notes:
```
Redraft notes:
- [Specific issue 1 with location in text]
- [Specific issue 2]
- [What to fix, not just what's wrong]
```
Do NOT save a validated file. Route back to draft skill.
