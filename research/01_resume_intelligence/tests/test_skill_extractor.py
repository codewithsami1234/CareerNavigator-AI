"""Skill extraction: aliases, boundaries, ambiguity, dedup, evidence, taxonomy independence."""
import json
from dataclasses import asdict

import pytest

from extractors.skill_extractor import SkillExtractor, load_taxonomy, validate_taxonomy
from schemas import Section


@pytest.fixture(scope="module")
def ex():
    return SkillExtractor()


def names(ex, text, section="skills"):
    return set(ex.find_in_text(text, section))


def sec(name, content):
    return Section(name=name, heading=name.title(), start_line=0, end_line=0, content=content)


# ------------------------------------------------------------------ taxonomy
class TestTaxonomy:
    def test_default_taxonomy_is_valid(self):
        assert validate_taxonomy(load_taxonomy()) == []

    def test_required_categories_exist(self):
        cats = set(load_taxonomy()["categories"])
        required = {"Programming Languages", "Frontend and Web Development", "Backend Development",
                    "Databases", "AI and Machine Learning", "Data Science", "Computer Vision", "NLP",
                    "Cloud and DevOps", "Cybersecurity", "Development Tools"}
        assert required <= cats

    def test_taxonomy_is_independent_of_source_code(self, tmp_path):
        custom = {"categories": {"Custom": [{"name": "Zig", "aliases": ["ziglang"]}]}}
        f = tmp_path / "tax.json"
        f.write_text(json.dumps(custom))
        custom_ex = SkillExtractor(taxonomy_path=f)
        assert names(custom_ex, "Skills: ziglang") == {"Zig"}
        assert names(custom_ex, "Skills: Python") == set()      # default skills are not hard-coded

    def test_duplicate_skill_names_rejected(self):
        bad = {"categories": {"A": [{"name": "X"}], "B": [{"name": "x"}]}}
        assert validate_taxonomy(bad)
        with pytest.raises(ValueError):
            SkillExtractor(taxonomy=bad)

    def test_conflicting_alias_rejected(self):
        bad = {"categories": {"A": [{"name": "One", "aliases": ["same"]}, {"name": "Two", "aliases": ["same"]}]}}
        assert any("same" in p for p in validate_taxonomy(bad))


# ------------------------------------------------------------- alias handling
class TestAliases:
    @pytest.mark.parametrize("text,expected", [
        ("js", "JavaScript"), ("sklearn", "scikit-learn"), ("scikit learn", "scikit-learn"),
        ("node.js", "Node.js"), ("NodeJS", "Node.js"), ("k8s", "Kubernetes"),
        ("postgres", "PostgreSQL"), ("Amazon Web Services", "AWS"), ("reactjs", "React"),
        ("html5", "HTML"), ("css3", "CSS"), ("Webflow", "Webflow"),
        ("golang", "Go"), ("cpp", "C++"), ("csharp", "C#"), ("natural language processing", "NLP"),
        ("tensor flow", "TensorFlow"), ("vscode", "VS Code"), ("ci/cd", "CI/CD"),
    ])
    def test_alias_maps_to_canonical_name(self, ex, text, expected):
        assert expected in names(ex, f"Skills: {text}")

    def test_case_insensitive(self, ex):
        assert names(ex, "PYTHON, javascript, DoCkEr") == {"Python", "JavaScript", "Docker"}

    def test_hyphen_and_space_variants(self, ex):
        assert "Machine Learning" in names(ex, "machine-learning and Machine Learning")

    def test_dotnet_names(self, ex):
        assert names(ex, "Experience with ASP.NET Core and C#", "experience") == {"ASP.NET", "C#"}

    def test_cpp_and_csharp_do_not_trigger_c(self, ex):
        assert names(ex, "I wrote code in C++ and C# daily", "experience") == {"C++", "C#"}


