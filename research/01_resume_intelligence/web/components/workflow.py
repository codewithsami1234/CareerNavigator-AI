"""Interactive sections. Widget order on the dashboard matches the existing workflow tests."""
from __future__ import annotations

import streamlit as st

import config
from web import service
from web.components.cards import render_overview_metrics
from web.components.charts import outcome_chart, skill_category_chart
from web.components.tables import requirement_lines
from web.service import analyze_job_input, analyze_upload, compare_with_resume
from web.ui import report_export
from web.ui.formatters import file_size_label
from web.ui.session_state import remember_analysis, reset_session, stored_weekly_hours, weekly_hours_key
from web.ui.validators import resume_limit_caption
from web.view_model import (
    certification_lines, comparison_groups, contact_fields, detected_section_names, display_warnings,
    education_entries, experience_entries, experience_tab_notice, extracted_preview, github_profile_lines,
    github_repository_lines, github_skill_lines, has_structured_result, job_feedback, missing_contact_labels,
    project_entries, readiness_lines, recommendation_lines, roadmap_lines, skill_rows, status_notice,
)

INTRO = (
    "CareerNavigator AI reads a resume on this computer and shows the contact details, "
    "sections, skills, education, and experience returned by the local pipeline. "
    "A job description is compared on this computer. "
    "An optional public GitHub profile is the only network request, and the resume is not sent. "
    "A job-specific readiness figure is a rule-based estimate, not a validated hiring prediction and not an ATS score."
)


def show_level(level: str, message: str) -> None:
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)


def show_lines(lines) -> None:
    for line in lines:
        st.text(line)


def _empty(message: str) -> None:
    st.caption(message)


def render_upload_controls() -> None:
    generation = st.session_state["upload_generation"]
    with st.container(border=True):
        st.markdown("<p class='cn-section'>Resume file</p>", unsafe_allow_html=True)
        st.caption(resume_limit_caption())
        uploaded = st.file_uploader(
            "Resume",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
            key=f"resume-{generation}",
        )
        if uploaded is not None:
            kind = uploaded.type or "file"
            st.caption(f"Selected: {uploaded.name} · {file_size_label(int(uploaded.size))} · {kind}")
        with st.expander("OCR for scanned documents"):
            use_ocr = st.checkbox("Use OCR for scanned PDFs and resume images", key="use_ocr")
            st.caption(
                "Leave this off for a normal PDF, DOCX, or TXT file. "
                "Turn it on for a scanned PDF or a PNG or JPEG photograph: Phase 2 keeps selectable PDF text and runs local Tesseract on sparse pages and images. "
                "OpenCV prepares the page before Tesseract. A low confidence figure is a warning, not proof the words are correct. "
                "DOCX and TXT always stay on Phase 1. An image with OCR off returns needs_ocr and is not read. "
                "Set TESSERACT_CMD, or install Tesseract on PATH, before launching."
            )
        analyze_clicked = st.button("Analyze resume", type="primary")
        st.button("New upload", on_click=reset_session)
        st.caption("New upload replaces the file and clears the stored resume, job, GitHub read, and readiness.")
    if analyze_clicked:
        if uploaded is None:
            st.error("Choose a PDF, DOCX, TXT, PNG, or JPEG resume first.")
        else:
            with st.spinner("Reading the resume on this computer..."):
                analysis = analyze_upload(uploaded.name, uploaded.getvalue(), use_ocr=bool(use_ocr))
                st.session_state["analysis"] = analysis
                st.session_state["job_analysis"] = None
                st.session_state["job_report"] = None
                st.session_state["github_analysis"] = None
                st.session_state["career_report"] = None
                remember_analysis(analysis)


