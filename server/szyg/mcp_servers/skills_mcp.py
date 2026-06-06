#!/usr/bin/env python3
"""
MCP Server: Skills — Claude Code Skills ported to szyg Hermes

Ported from anthropics/skills (Apache 2.0) via 数创引擎.

Skills loaded:
  Script-based (with actual tools): docx, xlsx, pptx, pdf, canvas-design
  Each skill's scripts are in server/szyg/skills/<name>/
"""
import sys, os, subprocess, tempfile, shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

SKILLS_DIR = Path(__file__).parent.parent / "skills"

server = MCPServer(
    "szyg-skills",
    "Claude Code compatible skills: docx, xlsx, pptx, pdf, canvas-design"
)


def _skill_dir(name: str) -> Path:
    return SKILLS_DIR / name


def _ensure_pandoc() -> bool:
    """Check if pandoc is available"""
    return shutil.which("pandoc") is not None


def _ensure_libreoffice() -> bool:
    """Check if LibreOffice is available"""
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
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        import openpyxl
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
            "data": rows[:1000],  # Limit to 1000 rows
        }
    except ImportError:
        return {"error": "openpyxl not installed. Run: pip install openpyxl"}
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
    import json
    try:
        import openpyxl
        data = json.loads(data_json)
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = sheet_name
        for row in data:
            sheet.append(row)
        wb.save(output_path)
        return {"output": output_path, "rows": len(data)}
    except ImportError:
        return {"error": "openpyxl not installed"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# pptx — PowerPoint
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_pptx_extract", "Extract text content from .pptx slides")
def skill_pptx_extract(file_path: str):
    """Extract text from each slide in a PowerPoint file."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        from pptx import Presentation
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
    except ImportError:
        return {"error": "python-pptx not installed. Run: pip install python-pptx"}
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
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt

        if template and Path(template).exists():
            prs = Presentation(template)
        else:
            prs = Presentation()

        lines = markdown.strip().split('\n')
        current_slide = None
        current_text = []

        for line in lines:
            if line.startswith('# ') or line.startswith('# '):
                # Save previous slide content
                if current_slide and current_text:
                    _add_text_to_slide(current_slide, current_text)
                slide_layout = prs.slide_layouts[1]  # Title and Content
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
    except ImportError:
        return {"error": "python-pptx not installed"}
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
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# pdf — PDF
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_pdf_extract", "Extract text from PDF file")
def skill_pdf_extract(file_path: str):
    """Extract text from PDF using PyPDF2 or pdfplumber."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    # Try pdfplumber first (better extraction)
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

    # Fallback: PyPDF2
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
    try:
        from PyPDF2 import PdfReader, PdfWriter
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
    except ImportError:
        return {"error": "PyPDF2 not installed"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# canvas-design — Banner/Poster Design
# ═══════════════════════════════════════════════════════════════

@server.tool("skill_canvas_get_fonts", "List available canvas design fonts")
def skill_canvas_get_fonts():
    """List fonts available in canvas-design skill."""
    fonts_dir = _skill_dir("canvas-design") / "canvas-fonts"
    if not fonts_dir.exists():
        return {"fonts": [], "error": "Fonts directory not found"}
    fonts = [f.stem for f in fonts_dir.glob("*.ttf")]
    return {"fonts": fonts, "count": len(fonts), "dir": str(fonts_dir)}


@server.tool("skill_canvas_preview_config", "Show canvas-design design parameters")
def skill_canvas_preview_config():
    """Return the canvas-design SKILL.md summary for Hermes agent."""
    skill_md = _skill_dir("canvas-design") / "SKILL.md"
    if not skill_md.exists():
        return {"error": "canvas-design SKILL.md not found"}
    content = skill_md.read_text(encoding="utf-8")[:3000]
    return {"skill": "canvas-design", "preview": content}


# ═══════════════════════════════════════════════════════════════
# Skill Info — metadata for discovery
# ═══════════════════════════════════════════════════════════════

@server.tool("skills_list", "List all available ported skills and their capabilities")
def skills_list():
    """Return all available skills with descriptions."""
    return {
        "skills": [
            {
                "name": "docx",
                "category": "office",
                "tools": ["skill_docx_to_markdown", "skill_docx_create", "skill_docx_extract_text"],
                "description": "Create, edit, and extract Word documents"
            },
            {
                "name": "xlsx",
                "category": "office",
                "tools": ["skill_xlsx_read", "skill_xlsx_create"],
                "description": "Read and create Excel spreadsheets"
            },
            {
                "name": "pptx",
                "category": "office",
                "tools": ["skill_pptx_extract", "skill_pptx_create"],
                "description": "Extract and create PowerPoint presentations"
            },
            {
                "name": "pdf",
                "category": "office",
                "tools": ["skill_pdf_extract", "skill_pdf_merge"],
                "description": "Extract text from PDF, merge PDFs"
            },
            {
                "name": "canvas-design",
                "category": "design",
                "tools": ["skill_canvas_get_fonts", "skill_canvas_preview_config"],
                "description": "Design banners, posters, and visual assets"
            },
        ],
        "total": 5,
        "office_skills": 4,
        "design_skills": 1,
    }


if __name__ == "__main__":
    server.run()