# -------------------------------------------------------- false-positive guards
class TestFalsePositives:
    @pytest.mark.parametrize("text", [
        "Pythonic style and monkeypatching", "scalability matters", "javelin throwing and javanese food",
        "I went to a gitar concert", "Mongoose and expressway", "The ship was swift and rusty",
    ])
    def test_substrings_do_not_match(self, ex, text):
        assert names(ex, text, "summary") == set()

    def test_java_is_not_javascript_and_vice_versa(self, ex):
        assert names(ex, "Java only", "summary") == {"Java"}
        assert names(ex, "JavaScript only", "summary") == {"JavaScript"}

    def test_java_script_with_space_is_javascript_only(self, ex):
        assert names(ex, "Wrote Java Script widgets", "experience") == {"JavaScript"}

    def test_mysql_postgresql_nosql_do_not_imply_sql(self, ex):
        assert names(ex, "MySQL", "summary") == {"MySQL"}
        assert names(ex, "PostgreSQL", "summary") == {"PostgreSQL"}
        assert names(ex, "NoSQL", "summary") == {"NoSQL"}

    def test_typescript_is_not_javascript(self, ex):
        assert names(ex, "TypeScript", "summary") == {"TypeScript"}

    def test_react_native_is_not_react(self, ex):
        assert names(ex, "Built apps in React Native", "experience") == {"React Native"}

    def test_node_js_suffix_is_not_javascript(self, ex):
        assert names(ex, "Node.js and React.js", "skills") == {"Node.js", "React"}

    def test_emails_and_urls_are_ignored(self, ex):
        text = "Reach me at python.dev@example.com or github.com/docker-lover and https://git.example.com/react"
        assert names(ex, text, "summary") == set()

    def test_contact_section_is_not_scanned(self, ex):
        res = ex.extract([sec("contact", "GitHub: github.com/x\nPython Street 5")])
        assert res == []

    def test_header_contact_lines_skipped_but_tagline_scanned(self, ex):
        res = ex.extract([sec("header", "Alex Morgan\nPython Developer\nalex@example.com | github.com/alex")])
        assert [s.name for s in res] == ["Python"]


# --------------------------------------------------------- ambiguous handling
class TestAmbiguity:
    def test_py_alone_is_not_python(self, ex):
        assert names(ex, "Skills: py, sql", "skills") == {"SQL"}

    def test_py_with_context_is_python(self, ex):
        assert "Python" in names(ex, "Wrote py scripts that use pandas", "experience")

    def test_py_context_on_adjacent_line(self, ex):
        assert "Python" in names(ex, "Used Django for the web layer\nWrote py helpers", "experience")

    def test_go_in_sentence_is_not_the_language(self, ex):
        assert "Go" not in names(ex, "Led the Go to market plan for a product", "experience")

    def test_go_as_list_item_in_skills_is_the_language(self, ex):
        assert "Go" in names(ex, "Languages: Python, Go, SQL", "skills")

    def test_go_with_cue_in_experience(self, ex):
        assert "Go" in names(ex, "Built a gRPC service in Go", "experience")

    def test_golang_always_matches(self, ex):
        assert "Go" in names(ex, "golang", "summary")

    def test_go_is_case_sensitive(self, ex):
        assert "Go" not in names(ex, "Skills: python, go, sql", "skills")

    def test_r_language(self, ex):
        assert "R" in names(ex, "Python, R, SQL", "skills")
        assert "R" not in names(ex, "Worked in R&D and plan B", "experience")
        assert "R" in names(ex, "Analysis in R with ggplot2", "experience")

    def test_c_language(self, ex):
        assert "C" in names(ex, "C, C++, Java", "skills")
        assert "C" not in names(ex, "Chose Option C for the layout", "experience")

    def test_swift_needs_context(self, ex):
        assert "Swift" not in names(ex, "A swift response to every ticket", "experience")
        assert "Swift" in names(ex, "Built iOS apps in Swift", "experience")

    def test_excel_verb_vs_tool(self, ex):
        assert "Microsoft Excel" not in names(ex, "I excel at teamwork", "summary")
        assert "Microsoft Excel" in names(ex, "Built Excel pivot tables", "experience")

    def test_ml_abbreviation_needs_context(self, ex):
        assert "Machine Learning" not in names(ex, "Added 5 mL of solution", "experience")
        assert "Machine Learning" in names(ex, "Built ML models for churn", "experience")

    def test_ai_is_case_sensitive(self, ex):
        assert "Artificial Intelligence" in names(ex, "Interested in AI", "summary")
        assert "Artificial Intelligence" not in names(ex, "ai", "summary")