def render_analysis(analysis) -> None:
    level, message = status_notice(analysis)
    show_level(level, message)
    for warning_level, warning in display_warnings(analysis):
        show_level(warning_level, warning)
    if analysis.quality_report is not None:
        for finding in analysis.quality_report.findings:
            st.caption(f"{finding.severity}: {finding.message} ({finding.kind})")
    if not has_structured_result(analysis):
        if analysis.status == "needs_ocr":
            if analysis.source_format == "image":
                st.caption("OCR was not run. Turn on the checkbox above so local Tesseract can read this image.")
            else:
                st.caption("Phase 1 did not call OCR. The checkbox above uses the Phase 2 reader for this PDF.")
        return

    st.subheader(analysis.file_name or "Resume")
    render_overview_metrics(analysis)
    sections = detected_section_names(analysis)
    if sections:
        st.caption("Detected sections: " + ", ".join(sections))
    else:
        st.caption("No section headings were detected.")
    st.caption(
        "“Used” means the skill was found in Experience or Projects. "
        "“Mentioned” means it was found elsewhere. Proficiency is not inferred."
    )
    if analysis.text_provenance:
        bits = []
        for item in analysis.text_provenance:
            where = f"page {item.page_number}" if item.page_number else "document"
            confidence = ""
            if item.confidence is not None:
                confidence = f", Tesseract estimate {item.confidence:.0f} (not proof the text is correct)"
            duplicate = ", duplicate left out of the analysis" if item.suppressed_duplicate else ""
            bits.append(f"{where}: {item.method} ({item.char_count} characters{confidence}{duplicate})")
        st.caption("Text source — " + "; ".join(bits))

    contact_tab, skills_tab, education_tab, experience_tab = st.tabs(
        ["Contact", "Skills", "Education", "Experience"]
    )
    with contact_tab:
        fields = contact_fields(analysis)
        if fields:
            for label, value in fields:
                st.text(f"{label}: {value}")
        else:
            _empty("No contact fields were returned.")
        missing = missing_contact_labels(analysis)
        if missing:
            st.caption("Not found: " + ", ".join(missing) + ".")
    with skills_tab:
        rows = skill_rows(analysis)
        if not rows:
            _empty("No skills were returned.")
        else:
            for name, category, evidence, mentions in rows:
                st.text(f"{name} · {category} · {evidence} · {mentions} mention(s)")
        skill_category_chart(analysis)
    with education_tab:
        _render_groups(education_entries(analysis))
    with experience_tab:
        experience_rows = experience_entries(analysis)
        notice = experience_tab_notice(analysis)
        if experience_rows:
            _render_groups(experience_rows)
        elif notice:
            st.caption(notice)
        else:
            _render_groups(experience_rows)

    projects = project_entries(analysis)
    certifications = certification_lines(analysis)
    with st.expander("Projects and certifications"):
        if not projects and not certifications:
            _empty("No projects or certifications were returned.")
        for lines in projects:
            for line in lines:
                st.text(line)
            st.divider()
        for line in certifications:
            st.text(line)

    preview = extracted_preview(analysis)
    with st.expander("Extracted text"):
        st.caption(
            "Rebuilt from the sections the pipeline returned. "
            "This is not a second copy of the original file, and it is not a completeness check."
        )
        if preview:
            st.text(preview)
        else:
            _empty("No section text was returned.")


def _render_groups(groups) -> None:
    if not groups:
        _empty("Nothing was returned for this section.")
        return
    for lines in groups:
        for line in lines:
            st.text(line)
        st.divider()


def render_job_result(job, report) -> None:
    level, message = job_feedback(job, report)
    show_level(level, message)
    for warning in report.warnings:
        st.caption(warning)
    if report.matches:
        st.caption("“Used” and “mentioned” describe where a matched skill was found. Proficiency is not inferred.")
        for outcome, heading, rows in comparison_groups(report):
            tone = {
                "matched": "cn-ok",
                "related": "cn-violet",
                "missing": "cn-bad",
                "indeterminate": "cn-neutral",
            }.get(outcome, "cn-neutral")
            st.markdown(f"<p class='cn-group {tone}'>{heading}</p>", unsafe_allow_html=True)
            if not rows:
                _empty("None.")
                continue
            for row in rows:
                for line in row.display_lines():
                    st.text(line)
                st.divider()
        outcome_chart(report)
    if job.requirements:
        st.markdown("**Extracted requirements**")
        st.caption("These lines are the requirements the parser returned. They are not a second score.")
        show_lines(requirement_lines(job))


