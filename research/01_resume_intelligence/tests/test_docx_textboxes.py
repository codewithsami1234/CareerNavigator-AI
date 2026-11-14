"""DOCX text boxes and letter-spaced headings.

Fixtures are synthetic and generated in a temporary folder. They do not contain
a real person's resume.
"""
import sample_data as sd
from extractors.section_extractor import SectionExtractor, normalize_heading
from parsers import parse_document
from pipeline import analyze_document, analyze_resume
from schemas import PARSE_OK, STATUS_SUCCESS


_SENTENCE = "I have used these tools on several projects and enjoy learning new methods."


class TestLetterSpacing:
    def test_stylized_declaration_matches_the_canonical_section(self):
        assert normalize_heading("Decl a r a tion") == "declaration"
        assert normalize_heading("S K I L L S") == "skills"
        assert normalize_heading("C a r e e r Objective") == "career objective"
        assert normalize_heading("Education & Qualifications") == "education and qualifications"
        hit = SectionExtractor().detect_heading("Decl a r a tion")
        assert hit is not None and hit[0] == "declaration"

    def test_ordinary_sentences_are_not_headings(self):
        extractor = SectionExtractor()
        assert extractor.detect_heading(_SENTENCE) is None
        assert extractor.detect_heading("Built a thing") is None
        assert extractor.detect_heading("I am a student of education") is None
        text = f"Riley Chen\n{_SENTENCE}\nSkills\nPython, SQL, Git, Docker\n"
        names = [section.name for section in extractor.extract(text)]
        assert names == ["header", "skills"]
        header = extractor.extract(text)[0]
        assert "enjoy learning" in header.content


class TestDocxTextBoxes:
    def test_floating_boxes_keep_heading_order_and_drop_fallback_duplicates(self, tmp_path):
        parsed = parse_document(sd.write_resume_with_text_boxes(tmp_path / "boxes.docx"))
        assert parsed.status == PARSE_OK, parsed.errors
        text = parsed.text
        assert text.index("riley.chen@example.com") < text.index("Career Objective")
        assert text.index("Career Objective") < text.index("careful student")
        assert text.index("careful student") < text.index("Skills")
        assert text.index("Skills") < text.index("Python, SQL, Git, Docker, and Linux")
        assert text.index("Python, SQL, Git, Docker, and Linux") < text.index("Languages | Python, SQL")
        assert text.index("Tools | Git, Docker") < text.index("Education")
        assert text.index("Education") < text.index("Example University")
        assert text.index("Example University") < text.index(_SENTENCE)
        assert text.index(_SENTENCE) < text.index("Course and Certificates")
        assert text.index("Course and Certificates") < text.index("Academic Interest")
        assert text.index("Academic Interest") < text.index("Decl a r a tion")
        assert text.index("Decl a r a tion") < text.index("synthetic resume is accurate")
        assert text.count("Career Objective") == 1
        assert text.count("Skills") == 1
        assert text.count("Decl a r a tion") == 1
        assert text.count("Weekly lab report") == 2
        assert any("text boxes" in warning for warning in parsed.warnings)
        assert not any("not extracted" in warning for warning in parsed.warnings)

    def test_plain_docx_does_not_warn_about_text_boxes(self, tmp_path):
        parsed = parse_document(sd.write_docx(tmp_path / "plain.docx", sd.FULL_RESUME))
        assert parsed.status == PARSE_OK
        assert not any("text box" in warning.lower() for warning in parsed.warnings)

    def test_inline_textbox_stays_between_neighbouring_runs(self, tmp_path):
        parsed = parse_document(sd.write_inline_textbox_resume(tmp_path / "inline.docx"))
        assert parsed.status == PARSE_OK, parsed.errors
        text = parsed.text
        assert text.index("Before heading") < text.index("Experience") < text.index("after heading")
        assert text.index("Experience") < text.index("Backend Developer")
        assert text.index("Backend Developer") < text.index("Tools | Python, Docker")
        assert text.index("Tools | Python, Docker") < text.index("Education")

    def test_negative_anchor_is_emitted_before_the_host_paragraph(self, tmp_path):
        parsed = parse_document(sd.write_textbox_above_paragraph(tmp_path / "above.docx"))
        assert parsed.status == PARSE_OK, parsed.errors
        text = parsed.text
        assert text.index("riley.chen@example.com") < text.index("Skills")
        assert text.index("Skills") < text.index("Python, SQL, Git, Docker, and Linux")


class TestDocxTextBoxPipeline:
    def test_textbox_resume_detects_sections_without_moving_the_sentence(self, tmp_path):
        path = sd.write_resume_with_text_boxes(tmp_path / "boxes.docx")
        analysis = analyze_resume(path)
        assert analysis.status == STATUS_SUCCESS, analysis.errors
        assert analysis.source_format == "docx"
        names = [section.name for section in analysis.sections]
        assert names[:3] == ["header", "summary", "skills"]
        assert "education" in names and "courses" in names
        assert "interests" in names and "declaration" in names
        assert names.index("skills") < names.index("education") < names.index("courses")
        assert names.index("courses") < names.index("interests") < names.index("declaration")

        header = next(section for section in analysis.sections if section.name == "header")
        summary = next(section for section in analysis.sections if section.name == "summary")
        education = next(section for section in analysis.sections if section.name == "education")
        declaration = next(section for section in analysis.sections if section.name == "declaration")
        assert "riley.chen@example.com" in header.content
        assert "riley.chen@example.com" not in summary.content
        assert "careful student" in summary.content
        assert "Example University" in education.content
        assert _SENTENCE in education.content
        assert all(section.heading != _SENTENCE for section in analysis.sections)
        assert "synthetic resume is accurate" in declaration.content
        assert analysis.education[0].degree == "BS"
        assert analysis.education[0].institution == "Example University"
        assert {"Python", "SQL", "Git", "Docker", "Linux"} <= {skill.name for skill in analysis.skills}
        assert any("text boxes" in warning for warning in analysis.warnings)

        phase2 = analyze_document(path, ocr=True)
        assert phase2.status == STATUS_SUCCESS
        assert phase2.text_provenance[0].method == "native_docx"
        assert [section.name for section in phase2.sections] == names
