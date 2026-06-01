---
name: export-pdf
description: Convert the validated blog post markdown to a clean PDF using reportlab. Run after validate passes.
invocation: manual
allowed-tools: bash, write_file
---

# Skill: export-pdf

## Purpose
Convert the validated blog markdown to a clean, readable PDF.
Simple formatting — no heavy design. Readable on screen and print.

## Input
Read: `outputs/blog/[latest]-validated.md`

## Dependencies
```bash
pip install reportlab --break-system-packages
pip install markdown --break-system-packages
```

## Export script
Run the following Python script:

```python
import re, sys
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

# --- Config ---
INPUT_FILE = "outputs/blog/REPLACE_WITH_FILENAME.md"
OUTPUT_FILE = INPUT_FILE.replace("-validated.md", ".pdf").replace("blog/", "pdf/")

# --- Read markdown ---
with open(INPUT_FILE, "r") as f:
    raw = f.read()

# Strip front matter
raw = re.sub(r'^---.*?---\s*', '', raw, flags=re.DOTALL)

# --- Styles ---
PAGE_W, PAGE_H = A4
MARGIN = 25 * mm

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "Title",
    fontName="Helvetica-Bold",
    fontSize=22,
    leading=28,
    spaceAfter=6,
    textColor=colors.HexColor("#111111"),
    alignment=TA_LEFT,
)
date_style = ParagraphStyle(
    "Date",
    fontName="Helvetica",
    fontSize=10,
    leading=14,
    spaceAfter=20,
    textColor=colors.HexColor("#888888"),
)
body_style = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=11,
    leading=18,
    spaceAfter=12,
    textColor=colors.HexColor("#222222"),
    alignment=TA_JUSTIFY,
)
h2_style = ParagraphStyle(
    "H2",
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=20,
    spaceBefore=16,
    spaceAfter=6,
    textColor=colors.HexColor("#111111"),
)

# --- Parse markdown into story ---
story = []
lines = raw.strip().split("\n")
title_found = False

for line in lines:
    line = line.strip()
    if not line:
        story.append(Spacer(1, 4))
        continue
    if line.startswith("# ") and not title_found:
        story.append(Paragraph(line[2:], title_style))
        story.append(Paragraph(str(date.today().strftime("%B %d, %Y")), date_style))
        title_found = True
    elif line.startswith("## "):
        story.append(Paragraph(line[3:], h2_style))
    elif line.startswith("# "):
        story.append(Paragraph(line[2:], h2_style))
    else:
        # Convert basic markdown inline
        line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
        line = re.sub(r'\*(.*?)\*', r'<i>\1</i>', line)
        story.append(Paragraph(line, body_style))

# --- Build PDF ---
import os
os.makedirs("outputs/pdf", exist_ok=True)

doc = SimpleDocTemplate(
    OUTPUT_FILE,
    pagesize=A4,
    leftMargin=MARGIN,
    rightMargin=MARGIN,
    topMargin=MARGIN,
    bottomMargin=MARGIN,
)
doc.build(story)
print(f"PDF exported → {OUTPUT_FILE}")
```

## Instructions
1. Replace `REPLACE_WITH_FILENAME.md` with the actual validated file name
2. Run the script via bash
3. Confirm output file exists in `outputs/pdf/`

## Output
Confirm: `PDF exported → outputs/pdf/YYYY-MM-DD-[slug].pdf`