# --------------------------------------------------------------------- dedupe
class TestDeduplication:
    def test_same_skill_many_spellings_on_one_line(self, ex):
        res = ex.extract([sec("skills", "Python, python3, PYTHON")])
        assert [s.name for s in res] == ["Python"]
        assert res[0].mention_count == 1

    def test_skill_in_several_lines_is_one_result_with_count(self, ex):
        res = ex.extract([sec("skills", "Python\nPython 3 basics\nAdvanced python")])
        assert len(res) == 1 and res[0].mention_count == 3

    def test_evidence_is_capped(self, ex):
        lines = "\n".join(f"Wrote python module {i}" for i in range(10))
        res = ex.extract([sec("experience", lines)])
        assert len(res[0].evidence) == 3 and res[0].mention_count == 10

    def test_matched_as_records_surface_forms(self, ex):
        res = ex.extract([sec("skills", "JS\nJavaScript")])
        assert set(res[0].matched_as) == {"JS", "JavaScript"}


# ------------------------------------------------------------------- evidence
class TestEvidence:
    def test_mentioned_in_skills_section_only(self, ex):
        r = ex.extract([sec("skills", "Python, Docker")])
        assert all(s.evidence_type == "mentioned" for s in r)
        assert r[0].evidence[0].section == "skills"

    def test_used_in_experience(self, ex):
        r = ex.extract([sec("experience", "- Deployed the API with Docker")])
        assert r[0].name == "Docker" and r[0].evidence_type == "used"
        assert r[0].evidence[0].section == "experience"
        assert "Deployed the API" in r[0].evidence[0].text

    def test_used_in_projects(self, ex):
        r = ex.extract([sec("projects", "Chatbot\n- Built with Flask")])
        assert r[0].evidence_type == "used"

    def test_mixed_evidence_is_used_and_lists_used_first(self, ex):
        r = ex.extract([sec("skills", "Django"), sec("experience", "Built services with Django")])
        assert len(r) == 1
        assert r[0].evidence_type == "used"
        assert r[0].evidence[0].evidence_type == "used"
        assert {e.section for e in r[0].evidence} == {"skills", "experience"}

    def test_summary_and_education_are_only_mentions(self, ex):
        r = ex.extract([sec("summary", "Passionate about Python"), sec("education", "Coursework: Java")])
        assert all(s.evidence_type == "mentioned" for s in r)

    def test_no_proficiency_is_inferred(self, ex):
        r = ex.extract([sec("skills", "Expert in Python")])
        keys = set(asdict(r[0]).keys())
        assert keys == {"name", "category", "evidence_type", "mention_count", "matched_as", "evidence"}
        assert not ({"proficiency", "level", "score", "years"} & keys)

    def test_categories_are_attached(self, ex):
        r = {s.name: s.category for s in ex.extract([sec("skills", "Python, MySQL, OpenCV, Docker, Nmap")])}
        assert r == {"Python": "Programming Languages", "MySQL": "Databases", "OpenCV": "Computer Vision",
                     "Docker": "Cloud and DevOps", "Nmap": "Cybersecurity"}

    def test_long_evidence_text_is_truncated(self, ex):
        r = ex.extract([sec("experience", "Used Python " + "x" * 500)])
        assert len(r[0].evidence[0].text) <= 200
