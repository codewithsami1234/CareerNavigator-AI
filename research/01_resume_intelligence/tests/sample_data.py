"""Synthetic (fictional) resume texts and file builders used by tests and fixtures.

No real person is described here: names, e-mails (example.com) and phone numbers are made up.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

FULL_RESUME = """Alex Morgan
Lahore, Pakistan | alex.morgan@example.com | +92 300 0000000 | github.com/alexmorgan-demo | linkedin.com/in/alexmorgan-demo

Summary
Final-year IT student interested in machine learning and web development.

Skills
Programming Languages: Python, Java, JavaScript, SQL
Frameworks: Django, React, scikit-learn, OpenCV
Tools: Git, Docker, Postman

Education
Bachelor of Science in Information Technology, Example University of Technology (2021 - 2025)
CGPA: 3.4/4.0
Intermediate in Pre-Engineering, Sample Government College (2019 - 2021)

Experience
Software Engineering Intern | Acme Software Solutions | Jun 2024 - Aug 2024
- Built REST API endpoints with Django and PostgreSQL for an internal tool
- Containerized the service using Docker and wrote unit tests with pytest

Junior Web Developer, Demo Technologies Ltd (Jan 2023 - Present)
- Developed responsive pages with React and CSS
- Used Git and GitHub for code review

Projects
Smart Attendance System | Python, OpenCV
- Built a face-recognition attendance tool using OpenCV and Flask
- Stored records in SQLite

Resume Screening Assistant
- Trained a text classifier with scikit-learn and NLTK to rank resumes

Certifications
- Google Data Analytics Professional Certificate - Coursera (2023)
- AWS Cloud Practitioner Essentials, Amazon Web Services

Courses
- Machine Learning Specialization by Stanford Online

Achievements
- Winner, Example University Hackathon 2024

Languages
English, Urdu
"""

# Same content, different heading names, order and capitalisation.
VARIANT_HEADINGS_RESUME = """JORDAN LEE
jordan.lee@example.com

TECHNICAL SKILLS
Python, Node.js, MongoDB, k8s

PROFESSIONAL EXPERIENCE
Backend Developer at Sample Systems Pvt Ltd | March 2022 - Present
- Maintained Node.js services and MongoDB collections

ACADEMIC BACKGROUND
BS Computer Science, Demo Institute of Science (2018 - 2022)

PERSONAL PROJECTS
Chat Server
- WebSocket chat built with Node.js

LICENSES & CERTIFICATIONS
- Certified Kubernetes Application Developer (2023)
"""

NO_CONTACT_RESUME = """Skills
Python, SQL, Git

Experience
Data Analyst, Sample Analytics Co. (2020 - 2022)
- Wrote SQL queries and Python scripts to clean data

Education
Master of Science in Data Science, Example University (2018 - 2020)
"""

NO_SECTIONS_RESUME = """Sam Carter is a developer who has used Python and Docker on several
projects and enjoys building things. Reach me at sam.carter@example.com for more details about my work history.
He also worked with PostgreSQL and React for a small startup over a couple of years."""

SECTION_ORDER_REVERSED_RESUME = """Casey Jordan
casey.jordan@example.com

Certifications
- Azure Fundamentals - Microsoft (2022)

Projects
Budget Tracker
- Built with Flask and SQLite

Experience
Support Engineer, Example Corp (2021 - 2023)
- Automated tickets with Python

Education
BS Software Engineering, Demo University (2017 - 2021)

Skills
Python, Flask, SQLite
"""


# ---------------------------------------------------------------------------
# File builders
# ---------------------------------------------------------------------------
def write_txt(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def write_docx(path: Path, text: str) -> Path:
    import docx
    document = docx.Document()
    for line in text.split("\n"):
        document.add_paragraph(line)
    document.save(str(path))
    return path


def _ascii(line: str) -> str:
    return line.replace("–", "-").replace("—", "-").replace("•", "-")


def write_pdf(path: Path, text: str, font_size: float = 10) -> Path:
    """Create a text-based PDF. Blank lines in ``text`` become larger vertical gaps."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60.0
    pitch = font_size * 1.4
    import textwrap
    for source_line in text.split("\n"):
        # insert_text does not wrap, so long lines are wrapped here to stay on the page.
        pieces = textwrap.wrap(_ascii(source_line), width=92) or [""]
        for line in pieces:
            if y > 780:
                page = doc.new_page()
                y = 60.0
            if line.strip():
                page.insert_text((60, y), line, fontsize=font_size, fontname="helv")
                y += pitch
            else:
                y += pitch * 0.9
    doc.save(str(path))
    doc.close()
    return path


