"""Regression tests from an audit of a real student resume.

All data here is fictional (example names, example.com, demo handles). The
layout mirrors the audited file: Objective, Technical Skills, Education, 11
projects with "GitHub:" lines, 9 certifications, Achievements, no Experience,
and profile labels whose URLs exist only as stored hyperlinks.
"""
import sample_data as sd
from extractors.entity_extractor import extract_contact
from extractors.section_extractor import SectionExtractor
from parsers import parse_document
from pipeline import analyze_document, analyze_resume, analyze_text
from schemas import DocumentLink, STATUS_SUCCESS

AUDIT_RESUME = """\
JORDAN AVERY
AI / Machine Learning Enthusiast | Full Stack Developer
Springfield, Exampleland | 0300-0000000 | jordan.avery@example.com
LinkedIn | GitHub | LeetCode | X (Twitter)

OBJECTIVE

Aspiring AI/ML Engineer with a foundation in Python, Machine Learning, Deep Learning, and agentic workflows
using LangGraph, with Full Stack experience in HTML, CSS, JavaScript, React.js, Node.js, Express.js, MongoDB,
and JWT-based authentication. Seeking a role that uses data analysis with Python (Pandas, NumPy).

TECHNICAL SKILLS

Artificial Intelligence & Machine Learning
Machine Learning Fundamentals • Deep Learning Fundamentals • LangGraph (Agentic AI Workflows) •
Python for AI/ML — Pandas, NumPy
Programming & Development
Python • C++ • Java • JavaScript • HTML5 • CSS3 • React.js • Node.js • Express.js
Frameworks & Libraries
Tailwind CSS • Bootstrap 5 • Pygame
Databases & Security
MongoDB • JWT (Authentication & Authorization)
Tools & Platforms
Git & GitHub • VS Code • Postman • Chrome DevTools
Productivity & Office Tools
Microsoft Word • Excel • PowerPoint

EDUCATION

BS Information Technology (BS IT)
Example Graduate College, Springfield — Affiliated with Example University
2023 – 2027 | Currently in 7th Semester | CGPA: 3.50 / 4.00

PROJECTS

AI Chatbot using LangGraph | Python, LangGraph
• Conversational chatbot built with LangGraph to orchestrate multi-step agent workflows
GitHub: github.com/demo-dev/chatbot-langgraph/tree/main

Shooter Game | Python, Pygame
• 2D shooter game developed using Python and Pygame with real-time controls

GitHub: github.com/demo-dev/shooter-game

Library Management System | C++, OOP
• Console-based library system built with object-oriented programming principles
GitHub: github.com/demo-dev/library-system

DSA — Data Structures & Algorithms | C++
• Collection of solved problems reinforcing core CS fundamentals
GitHub: github.com/demo-dev/dsa

Authentication & Authorization System | Node.js, Express.js, MongoDB, JWT
• Secure login system with role-based access control
GitHub: github.com/demo-dev/auth-system

Puzzle Game | React.js, Tailwind CSS
• Interactive memory puzzle game with login and CRUD functionality
Live Demo: demo-dev.github.io/puzzle-game/ GitHub: github.com/demo-dev/puzzle-game

AI Image Generator | HTML, CSS, JavaScript
• Generates images from user prompts via API integration
GitHub: github.com/demo-dev/image-generator

Bohr Atomic Model | C++
• Graphics-based simulation of an atomic model
GitHub: github.com/demo-dev/bohr-model

Snake Game | C++
• Classic snake game with scoring and high-score tracking
GitHub: github.com/demo-dev/snake-game

Tic-Tac-Toe Game | HTML, CSS, JavaScript
• Browser-based game with win and draw detection
GitHub: github.com/demo-dev/tic-tac-toe

Flower Selling Website | HTML, CSS
• Responsive online store with a clean layout
GitHub: github.com/demo-dev/flower-site

CERTIFICATIONS

• Introduction to Web Development — Simplilearn (2025)
• UI/UX Designer — Simplilearn (2025)
• Frontend Developer (React) — HackerRank (2025)
• SQL — HackerRank (2026)
• Graphic Designing — DigiSkills
• Creative Writing — DigiSkills
• Microsoft Certified: Azure AI Fundamentals (AI-900) — GCT (July 2026)
• Artificial Intelligence using Python — DigiSkills (July 2026)

• Freelancing — DigiSkills (July 2026)

ACHIEVEMENTS

• Merit Scholarship recipient
Solved 150+ problems on LeetCode — leetcode.com/u/demo_dev
"""

