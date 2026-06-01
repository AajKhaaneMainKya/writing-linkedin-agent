---
name: linkedin-distill
description: Distill the validated blog post into a ~300 word LinkedIn post. Same voice, different format. Run after validate passes.
invocation: manual
allowed-tools: read_file, write_file
---

# Skill: linkedin-distill

## Purpose
One research run, two outputs. Take the validated blog post and compress it into
a LinkedIn post that works as a standalone piece — not a "read my blog" teaser.

## Input
Read: `outputs/blog/[latest]-validated.md`
Read: `CLAUDE.md`

## LinkedIn format rules
- ~300 words. Hard ceiling at 320.
- No hashtags (looks desperate)
- No "link in comments" call to action
- No "I wrote a blog post about X, here's the summary" framing — just write the piece
- First line must work as a hook without the rest of the post
- Line breaks used deliberately — not after every sentence, but to pace the reader
- Can be slightly more punchy and direct than the blog — LinkedIn rewards a stronger take

## Structure
**Hook (1-2 lines)**
The most interesting or provocative claim from the blog.
Not a question. A statement that makes someone stop scrolling.

**The point (3-5 lines)**
The core argument, compressed. Drop the supporting moves, keep the spine.

**One concrete detail (2-3 lines)**
The single best data point or specific claim from the research.
This is what makes it credible rather than just another hot take.

**The implication or close (2-3 lines)**
What this means for the reader — investor, operator, or builder.
No "what do you think?" at the end.

## What to strip from the blog
- All the supporting moves beyond the strongest one
- Source attributions (unless a named company or person anchors the claim)
- The counterargument section (unless it is the point)
- The nuanced qualifications — pick a side for LinkedIn

## Output
Save to: `outputs/linkedin/YYYY-MM-DD-[slug]-linkedin.md`

Confirm: `LinkedIn post saved → outputs/linkedin/YYYY-MM-DD-[slug]-linkedin.md ([n] words)`
