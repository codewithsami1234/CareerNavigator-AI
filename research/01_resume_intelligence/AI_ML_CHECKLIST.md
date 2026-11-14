# AI/ML implementation checklist

Internal audit of `research/01_resume_intelligence`. The README describes the same behavior.

The notes dated 19 October 2026 are a historical snapshot. The React workspace is now connected to the FastAPI process, DOCX text boxes are read, and PNG and JPEG uploads go through `analyze_document` when the API or the page accepts them. No later pass trained a model or added embeddings.

No model was trained. The pipeline is rule-based. OpenCV preprocesses images, and Tesseract performs OCR when it is installed. Readiness is a fixed rubric, not a hiring prediction and not an ATS score.

No real-resume or real-scan accuracy figure is claimed. The 50-snippet skill check (precision 0.993, recall 0.974, F1 0.983) and the synthetic OCR token recall of 1.000 are regression checks on labelled fixtures. They are not measured accuracy on real resumes or photographed scans.

## Implemented and tested

- PDF, DOCX, and TXT parsing, including empty, malformed, password-protected, unsupported, and oversized files.
- Contact, section, skill, education, project, certification, and employment extraction.
- OpenCV preprocessing and optional Tesseract OCR, including per-page native text versus OCR and provenance.
- Document-quality and uncertainty reporting.
- A missing Experience section stays the pipeline finding `Section not detected: experience.`, not an error. The page shows a fresher info notice instead of that finding. A heading that was found but not parsed stays a warning.
- Temporary upload cleanup and privacy checks already covered by the web and robustness tests.
- Job-description parsing, required versus preferred status, and promotional-section skipping.
- Exact, related, missing, and indeterminate comparison. Related is limited to the PyTorch/TensorFlow/Keras/scikit-learn group and the Docker/Kubernetes group.
- Phrase requirements such as React hooks, functional programming, REST API, state management, testing, and build automation.
- Explicit `A or B`, `A/B`, `A, B, or C`, and `or similar` groups. Evidence of one accepted name satisfies that one requirement. `satisfied_by` records which name matched. Repeated Redux, Flux, and state-management alternatives are one requirement. React and React hooks stay separate.
- Webflow is a frontend skill. HTML5 and CSS3 stay aliases of HTML and CSS.
- A posting with no required or preferred heading leaves skills unspecified. Missing unspecified skills are compared, recommended, and placed on the roadmap. They are not scored and are not relabeled required.
- Experience-duration requirements, including a named-skill duration on the same line as a skill. The skill text is the skill name. Project text is not professional employment. No dates stay unverified and are not marked satisfied or failed.
- Public GitHub reading through `api.github.com` only. A token is optional (`GITHUB_TOKEN` or the `token` argument) and is redacted from errors. Tests use a fake transport.
- Evidence-based readiness estimate, only when a job comparison has required items that can be scored.
- Skill-gap recommendations and a prerequisite-ordered roadmap from the same comparison. No course URLs or measured durations.
- `career_report` runs comparison, readiness, recommendations, and the roadmap. Resume-only analysis still works. A GitHub failure does not discard the resume.
- The Streamlit page accepts an optional GitHub username or profile URL, shows the comparison groups, the rule-based estimate and its criteria, recommendations, and the ordered roadmap. Weekly hours are an optional planning note. The fresher notice is unchanged.

## Checked on 19 October 2026

- `python -m compileall -q web pipeline.py assessment github_analysis job_analysis api config.py` from `research\01_resume_intelligence`: exit 0.
- `python -m pytest --tb=line -q --override-ini="addopts="` from the repository root: 424 passed, 0 failed, 0 skipped, in 55.02s.
- `python -m pytest research/01_resume_intelligence/tests/test_api.py --tb=short --override-ini="addopts="`: 14 passed in 1.28s.
- `python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py -v --override-ini="addopts="`: 2 passed in 6.88s. Tesseract was installed for this run.
- No lint or type-check configuration is present.
- Streamlit AppTest covered the fresher notice, a job comparison, the estimate, recommendations, the roadmap, an invalid GitHub URL, a mocked successful profile, and the unlabeled Webflow posting (matched JavaScript, HTML, and CSS; missing unspecified Webflow; no numeric estimate; denominator 0; Webflow is the only recommendation and roadmap milestone).
- This task did not open a browser. A manual browser check of that Webflow posting was reported by the project owner before this task and is separate from the AppTest result above. The 17 October browser check in `PROJECT_AUDIT.md` did not drive the operating-system file picker.

## Implemented but only partially structured

- Achievements are detected as section text. There is no separate achievement entity list.

## Not claimed

- Embeddings, OpenAI, LangChain, LangGraph, and any trained classifier.
- ATS compatibility or a validated employability prediction.
- Proficiency, ownership, or employment inferred from GitHub stars, forks, commits, or language percentages.
- A connected React application. The local Streamlit page still works. An optional FastAPI process in `api/app.py` exposes the four existing service calls for a later frontend. That React app has not been connected or tested.

## Known limits

- Generic dated jobs can overlap and are not de-duplicated. Two overlapping six-year jobs are added, so they can meet a 10-year requirement. The overlap warning is still shown. A master's degree does not satisfy a bachelor's requirement. An unlabeled line such as "3 years with React", with only a React project and no dated employment, stays unverified, stays out of the readiness denominator, and still produces an experience recommendation.
- Different year numbers joined by "or" on one line stay one indeterminate experience item. "3 years of experience, including 2 years with React" stays two durations.
- An alternative group is formed from `or`, `or similar`, `/`, or a comma list that ends in `or`. Names outside that pattern stay separate requirements.
- GitHub reads at most eight recently pushed public non-fork repositories. The in-memory cache lasts 900 seconds and stores successful responses only.
- Preferred requirements, unspecified requirements, and unverified experience are reported and left out of the readiness denominator. If the posting labels nothing required, the summary says no numeric estimate is available and the denominator is 0. Related skills contribute no credit. A matched required item contributes 1 and a related or missing required item contributes 0. GitHub observations do not change the number. Repository counts, stars, and push dates are not proficiency.
- Prerequisite links and the frontend sequence live in `assessment/prerequisites.py`. Functional programming is placed with the JavaScript foundation when that gap exists. A resume mention is not treated as proof of proficiency.
- A weekly hour budget adds a planning note only. No milestone is given a duration.
