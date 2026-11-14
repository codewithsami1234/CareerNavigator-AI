# CareerNavigator AI — Resume intelligence (Phase 1 and Phase 2)

A local Python pipeline that reads a resume and returns structured JSON: contact details, sections, education, experience, projects, certifications, and normalised skills with evidence.

Phase 1 reads **text-based PDF, DOCX, and TXT** files with rules and two editable JSON files. Phase 2 adds **OpenCV preprocessing**, **Tesseract OCR** for images and scanned or mixed PDFs, and **readability diagnostics**. OCR text is passed into the same Phase 1 analysers (`analyze_text`). A local Streamlit page can also compare a job description, optionally read a public GitHub profile, and show a rule-based readiness estimate, recommendations, and a learning roadmap. There is no database and no paid API.

This repository does **not** train a model. OpenCV steps are classical image processing. Tesseract, when installed, uses its own pretrained OCR models. Those models are not trained or shipped here. Confidence scores are engine estimates, not proof that the text is correct. Nothing in this phase decides that a resume is ATS-compatible or ATS-incompatible.

---

## 1. Windows setup (PowerShell)

Python 3.10 or newer is required. This tree was run with **Python 3.12.10** on Windows 10.

```powershell
# From the CareerNavigator AI folder:
cd "research\01_resume_intelligence"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If scripts are disabled for this window:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` installs PyMuPDF, python-docx, pytest, OpenCV (`opencv-python-headless`), NumPy, and `pytesseract`. The Tesseract **program** is separate.

### Install Tesseract on Windows

1. Install the UB Mannheim build: <https://github.com/UB-Mannheim/tesseract/wiki>
2. The usual executable is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Either add that folder to `PATH`, or point the pipeline at the executable.

PowerShell, current window only:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Or pass it per command (this does not change the system permanently):

```powershell
python main.py path\to\resume.png --ocr --tesseract "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Resolution order when OCR runs: `--tesseract`, then the `TESSERACT_CMD` environment variable, then `tesseract` on `PATH`, then the two default Windows install paths above. A path you set explicitly is not replaced by a guess. If the program is missing, the result is status `failed` and an error that names the install step. The rest of the app keeps running.

Text PDFs, DOCX, and TXT do not need Tesseract.

---

## 2. Commands that exist

From `research\01_resume_intelligence`:

```powershell
# Phase 1 path. A scanned PDF stays needs_ocr and is not sent to OCR.
python main.py tests\fixtures\sample_resume_full.pdf

python main.py tests\fixtures\sample_resume_full.docx --output outputs\result.json
python main.py tests\fixtures\sample_resume_full.txt --json
python main.py path\to\resume.pdf --taxonomy path\to\my_taxonomy.json

# Phase 2 path. Native text is kept when a PDF page already has enough of it.
# Images and sparse or scanned pages are preprocessed and OCR'd.
python main.py tests\fixtures\sample_resume_full.pdf --ocr
python main.py path\to\scan.pdf --ocr
python main.py path\to\mixed.pdf --ocr
python main.py path\to\resume.png --ocr --json
python main.py path\to\resume.jpg --ocr --ocr-lang eng --output outputs\result.json
```

Exit code is `0` for status `success` or `partial`, and `1` otherwise (`failed`, `empty`, `needs_ocr`). `--tesseract` turns OCR on even if you omit `--ocr`.

### Tests and evaluation

```powershell
# From this folder, or from the repository root (both use the same suite):
python -m pytest
python -m pytest -m "not integration"     # everything that does not need the Tesseract program
python -m pytest -m integration           # skipped, with a reason, when Tesseract is absent
python -m pytest tests\test_taxonomy_evidence.py tests\test_resume_audit.py -q   # link-label, taxonomy, and audit regressions
python -m pytest tests\test_job_analysis.py -q   # job-description requirements and comparison

python evaluation\evaluate_skills.py
python evaluation\evaluate_phase2.py
python evaluation\evaluate_phase2.py --json outputs\phase2_eval.json

