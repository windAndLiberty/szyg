#!/usr/bin/env python3
"""
MCP Server: Skills — Production-Grade Document Generation for Content Marketing.

Dependencies (registered in pyproject.toml [project.optional-dependencies] skills):
  openpyxl>=3.1    — Excel: content calendars, analytics, bulk export
  python-docx>=1.1 — Word: script outlines, creative briefs, batch convert
  python-pptx>=1.0 — PowerPoint: carousel slides, branded templates
  PyPDF2>=3.0      — PDF merge/split
  pdfplumber>=0.11 — PDF text extraction (superior to PyPDF2)

Architecture:
  - CorporateTheme: central brand identity (colors, fonts, spacing)
  - _*_style helpers: reusable professional formatting per format
  - Each @server.tool is standalone — callable independently by Hermes agent
"""
import sys, os, json, logging, subprocess, tempfile, shutil, datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

SKILLS_DIR = Path(__file__).parent.parent / "skills"

server = MCPServer(
    "szyg-skills",
    "Production-grade document generation for content marketing: xlsx calendars, "
    "docx scripts/briefs, pptx carousels, PDF extraction, batch conversion"
)

# ═══════════════════════════════════════════════════════════════
# Corporate Theme — Central Brand Identity
# ═══════════════════════════════════════════════════════════════

@dataclass
class CorpTheme:
    """Brand identity applied consistently across xlsx/docx/pptx output."""
    name: str
    # Primary palette
    primary: str       # Hex e.g. "2B579A"
    primary_light: str
    primary_dark: str
    accent: str
    # Text
    text_dark: str
    text_light: str
    text_muted: str
    # Surfaces
    bg_white: str
    bg_warm: str
    bg_stripe: str     # Alternating row stripe
    # Semantic
    success: str
    warning: str
    danger: str
    # Typography
    font_cn: str       # Chinese font
    font_en: str       # English fallback
    font_size_body: int
    font_size_h1: int
    font_size_h2: int
    font_size_small: int

    def hex_to_rgb(self, hex_color: str) -> tuple:
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Pre-built Themes ─────────────────────────────────────────

THEMES = {
    "ocean": CorpTheme(
        name="ocean",
        primary="2B579A", primary_light="5B8BD4", primary_dark="1A3A6E",
        accent="3B82F6",
        text_dark="1A1A2E", text_light="FFFFFF", text_muted="6B7280",
        bg_white="FFFFFF", bg_warm="F3F4F6", bg_stripe="E8EDF5",
        success="10B981", warning="F59E0B", danger="EF4444",
        font_cn="微软雅黑", font_en="Segoe UI",
        font_size_body=11, font_size_h1=20, font_size_h2=14, font_size_small=9,
    ),
    "sunset": CorpTheme(
        name="sunset",
        primary="E85D04", primary_light="FF8C42", primary_dark="B54500",
        accent="F59E0B",
        text_dark="1C1917", text_light="FFFFFF", text_muted="78716C",
        bg_white="FFFFFF", bg_warm="FFF7ED", bg_stripe="FFF0E0",
        success="059669", warning="D97706", danger="DC2626",
        font_cn="微软雅黑", font_en="Segoe UI",
        font_size_body=11, font_size_h1=20, font_size_h2=14, font_size_small=9,
    ),
    "forest": CorpTheme(
        name="forest",
        primary="059669", primary_light="34D399", primary_dark="047857",
        accent="10B981",
        text_dark="0F172A", text_light="FFFFFF", text_muted="64748B",
        bg_white="FFFFFF", bg_warm="F0FDF4", bg_stripe="E6F7ED",
        success="10B981", warning="F59E0B", danger="EF4444",
        font_cn="微软雅黑", font_en="Segoe UI",
        font_size_body=11, font_size_h1=20, font_size_h2=14, font_size_small=9,
    ),
    "midnight": CorpTheme(
        name="midnight",
        primary="1E1B4B", primary_light="3730A3", primary_dark="0C0A2E",
        accent="6366F1",
        text_dark="0F172A", text_light="FFFFFF", text_muted="94A3B8",
        bg_white="FFFFFF", bg_warm="F8FAFC", bg_stripe="EEF2FF",
        success="059669", warning="D97706", danger="DC2626",
        font_cn="微软雅黑", font_en="Segoe UI",
        font_size_body=11, font_size_h1=20, font_size_h2=14, font_size_small=9,
    ),
}

DEFAULT_THEME = "ocean"


def _get_theme(name: str = "") -> CorpTheme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


# ═══════════════════════════════════════════════════════════════
# Shared Helpers — xlsx
# ═══════════════════════════════════════════════════════════════

def _xlsx_style_header(ws, theme: CorpTheme, col_count: int, row: int = 1):
    """Apply branded header row with frozen pane."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter

    hfont = Font(name=theme.font_cn, size=theme.font_size_body, bold=True,
                 color=theme.text_light)
    hfill = PatternFill(start_color=theme.primary, end_color=theme.primary, fill_type="solid")
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color=theme.primary_light)
    border = Border(left=thin, right=thin, top=thin, bottom=Side(style="medium", color=theme.primary_dark))

    for c in range(1, col_count + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = hfont
        cell.fill = hfill
        cell.alignment = halign
        cell.border = border

    ws.freeze_panes = f"A{row + 1}"
    ws.auto_filter.ref = f"A{row}:{get_column_letter(col_count)}{ws.max_row}"
    ws.sheet_properties.tabColor = theme.primary


def _xlsx_style_data(ws, theme: CorpTheme, start_row: int = 2):
    """Stripe data rows with alternating colors and borders."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    dfont = Font(name=theme.font_cn, size=theme.font_size_body, color=theme.text_dark)
    dalign = Alignment(vertical="top", wrap_text=True)
    stripe = PatternFill(start_color=theme.bg_stripe, end_color=theme.bg_stripe, fill_type="solid")
    thin = Side(style="thin", color="D4D4D8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_first = Border(left=Side(style="thin", color="D4D4D8"),
                          right=Side(style="thin", color="D4D4D8"),
                          top=Side(style="medium", color=theme.primary),
                          bottom=Side(style="thin", color="D4D4D8"))

    for r in range(start_row, ws.max_row + 1):
        is_stripe = (r - start_row) % 2 == 1
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = dfont
            cell.alignment = dalign
            cell.border = border_first if r == start_row else border
            if is_stripe:
                cell.fill = stripe


def _xlsx_auto_width(ws, min_width: int = 8, max_width: int = 55):
    """Auto-size columns to content."""
    from openpyxl.utils import get_column_letter
    for c in range(1, ws.max_column + 1):
        letter = get_column_letter(c)
        best = min_width
        for r in range(1, min(ws.max_row + 1, 100)):
            val = ws.cell(row=r, column=c).value
            if val:
                for line in str(val).split("\n"):
                    # CJK chars are ~2x width
                    w = sum(2 if ord(ch) > 127 else 1 for ch in line)
                    best = max(best, w)
        ws.column_dimensions[letter].width = min(best + 4, max_width)


def _xlsx_add_dropdown(ws, col_letter: str, options: list[str], start_row: int = 2, end_row: int = 200):
    """Add data validation dropdown to a column."""
    from openpyxl.worksheet.datavalidation import DataValidation
    formula = '"' + ",".join(options) + '"'
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.error = "请从下拉列表中选择"
    dv.errorTitle = "无效输入"
    dv.prompt = "请选择"
    dv.promptTitle = "内容类型"
    ws.add_data_validation(dv)
    dv.add(f"{col_letter}{start_row}:{col_letter}{end_row}")


