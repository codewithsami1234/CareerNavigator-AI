"""Link-label evidence, new concept skills, and the Excel category move.

Synthetic text only.
"""
import pytest

from extractors.skill_extractor import SkillExtractor, load_taxonomy
from pipeline import analyze_text
from schemas import Section
from utils.links import is_link_line, is_profile_label_line


@pytest.fixture(scope="module")
def ex():
    return SkillExtractor()


def _skills(ex, **sections):
    found = ex.extract([
        Section(name=name, heading=name.title(), start_line=0, end_line=0, content=text)
        for name, text in sections.items()
    ])
    return {skill.name: skill for skill in found}


class TestLinkLabelsAreNotEvidence:
    def test_link_line_detection(self):
        assert is_link_line("GitHub: github.com/demo-dev/app")
        assert is_link_line("- GitHub: https://github.com/demo-dev/app")
        assert is_link_line("Live Demo: demo.vercel.app/    GitHub: github.com/demo-dev/app")
        assert not is_link_line("Built CI with GitHub Actions: github.com/demo-dev/app")
        assert not is_link_line("GitHub")
        assert not is_link_line("Used Git and GitHub for code review")

    def test_project_link_label_alone_gives_no_github_skill(self, ex):
        found = _skills(ex, projects="Weather App | Python\n- Fetches forecasts\nGitHub: github.com/demo-dev/weather")
        assert "GitHub" not in found
        assert found["Python"].evidence_type == "used"

    def test_listed_github_stays_mentioned_with_one_mention(self, ex):
        found = _skills(
            ex,
            skills="Git & GitHub, VS Code",
            projects="App One | Python\nGitHub: github.com/demo-dev/one\n\nApp Two | Python\nGitHub: github.com/demo-dev/two",
        )
        github = found["GitHub"]
        assert github.evidence_type == "mentioned"
        assert github.mention_count == 1
        assert [e.section for e in github.evidence] == ["skills"]

    def test_header_profile_label_row_is_not_evidence(self, ex):
        assert is_profile_label_line("LinkedIn | GitHub | LeetCode | X (Twitter)")
        assert is_profile_label_line("LinkedIn  •  GitHub")
        assert not is_profile_label_line("GitHub")
        assert not is_profile_label_line("GitHub Actions and Docker enthusiast")
        found = _skills(ex, header="Jane Roe\nPython Developer\nLinkedIn | GitHub | LeetCode | X (Twitter)",
                        skills="Git & GitHub")
        assert [e.section for e in found["GitHub"].evidence] == ["skills"]
        assert found["Python"].evidence[0].section == "header"

    def test_real_github_use_is_still_used(self, ex):
        found = _skills(ex, projects="Team Site | React\n- Used GitHub pull requests for code review")
        assert found["GitHub"].evidence_type == "used"
        assert found["GitHub"].evidence[0].text == "- Used GitHub pull requests for code review"

    def test_pipeline_keeps_repository_url_in_project_links(self):
        a = analyze_text(
            "Jane Roe\njane@example.com\n\nSkills\nPython, Git & GitHub\n\n"
            "Projects\nWeather App | Python\n- Fetches forecasts from a public API\n"
            "GitHub: github.com/demo-dev/weather\n"
        )
        assert a.projects[0].links == ["github.com/demo-dev/weather"]
        github = next(s for s in a.skills if s.name == "GitHub")
        assert github.evidence_type == "mentioned" and github.mention_count == 1


class TestConceptSkills:
    def test_oop_forms(self, ex):
        for text in ("C++, OOP", "Object-Oriented Programming", "object oriented programming in Java", "OOPs concepts"):
            assert "Object-Oriented Programming" in _skills(ex, skills=text), text

    def test_oop_is_case_sensitive(self, ex):
        assert "Object-Oriented Programming" not in _skills(ex, summary="Oops, a typo. I loop over lists.")

    def test_oop_in_project_stack_is_used(self, ex):
        found = _skills(ex, projects="Library Management System | C++, OOP\n- Console app")
        assert found["Object-Oriented Programming"].evidence_type == "used"

    def test_vision_transformer_forms(self, ex):
        found = _skills(ex, projects="Image Classifier | Python, Vision Transformer (ViT), Deep Learning")
        assert found["Vision Transformers"].evidence_type == "used"
        assert set(found["Vision Transformers"].matched_as) <= {"Vision Transformer", "ViT"}
        assert "Transformers" not in found
        listed = _skills(ex, skills="Vision Transformers (ViT), PyTorch")
        assert "Vision Transformers" in listed and "Transformers" not in listed

    def test_vit_needs_exact_case(self, ex):
        assert "Vision Transformers" not in _skills(ex, summary="Vit and vigour; a VITAL project.")

    def test_categories_follow_existing_design(self):
        ex = SkillExtractor()
        assert ex.categories["Object-Oriented Programming"] == "Programming Languages"
        assert ex.categories["Vision Transformers"] == "Computer Vision"


class TestExcelCategory:
    def test_excel_moved_with_same_name_and_matching(self, ex):
        assert ex.categories["Microsoft Excel"] == "Office and Productivity"
        assert ex.previous_categories["Microsoft Excel"] == ["Data Science"]
        found = _skills(ex, experience="- Built Excel dashboards with pivot tables")
        assert found["Microsoft Excel"].category == "Office and Productivity"
        assert found["Microsoft Excel"].evidence_type == "used"
        assert "Microsoft Excel" not in _skills(ex, summary="I excel at teamwork")

    def test_word_excel_powerpoint_share_a_category(self, ex):
        found = _skills(ex, skills="Microsoft Word, Excel, PowerPoint")
        assert {found[n].category for n in ("Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint")} == {
            "Office and Productivity"}

    def test_previous_categories_must_be_strings(self):
        data = load_taxonomy()
        data["categories"]["Office and Productivity"][0]["previous_categories"] = "Data Science"
        with pytest.raises(ValueError, match="previous_categories"):
            SkillExtractor(taxonomy=data)