# Local web app. Stay in this folder so .streamlit\config.toml is used
# (localhost only, usage stats off, 10 MB upload cap).
python -m streamlit run web\app.py --server.address 127.0.0.1 --server.port 8501
```

The same launch from Windows CMD:

```bat
cd /d "C:\Users\DELL\Desktop\CareerNavigator AI\research\01_resume_intelligence"
python -m streamlit run web\app.py --server.address 127.0.0.1 --server.port 8501
```

Set these in that same CMD window before launching, only if you need them:

```bat
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
set GITHUB_TOKEN=your_token_here
```

`GITHUB_TOKEN` is optional. Public profiles can be read without it. Do not put a token in source code. The resume file is not sent to GitHub. The only network request is `https://api.github.com`, and only after you click **Read public GitHub profile**. Unauthenticated calls share GitHub's public rate limit. A limit, timeout, missing user, or network failure is shown on the page and does not discard the resume analysis. At most eight recently pushed public non-fork repositories are read. Successful API responses are cached in memory for 15 minutes. Repository code is not downloaded.

The page accepts PDF, DOCX, TXT, PNG, and JPEG. DOCX and TXT use Phase 1 (`analyze_resume`). A PDF uses Phase 1 unless **Use OCR for scanned PDFs and resume images** is checked, in which case Phase 2 (`analyze_document`) keeps native text and runs local Tesseract on sparse pages. PNG and JPEG always use Phase 2. With the checkbox off they return `needs_ocr` and are not read. Set `TESSERACT_CMD` the same way as the CLI before launching if you want that checkbox to work. The upload is written to a temporary folder and deleted when the pipeline returns. It is not stored in the project and it is not sent to an external service. Bytes that do not match the extension are rejected before that folder is created.

### Local API for a separate frontend

Streamlit remains a working page. `api/app.py` is the FastAPI process used by the React workspace in `frontend/`. It calls `web/service.py` and returns each object's existing `to_dict()`. It does not reimplement parsing, OCR, matching, scoring, GitHub reading, recommendations, or the roadmap. `career_report` also builds `guidance` from those objects. Guidance does not calculate a second score. `POST /api/report` copies that career report into a markdown file and CSV extracts. Request logs record the route, HTTP status, upload size, and file suffix. They do not record the file name, the resume text, the job text, the GitHub username, or a token.

From `research\01_resume_intelligence`:

```powershell
$env:CAREERNAV_CORS_ORIGINS = "http://localhost:5173"
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

On this Windows machine `python` may not be on `PATH`. `py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000` is the same command. The React workspace is `frontend/` at the repository root. Start it with `npm install` once, then `npm run dev`, and open `http://localhost:5173`. The root `README.md` is the hackathon setup guide.

`CAREERNAV_CORS_ORIGINS` is a comma-separated list. When it is unset, `http://localhost:5173` and `http://127.0.0.1:5173` are allowed. A `*` value is ignored and the fallback remains `http://localhost:5173` only. `http://localhost:3000` is a different origin and must be set explicitly. The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so the browser page and the API do not need a second origin during local development. Open the app at `http://localhost:5173`.

| Method and path | Request | HTTP 200 body |
|---|---|---|
| `POST /api/resume` | Multipart field `file` (PDF, DOCX, or TXT). Optional form field `use_ocr` (`true` or `false`, default false). OCR applies only to PDF | `ResumeAnalysis.to_dict()` |
| `POST /api/job` | JSON `{"text": "..."}`, or multipart field `file` | `JobAnalysis.to_dict()` |
| `POST /api/github` | JSON `{"username": "octocat"}`. A `https://github.com/username` profile URL is also accepted | `GitHubAnalysis.to_dict()` |
| `GET /api/health` | None | `{"status": "ok", "service": "CareerNavigator AI", "scoring": "rule-based readiness estimate"}` |
| `POST /api/career-report` | JSON `{"resume": <resume object>, "job": <job object or null>, "github": <github object or null>, "weekly_hours": 4}` | `CareerReport.to_dict()`, including `guidance` |
| `POST /api/report` | The career-report body, plus optional string labels `job_title`, `company`, and `target_career` (each at most 200 characters) | Markdown, the same report objects, and CSV extracts. The readiness number is copied |