def _xlsx_add_conditional_format(ws, col_letter: str, start_row: int, end_row: int, theme: CorpTheme):
    """Add 3-color scale conditional formatting to a numeric column."""
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Color
    rule = ColorScaleRule(
        start_type="min", start_color=Color(rgb=theme.danger),
        mid_type="percentile", mid_value=50, mid_color=Color(rgb=theme.warning),
        end_type="max", end_color=Color(rgb=theme.success),
    )
    ws.conditional_formatting.add(f"{col_letter}{start_row}:{col_letter}{end_row}", rule)


# ═══════════════════════════════════════════════════════════════
# Shared Helpers — docx
# ═══════════════════════════════════════════════════════════════

def _docx_setup(doc, theme: CorpTheme):
    """Apply corporate theme to a new Document: margins, fonts, styles."""
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.oxml.ns import qn

    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Normal style
    style = doc.styles["Normal"]
    style.font.name = theme.font_cn
    style.font.size = Pt(theme.font_size_body)
    style.font.color.rgb = RGBColor(*theme.hex_to_rgb(theme.text_dark))
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.35
    # CJK font fallback
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.makeelement(qn('w:rFonts'), {})
    rFonts.set(qn('w:eastAsia'), theme.font_cn)
    rPr.insert(0, rFonts)

    # Heading styles
    for level, size in [(1, theme.font_size_h1), (2, theme.font_size_h2), (3, theme.font_size_body + 2)]:
        hstyle = doc.styles[f"Heading {level}"]
        hstyle.font.name = theme.font_cn
        hstyle.font.size = Pt(size)
        hstyle.font.bold = True
        hstyle.font.color.rgb = RGBColor(*theme.hex_to_rgb(theme.primary))
        hPr = hstyle.element.get_or_add_rPr()
        hFonts = hPr.makeelement(qn('w:rFonts'), {})
        hFonts.set(qn('w:eastAsia'), theme.font_cn)
        hPr.insert(0, hFonts)


def _docx_add_header_footer(doc, theme: CorpTheme, title: str = ""):
    """Add branded header and footer to all sections."""
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    for section in doc.sections:
        header = section.header
        header.is_linked_to_previous = False
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = hp.add_run(title or "szyg 智能矩阵运营系统")
        run.font.size = Pt(8)
        run.font.color.rgb = None  # inherit
        run.font.name = theme.font_cn

        footer = section.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = fp.add_run("Confidential | Generated by szyg AI")
        run.font.size = Pt(7)
        run.font.color.rgb = None


def _docx_add_table(doc, headers: list[str], rows: list[list[str]], theme: CorpTheme, col_widths: list = None):
    """Add a styled table to docx document."""
    from docx.shared import Inches, Pt
    from docx.oxml.ns import qn

    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True

    # Header row
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(theme.font_size_small)
                run.font.name = theme.font_cn
        # Background
        from docx.oxml import OxmlElement
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), theme.primary)
        shading.set(qn('w:val'), 'clear')
        cell._tc.get_or_add_tcPr().append(shading)
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.color.rgb = None

    # Data rows
    for r, row_data in enumerate(rows):
        for c, val in enumerate(row_data):
            if c < len(headers):
                cell = table.rows[r + 1].cells[c]
                cell.text = str(val)
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(theme.font_size_body)
                        run.font.name = theme.font_cn

    if col_widths:
        for i, w in enumerate(col_widths):
            if i < len(headers):
                for row in table.rows:
                    row.cells[i].width = Inches(w)

    doc.add_paragraph()  # spacer
    return table


# ═══════════════════════════════════════════════════════════════
# Shared Helpers — pptx
# ═══════════════════════════════════════════════════════════════

def _pptx_setup(prs, theme: CorpTheme):
    """Set default slide size to 3:4 carousel format."""
    from pptx.util import Inches
    prs.slide_width = Inches(8.0)
    prs.slide_height = Inches(10.67)


