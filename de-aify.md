---
name: de-aify
description: Strip AI-generated language patterns from the blog post and restore Rahul's natural writing voice. Run after proofread.
invocation: manual
allowed-tools: read_file, write_file
---

# Skill: de-aify

## Purpose
AI-written text has fingerprints. This skill finds and removes them.
The goal is prose that reads like it came from a person who thinks clearly and has opinions —
not from a model trained to sound helpful and comprehensive.

## Input
Read: `outputs/blog/[latest]-proofed.md`
Read: `CLAUDE.md` — banned words and voice rules

## Banned words and phrases (hard remove or rewrite)
If any of the following appear, rewrite the sentence entirely:

**AI-ism words:**
delve, unpack, underscore, leverage (as verb), transformative, nuanced, game-changer,
paradigm, ecosystem (unless quoting someone), synergy, seamless, robust, cutting-edge,
groundbreaking, revolutionary, unprecedented, holistic, pivotal, crucial (overused),
it's worth noting, at its core, in essence, when it comes to, the fact that,
in conclusion, to summarise, in today's [anything], the [noun] landscape

**Sentence patterns that signal AI:**
- Starting with "It's important to..." → just say the thing
- "This [noun] highlights/underscores/demonstrates..." → cut, say what it means directly
- "One thing that stands out is..." → cut the preamble
- Ending a paragraph with a one-line summary of what was just said → delete it
- Two-sentence paragraph where sentence 2 just restates sentence 1 → delete sentence 2
- "Not only X, but also Y" constructions → usually can be simplified
- Passive voice used to avoid taking a position → make it active and own the claim

**Structural patterns:**
- Tricolon lists used as filler ("speed, scale, and efficiency") → cut or make specific
- Parenthetical asides that hedge ("which, of course, varies") → remove or commit
- Transition sentences that only say "now let's look at X" → delete, just start X

## What to preserve
- Short, punchy sentences that state something plainly
- Specific numbers and named entities
- Contractions and colloquial phrasing
- Any sentence that sounds like something Rahul would say out loud

## Test: the read-aloud check
After de-AIification, mentally read the piece aloud.
If any sentence would sound weird coming from a 28-year-old PM talking to a peer —
if it sounds like a report rather than a conversation — flag it.

## Output
Save to: `outputs/blog/YYYY-MM-DD-[slug]-deaified.md`

Update front matter status: `deaified`

Append change log:
```
---
## De-AIify changes
- [List of removed/rewritten phrases]
- Total rewrites: [n]
```

Confirm: `De-AIify complete → outputs/blog/YYYY-MM-DD-[slug]-deaified.md ([n] rewrites)`