Send the objects returned by the first three endpoints to the career-report endpoint. Do not upload the resume again and do not send resume text to another service. `weekly_hours` is optional. A positive whole number adds a planning note. Zero, a negative number, or omitting it leaves the note out.

Pipeline results stay HTTP 200. Their `status` can be `success`, `partial`, `failed`, `empty`, or `needs_ocr`. GitHub can also return `rate_limited`. A career report whose resume cannot be used keeps the existing readiness status `unavailable`. A missing file, a body that is not JSON, a career-report value that is not an analysis object, or a non-integer `weekly_hours` is HTTP 400. The wrong content type is HTTP 415. An unexpected exception is HTTP 500. Those three responses are only `{"status": "failed", "errors": ["..."]}` and do not include a traceback, a token, or the uploaded bytes. Unsupported, empty, and oversized files are HTTP 200 with `status: failed` because that is the existing analysis result. Uploads are still deleted when the service call returns.

Regenerate the synthetic fixtures if you need to:

```powershell
python tests\make_fixtures.py
```

---

## 3. Python API

```python
from pipeline import analyze_resume, analyze_text, analyze_document

# Phase 1. PDF, DOCX, TXT. Scans return status "needs_ocr" and no extracted fields.
result = analyze_resume(r"C:\path\to\resume.pdf")

# Already-extracted text, including text you obtained some other way.
result = analyze_text(some_text, source_format="ocr")

# Phase 2. Also accepts .png, .jpg, .jpeg.
# Native PDF text is preferred. Sparse pages and images go through OpenCV and Tesseract.
result = analyze_document(r"C:\path\to\scan.pdf", ocr=True, tesseract_cmd=None, ocr_lang="eng")
print(result.status, [s.name for s in result.skills])
print([(p.page_number, p.method, p.confidence) for p in result.text_provenance])
print(result.to_json())
```

`analyze_resume` and `analyze_document` do not raise for a bad file. Problems are `status`, `errors`, and `warnings`.

`analyze_resume` is unchanged: it never calls OCR. Use `analyze_document` or `main.py --ocr` for images and scans.

### Status values

| status | meaning |
|---|---|
| `success` | text recovered, at least one section found, and something was extracted |
| `partial` | text recovered, but headings were missing or little could be extracted |
| `needs_ocr` | Phase 1 path: the PDF has too little text. Phase 2 path: OCR was turned off for an image or a sparse page |
| `empty` | the file was read, or OCR ran, and there was no meaningful text. This is not an engine crash |
| `failed` | missing, unsupported, too large, corrupt, encrypted, or OCR could not run (for example Tesseract is missing) |

### Output contract

Phase 1 JSON keys are unchanged when you use `analyze_resume` or `analyze_text`: `text_provenance` and `quality_report` are omitted while they are empty. `schema_version` stays `"1.0"`.

Phase 2 adds, when present:

- `text_provenance`: page number (or null for DOCX/TXT), method (`native_pdf`, `native_docx`, `native_text`, `ocr`), character count, optional Tesseract confidence, and `suppressed_duplicate` when a repeated copy was left out of the analysis text.
- `quality_report`: `findings`, `measured`, and `limitations`. Each finding has `kind` of `measured`, `heuristic`, or `unsupported`.

Unknown entity fields stay `null` or empty lists. The file name is the name only, never the full path.

Skill evidence is unchanged: `used` means the skill was found in Experience or Projects; `mentioned` means it was found elsewhere. Proficiency is not inferred.

---

## 4. How Phase 2 connects to Phase 1