def render_job(analysis) -> None:
    st.subheader("Job description")
    st.write(
        "Paste a posting or upload a PDF, DOCX, or TXT file. "
        "The comparison runs on this computer and is not sent anywhere. "
        "Related skills are listed separately and are not matches. "
        "OCR is not run on job descriptions. "
        "Automatic collection from job boards is not available."
    )
    generation = st.session_state["upload_generation"]
    pasted = st.text_area(
        "Pasted job description",
        height=180,
        key=f"job-text-{generation}",
        placeholder="Requirements\n- Python",
    )
    uploaded = st.file_uploader(
        "Job description file",
        type=["pdf", "docx", "txt"],
        key=f"job-file-{generation}",
    )
    st.caption(
        "If you choose a file, that file is read and the pasted text is not. "
        "The file is stored in a temporary folder and deleted after reading."
    )
    if st.button("Compare with resume"):
        with st.spinner("Reading the job description on this computer..."):
            if uploaded is not None:
                job = analyze_job_input(filename=uploaded.name, data=uploaded.getvalue())
            else:
                job = analyze_job_input(text=pasted or "")
            st.session_state["job_analysis"] = job
            st.session_state["job_report"] = compare_with_resume(analysis, job)
            st.session_state["career_report"] = None
    job = st.session_state.get("job_analysis")
    report = st.session_state.get("job_report")
    if job is not None and report is not None:
        render_job_result(job, report)


def _repository_extra(repository) -> None:
    if repository.topics:
        st.text("Topics: " + ", ".join(repository.topics))
    else:
        st.text("Topics: none listed")
    if repository.readme_excerpt:
        st.text("README excerpt: " + repository.readme_excerpt)
    else:
        st.text("README excerpt: none returned")


def render_github() -> None:
    st.subheader("GitHub profile")
    st.write(
        "Optional. Enter a username or a public profile URL such as https://github.com/username. "
        "The app requests public data from https://api.github.com. The resume is not sent. "
        "No token is required. If GITHUB_TOKEN is set in the environment before launch, "
        "it is sent only to api.github.com and is not shown here. "
        "Repository code is not downloaded. "
        "At most "
        f"{config.GITHUB_MAX_REPOS} recently pushed public non-fork repositories are read. "
        "Commit quality is not scored, and an empty profile is not treated as a lack of ability."
    )
    generation = st.session_state["upload_generation"]
    login = st.text_input(
        "GitHub username or profile URL",
        key=f"github-login-{generation}",
        placeholder="octocat",
    )
    if st.button("Read public GitHub profile"):
        if not (login or "").strip():
            st.error("Enter a GitHub username or a public profile URL.")
        else:
            with st.spinner("Requesting public data from api.github.com..."):
                st.session_state["github_analysis"] = service.read_github_profile(login.strip())
                st.session_state["career_report"] = None
    github = st.session_state.get("github_analysis")
    if github is None:
        st.caption("No GitHub profile has been requested. Resume and job analysis do not need one.")
        return
    if github.status == "rate_limited":
        st.warning(github.reason or "GitHub rate limit was reached.")
    elif github.status != "success":
        st.error(github.reason or "The GitHub profile could not be read.")
    else:
        st.info(
            "Public GitHub data was read. It is separate from resume evidence "
            "and it is not a measure of professional ability."
        )
    for warning in github.warnings:
        st.caption(warning)
    for limitation in github.limitations:
        st.caption(limitation)
    show_lines(github_profile_lines(github))
    if not github.repositories:
        st.caption(
            "No public non-fork repositories were returned for display. "
            "That does not mean the person has no technical ability."
        )
    for repository in github.repositories:
        with st.container(border=True):
            st.markdown(f"**{repository.name}**")
            show_lines(github_repository_lines(repository))
            _repository_extra(repository)
            for warning in repository.warnings:
                st.caption(warning)
    show_lines(github_skill_lines(github))