STORED_LINKS = [
    DocumentLink(text="github.com/demo-dev/chatbot-langgraph/tree/main",
                 uri="https://github.com/demo-dev/chatbot-langgraph/tree/main", page_number=1),
    DocumentLink(text="X (Twitter)", uri="https://x.com/demo_dev", page_number=1),
    DocumentLink(text="LeetCode", uri="https://leetcode.com/u/demo_dev/", page_number=1),
    DocumentLink(text="GitHub", uri="https://github.com/demo-dev", page_number=1),
    DocumentLink(text="LinkedIn", uri="https://linkedin.com/in/demo-dev", page_number=1),
]

PROJECT_NAMES = [
    "AI Chatbot using LangGraph", "Shooter Game", "Library Management System",
    "DSA — Data Structures & Algorithms", "Authentication & Authorization System", "Puzzle Game",
    "AI Image Generator", "Bohr Atomic Model", "Snake Game", "Tic-Tac-Toe Game", "Flower Selling Website",
]


def _analysis(links=None):
    return analyze_text(AUDIT_RESUME, "text", links=links)


class TestSections:
    def test_objective_and_body_sections(self):
        a = _analysis()
        assert [s.name for s in a.sections] == [
            "header", "summary", "skills", "education", "projects", "certifications", "achievements"]
        assert next(s for s in a.sections if s.name == "summary").heading == "OBJECTIVE"

    def test_missing_experience_is_a_warning_not_an_error(self):
        a = _analysis()
        assert a.status == STATUS_SUCCESS
        assert a.errors == [] and a.experience == []
        assert "Section not detected: experience." in a.warnings
        assert not any("Experience section was found" in w for w in a.warnings)

    def test_grouped_all_caps_project_headings(self):
        text = (
            "Jordan Avery\njordan.avery@example.com\n\nTECHNICAL SKILLS\nPython, C++\n\n"
            "AI / ML PROJECTS\nChatbot | Python, LangGraph\n- Built a chatbot\n\n"
            "WEB PROJECTS\nPuzzle Game | React.js\n- Built a puzzle game\n\n"
            "OTHER PROJECTS (C++ / JAVA / PYTHON)\nSnake Game | C++\n- Built a snake game\n\n"
            "EDUCATION\nBS Computer Science, Example University (2019 - 2023)\n"
        )
        a = analyze_text(text)
        assert [s.name for s in a.sections] == [
            "header", "skills", "projects", "projects", "projects", "education"]
        assert [p.name for p in a.projects] == ["Chatbot", "Puzzle Game", "Snake Game"]
        assert {s.name: s.evidence_type for s in a.skills}["LangGraph"] == "used"

    def test_sentences_about_projects_are_not_headings(self):
        extractor = SectionExtractor()
        assert extractor.detect_heading("Completed several projects") is None
        assert extractor.detect_heading("I enjoy building web projects") is None
        assert extractor.detect_heading("- WEB PROJECTS") is None


class TestProjects:
    def test_all_eleven_projects_with_stack_description_and_links(self):
        projects = _analysis().projects
        assert [p.name for p in projects] == PROJECT_NAMES
        by_name = {p.name: p for p in projects}

        chatbot = by_name["AI Chatbot using LangGraph"]
        assert chatbot.description[0] == "Python, LangGraph"
        assert "LangGraph" in chatbot.description[1]
        assert {"Python", "LangGraph"} <= set(chatbot.technologies)
        assert chatbot.links == ["github.com/demo-dev/chatbot-langgraph/tree/main"]

        shooter = by_name["Shooter Game"]
        assert set(shooter.technologies) == {"Python", "Pygame"}
        assert shooter.links == ["github.com/demo-dev/shooter-game"]

        auth = by_name["Authentication & Authorization System"]
        assert set(auth.technologies) == {"Node.js", "Express.js", "MongoDB", "JWT"}

        puzzle = by_name["Puzzle Game"]
        assert puzzle.links == ["demo-dev.github.io/puzzle-game/", "github.com/demo-dev/puzzle-game"]
        assert set(puzzle.technologies) == {"React", "Tailwind CSS"}

        for project in projects:
            assert len(project.links) >= 1, project.name
            assert all("github.com" not in line for line in project.description), project.name
            assert "GitHub" not in project.technologies, project.name
            assert project.description and project.description[0], project.name

    def test_dash_without_pipe_still_splits_name_from_stack(self):
        a = analyze_text(
            "Jane Roe\njane@example.com\n\nProjects\nSmart Attendance System – Python, OpenCV\n"
            "- Built a face-recognition attendance tool\n\nSkills\nPython\n"
        )
        assert a.projects[0].name == "Smart Attendance System"
        assert a.projects[0].description[0] == "Python, OpenCV"