```
file -> validate (type, size, image dimensions, PDF page cap)
     -> native PDF / DOCX / TXT text when that text is enough
     -> else render the page, OpenCV preprocess, Tesseract
     -> one string, with page order and a method label per piece
     -> analyze_text  (same sections, skills, entities as Phase 1)
```

A PDF page keeps its native text when it has at least 400 letters/digits, or at least 80 and no large image. Otherwise the page is rendered at 200 DPI (see `config.py`) and OCR'd. A page that has both a short native fragment and an OCR reading is merged with a token-overlap rule: near-copies keep one side, and the dropped side stays in `text_provenance` with `suppressed_duplicate: true`. A later page that repeats the previous page (very high token overlap and similar length) is left out the same way.

Preprocessing builds a few candidates (grayscale, denoise + CLAHE, Otsu, adaptive threshold, and a deskewed grayscale when the skew estimate is large enough). A readability score (contrast, sharpness, ink coverage) drops candidates that look worse than grayscale. At most two candidates are sent to Tesseract. The higher text yield wins; confidence is only a weak tie-break. If the first result already has enough characters and confidence at least 70, the second OCR call is skipped. An engine failure is not retried. Empty OCR (`status` empty inside the OCR module, document status `empty` when nothing else was read) is not reported as a crash.

OpenCV does not "understand" a resume layout. Column order is used only when word positions show a clear vertical gap. Quality warnings are heuristics. The report always includes an explicit note that ATS compatibility is not assessed.

---

## 5. What Phase 1 still does

```
file -> validate (pdf, docx, txt, 10 MB) -> parser -> normalize_text
     -> section detection -> contact, education, experience, projects, certifications
     -> skill extraction from data/skills_taxonomy.json -> ResumeAnalysis
```

- PDF text is PyMuPDF. A blank line is inserted where a vertical gap looks like a paragraph break. A PDF with almost no text returns `needs_ocr` and **empty text**.
- On 3 or more pages, a short margin line that repeats is removed after page 1 (the first page keeps it). A clear two-column gutter is read left column, then right. Single-column pages keep PyMuPDF's original line order.
- DOCX uses python-docx: body paragraphs and tables in order, headers from every section (exact duplicates of body lines are not repeated), and footer text other than a bare page number. Text inside Word text boxes is included. A floating box anchored clearly below its paragraph is placed after that paragraph's own text; a negative offset is placed before it; an inline box stays in run order. The VML fallback of a shape is omitted when the modern drawing already has text. A warning remains because page-relative and overlapping shapes can still differ from the visual page.
- Hyperlink targets stored in the file (PDF link annotations, DOCX body hyperlinks) are collected separately from the text. They fill `contact.linkedin`, `github`, `leetcode`, and `twitter` (X) only when the visible text has a bare label such as `GitHub` and the stored target is profile-shaped. A label with no stored target stays `null`. A repository URL (`github.com/user/repo`) is never reported as the GitHub profile.
- Each project keeps the URLs written in it in `links`. Lines that only hold labelled URLs (`GitHub: ...`, `Live Demo: ...`) are left out of `description` and out of the project's `technologies`. When a project title has a pipe, the pipe separates the name from the stack, so `DSA — Data Structures | C++` keeps its full name.
- All-caps grouped headings ending in "PROJECTS" (`AI / ML PROJECTS`, `WEB PROJECTS`) start a projects section. Mixed-case sentences about projects do not.
- Certification lines keep balanced brackets (`(AI-900)`, `(React)`), drop `(July 2026)` style dates into `year`, and split `A — X (2025) | B — Y (2026)` into two entries. `kind` follows the section heading (Certifications or Courses). It is not guessed from the wording.
- A resume without an Experience section still gets `success` when other sections yield data. The pipeline keeps the finding `Section not detected: experience.` The page shows: "No professional experience section found. That's okay for freshers. Your projects and skills can still be evaluated." A heading that was found but not parsed stays a warning. Projects are not treated as employment.
- Sections come from `data/section_aliases.json`. Skills come from `data/skills_taxonomy.json` (222 skills, 13 categories). Aliases are word-boundary aware (`Java` does not match `JavaScript`). Ambiguous forms such as `Go`, `R`, and `C` need a cue or a skills-list item. The contact section and the human-languages section are not scanned for skills.

