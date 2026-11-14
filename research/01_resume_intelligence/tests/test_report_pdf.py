"""The PDF export is a real PDF of the pipeline report, not a renamed HTML file."""
import pymupdf

from pipeline import analyze_job, analyze_text
from web.service import build_career_report
from web.ui.report_export import report_pdf

RESUME = """
Jordan Hale
jordan.hale@example.com
Skills
Python, JavaScript, SQL, Git, Docker
Experience
Software engineer at Northwind Labs
Built REST APIs with Python and SQL.
Shipped a dashboard using JavaScript.
Education
BSc Computer Science, State University
""" + ("\n".join(f"- Delivered internal tool number {index} with Python and SQL." for index in range(40)))

JOB = """
Required qualifications
- Python
- SQL
- JavaScript
Preferred qualifications
- Kubernetes
"""

UNSPECIFIED = """
About the job
We build marketing sites with JavaScript, HTML, and CSS in Webflow.
"""


def _open(pdf: bytes):
    assert pdf.startswith(b"%PDF")
    return pymupdf.open(stream=pdf, filetype="pdf")


def _text(document) -> str:
    return "\n".join(page.get_text() for page in document)


def _no_overlapping_lines(document) -> None:
    for page in document:
        boxes = [block["bbox"] for block in page.get_text("dict")["blocks"] if block.get("type") == 0]
        boxes.sort(key=lambda box: (box[1], box[0]))
        for earlier, later in zip(boxes, boxes[1:]):
            if later[1] >= earlier[3] - 1:
                continue
            assert abs(later[1] - earlier[1]) < 1.5


def test_pdf_copies_scored_analysis_across_pages():
    resume = analyze_text(RESUME, "text")
    job = analyze_job(JOB)
    career = build_career_report(resume, job, None)
    pdf = report_pdf(
        resume, job, career.comparison, None, career,
        job_title="Backend engineer", company="Northwind", target_career="Software engineering",
    )
    document = _open(pdf)
    assert document.page_count >= 2
    text = _text(document)
    assert "CareerNavigator AI" in text
    assert "Backend engineer" in text
    assert "Python" in text
    assert "Kubernetes" in text
    assert "Jordan Hale" in text or "jordan.hale@example.com" in text
    estimate = career.readiness.estimate
    assert f"Estimate: {estimate}" in text
    assert "Page 1 of" in document[0].get_text()
    assert f"Page {document.page_count} of {document.page_count}" in document[-1].get_text()
    _no_overlapping_lines(document)
    document.close()


def test_pdf_says_not_scored_without_inventing_a_number():
    resume = analyze_text(RESUME, "text")
    job = analyze_job(UNSPECIFIED)
    career = build_career_report(resume, job, None)
    assert career.readiness.estimate is None
    document = _open(report_pdf(resume, job, career.comparison, None, career))
    text = _text(document)
    assert "Estimate: Not scored" in text
    assert "Estimate: 100" not in text
    assert "Webflow" in text
    _no_overlapping_lines(document)
    document.close()


def test_pdf_handles_a_resume_without_optional_sections():
    resume = analyze_text("Skills\nPython\n", "text")
    document = _open(report_pdf(resume, None, None, None, None))
    text = _text(document)
    assert "No job description was supplied" in text
    assert "GitHub analysis was not requested" in text
    assert "No readiness object was returned" in text or "Not scored" in text
    assert document.page_count >= 1
    document.close()
