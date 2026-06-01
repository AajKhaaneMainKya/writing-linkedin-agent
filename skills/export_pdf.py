import os
import re
from datetime import date as date_module
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "outputs", "pdf")

MARGIN = 25 * mm


def _styles() -> dict:
    """Create fresh style objects each call — avoids ReportLab 'already defined' errors."""
    return {
        "title": ParagraphStyle(
            "PipelineTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            spaceAfter=6,
            textColor=colors.HexColor("#111111"),
            alignment=TA_LEFT,
        ),
        "date": ParagraphStyle(
            "PipelineDate",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=20,
            textColor=colors.HexColor("#888888"),
        ),
        "body": ParagraphStyle(
            "PipelineBody",
            fontName="Helvetica",
            fontSize=11,
            leading=18,
            spaceAfter=12,
            textColor=colors.HexColor("#222222"),
            alignment=TA_JUSTIFY,
        ),
        "h2": ParagraphStyle(
            "PipelineH2",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=20,
            spaceBefore=16,
            spaceAfter=6,
            textColor=colors.HexColor("#111111"),
        ),
    }


def md_to_xml(line: str) -> str:
    """Escape XML special chars and convert **bold** / *italic* to ReportLab tags."""
    parts = []
    pos = 0
    for m in re.finditer(r"\*\*(.*?)\*\*|\*(.*?)\*", line):
        parts.append(escape(line[pos: m.start()]))
        if m.group(1) is not None:
            parts.append(f"<b>{escape(m.group(1))}</b>")
        else:
            parts.append(f"<i>{escape(m.group(2))}</i>")
        pos = m.end()
    parts.append(escape(line[pos:]))
    return "".join(parts)


def run(validated_text: str, voice_context: str, model: str, slug: str = "post") -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    from skills.common import today
    date_str = today()
    out_path = os.path.join(OUTPUT_DIR, f"{date_str}-{slug}.pdf")

    # Strip YAML front matter if present (validated_text is usually clean body text,
    # but guard in case it gets front matter passed in from --skill mode)
    raw = re.sub(r"^---.*?---\s*", "", validated_text, flags=re.DOTALL)

    s = _styles()
    story = []
    title_found = False

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        # Stop at changelog separator appended by proofread/de-aify skills
        if line == "---":
            break
        if line.startswith("# ") and not title_found:
            story.append(Paragraph(escape(line[2:]), s["title"]))
            story.append(Paragraph(date_module.today().strftime("%B %d, %Y"), s["date"]))
            title_found = True
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), s["h2"]))
        elif line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), s["h2"]))
        else:
            story.append(Paragraph(md_to_xml(line), s["body"]))

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    doc.build(story)

    print(f"  PDF exported → {out_path}")
    return out_path