Edit the JSON files to add a skill or a heading alias. The loader rejects duplicate names and aliases. Do not put real people's resumes in the repository.

---

## 6. Results from this run

Machine: Windows 10, Python 3.12.10, PyMuPDF 1.28.2, python-docx 1.2.0, pytest 9.1.1, opencv-python-headless 5.0.0.93, NumPy 2.5.1, pytesseract 0.3.13. The Tesseract program is installed at `C:\Program Files\Tesseract-OCR`, so the OCR integration tests ran. Re-checked on 17 October 2026. See `PROJECT_AUDIT.md` in the repository root.

| | result |
|---|---|
| `python -m pytest` | **358 passed, 0 failed, 0 skipped**, 40.51 seconds, from the repository root. No unregistered-marker warning |
| OCR integration | `tests/test_ocr_integration.py`: 2 passed. Without Tesseract these 2 tests are skipped, with an install hint |
| Phase 1 tests | The original Phase 1 files (`test_parsers.py`, `test_pipeline.py`, `test_skill_extractor.py`) still pass. An earlier run of only those files was **185 passed**. This re-check added one CLI regression in `test_pipeline.py` |
| Skill evaluation | 50 synthetic snippets: TP 148, FP 1, FN 4, precision 0.993, recall 0.974, F1 0.983. Same labelled file as Phase 1. Not a real-resume accuracy figure |
| Readable fixtures | 3/3 (`pdf`, `docx`, `txt`) status `success` via `analyze_resume` |
| Expected non-success fixtures | 4/4 matched: image-only PDF `needs_ocr`, malformed PDF `failed`, malformed DOCX `failed`, encrypted PDF `failed` |
| Phase 2 on the text PDF | status `success`, 24 skills, same native-text path (OCR not required) |
| OCR fixture | **not run.** There is no OCR token-recall number from this machine |

Timed on this PC after a one-file warmup (`evaluation/evaluate_phase2.py`). These times will differ on another computer:

| document | route | status | seconds | skills |
|---|---|---|---|---|
| sample_resume_full.pdf | phase1 | success | 4.832 | 24 |
| sample_resume_full.docx | phase1 | success | 0.717 | 24 |
| sample_resume_full.txt | phase1 | success | 0.159 | 24 |
| image_only_scan_like.pdf | phase1 | needs_ocr | 0.011 | 0 |
| malformed.pdf | phase1 | failed | 0.002 | 0 |
| malformed.docx | phase1 | failed | 0.001 | 0 |
| encrypted.pdf | phase1 | failed | 0.097 | 0 |
| sample_resume_full.pdf | phase2 | success | 0.230 | 24 |

Peak tracemalloc for those timed calls: **16.05 MB**. The three `failed` rows are the corrupt and encrypted fixtures. They are supposed to fail. Timings are from the 17 October 2026 re-check and will differ on another run.

The 50-snippet skill set was written with the extractor. It is a regression check. It is not precision on real resumes. Entity extraction (education, jobs, projects) is covered by tests and has no accuracy percentage. OCR accuracy on real scans was **not** measured here.

---

## 7. Limits and troubleshooting