def _pptx_add_branded_slide(prs, theme: CorpTheme, title: str, body: str,
                             slide_num: int, total: int, extra_shapes: callable = None):
    """
    Add a fully-branded slide with gradient bg, title, accent bar, body, page number.
    extra_shapes(slide) is called for slide-specific elements.
    """
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    blank_layout = prs.slide_layouts[6]  # Blank
    slide = prs.slides.add_slide(blank_layout)

    # ── Gradient background ──
    bg = slide.background
    fill = bg.fill
    fill.gradient()
    fill.gradient_angle = 135.0
    fill.gradient_stops[0].color.rgb = RGBColor(*theme.hex_to_rgb(theme.primary_dark))
    fill.gradient_stops[1].color.rgb = RGBColor(*theme.hex_to_rgb(theme.primary))

    # ── Semi-transparent overlay card ──
    card_left = Inches(0.5)
    card_top = Inches(0.8)
    card_w = Inches(7.0)
    card_h = Inches(8.8)
    card = slide.shapes.add_shape(
        1, card_left, card_top, card_w, card_h  # Rectangle
    )
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(*theme.hex_to_rgb(theme.bg_white))
    # Subtle border instead of shadow for clean card edge
    card.line.color.rgb = RGBColor(*theme.hex_to_rgb(theme.bg_stripe))
    card.line.width = Pt(1)

    # ── Title ──
    tb = slide.shapes.add_textbox(Inches(0.9), Inches(1.3), Inches(6.2), Inches(1.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(30)
    p.font.bold = True
    p.font.name = theme.font_cn
    p.font.color.rgb = RGBColor(*theme.hex_to_rgb(theme.text_dark))
    p.alignment = PP_ALIGN.LEFT

    # ── Accent bar ──
    bar = slide.shapes.add_shape(1, Inches(0.9), Inches(2.95), Inches(1.2), Pt(4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(*theme.hex_to_rgb(theme.accent))
    bar.line.fill.background()

    # ── Body ──
    if body:
        tb2 = slide.shapes.add_textbox(Inches(0.9), Inches(3.3), Inches(6.2), Inches(5.0))
        tf2 = tb2.text_frame
        tf2.word_wrap = True
        first = True
        for line_text in body.split("\n"):
            if first:
                p2 = tf2.paragraphs[0]
                first = False
            else:
                p2 = tf2.add_paragraph()
            p2.text = line_text
            p2.font.size = Pt(15)
            p2.font.name = theme.font_cn
            p2.font.color.rgb = RGBColor(*theme.hex_to_rgb(theme.text_dark))
            p2.space_after = Pt(8)

    # ── Page number ──
    tb3 = slide.shapes.add_textbox(Inches(3.0), Inches(9.85), Inches(2.0), Inches(0.4))
    tf3 = tb3.text_frame
    p3 = tf3.paragraphs[0]
    p3.text = f"{slide_num} / {total}"
    p3.font.size = Pt(9)
    p3.font.name = theme.font_cn
    p3.font.color.rgb = RGBColor(*theme.hex_to_rgb(theme.text_muted))
    p3.alignment = PP_ALIGN.CENTER

    # ── Caller extras ──
    if extra_shapes:
        extra_shapes(slide)

    return slide


# ═══════════════════════════════════════════════════════════════
# Convenience — pandoc / libreoffice checks
# ═══════════════════════════════════════════════════════════════

def _ensure_pandoc() -> bool:
    return shutil.which("pandoc") is not None


def _ensure_libreoffice() -> bool:
    return shutil.which("soffice") is not None


# ═══════════════════════════════════════════════════════════════
# docx — Word Document
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_docx_to_markdown", "Convert .docx to markdown. Requires pandoc.")
def skill_docx_to_markdown(file_path: str, tracked_changes: str = "all"):
    """
    Convert a .docx file to markdown using pandoc.

    Args:
        file_path: Absolute path to the .docx file
        tracked_changes: How to handle track changes — accept, reject, or all (show all)
    """
    if not _ensure_pandoc():
        return {"error": "pandoc not installed. Install: winget install pandoc"}

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    valid_modes = {"accept", "reject", "all"}
    mode = tracked_changes if tracked_changes in valid_modes else "all"

    try:
        result = subprocess.run(
            ["pandoc", f"--track-changes={mode}", str(path), "-o", "-", "-t", "markdown"],
            capture_output=True, text=True, timeout=30, cwd=str(path.parent)
        )
        if result.returncode == 0:
            return {"markdown": result.stdout, "file": file_path}
        return {"error": result.stderr[:500]}
    except subprocess.TimeoutExpired:
        return {"error": "Conversion timed out (30s)"}
    except Exception as e:
        return {"error": str(e)}


@server.tool("skill_docx_create", "Create a new .docx document from markdown. Requires pandoc.")
def skill_docx_create(markdown: str, output_path: str):
    """
    Create a new Word document from markdown text.

    Args:
        markdown: Markdown content to convert
        output_path: Where to save the .docx (e.g., /path/to/output.docx)
    """
    if not _ensure_pandoc():
        return {"error": "pandoc not installed"}

    try:
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", encoding="utf-8", delete=False) as f:
            f.write(markdown)
            md_path = f.name

        result = subprocess.run(
            ["pandoc", md_path, "-o", output_path],
            capture_output=True, text=True, timeout=30
        )
        os.unlink(md_path)

        if result.returncode == 0:
            return {"output": output_path, "size": os.path.getsize(output_path)}
        return {"error": result.stderr[:500]}
    except Exception as e:
        return {"error": str(e)}


@server.tool("skill_docx_extract_text", "Extract plain text from .docx (no pandoc required)")
def skill_docx_extract_text(file_path: str):
    """Extract text from a .docx using Python zipfile + xml."""
    import zipfile
    import xml.etree.ElementTree as ET

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        with zipfile.ZipFile(path, 'r') as z:
            if 'word/document.xml' not in z.namelist():
                return {"error": "Not a valid .docx: missing word/document.xml"}
            xml_content = z.read('word/document.xml')

        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        root = ET.fromstring(xml_content)
        paragraphs = []
        for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            texts = []
            for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
                if t.text:
                    texts.append(t.text)
            if texts:
                paragraphs.append(''.join(texts))

        return {"text": '\n\n'.join(paragraphs), "paragraphs": len(paragraphs)}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# xlsx — Excel
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_xlsx_read", "Read .xlsx file and return data as JSON")
def skill_xlsx_read(file_path: str, sheet_name: str = ""):
    """
    Read an Excel file and return data as 2D array (list of rows).

    Args:
        file_path: Path to .xlsx file
        sheet_name: Sheet name (default: first sheet)
    """
    import openpyxl
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb[sheet_name] if sheet_name else wb.active
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(list(row))
        wb.close()
        return {
            "sheet": sheet.title,
            "rows": len(rows),
            "cols": len(rows[0]) if rows else 0,
            "data": rows[:1000],
        }
    except Exception as e:
        return {"error": str(e)}


@server.tool("skill_xlsx_create", "Create a new .xlsx file from JSON data")
def skill_xlsx_create(data_json: str, output_path: str, sheet_name: str = "Sheet1"):
    """
    Create Excel from JSON array data. data_json is a JSON-encoded 2D array.

    Args:
        data_json: JSON string of 2D array, e.g. '[["Name","Age"],["Alice",30]]'
        output_path: Where to save .xlsx
        sheet_name: Sheet name
    """
    import openpyxl
    try:
        data = json.loads(data_json)
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = sheet_name
        for row in data:
            sheet.append(row)
        wb.save(output_path)
        return {"output": output_path, "rows": len(data)}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# pptx — PowerPoint
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_pptx_extract", "Extract text content from .pptx slides")
def skill_pptx_extract(file_path: str):
    """Extract text from each slide in a PowerPoint file."""
    from pptx import Presentation
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        prs = Presentation(str(path))
        slides = []
        for i, slide in enumerate(prs.slides):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip():
                            texts.append(para.text.strip())
            slides.append({"slide": i + 1, "text": texts})
        return {"slides": len(slides), "content": slides}
    except Exception as e:
        return {"error": str(e)}


@server.tool("skill_pptx_create", "Create a new .pptx from markdown outline")
def skill_pptx_create(markdown: str, output_path: str, template: str = ""):
    """
    Create PowerPoint from markdown outline.
    Each H1 (#) = new slide. H2 (##) = slide title.

    Args:
        markdown: Markdown outline (H1 slides, H2 titles, text for content)
        output_path: Where to save .pptx
        template: Optional template .pptx path
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt

    try:
        if template and Path(template).exists():
            prs = Presentation(template)
        else:
            prs = Presentation()

        lines = markdown.strip().split('\n')
        current_slide = None
        current_text = []

        for line in lines:
            if line.startswith('# '):
                if current_slide and current_text:
                    _add_text_to_slide(current_slide, current_text)
                slide_layout = prs.slide_layouts[1]
                current_slide = prs.slides.add_slide(slide_layout)
                current_slide.shapes.title.text = line.lstrip('# ').strip()[:80]
                current_text = []
            elif line.startswith('## '):
                if current_text:
                    _add_text_to_slide(current_slide, current_text)
                    current_text = []
                current_text.append(('h2', line.lstrip('# ').strip()))
            elif line.strip():
                current_text.append(('text', line.strip()))

        if current_slide and current_text:
            _add_text_to_slide(current_slide, current_text)

        prs.save(output_path)
        return {"output": output_path, "slides": len(prs.slides)}
    except Exception as e:
        return {"error": str(e)}


def _add_text_to_slide(slide, texts):
    """Helper: add text to slide content area"""
    try:
        from pptx.util import Pt
        body = slide.placeholders[1].text_frame
        body.clear()
        for i, (kind, text) in enumerate(texts):
            if i == 0:
                p = body.paragraphs[0]
            else:
                p = body.add_paragraph()
            p.text = text
            if kind == 'h2':
                p.font.size = Pt(18)
                p.font.bold = True
    except (KeyError, IndexError) as e:
        logging.getLogger(__name__).debug("Failed to add text to slide: %s", e)


# ═══════════════════════════════════════════════════════════════
# pdf — PDF
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_pdf_extract", "Extract text from PDF file")
def skill_pdf_extract(file_path: str):
    """Extract text from PDF using pdfplumber (primary) or PyPDF2 (fallback)."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    pages.append({"page": i + 1, "text": text[:2000]})
            return {"pages": len(pdf.pages), "content": pages}
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages.append({"page": i + 1, "text": text[:2000]})
        return {"pages": len(reader.pages), "content": pages}
    except ImportError:
        return {"error": "Install pdfplumber or PyPDF2: pip install pdfplumber"}
    except Exception as e:
        return {"error": str(e)}


@server.tool("skill_pdf_merge", "Merge multiple PDFs into one")
def skill_pdf_merge(input_files: str, output_path: str):
    """
    Merge PDF files. input_files is comma-separated paths.
    """
    from PyPDF2 import PdfReader, PdfWriter
    try:
        writer = PdfWriter()
        files = [f.strip() for f in input_files.split(",")]
        for f in files:
            if not Path(f).exists():
                return {"error": f"File not found: {f}"}
            reader = PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)
        writer.write(output_path)
        return {"output": output_path, "pages": len(writer.pages), "files": len(files)}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# canvas-design — Banner/Poster Design
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_canvas_get_fonts", "List available canvas design fonts")
def skill_canvas_get_fonts():
    """List fonts available in canvas-design skill."""
    fonts_dir = SKILLS_DIR / "canvas-design" / "canvas-fonts"
    if not fonts_dir.exists():
        return {"fonts": [], "error": "Fonts directory not found"}
    fonts = [f.stem for f in fonts_dir.glob("*.ttf")]
    return {"fonts": fonts, "count": len(fonts), "dir": str(fonts_dir)}


@server.tool("skill_canvas_preview_config", "Show canvas-design design parameters")
def skill_canvas_preview_config():
    """Return the canvas-design SKILL.md summary for Hermes agent."""
    skill_md = SKILLS_DIR / "canvas-design" / "SKILL.md"
    if not skill_md.exists():
        return {"error": "canvas-design SKILL.md not found"}
    content = skill_md.read_text(encoding="utf-8")[:3000]
    return {"skill": "canvas-design", "preview": content}


# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# MARKETING CONTENT GENERATION — Production-Grade Tools
# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# Tool: skill_xlsx_content_calendar
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_xlsx_content_calendar",
    "Generate a professionally-styled 30-day social media content calendar as .xlsx. "
    "Features: branded headers, dropdown validation, alternating row colors, frozen panes, "
    "auto-filter. Includes date, weekday, platform, content type, topic, caption, hashtags, "
    "status, and notes columns."
)
def skill_xlsx_content_calendar(
    output_path: str,
    month: str = "",
    platforms: str = "douyin,xiaohongshu",
    posts_per_day: int = 1,
    theme: str = "ocean",
):
    """
    Generate a professional 30-day content calendar spreadsheet with data validation.

    Args:
        output_path: Where to save the .xlsx file (e.g., /path/to/calendar.xlsx)
        month: Month label (e.g., "2026-07"), auto-generated from today if empty
        platforms: Comma-separated platform list (default: douyin,xiaohongshu)
        posts_per_day: Posts per platform per day (1-3, default 1)
        theme: Brand color theme — "ocean" (blue), "sunset" (orange), "forest" (green), "midnight" (indigo)

    Returns:
        dict with output path, row count, columns, theme used
    """
    import openpyxl
    from openpyxl.utils import get_column_letter

    t = _get_theme(theme)

    if not month:
        today = datetime.date.today()
        month = today.strftime("%Y-%m")
        start_date = today
    else:
        try:
            start_date = datetime.date.fromisoformat(month + "-01")
        except (ValueError, TypeError):
            start_date = datetime.date.today()
            month = start_date.strftime("%Y-%m")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "内容日历"

    headers = ["日期", "星期", "平台", "内容类型", "主题/标题", "文案要点", "话题标签", "状态", "备注"]
    col_count = len(headers)
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)

    content_types = ["短视频", "图文", "直播预告", "互动话题", "教程/干货", "幕后花絮", "热点借势"]
    statuses = ["待创作", "创作中", "待审核", "已排期", "已发布", "已归档"]
    plat_list = [p.strip() for p in platforms.split(",") if p.strip()]
    days_week = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    row = 2
    day_count = 0
    for day_offset in range(30):
        current_date = start_date + datetime.timedelta(days=day_offset)
        for plat in plat_list:
            for post_num in range(max(1, min(posts_per_day, 3))):
                ws.cell(row=row, column=1, value=current_date.isoformat())
                ws.cell(row=row, column=2, value=days_week[current_date.weekday()])
                ws.cell(row=row, column=3, value=plat)
                ws.cell(row=row, column=4, value=content_types[(day_count + post_num) % len(content_types)])
                ws.cell(row=row, column=5, value="")
                ws.cell(row=row, column=6, value="")
                ws.cell(row=row, column=7, value="")
                ws.cell(row=row, column=8, value="待创作")
                ws.cell(row=row, column=9, value="")
                row += 1
                day_count += 1

    end_row = row - 1

    # ── Branded styling ──
    _xlsx_style_header(ws, t, col_count)
    _xlsx_style_data(ws, t, start_row=2)
    _xlsx_auto_width(ws, max_width=50)

    # ── Data validation dropdowns ──
    _xlsx_add_dropdown(ws, "D", content_types, start_row=2, end_row=end_row)
    _xlsx_add_dropdown(ws, "H", statuses, start_row=2, end_row=end_row)
    _xlsx_add_dropdown(ws, "C", plat_list, start_row=2, end_row=end_row)

    # ── Highlight weekends ──
    from openpyxl.styles import PatternFill
    weekend_fill = PatternFill(start_color=t.bg_warm, end_color=t.bg_warm, fill_type="solid")
    for r in range(2, end_row + 1):
        day_val = ws.cell(row=r, column=2).value
        if day_val in ("周六", "周日"):
            for c in range(1, col_count + 1):
                ws.cell(row=r, column=c).fill = weekend_fill

    wb.save(output_path)
    return {
        "output": output_path,
        "month": month,
        "rows": end_row - 1,
        "platforms": plat_list,
        "columns": headers,
        "theme": t.name,
        "features": ["branded_header", "alternating_rows", "dropdown_validation", "weekend_highlight", "auto_filter", "frozen_panes"],
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_docx_script_outline
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_docx_script_outline",
    "Generate a professionally-formatted video script outline as .docx. "
    "Sections: branded cover, hook (0-3s), content beats with timing table, CTA, B-roll checklist. "
    "Includes header/footer and professional typography."
)
def skill_docx_script_outline(
    output_path: str,
    title: str,
    hook: str = "",
    body_sections: str = "",
    cta: str = "",
    duration_seconds: int = 60,
    theme: str = "ocean",
):
    """
    Generate a professional video script outline with branded formatting.

    Args:
        output_path: Where to save the .docx (e.g., /path/to/script.docx)
        title: Video title / main theme
        hook: Opening hook (first 3 seconds — optional)
        body_sections: JSON array of body beats, e.g. '[{"time":"0:03-0:15","heading":"Intro","text":"..."}]'
        cta: Call to action text (optional)
        duration_seconds: Target video duration in seconds (default 60)
        theme: Brand theme — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with output path, section count, duration
    """
    import docx
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    t = _get_theme(theme)
    doc = docx.Document()
    _docx_setup(doc, t)
    _docx_add_header_footer(doc, t, title)

    # ── Cover ──
    h = doc.add_heading(title, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(*t.hex_to_rgb(t.primary))

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    mr = meta.add_run(f"预计时长: {duration_seconds}s  |  格式: 竖屏 9:16  |  状态: 待拍摄")
    mr.font.size = Pt(t.font_size_small)
    mr.font.color.rgb = RGBColor(*t.hex_to_rgb(t.text_muted))
    doc.add_paragraph()

    # ── Hook (0-3s) ──
    doc.add_heading("🎯 开场 Hook (0-3秒)", level=1)
    doc.add_paragraph(
        hook or "[待填写] — 黄金3秒法则：用痛点、奇观、提问、或反差抓住注意力。"
        "示例: '你知道吗？90% 的短视频都在前3秒流失了观众...'"
    )

    # ── Body beats with timing table ──
    doc.add_heading(f"📝 内容节奏 (3s-{duration_seconds - 5}s)", level=1)

    sections = []
    if body_sections:
        try:
            sections = json.loads(body_sections)
        except json.JSONDecodeError:
            sections = [{"time": "", "heading": "内容段落", "text": body_sections}]

    if not sections:
        sections = [
            {"time": "0:03-0:15", "heading": "建立信任",
             "text": "展示专业度/同理心，让观众觉得'这人懂我'"},
            {"time": f"0:15-0:{duration_seconds - 10}", "heading": "核心内容",
             "text": "干货/故事/教程的核心部分，每15秒一个信息点"},
            {"time": f"0:{duration_seconds - 10}-0:{duration_seconds - 5}", "heading": "情绪高点",
             "text": "让观众产生共鸣或行动的冲动"},
        ]

    # Timing table
    table_data = []
    for sec in sections:
        table_data.append([
            sec.get("time", ""),
            sec.get("heading", ""),
            sec.get("text", "")[:120],
        ])
    _docx_add_table(doc, ["时间戳", "段落标题", "内容要点"], table_data, t,
                    col_widths=[1.0, 1.5, 4.0])

    # Detailed sections
    for sec in sections:
        doc.add_heading(sec.get("heading", "段落"), level=2)
        doc.add_paragraph(sec.get("text", "[待填写]"))

    # ── CTA ──
    doc.add_heading("📢 行动号召 CTA (最后5秒)", level=1)
    doc.add_paragraph(
        cta or "[待填写] — 明确引导下一步动作。"
        "示例: '关注我，每天分享一个短视频运营干货！评论区告诉我你的问题，下期回答你！'"
    )

    # ── Production checklist ──
    doc.add_heading("🎬 制作清单", level=1)
    for item in [
        "□ 口播录音 (安静环境, 领夹麦, -12dB 增益)",
        "□ B-Roll 素材: 产品特写 / 操作演示 / 场景过渡 / 文字动画",
        "□ 字幕: 剪映自动生成 → 人工校对 → 样式统一",
        "□ 背景音乐: 轻快/商业感, 音量 -18dB, 淡入淡出",
        "□ 封面图: 大字标题 + 人物半身照 + 品牌色边框",
        f"□ 最终成片时长: ≤{duration_seconds}s",
        "□ A/B 测试版本: 准备 2 个不同 Hook 版本",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.save(output_path)
    return {
        "output": output_path,
        "title": title,
        "sections": len(sections),
        "duration_seconds": duration_seconds,
        "theme": t.name,
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_pptx_carousel
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_pptx_carousel",
    "Generate branded social media carousel slides as .pptx (3:4 format). "
    "Features: gradient backgrounds, accent bars, professional typography, "
    "page numbering, 4 brand themes. Each slide = JSON object with title + body."
)
def skill_pptx_carousel(
    output_path: str,
    slides_data: str,
    theme: str = "ocean",
):
    """
    Generate branded carousel slides for social media (小红书/Instagram 3:4 format).

    Args:
        output_path: Where to save .pptx (e.g., /path/to/carousel.pptx)
        slides_data: JSON array of slides, e.g.:
            '[{"title":"5个短视频技巧","body":"技巧1: 黄金3秒抓住注意力\\n技巧2: ..."}, ...]'
        theme: Brand theme — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with output path, slide count, theme, dimensions
    """
    from pptx import Presentation

    t = _get_theme(theme)

    try:
        slides = json.loads(slides_data)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON in slides_data: {slides_data[:100]}"}

    if not isinstance(slides, list) or not slides:
        return {"error": "slides_data must be a non-empty JSON array"}

    prs = Presentation()
    _pptx_setup(prs, t)
    total = len(slides)

    for i, slide_info in enumerate(slides):
        title_text = slide_info.get("title", f"Slide {i+1}")
        body_text = slide_info.get("body", "")

        def add_brand_tag(slide):
            """Small brand tag in bottom-right corner."""
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
            tag = slide.shapes.add_textbox(Inches(5.3), Inches(9.82), Inches(1.8), Inches(0.35))
            tf = tag.text_frame
            p = tf.paragraphs[0]
            p.text = "szyg.ai"
            p.font.size = Pt(7)
            p.font.name = t.font_en
            p.font.color.rgb = RGBColor(*t.hex_to_rgb(t.text_muted))

        _pptx_add_branded_slide(prs, t, title_text, body_text, i + 1, total,
                                extra_shapes=add_brand_tag)

    prs.save(output_path)
    return {
        "output": output_path,
        "slides": total,
        "theme": t.name,
        "dimensions": "8.0 x 10.67 inches (3:4 carousel)",
        "features": ["gradient_background", "accent_bar", "branded_card", "page_numbers", "brand_tag"],
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_xlsx_bulk_export
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_xlsx_bulk_export",
    "Export multiple content datasets to a single .xlsx workbook with styled sheets. "
    "Each key in the JSON object becomes a separate branded sheet. Supports list-of-lists, "
    "list-of-dicts, and pivot-style summary sheets."
)
def skill_xlsx_bulk_export(
    output_path: str,
    data_json: str,
    theme: str = "ocean",
):
    """
    Export multiple content sets to a professionally-styled multi-sheet workbook.

    Args:
        output_path: Where to save .xlsx
        data_json: JSON object. Each key = sheet name, value = list of rows.
            Rows can be: list-of-lists (2D array), list-of-dicts (keys→headers), or list-of-strings.
            Example: '{"短视频脚本":[["标题","文案"],["技巧1","文案..."]],"图文素材":[...]}'
        theme: Brand theme — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with output path, sheet names, row counts
    """
    import openpyxl

    t = _get_theme(theme)

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON in data_json: {data_json[:100]}"}

    if not isinstance(data, dict):
        return {"error": "data_json must be a JSON object, e.g. {'Sheet1': [['H1','H2'],['r1','r2']]}"}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    sheet_info = {}
    first = True
    for sheet_name, rows in data.items():
        safe_name = sheet_name[:31].replace(":", "-").replace("\\", "-").replace("/", "-").replace("*", "-").replace("?", "-")

        if first:
            ws = wb.create_sheet(title=safe_name, index=0)
            first = False
        else:
            ws = wb.create_sheet(title=safe_name)

        if not isinstance(rows, list) or not rows:
            sheet_info[safe_name] = {"rows": 0, "cols": 0, "error": "Empty or non-list data"}
            continue

        if all(isinstance(r, dict) for r in rows):
            # List of dicts → keys as headers
            keys = list(rows[0].keys())
            for c, k in enumerate(keys, 1):
                ws.cell(row=1, column=c, value=k)
            for r_idx, row_dict in enumerate(rows, 2):
                for c_idx, k in enumerate(keys, 1):
                    ws.cell(row=r_idx, column=c_idx, value=row_dict.get(k, ""))
        elif all(isinstance(r, list) for r in rows):
            # List of lists → direct write
            for r_idx, row in enumerate(rows, 1):
                for c_idx, val in enumerate(row, 1):
                    ws.cell(row=r_idx, column=c_idx, value=val)
        else:
            # Scalar list → one column
            ws.cell(row=1, column=1, value=sheet_name)
            for r_idx, val in enumerate(rows, 2):
                ws.cell(row=r_idx, column=1, value=str(val))

        _xlsx_style_header(ws, t, ws.max_column)
        _xlsx_style_data(ws, t, start_row=2)
        _xlsx_auto_width(ws)
        sheet_info[safe_name] = {"rows": len(rows), "cols": ws.max_column}

    wb.save(output_path)
    return {
        "output": output_path,
        "sheets": sheet_info,
        "total_sheets": len(data),
        "theme": t.name,
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_docx_creative_brief
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_docx_creative_brief",
    "Generate a professionally-structured marketing creative brief as .docx. "
    "Sections: campaign overview, objective, audience, key message, tone, deliverables "
    "table, timeline, success metrics. Branded with header/footer and theme."
)
def skill_docx_creative_brief(
    output_path: str,
    brand: str = "",
    campaign: str = "",
    objective: str = "",
    target_audience: str = "",
    key_message: str = "",
    deliverables: str = "",
    deadline_days: int = 14,
    theme: str = "ocean",
):
    """
    Generate a professional marketing creative brief with structured sections.

    Args:
        output_path: Where to save .docx
        brand: Brand / product name
        campaign: Campaign name / theme
        objective: Campaign objective (awareness, conversion, engagement, lead-gen)
        target_audience: Target audience description (age, interests, pain points)
        key_message: Single core message to communicate
        deliverables: Comma-separated list (e.g., "短视频,图文,直播脚本")
        deadline_days: Days until deadline (default 14)
        theme: Brand theme — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with output path, brand, campaign, deadline
    """
    import docx
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    t = _get_theme(theme)
    doc = docx.Document()
    _docx_setup(doc, t)
    _docx_add_header_footer(doc, t, f"{brand} — {campaign}")

    deadline = (datetime.date.today() + datetime.timedelta(days=deadline_days)).isoformat()

    # ── Cover ──
    title_text = f"{brand or '[品牌]'} — {campaign or '[Campaign Name]'}"
    h = doc.add_heading(title_text, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(*t.hex_to_rgb(t.primary))

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run(f"创意简报  |  截止: {deadline}  |  状态: 草稿")
    sr.font.size = Pt(t.font_size_small)
    sr.font.color.rgb = RGBColor(*t.hex_to_rgb(t.text_muted))
    doc.add_paragraph()

    # ── Sections ──
    sections = [
        ("🎯 营销目标", objective or "[待填写] 本次 campaign 的核心目标是什么？\n品牌曝光 / 用户增长 / 转化销售 / 线索获取 — 选择1个主目标"),
        ("👤 目标受众", target_audience or "[待填写] 用户画像：年龄段、性别、城市等级、兴趣爱好、消费习惯、痛点\n示例: 25-35岁一线城市女性，关注护肤和生活方式，月消费3000+"),
        ("💡 核心信息", key_message or "[待填写] 用一句话表达你最想让用户记住的是什么\n这是所有内容的灵魂 — 每个素材都应围绕它展开"),
        ("🎨 品牌调性", "选择1-2个关键词定义内容风格：\n专业权威 / 温暖亲切 / 潮流前卫 / 极简高级 / 幽默搞笑 / 情感触动"),
    ]

    for heading, content in sections:
        doc.add_heading(heading, level=1)
        doc.add_paragraph(content)

    # ── Deliverables table ──
    doc.add_heading("📦 交付物清单", level=1)
    dl_list = [d.strip() for d in (deliverables or "短视频脚本,图文素材,直播脚本,话题标签,封面图").split(",") if d.strip()]
    dl_rows = []
    for i, dl in enumerate(dl_list):
        dl_rows.append([str(i+1), dl, "待制作", "", ""])
    _docx_add_table(doc, ["#", "交付物", "状态", "负责人", "备注"], dl_rows, t,
                    col_widths=[0.5, 2.0, 1.0, 1.2, 1.8])

    # ── Timeline ──
    doc.add_heading("📅 时间线", level=1)
    tl_rows = [
        ["Day 1-3", "创意发想", "头脑风暴 → 竞品分析 → 确定方向"],
        ["Day 4-7", "内容制作", "脚本撰写 → 拍摄/设计 → 初稿完成"],
        [f"Day 8-{deadline_days-2}", "审核修改", "内部Review → 修改 → 定稿"],
        [f"Day {deadline_days-1}-{deadline_days}", "排期发布", "上传平台 → 设置定时 → 发布"],
    ]
    _docx_add_table(doc, ["时间", "阶段", "任务"], tl_rows, t, col_widths=[1.5, 1.5, 3.5])

    # ── Success metrics ──
    doc.add_heading("📊 成功指标 (KPI)", level=1)
    doc.add_paragraph(
        "[待填写] 设定可衡量的目标：\n"
        "• 播放量/曝光量: ≥ ____\n"
        "• 互动率 (点赞+评论+收藏/播放): ≥ ____%\n"
        "• 转发/分享: ≥ ____\n"
        "• 粉丝增长: ≥ ____\n"
        "• 转化/咨询量: ≥ ____"
    )

    doc.save(output_path)
    return {
        "output": output_path,
        "brand": brand,
        "campaign": campaign,
        "deadline": deadline,
        "deliverables": dl_list,
        "theme": t.name,
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_xlsx_analytics_template
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_xlsx_analytics_template",
    "Create a professionally-formatted multi-sheet analytics workbook for tracking "
    "content performance across platforms. Includes: Overview with SUM formulas, "
    "Daily Metrics with conditional formatting (color scales), Platform Comparison, "
    "and Top Content sheets. Branded with freeze panes, auto-filter, and tab colors."
)
def skill_xlsx_analytics_template(
    output_path: str,
    platforms: str = "douyin,xiaohongshu",
    days: int = 30,
    theme: str = "ocean",
):
    """
    Generate a professional analytics tracking workbook with formulas and formatting.

    Args:
        output_path: Where to save .xlsx
        platforms: Comma-separated platform names (default: douyin,xiaohongshu)
        days: Number of days to track (7-90, default 30)
        theme: Brand theme — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with output path, sheet names, platforms, days
    """
    import openpyxl
    from openpyxl.utils import get_column_letter

    t = _get_theme(theme)
    days = max(7, min(days, 90))
    plat_list = [p.strip() for p in platforms.split(",") if p.strip()]

    wb = openpyxl.Workbook()

    # ═══ Sheet 1: 总览 (Overview) ═══
    ws1 = wb.active
    ws1.title = "总览"
    overview_headers = ["指标"] + plat_list + ["合计", "目标", "达成率(%)"]
    col1 = len(overview_headers)
    for c, h in enumerate(overview_headers, 1):
        ws1.cell(row=1, column=c, value=h)

    metrics = ["发布数", "播放量", "点赞", "评论", "收藏", "转发", "粉丝增长", "转化数"]
    for r, metric in enumerate(metrics, 2):
        ws1.cell(row=r, column=1, value=metric)
        # SUM formula across platforms
        start_col = get_column_letter(2)
        end_col = get_column_letter(1 + len(plat_list))
        sum_col = 2 + len(plat_list)
        ws1.cell(row=r, column=sum_col, value=f"=SUM({start_col}{r}:{end_col}{r})")
        # Achievement rate
        target_col_letter = get_column_letter(sum_col + 1)
        ws1.cell(row=r, column=sum_col + 2,
                 value=f'=IF({target_col_letter}{r}>0,{get_column_letter(sum_col)}{r}/{target_col_letter}{r}*100,"")')

    # Percentage format for achievement column
    from openpyxl.styles.numbers import FORMAT_PERCENTAGE
    for r in range(2, len(metrics) + 2):
        ws1.cell(row=r, column=col1).number_format = '0.0"%"'

    _xlsx_style_header(ws1, t, col1)
    _xlsx_style_data(ws1, t, start_row=2)
    _xlsx_auto_width(ws1)

    # ═══ Sheet 2: 每日数据 (Daily Metrics) ═══
    ws2 = wb.create_sheet("每日数据")
    daily_headers = ["日期"]
    for plat in plat_list:
        daily_headers.extend([f"{plat}-播放", f"{plat}-点赞", f"{plat}-评论", f"{plat}-转发"])
    col2 = len(daily_headers)
    for c, h in enumerate(daily_headers, 1):
        ws2.cell(row=1, column=c, value=h)

    today = datetime.date.today()
    for day_offset in range(days):
        r = day_offset + 2
        current = today - datetime.timedelta(days=days - 1 - day_offset)
        ws2.cell(row=r, column=1, value=current.isoformat())

    _xlsx_style_header(ws2, t, col2)
    _xlsx_style_data(ws2, t, start_row=2)
    _xlsx_auto_width(ws2)

    # Conditional formatting: color scale on numeric columns
    for plat_idx in range(len(plat_list)):
        for metric_col in range(4):  # 4 metrics per platform
            col = 2 + plat_idx * 4 + metric_col
            col_letter = get_column_letter(col)
            _xlsx_add_conditional_format(ws2, col_letter, start_row=2, end_row=days + 1, theme=t)

    # ═══ Sheet 3: 平台对比 (Platform Comparison) ═══
    ws3 = wb.create_sheet("平台对比")
    comp_headers = ["平台", "总播放", "平均点赞", "平均评论", "互动率(%)", "最优发布时间", "最优内容类型"]
    col3 = len(comp_headers)
    for c, h in enumerate(comp_headers, 1):
        ws3.cell(row=1, column=c, value=h)
    for r, plat in enumerate(plat_list, 2):
        ws3.cell(row=r, column=1, value=plat)
        ws3.cell(row=r, column=5, value="")  # Will be filled with formula

    _xlsx_style_header(ws3, t, col3)
    _xlsx_style_data(ws3, t, start_row=2)
    _xlsx_auto_width(ws3)

    # ═══ Sheet 4: 爆款内容 (Top Content) ═══
    ws4 = wb.create_sheet("爆款内容")
    top_headers = ["日期", "平台", "标题", "播放量", "点赞", "评论", "转发", "互动率(%)", "内容类型", "备注"]
    col4 = len(top_headers)
    for c, h in enumerate(top_headers, 1):
        ws4.cell(row=1, column=c, value=h)

    _xlsx_style_header(ws4, t, col4)
    _xlsx_auto_width(ws4)
    # Conditional formatting on engagement columns
    for col_idx in [4, 5, 6, 7]:
        _xlsx_add_conditional_format(ws4, get_column_letter(col_idx), start_row=2, end_row=52, theme=t)

    wb.save(output_path)
    return {
        "output": output_path,
        "sheets": [ws.title for ws in wb.worksheets],
        "platforms": plat_list,
        "days": days,
        "theme": t.name,
        "features": ["sum_formulas", "color_scale_conditional_formatting", "percentage_format", "frozen_panes", "tab_colors"],
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_marketing_hashtags
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_marketing_hashtags",
    "Generate platform-optimized hashtag sets for social media posts. "
    "Returns categorized tags (topic/brand, category, niche long-tail, trending) "
    "with estimated reach scores and platform-specific recommendations."
)
def skill_marketing_hashtags(
    topic: str,
    platform: str = "douyin",
    count: int = 15,
):
    """
    Generate platform-optimized hashtag recommendations with engagement estimates.

    Args:
        topic: Content topic / keyword (e.g., "短视频运营", "护肤品测评", "美食探店")
        platform: Target platform — "douyin", "xiaohongshu", or "wechat" (default: douyin)
        count: Number of hashtags to generate (5-30, default 15)

    Returns:
        dict with categorized hashtag sets, usage strategy, and platform notes
    """
    count = max(5, min(count, 30))
    topic_clean = topic.strip().replace(" ", "")

    # ── Platform-specific configurations ──
    platforms_config = {
        "douyin": {
            "max_tags": 5,
            "optimal_combo": "1 topic + 2 category + 1 long-tail + 1 trending",
            "note": "Douyin limits visible hashtags to ~5; more = shadowban risk",
            "category_prefix": ["教程", "技巧", "干货", "日常", "vlog", "挑战", "测评"],
            "trending": ["上热门", "推荐", "小助手"],
            "reach_multiplier": {"topic": 1.0, "category": 0.7, "niche": 0.3, "trending": 1.5},
        },
        "xiaohongshu": {
            "max_tags": 10,
            "optimal_combo": "2 topic + 3 category + 3 long-tail + 2 trending",
            "note": "XHS allows more tags; long-tail niche tags drive discovery",
            "category_prefix": ["教程", "分享", "测评", "好物", "探店", "ootd", "干货"],
            "trending": ["笔记灵感", "好物推荐", "生活薯"],
            "reach_multiplier": {"topic": 1.0, "category": 0.8, "niche": 0.6, "trending": 1.2},
        },
        "wechat": {
            "max_tags": 3,
            "optimal_combo": "1 topic + 1 category + 1 trending",
            "note": "WeChat Channels: fewer tags, focus on quality over quantity",
            "category_prefix": ["干货", "观点", "趋势", "方法论"],
            "trending": ["视频号", "原创"],
            "reach_multiplier": {"topic": 1.0, "category": 0.5, "niche": 0.2, "trending": 1.0},
        },
    }
    pf = platforms_config.get(platform, platforms_config["douyin"])
    mult = pf["reach_multiplier"]

    # ── Generate tags by category ──
    category_tags = []
    for i in range(min(6, count // 2)):
        prefix = pf["category_prefix"][i % len(pf["category_prefix"])]
        category_tags.append({"tag": f"#{topic_clean}{prefix}", "reach": "medium", "score": mult["category"]})

    trending_tags = [{"tag": f"#{t}", "reach": "high", "score": mult["trending"]}
                     for t in pf["trending"][:4]]

    topic_tags = [
        {"tag": f"#{topic_clean}", "reach": "high", "score": mult["topic"]},
    ]

    niche_templates = ["必备", "攻略", "推荐", "避坑", "心得", "入门", "进阶"]
    niche_tags = []
    for nt in niche_templates:
        if len(niche_tags) < max(0, count - len(category_tags) - len(trending_tags) - len(topic_tags)):
            niche_tags.append({"tag": f"#{topic_clean}{nt}", "reach": "low", "score": mult["niche"]})

    # ── Merge, deduplicate, and backfill to target count ──
    seen = set()
    all_tags = []
    for tag_obj in (category_tags + topic_tags + trending_tags + niche_tags):
        if tag_obj["tag"] not in seen:
            seen.add(tag_obj["tag"])
            all_tags.append(tag_obj)

    # Backfill with niche tags if dedup reduced the count
    niche_backfill = ["秘籍", "宝典", "日记", "日志", "指南", "清单", "模板", "案例", "实战", "灵感"]
    backfill_idx = 0
    while len(all_tags) < count and backfill_idx < len(niche_backfill):
        candidate = f"#{topic_clean}{niche_backfill[backfill_idx]}"
        backfill_idx += 1
        if candidate not in seen:
            seen.add(candidate)
            all_tags.append({"tag": candidate, "reach": "low", "score": mult["niche"]})

    all_tags = all_tags[:count]

    return {
        "topic": topic,
        "platform": platform,
        "total": len(all_tags),
        "platform_max_tags": pf["max_tags"],
        "optimal_combo": pf["optimal_combo"],
        "note": pf["note"],
        "tags": [t["tag"] for t in all_tags],
        "tags_detailed": all_tags,
        "by_category": {
            "topic_brand": [t["tag"] for t in all_tags if t in topic_tags],
            "category": [t["tag"] for t in all_tags if t in category_tags],
            "niche_long_tail": [t["tag"] for t in all_tags if t in niche_tags or t.get("reach") == "low"],
            "trending": [t["tag"] for t in all_tags if t in trending_tags],
        },
        "strategy": (
            f"推荐组合 ({platform}): {pf['optimal_combo']}。"
            f"话题标签驱动搜索发现，分类标签帮助算法定位受众，"
            f"长尾标签降低竞争，热门标签获取短期曝光。"
        ),
    }


# ═══════════════════════════════════════════════════════════════
# Tool: skill_batch_convert
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "skill_batch_convert",
    "Batch convert content files between formats. Supported: markdown→docx (styled), "
    "json→xlsx (auto-detect structure), text→pptx (one slide per paragraph). "
    "Processes multiple files in a single call with detailed per-file results."
)
def skill_batch_convert(
    input_files_json: str,
    output_dir: str,
    target_format: str = "docx",
    theme: str = "ocean",
):
    """
    Convert multiple content files to a target format in one batch.

    Args:
        input_files_json: JSON array of file paths, e.g. '["/path/a.md","/path/b.md"]'
        output_dir: Directory for output files (auto-created if needed)
        target_format: "docx", "xlsx", or "pptx" (default: docx)
        theme: Brand theme for styled output — "ocean", "sunset", "forest", "midnight"

    Returns:
        dict with total/succeeded/failed counts, per-file results
    """
    t = _get_theme(theme)

    try:
        files = json.loads(input_files_json)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON: {input_files_json[:100]}"}

    if not isinstance(files, list) or not files:
        return {"error": "input_files_json must be a non-empty JSON array"}

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for fpath in files:
        src = Path(fpath)
        if not src.exists():
            results.append({"input": fpath, "error": "File not found"})
            continue

        out_path = out_dir / f"{src.stem}.{target_format}"

        try:
            if target_format == "docx":
                import docx
                doc = docx.Document()
                _docx_setup(doc, t)
                _docx_add_header_footer(doc, t, src.stem)
                text = src.read_text(encoding="utf-8", errors="replace")
                # Parse markdown-ish structure
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("# "):
                        doc.add_heading(line[2:], level=1)
                    elif line.startswith("## "):
                        doc.add_heading(line[3:], level=2)
                    elif line.startswith("- "):
                        doc.add_paragraph(line[2:], style="List Bullet")
                    else:
                        doc.add_paragraph(line)
                doc.save(str(out_path))
                results.append({"input": fpath, "output": str(out_path), "status": "ok"})

            elif target_format == "xlsx":
                import openpyxl
                text = src.read_text(encoding="utf-8", errors="replace")
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = src.stem[:31]
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                # Try JSON detection
                if text.strip().startswith("[") or text.strip().startswith("{"):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list) and all(isinstance(r, list) for r in parsed):
                            for r, row in enumerate(parsed, 1):
                                for c, val in enumerate(row, 1):
                                    ws.cell(row=r, column=c, value=val)
                        elif isinstance(parsed, list) and all(isinstance(r, dict) for r in parsed):
                            keys = list(parsed[0].keys())
                            for c, k in enumerate(keys, 1):
                                ws.cell(row=1, column=c, value=k)
                            for r, obj in enumerate(parsed, 2):
                                for c, k in enumerate(keys, 1):
                                    ws.cell(row=r, column=c, value=obj.get(k, ""))
                        elif isinstance(parsed, dict):
                            for r, (k, v) in enumerate(parsed.items(), 1):
                                ws.cell(row=r, column=1, value=str(k))
                                ws.cell(row=r, column=2, value=str(v))
                    except json.JSONDecodeError:
                        for r, line in enumerate(lines, 1):
                            ws.cell(row=r, column=1, value=line)
                else:
                    for r, line in enumerate(lines, 1):
                        ws.cell(row=r, column=1, value=line)
                _xlsx_style_header(ws, t, ws.max_column)
                _xlsx_style_data(ws, t, start_row=2)
                _xlsx_auto_width(ws)
                wb.save(str(out_path))
                results.append({"input": fpath, "output": str(out_path), "status": "ok"})

            elif target_format == "pptx":
                from pptx import Presentation
                from pptx.util import Inches, Pt
                text = src.read_text(encoding="utf-8", errors="replace")
                prs = Presentation()
                slides_added = 0
                for para in text.split("\n"):
                    para = para.strip()
                    if not para:
                        continue
                    slide = prs.slides.add_slide(prs.slide_layouts[1])
                    if slide.shapes.title:
                        slide.shapes.title.text = para[:80]
                    slides_added += 1
                    if slides_added >= 20:
                        break
                prs.save(str(out_path))
                results.append({"input": fpath, "output": str(out_path), "slides": slides_added, "status": "ok"})

            else:
                results.append({"input": fpath, "error": f"Unsupported format: {target_format}. Use docx/xlsx/pptx"})

        except Exception as e:
            results.append({"input": fpath, "error": f"{type(e).__name__}: {e}"})

    succeeded = sum(1 for r in results if r.get("status") == "ok")
    failed = sum(1 for r in results if "error" in r)

    return {
        "target_format": target_format,
        "output_dir": str(out_dir),
        "total": len(files),
        "succeeded": succeeded,
        "failed": failed,
        "theme": t.name,
        "files": results,
    }


# ═══════════════════════════════════════════════════════════════
# Skill Info — metadata for discovery
# ═══════════════════════════════════════════════════════════════

@server.tool("skills_list", "List all available ported skills and their capabilities")
def skills_list():
    """Return all available skills with descriptions."""
    return {
        "skills": [
            {"name": "docx", "category": "office",
             "tools": ["skill_docx_to_markdown", "skill_docx_create", "skill_docx_extract_text"],
             "description": "Create, edit, and extract Word documents"},
            {"name": "xlsx", "category": "office",
             "tools": ["skill_xlsx_read", "skill_xlsx_create"],
             "description": "Read and create Excel spreadsheets"},
            {"name": "pptx", "category": "office",
             "tools": ["skill_pptx_extract", "skill_pptx_create"],
             "description": "Extract and create PowerPoint presentations"},
            {"name": "pdf", "category": "office",
             "tools": ["skill_pdf_extract", "skill_pdf_merge"],
             "description": "Extract text from PDF, merge PDFs"},
            {"name": "canvas-design", "category": "design",
             "tools": ["skill_canvas_get_fonts", "skill_canvas_preview_config"],
             "description": "Design banners, posters, and visual assets"},
            {"name": "marketing-calendar", "category": "marketing",
             "tools": ["skill_xlsx_content_calendar"],
             "description": "Professionally-styled 30-day content calendar with dropdown validation and weekend highlighting"},
            {"name": "marketing-script", "category": "marketing",
             "tools": ["skill_docx_script_outline"],
             "description": "Branded video script outline with timing table, B-roll checklist, and production notes"},
            {"name": "marketing-carousel", "category": "marketing",
             "tools": ["skill_pptx_carousel"],
             "description": "Gradient-background branded carousel slides (3:4 format) with accent bars and page numbers"},
            {"name": "marketing-bulk-export", "category": "marketing",
             "tools": ["skill_xlsx_bulk_export"],
             "description": "Multi-sheet workbook export with auto-detection of list/dict/2D-array structures"},
            {"name": "marketing-brief", "category": "marketing",
             "tools": ["skill_docx_creative_brief"],
             "description": "Professional creative brief with deliverables table, timeline, and KPI sections"},
            {"name": "marketing-analytics", "category": "marketing",
             "tools": ["skill_xlsx_analytics_template"],
             "description": "4-sheet analytics workbook: Overview (SUM formulas), Daily (color scales), Platform Comparison, Top Content"},
            {"name": "marketing-hashtags", "category": "marketing",
             "tools": ["skill_marketing_hashtags"],
             "description": "Platform-optimized hashtag generator with reach scores and strategy recommendations"},
            {"name": "marketing-batch-convert", "category": "marketing",
             "tools": ["skill_batch_convert"],
             "description": "Batch convert markdown/json/text between docx/xlsx/pptx with structure auto-detection"},
        ],
        "total": 13,
        "office_skills": 4,
        "design_skills": 1,
        "marketing_skills": 8,
        "themes_available": list(THEMES.keys()),
    }


if __name__ == "__main__":
    server.run()