def write_image_only_pdf(path: Path) -> Path:
    """A PDF that contains only a raster image (like a scan) and no text layer."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(50, 50, 350, 350), pixmap=pix)
    doc.save(str(path))
    doc.close()
    return path


def write_encrypted_pdf(path: Path, text: str = FULL_RESUME) -> Path:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 60), "Confidential synthetic document", fontsize=10)
    doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    doc.close()
    return path


def write_empty_docx(path: Path) -> Path:
    import docx
    docx.Document().save(str(path))
    return path


def write_docx_with_table(path: Path) -> Path:
    import docx
    document = docx.Document()
    document.add_paragraph("Taylor Reed")
    document.add_paragraph("taylor.reed@example.com")
    document.add_paragraph("Skills")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Languages"
    table.cell(0, 1).text = "Python, Java"
    table.cell(1, 0).text = "Tools"
    table.cell(1, 1).text = "Git, Docker"
    document.add_paragraph("Education")
    document.add_paragraph("BS Computer Science, Example University (2019 - 2023)")
    document.save(str(path))
    return path


# Word text boxes. ``offset_emu`` is a paragraph-relative vertical anchor.
# Positive values sit below the host paragraph; negative values sit above it.
# ``None`` builds an inline box, kept in run order.
_TEXTBOX_NSDECL = " ".join([
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"',
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"',
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"',
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"',
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"',
    'xmlns:v="urn:schemas-microsoft-com:vml"',
])


def _xml_text(value: str) -> str:
    from xml.sax.saxutils import escape
    return f'<w:t xml:space="preserve">{escape(value)}</w:t>'


def _textbox_run_xml(lines: List[str], doc_id: int, offset_emu: int | None, fallback: bool) -> str:
    paras = "".join(f"<w:p><w:r>{_xml_text(line)}</w:r></w:p>" for line in lines)
    content = f"<w:txbxContent>{paras}</w:txbxContent>"
    shape = (
        "<wps:wsp>"
        f"<wps:txbx>{content}</wps:txbx>"
        '<wps:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/>'
        "</wps:wsp>"
    )
    graphic = (
        "<a:graphic><a:graphicData "
        'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f"{shape}</a:graphicData></a:graphic>"
    )
    if offset_emu is None:
        drawing = (
            '<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            '<wp:extent cx="3200000" cy="360000"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{doc_id}" name="TextBox{doc_id}"/>'
            "<wp:cNvGraphicFramePr/>"
            f"{graphic}</wp:inline></w:drawing>"
        )
    else:
        drawing = (
            '<w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" '
            'relativeHeight="251658240" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/>'
            '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="paragraph">'
            f"<wp:posOffset>{int(offset_emu)}</wp:posOffset></wp:positionV>"
            '<wp:extent cx="3200000" cy="360000"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            "<wp:wrapNone/>"
            f'<wp:docPr id="{doc_id}" name="TextBox{doc_id}"/>'
            "<wp:cNvGraphicFramePr/>"
            f"{graphic}</wp:anchor></w:drawing>"
        )
    if fallback:
        inner = (
            "<mc:AlternateContent>"
            f'<mc:Choice Requires="wps">{drawing}</mc:Choice>'
            "<mc:Fallback><w:pict>"
            '<v:shape style="width:180pt;height:24pt" filled="f" stroked="f">'
            f"<v:textbox>{content}</v:textbox></v:shape>"
            "</w:pict></mc:Fallback></mc:AlternateContent>"
        )
    else:
        inner = drawing
    return f"<w:r {_TEXTBOX_NSDECL}>{inner}</w:r>"


def add_textbox_paragraph(
    document,
    text: str,
    box_lines: List[str],
    doc_id: int,
    *,
    offset_emu: int | None,
    fallback: bool = False,
    box_first: bool = True,
) -> int:
    """Add a paragraph that may contain ordinary text and one Word text box.

    ``box_first`` controls XML run order, which is not always the visual order.
    Returns the next drawing id.
    """
    from docx.oxml import parse_xml

    paragraph = document.add_paragraph()
    run_xml = _textbox_run_xml(box_lines, doc_id, offset_emu, fallback) if box_lines else ""

    def _append_box() -> None:
        if run_xml:
            paragraph._p.append(parse_xml(run_xml))

    def _append_text() -> None:
        if text:
            paragraph.add_run(text)

    if box_first:
        _append_box()
        _append_text()
    else:
        _append_text()
        _append_box()
    return doc_id + 1


def write_resume_with_text_boxes(path: Path) -> Path:
    """Synthetic resume: headings live in floating text boxes, body text does not.

    The box is stored on the previous paragraph and anchored below it, which is
    how several Word templates keep a heading visually above the next block.
    Choice and Fallback copies repeat some headings. Two identical body lines
    are real repeated content and must both survive.
    """
    import docx

    document = docx.Document()
    doc_id = 1
    below = 365760  # 0.4 inch, clearly below the anchor paragraph
    document.add_paragraph("Riley Chen")
    doc_id = add_textbox_paragraph(
        document, "riley.chen@example.com", ["Career Objective"], doc_id,
        offset_emu=below, fallback=True, box_first=True,
    )
    doc_id = add_textbox_paragraph(
        document,
        "A careful student who wants to learn data analysis and write maintainable software.",
        ["Skills"], doc_id, offset_emu=below, fallback=True, box_first=True,
    )
    document.add_paragraph("Python, SQL, Git, Docker, and Linux")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Languages"
    table.cell(0, 1).text = "Python, SQL"
    table.cell(1, 0).text = "Tools"
    table.cell(1, 1).text = "Git, Docker"
    document.add_paragraph("Weekly lab report")
    document.add_paragraph("Weekly lab report")
    doc_id = add_textbox_paragraph(
        document, "Completed coursework projects with those tools.", ["Education"], doc_id,
        offset_emu=below, fallback=False, box_first=True,
    )
    document.add_paragraph("BS Computer Science, Example University (2019 - 2023)")
    doc_id = add_textbox_paragraph(
        document,
        "I have used these tools on several projects and enjoy learning new methods.",
        ["Course and Certificates"], doc_id, offset_emu=below, fallback=False, box_first=True,
    )
    doc_id = add_textbox_paragraph(
        document, "Intro to Python, Example Academy (2023)", ["Academic Interest"], doc_id,
        offset_emu=below, fallback=False, box_first=True,
    )
    add_textbox_paragraph(
        document, "Data analysis and careful software design.", ["Decl a r a tion"], doc_id,
        offset_emu=below, fallback=True, box_first=True,
    )
    document.add_paragraph("I confirm that this synthetic resume is accurate.")
    document.save(str(path))
    return path


def write_inline_textbox_resume(path: Path) -> Path:
    """Inline text box between two runs, plus a later paragraph heading and a table."""
    import docx

    document = docx.Document()
    document.add_paragraph("Riley Chen")
    document.add_paragraph("riley.chen@example.com")
    paragraph = document.add_paragraph()
    paragraph.add_run("Before heading ")
    from docx.oxml import parse_xml
    paragraph._p.append(parse_xml(_textbox_run_xml(["Experience"], 1, None, fallback=False)))
    paragraph.add_run("after heading")
    document.add_paragraph("Backend Developer, Sample Labs (2020 - 2022)")
    document.add_paragraph("- Built internal tools with Python and Docker")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Tools"
    table.cell(0, 1).text = "Python, Docker"
    document.add_paragraph("Education")
    document.add_paragraph("BS Computer Science, Example University (2019 - 2023)")
    document.save(str(path))
    return path


def write_textbox_above_paragraph(path: Path) -> Path:
    """The text run is stored first, but the anchor sits above that paragraph."""
    import docx

    document = docx.Document()
    document.add_paragraph("Riley Chen")
    document.add_paragraph("riley.chen@example.com")
    add_textbox_paragraph(
        document, "Python, SQL, Git, Docker, and Linux", ["Skills"], 1,
        offset_emu=-365760, fallback=False, box_first=False,
    )
    document.save(str(path))
    return path