- **Tesseract missing:** `analyze_document` on an image or a scan returns `failed` and an install message. `analyze_resume` on a scan still returns `needs_ocr` and does not try OCR.
- **Empty OCR** means the engine ran and returned no readable words. **Failed OCR** means it did not run or it raised. Those are different.
- **Low confidence** is reported and is not treated as correctness.
- **Layouts.** Multi-column order runs only when a gutter is obvious. Sidebars and heavy templates can still come out in the wrong order. DOCX text-box text is read, but a floating shape positioned against the page (rather than its anchor paragraph) can still be out of visual order. A warning is a hint, not a judgment.
- **Images.** PNG and JPEG only. Limits live in `config.py` (10 MB file, sides between 32 and 10000 pixels, 25 million pixels, 30 PDF pages). Low resolution, low contrast, skew, odd aspect ratio, a blank page, and a crowded page produce heuristic warnings.
- **PDF text inside images** is not read by the Phase 1 parser. Phase 2 reads a PDF image page only when that page's native text is below the threshold above. DOCX text boxes are read, with the layout limit above. A heading that shares a table cell with other text stays on that cell's line.
- **English heuristics.** Names, degrees, and job lines depend on common layouts. Only taxonomy skills are found. Implied skills are not. `OOP` and `ViT` are matched only in that exact case, so the word `vit` in other text is ignored.
- **Link lines are not skill evidence.** A line such as `GitHub: github.com/...` or `Live Demo: ...` is skipped by the skill extractor. The URL is still kept in `ProjectEntry.links` and used for contact profiles. A header row made only of profile labels (`LinkedIn | GitHub | LeetCode`) is skipped too. GitHub is still found when it is listed as a skill or written in a sentence.
- **Category moves keep the old name.** Microsoft Excel moved from Data Science to Office and Productivity. Its taxonomy entry lists `"previous_categories": ["Data Science"]` (available as `SkillExtractor.previous_categories`), so older outputs can still be mapped. The skill name is unchanged.
- **Not inferred:** proficiency, years per skill, or sensitive attributes.
- **Job descriptions.** `analyze_job` reads pasted text or a PDF, DOCX, or TXT file. Priority is required or preferred only from a heading or from explicit words; otherwise it is unspecified. Comparison outcomes are matched, related, missing, or indeterminate. Related means a listed alternative in a small group (PyTorch, TensorFlow, Keras, and scikit-learn, or Docker and Kubernetes) and is not a match. Stated phrases such as React hooks, functional programming, REST API, testing, and build automation can be requirements. An explicit "A or B" requirement is one item and is satisfied by evidence of either name. `A/B` and `A, B, or C` are the same kind of alternative list. `A and B` stays two requirements. When Redux, Flux, and state management are stated as alternatives, including separate repeats of those names, they are one requirement and either accepted name satisfies it once. Redux and Flux without alternative wording stay separate. React and React hooks stay separate. A skill match keeps the resume line and whether it was used or mentioned. Proficiency is not inferred. A line such as "3 years of professional web development experience, including 2 years with React" keeps the React skill and two experience durations. The skill text is the skill name. A React project can support that skill and does not prove the years. Years of experience are compared only from explicit resume dates. Project text does not prove professional employment. Vague wording and missing dates stay unverified, and an unverified duration is not marked satisfied or failed. A higher degree is not treated as satisfying a lower one. School diplomas are not classified. Dated jobs are added together, so overlapping jobs can inflate the total. The comparison report itself has no score. `career_report` can add a separate rule-based readiness estimate when required items can be scored. Preferred items and unverified experience are shown and left out of that denominator. The summary states the denominator. The weights are unchanged: a matched required item contributes 1 and a related or missing required item contributes 0. The estimate is not a validated hiring prediction and not an ATS score. A posting that does not label any item required or preferred leaves those skills unspecified. They are still compared. A missing unspecified skill is recommended and can appear on the roadmap, and it does not create a numeric estimate. The summary says the denominator is 0 because nothing was labeled required. Recommendations are not repeated for the same alternative requirement, and they still say not to add a skill or a length of employment until the evidence exists. When the gaps are present, roadmap order is JavaScript, functional programming, TypeScript, React hooks, one state-management option, REST API, testing, build automation, and CI/CD, then Docker, Linux, and Bash. A skill already shown on the resume is not added again and is not treated as proof of proficiency. The Streamlit page shows the comparison groups, that estimate, recommendations, and the roadmap.
- **No ATS label.** Do not describe a warning as an ATS pass or fail.