def build_career(analysis, weekly: int | None):
    report = service.build_career_report(
        analysis,
        st.session_state.get("job_analysis"),
        st.session_state.get("github_analysis"),
        weekly_hours=weekly,
    )
    st.session_state["career_report"] = report
    return report


def render_career(analysis, *, show_hours: bool = True):
    st.subheader("Readiness, recommendations, and roadmap")
    st.caption(
        "Calculated on this computer from the stored resume and, when you have compared one, "
        "the job description. GitHub is included only after a profile read, and those observations "
        "do not change the estimate. Leave weekly hours at 0 to skip a time budget. "
        "A budget does not assign a duration to a milestone and is not a guarantee."
    )
    if show_hours:
        hours = st.number_input(
            "Optional weekly study hours",
            min_value=0,
            max_value=80,
            value=0,
            step=1,
            key=weekly_hours_key(),
        )
        weekly = int(hours) if int(hours) > 0 else None
    else:
        weekly = stored_weekly_hours()
    report = build_career(analysis, weekly)
    render_career_body(report)
    return report


def render_career_body(report) -> None:
    if report is None:
        _empty("Readiness was not calculated.")
        return
    readiness = report.readiness
    if readiness.estimate is None:
        st.info(readiness.summary)
    else:
        estimate = int(readiness.estimate)
        st.markdown(
            f"<div class='cn-ring-wrap' style='--p:{estimate}'><span>{estimate}</span></div>",
            unsafe_allow_html=True,
        )
        st.metric("Rule-based estimate", f"{estimate} / 100")
        st.caption(readiness.band)
        st.progress(min(max(estimate, 0), 100) / 100.0)
    show_lines(readiness_lines(readiness))
    st.markdown("**Recommendations**")
    recommendation_text = recommendation_lines(report.recommendations)
    if report.recommendations.status != "success":
        st.caption(recommendation_text[0])
    else:
        show_lines(recommendation_text)
    st.markdown("**Learning roadmap**")
    roadmap_text = roadmap_lines(report.roadmap)
    if report.roadmap.status != "success":
        st.caption(roadmap_text[0])
    else:
        show_lines(roadmap_text)
    if report.limitations:
        for note in report.limitations:
            st.caption(note)


def render_downloads() -> None:
    analysis = st.session_state.get("analysis")
    if analysis is None:
        return
    st.subheader("Download")
    st.caption("Files contain the stored pipeline objects only. Nothing new is scored at download time.")
    payload = report_export.report_json(
        analysis,
        st.session_state.get("job_analysis"),
        st.session_state.get("job_report"),
        st.session_state.get("github_analysis"),
        st.session_state.get("career_report"),
    )
    st.download_button(
        "Download JSON report",
        data=payload,
        file_name="careernavigator-report.json",
        mime="application/json",
        key="download-json",
    )
    skills = report_export.skills_csv(analysis)
    if skills:
        st.download_button(
            "Download skills CSV",
            data=skills,
            file_name="careernavigator-skills.csv",
            mime="text/csv",
            key="download-skills",
        )
    matches = report_export.comparison_csv(st.session_state.get("job_report"))
    if matches:
        st.download_button(
            "Download comparison CSV",
            data=matches,
            file_name="careernavigator-comparison.csv",
            mime="text/csv",
            key="download-comparison",
        )


def render_full_workflow() -> None:
    """Dashboard order. The first uploader, text area, text input, and number input stay stable."""
    render_upload_controls()
    analysis = st.session_state.get("analysis")
    if analysis is None:
        st.subheader("Job description")
        st.caption("Analyze a resume first. The comparison is shown under that result.")
        return
    render_analysis(analysis)
    render_job(analysis)
    if has_structured_result(analysis):
        render_github()
        render_career(analysis)
        render_downloads()
