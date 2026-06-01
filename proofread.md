---
name: proofread
description: Fix grammar, punctuation, and flow in the draft blog post. Does NOT restructure or rewrite. Preserves Rahul's voice exactly.
invocation: manual
allowed-tools: read_file, write_file
---

# Skill: proofread

## Purpose
Clean up the draft without changing what it says or how it sounds.
This is a grammar and flow pass only. Not a rewrite. Not a restructure.

## Input
Read: `outputs/blog/[latest]-draft.md`

## What to fix
- Grammatical errors (subject-verb agreement, tense consistency, missing articles)
- Punctuation (missing commas, double spaces, inconsistent quote marks)
- Sentence flow — if a sentence is hard to parse on first read, simplify the structure
- Transitions between paragraphs that are abrupt or missing
- Repetition of the same word within 2 sentences (unless deliberate for emphasis)

## What NOT to touch
- Sentence length — if Rahul writes a short punchy sentence, keep it short
- Word choice — do not replace his words with "better" synonyms
- Structure — do not reorder paragraphs or merge sections
- Opinions — do not soften or qualify what he's said
- Contractions — keep them if they're there
- Opening and closing lines — these are the most intentional; do not touch

## Output
Save to: `outputs/blog/YYYY-MM-DD-[slug]-proofed.md`

Update front matter status: `proofed`

At the end of the file, append a short change log:
```
---
## Proofread changes
- [List of changes made, one line each]
- Total: [n] changes
```

Confirm: `Proofread complete → outputs/blog/YYYY-MM-DD-[slug]-proofed.md ([n] changes)`