class TestCertifications:
    EXPECTED = [
        ("Introduction to Web Development", "Simplilearn", 2025),
        ("UI/UX Designer", "Simplilearn", 2025),
        ("Frontend Developer (React)", "HackerRank", 2025),
        ("SQL", "HackerRank", 2026),
        ("Graphic Designing", "DigiSkills", None),
        ("Creative Writing", "DigiSkills", None),
        ("Microsoft Certified: Azure AI Fundamentals (AI-900)", "GCT", 2026),
        ("Artificial Intelligence using Python", "DigiSkills", 2026),
        ("Freelancing", "DigiSkills", 2026),
    ]

    def test_all_nine_with_brackets_and_month_dates(self):
        certs = _analysis().certifications
        assert [(c.name, c.issuer, c.year) for c in certs] == self.EXPECTED
        assert {c.kind for c in certs} == {"certification"}

    def test_two_certificates_on_one_line(self):
        a = analyze_text(
            "Jane Roe\njane@example.com\n\nCertifications\n"
            "- SQL — HackerRank (2026) | Frontend Developer (React) — HackerRank (2025)\n"
            "- AWS Cloud Practitioner | Amazon Web Services\n"
        )
        assert [(c.name, c.issuer, c.year) for c in a.certifications] == [
            ("SQL", "HackerRank", 2026),
            ("Frontend Developer (React)", "HackerRank", 2025),
            ("AWS Cloud Practitioner", "Amazon Web Services", None),
        ]


class TestSkills:
    LISTED = {
        "Python", "C++", "Java", "JavaScript", "React", "Node.js", "Express.js", "MongoDB", "JWT",
        "LangGraph", "Pandas", "NumPy", "Tailwind CSS", "Bootstrap", "Pygame", "Git", "GitHub", "VS Code",
        "Postman", "Chrome DevTools", "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
    }

    def test_every_listed_technical_skill_is_detected_once(self):
        skills = _analysis().skills
        names = [s.name for s in skills]
        assert self.LISTED <= set(names), sorted(self.LISTED - set(names))
        assert len(names) == len(set(names))

    def test_repeats_across_sections_keep_evidence_and_used_vs_mentioned(self):
        skills = {s.name: s for s in _analysis().skills}
        langgraph = skills["LangGraph"]
        assert langgraph.evidence_type == "used"
        assert langgraph.evidence[0].evidence_type == "used"
        assert langgraph.evidence[0].section == "projects"
        assert {"summary", "projects"} <= {e.section for e in langgraph.evidence}
        # Title line, bullet, objective line, skills line: distinct lines, counted once each.
        assert langgraph.mention_count == 4
        assert skills["Pygame"].evidence_type == "used"
        for name in ("Java", "Chrome DevTools", "Microsoft Word", "Microsoft PowerPoint", "Bootstrap"):
            assert skills[name].evidence_type == "mentioned", name
            assert skills[name].mention_count == 1, name

    def test_word_needs_office_context(self):
        a = analyze_text(
            "Jane Roe\njane@example.com\n\nSkills\nWord Embeddings, NLP\n\n"
            "Projects\nNotes App | Python\n- Counts each Word in a document\n"
        )
        assert "Microsoft Word" not in {s.name for s in a.skills}