If a text PDF is wrongly sent to OCR, lower `NATIVE_PAGE_SUFFICIENT_CHARS` only after looking at the page's character count in a debugger. Prefer fixing the PDF text layer over tuning blind.

---

## 8. Project structure

```
research/01_resume_intelligence/
  main.py                     CLI (Phase 1 by default, --ocr for Phase 2)
  pipeline.py                 analyze_resume, analyze_text, analyze_document, analyze_job, compare, career_report
  schemas.py, config.py       models, thresholds
  job_analysis/               job-description parser, requirements, matcher
  github_analysis/            public GitHub API client; tests use a fake transport
  assessment/                 readiness rubric, recommendations, roadmap, prerequisite map
  errors.py                   TesseractUnavailable, DocumentReadError
  parsers/                    pdf, docx, txt; pdf_layout.py for columns and margins
  vision/                     image load, OpenCV preprocess, quality findings
  ocr/tesseract_ocr.py        Tesseract location, one-image OCR, strategy choice
  extraction/                 merge native + OCR text; unified document entry
  extractors/                 sections, skills, entities (Phase 1)
  utils/text_cleaner.py
  data/                       skills_taxonomy.json, section_aliases.json, job_section_aliases.json
  evaluation/                 evaluate_skills.py, evaluate_phase2.py, labelled_examples.json
  web/                        local Streamlit app; service.py calls the pipeline
  api/                        optional FastAPI process; app.py calls web.service
  tests/                      Phase 1 tests plus vision, layout, extraction, OCR integration, web, API
```

Job comparison reports matched, related, missing, and indeterminate requirements. The comparison object itself does not contain an employability or ATS score. `career_report` adds a separate rule-based estimate, recommendations, and a prerequisite-ordered roadmap. The local Streamlit page can run all of those. Embeddings, OpenAI, LangChain, and LangGraph are not implemented. No model is trained here.

Re-checked on 19 October 2026.

From the repository root:

`python -m pytest --tb=line -q --override-ini="addopts="` — **424 passed, 0 failed, 0 skipped, in 55.02s**.

From `research\01_resume_intelligence`:

`python -m compileall -q web pipeline.py assessment github_analysis job_analysis api config.py` — exit 0.

`python -m pytest research/01_resume_intelligence/tests/test_api.py --tb=short --override-ini="addopts="` — **14 passed in 1.28s**.

`python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py -v --override-ini="addopts="` — **2 passed in 6.88s**. Tesseract was installed, so these tests ran. They skip, with an install hint, when the program is absent. The passing OCR tests use a synthetic rendered page. Accuracy on real photographed scans was not measured.

No ruff, mypy, flake8, or pylint configuration is present, so no separate lint or type command was run.

The page flow, including the unlabeled Front-End Developer posting, was exercised with Streamlit AppTest. This task did not open a browser. A manual browser check of that same Webflow posting was reported by the project owner before this task: JavaScript, HTML, and CSS matched, Webflow was missing with unspecified priority, there was no numeric estimate, the denominator was 0, and Webflow was the only recommendation and roadmap milestone. The 17 October browser check in `PROJECT_AUDIT.md` covered the empty page and a narrow viewport. It did not drive the operating-system file picker.

The Streamlit page still calls `web/service.py`, which calls `pipeline.py`. The HTTP API does the same. The React workspace in `frontend` calls that API. `PROJECT_AUDIT.md` is an earlier audit; where it disagrees with this file, this file is the current description. The request contract is in the API section above.

---

## 9. Keeping private resumes out of git

`.gitignore` ignores virtual environments, caches, `outputs/`, secrets, `datasets/` (except its README), and `*.pdf` / `*.docx` / `*.doc` except the synthetic fixtures. Keep real resumes in `private_resumes\` or outside the repo. Do not paste them into tests.