class TestContactLinks:
    def test_labels_without_urls_are_not_invented(self):
        c = _analysis().contact
        assert c.linkedin is None and c.github is None and c.twitter is None
        assert c.leetcode == "leetcode.com/u/demo_dev"

    def test_project_repository_is_not_the_github_profile(self):
        text = "Jane Roe\njane@example.com\n\nProjects\nApp | Python\nGitHub: github.com/jane-demo/app\n"
        assert analyze_text(text).contact.github is None

    def test_stored_profile_links_fill_label_only_header(self):
        c = _analysis(links=STORED_LINKS).contact
        assert c.linkedin == "https://linkedin.com/in/demo-dev"
        assert c.github == "https://github.com/demo-dev"
        assert c.twitter == "https://x.com/demo_dev"
        assert c.leetcode == "leetcode.com/u/demo_dev"

    def test_repository_link_alone_never_becomes_a_profile(self):
        links = [DocumentLink(text="GitHub", uri="https://github.com/demo-dev/app")]
        c = extract_contact("Jane Roe\nGitHub", [], links=links)
        assert c.github is None

    def test_visible_header_urls_keep_previous_behaviour(self):
        c = analyze_text(sd.FULL_RESUME).contact
        assert c.github == "github.com/alexmorgan-demo"
        assert c.linkedin == "linkedin.com/in/alexmorgan-demo"
        assert c.leetcode is None and c.twitter is None

    def test_visible_x_and_leetcode_urls(self):
        text = (
            "Jane Roe\njane@example.com | x.com/jane_demo | leetcode.com/jane-demo\n\n"
            "Skills\nPython, Docker, SQL and Git\n\nAchievements\n- Visited linux.com/x and x.com/i/flow\n"
        )
        c = analyze_text(text).contact
        assert c.twitter == "x.com/jane_demo"
        assert c.leetcode == "leetcode.com/jane-demo"


def _write_linked_pdf(path):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    header = ["Jordan Avery", "jordan.avery@example.com | 0300-0000000"]
    for line in header:
        page.insert_text((60, y), line, fontsize=10, fontname="helv")
        y += 14
    labels = [("LinkedIn", "https://linkedin.com/in/demo-dev"), ("GitHub", "https://github.com/demo-dev"),
              ("LeetCode", "https://leetcode.com/u/demo_dev/"), ("X (Twitter)", "https://x.com/demo_dev")]
    x = 60
    for label, uri in labels:
        page.insert_text((x, y), label, fontsize=10, fontname="helv")
        width = pymupdf.get_text_length(label, fontname="helv", fontsize=10)
        page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(x, y - 9, x + width, y + 2), "uri": uri})
        x += width + 20
    y += 24
    body = [
        "Skills", "Python, Docker, SQL, Git, Linux and Flask", "",
        "Projects", "Inventory App | Python, Flask", "- Built an inventory tracker",
        "GitHub: github.com/demo-dev/inventory-app", "",
        "Education", "BS Computer Science, Example University (2019 - 2023)",
    ]
    for line in body:
        if line:
            page.insert_text((60, y), line, fontsize=10, fontname="helv")
        y += 14
    doc.save(str(path))
    doc.close()
    return path


class TestStoredLinksEndToEnd:
    def test_pdf_link_annotations_are_read_without_changing_text(self, tmp_path):
        path = _write_linked_pdf(tmp_path / "linked.pdf")
        parsed = parse_document(path)
        assert "https://" not in parsed.text
        assert {link.uri for link in parsed.links} >= {"https://github.com/demo-dev", "https://x.com/demo_dev"}

        for analysis in (analyze_resume(path), analyze_document(path, ocr=False)):
            c = analysis.contact
            assert analysis.status == STATUS_SUCCESS, analysis.errors
            assert c.linkedin == "https://linkedin.com/in/demo-dev"
            assert c.github == "https://github.com/demo-dev"
            assert c.leetcode == "https://leetcode.com/u/demo_dev/"
            assert c.twitter == "https://x.com/demo_dev"
            assert analysis.projects[0].links == ["github.com/demo-dev/inventory-app"]

    def test_docx_hyperlink_targets_are_collected(self, tmp_path):
        import docx
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        document = docx.Document()
        document.add_paragraph("Jordan Avery")
        document.add_paragraph("jordan.avery@example.com")
        paragraph = document.add_paragraph()
        rid = paragraph.part.relate_to("https://github.com/demo-dev", RT.HYPERLINK, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), rid)
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "GitHub"
        run.append(text)
        link.append(run)
        paragraph._p.append(link)
        for line in ("Skills", "Python, Docker, SQL, Git, Linux and Flask",
                     "Education", "BS Computer Science, Example University (2019 - 2023)"):
            document.add_paragraph(line)
        path = tmp_path / "linked.docx"
        document.save(str(path))

        parsed = parse_document(path)
        assert [(link.text, link.uri) for link in parsed.links] == [("GitHub", "https://github.com/demo-dev")]
        assert analyze_resume(path).contact.github == "https://github.com/demo-dev"
