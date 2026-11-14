# CareerNavigator AI — Phase 1 and Phase 2 audit

Audit date: 17 October 2026
Workspace: `C:\Users\DELL\Desktop\CareerNavigator AI`
Environment: Windows 10, Python 3.12.10

Statuses: `PASS`, `PARTIAL`, `MISSING`, `BROKEN`, `NOT VERIFIED`.

Later notes in the root `README.md`, `docs/ARCHITECTURE.md`, and `research/01_resume_intelligence/README.md` supersede statements below that the React app is disconnected, that DOCX text boxes are unread, or that PNG and JPEG cannot be uploaded. Those three statements are no longer true.

## What is in this workspace

Phase 1 and Phase 2 are one local Python package, not two applications.

```
CareerNavigator AI/
  pytest.ini                          marker registration for repository-root runs
  datasets/README.md                  placeholder for later datasets (unused by these phases)
  experiments/README.md               placeholder for later experiments (unused by these phases)
  research/01_resume_intelligence/    the resume-intelligence package
```

There is no database, trained model, or paid API in this tree. The intelligence pipeline is rule-based. OpenCV preprocesses images. Tesseract, when installed, performs OCR with its own pretrained models; those models are not trained or shipped here. Job comparison reports matched, related, missing, and indeterminate requirements. `career_report` adds a separate readiness estimate, recommendations, and a learning roadmap. The comparison object itself has no employability or ATS score. Embeddings, OpenAI, LangChain, and LangGraph are not implemented. Sections written on 17 October 2026 describe that day's tree. Where they say a roadmap, a readiness estimate, or a web page is missing, the 19 October 2026 section at the end is the current statement.

Phase 2 does not replace Phase 1. `analyze_resume` still parses PDF, DOCX, and TXT and never calls OCR. `analyze_document` and `main.py --ocr` recover text (native, or OpenCV + Tesseract) and then call the same `analyze_text` function.

## Phase 1 checklist

| Feature | Status | Evidence |
|---|---|---|
| PDF text extraction (PyMuPDF), paragraph gaps, page cap | PASS | `parsers/pdf_parser.py`, `tests/test_parsers.py`, CLI on `sample_resume_full.pdf` returned success with 24 skills |
| Two-column order and repeated margin removal | PASS | `parsers/pdf_layout.py`, `tests/test_pdf_layout.py` (8 passed) |
| DOCX paragraphs, tables, headers, footer page numbers | PASS | `parsers/docx_parser.py`, parser and pipeline tests, CLI `--json` on the DOCX fixture |
| TXT including UTF-8 BOM and cp1252 | PASS | `parsers/text_parser.py`, `tests/test_parsers.py` |
| Text normalisation | PASS | `utils/text_cleaner.py`, cleaner tests |
| Section detection from `data/section_aliases.json` | PASS | `extractors/section_extractor.py`, heading-variation tests |
| Contact, education, experience, projects, certifications | PASS | `extractors/entity_extractor.py`, `TestFullResume`, CLI summary for Alex Morgan |
| Skill extraction, 215 skills, 11 categories | PASS | `data/skills_taxonomy.json` counted at 215 skills / 11 categories; `tests/test_skill_extractor.py` (66 passed) |
| Evidence type `used` vs `mentioned`; no proficiency inference | PASS | skill and pipeline tests |
| Validation: missing, empty, oversized, unsupported, encrypted, malformed | PASS | parser and pipeline tests; CLI on `malformed.pdf` returned `failed` |
| Image-only PDF stays `needs_ocr` and does not call OCR | PASS | `test_analyze_resume_does_not_call_ocr`; CLI without `--ocr` returned `NEEDS_OCR` |
| `analyze_resume` / `analyze_text` do not raise for bad input | PASS | pipeline tests |
| Phase 1 JSON omits `text_provenance` and `quality_report` | PASS | `schemas.ResumeAnalysis.to_dict`, `test_phase1_json_omits_phase2_fields` |
| Skill evaluation script | PASS | `evaluation/evaluate_skills.py`: 50 snippets, TP 148, FP 1, FN 4, precision 0.993, recall 0.974, F1 0.983. Synthetic regression only |
| CLI default path | PASS | `python main.py <pdf\|docx\|txt>` from `research\01_resume_intelligence` |

DOCX text boxes remain skipped, with a warning. That is the documented limit, not a missing file.

## Phase 2 checklist

| Feature | Status | Evidence |
|---|---|---|
| Image load and validation (PNG, JPEG, size, magic bytes) | PASS | `vision/image_io.py`, `tests/test_vision.py` |
| OpenCV preprocess (grayscale, denoise/CLAHE, threshold, deskew) and candidate cap | PASS | `vision/preprocess.py`, vision tests. No Tesseract required |
| Readability / quality report, including the explicit “ATS is not assessed” finding | PASS | `vision/quality.py`, native-PDF and fake-OCR tests |
| Page rule: keep native text at 400+ characters, or at 80+ with image fraction under 0.35 | PASS | `extraction/unified.py` `page_needs_ocr`, `test_page_needs_ocr_rules`. Text PDF is not sent to OCR |
| Native DOCX and TXT provenance | PASS | `test_docx_and_txt_provenance` |
| Merge native and OCR text; drop near-copies; drop a repeated next page | PASS | `extraction/text_merge.py`, duplicate tests |
| Hyphen repair only on OCR text | PASS | `test_hyphen_repair_does_not_touch_phase1_cleaner` |
| Recovered text goes through Phase 1 `analyze_text` | PASS | `pipeline.analyze_document`; fake OCR on a PNG produced skills, contact, and `method=ocr` |
| Mixed PDF keeps native page 1 and OCRs a sparse page 2 | PASS | `test_mixed_pdf_keeps_page_order` (OCR function patched; ordering is real) |
| Missing or bad Tesseract is `failed`, not a crash; empty OCR is `empty` | PASS | OCR failure tests, and a live CLI run on `image_only_scan_like.pdf --ocr` |
| Engine failure is not retried | PASS | `test_engine_failure_is_not_retried` |
| `evaluation/evaluate_phase2.py` fixture report | PASS | Readable fixtures 3/3 success, expected non-success 4/4, Phase 2 native PDF `success` with 24 skills. Peak tracemalloc 16.05 MB. OCR fixture on the synthetic page: `success`, token recall 1.000 (`python`, `django`, `docker`, `sql`, `flask`, `alex`). `image_only_scan_like.pdf` stays on the Phase 1 route and is still `needs_ocr` |
| Live Tesseract OCR on an image and on a scanned PDF | PASS | `python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py -v`: 2 passed in 7.38s. Tesseract 5.5.3 via `TESSERACT_CMD`. The scanned PDF is 64,510 bytes. That test checks recovered tokens and `analyze_document` skills |
| Real-scan OCR accuracy | NOT VERIFIED | The passing OCR tests use a synthetic rendered page. The project does not ship a real-scan benchmark |

The 400-character and 0.35 image-fraction cutoffs are written in `page_needs_ocr` rather than `config.py`. Behaviour matches the README and the tests. They were left as they are.

## Combined integration checklist

| Check | Status | Evidence |
|---|---|---|
| Phase 2 calls Phase 1 analysers and does not duplicate them | PASS | `analyze_document` → `extract_document` → `analyze_text` |
| Phase 1 entry point still refuses images and does not OCR scans | PASS | `parse_document` on PNG is `failed`; `analyze_resume` on a scan is `needs_ocr` |
| CLI chooses the path from `--ocr` / `--tesseract` | PASS | Summary title is `Phase 1` or `Phase 2` to match the path |
| Config and env handling | PASS | Thresholds in `config.py`. Tesseract resolution order is `--tesseract`, then `TESSERACT_CMD`, then `PATH`, then the two default Windows paths |
| Python 3.12 / Windows dependencies import | PASS | PyMuPDF 1.28.2, python-docx 1.2.0, pytest 9.1.1, opencv-python-headless 5.0.0.93, NumPy 2.5.1, pytesseract 0.3.13 |
| Secrets or live model APIs | PASS | None in this phase. Nothing was printed |
| Package imports when tests run from the repository root | PASS | `conftest.py` and root `pytest.ini` `pythonpath` |
| Logging | PASS | Failures are `status`, `errors`, and `warnings` on the result. The CLI prints them. There is no separate log file |

## Test results

### Before the fixes

Command: `python -m pytest` from `research\01_resume_intelligence`
**236 passed, 2 skipped**, about 16 seconds. No marker warning, because that folder’s `pytest.ini` already registers `integration`.

Command: `python -m pytest` from the repository root
**238 collected, 236 passed, 2 skipped, 1 warning.**
Warning: `PytestUnknownMarkWarning` for `pytest.mark.integration` in `tests/test_ocr_integration.py`. Pytest did not load the package `pytest.ini`.

Skipped both times, with the install hint, not a pass:

- `test_ocr_integration.py::TestTesseractIntegration::test_image_resume_reaches_the_phase1_pipeline`
- `test_ocr_integration.py::TestTesseractIntegration::test_scanned_pdf_uses_ocr`

Reason: Tesseract OCR is not installed. Checked `PATH`, `TESSERACT_CMD`, `C:\Program Files\Tesseract-OCR\tesseract.exe`, `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`, and `%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe`.

### After the fixes

Same two commands. **241 collected, 239 passed, 2 skipped, 0 warnings**, about 26 seconds. The two OCR integration tests were still skipped at that point because Tesseract was not installed.

### OCR integration re-check

Tesseract OCR 5.5.3 is installed and `TESSERACT_CMD` points at `C:\Program Files\Tesseract-OCR\tesseract.exe`.

The scanned-PDF fixture was 13.4 MB because `insert_image` decodes the PNG and a default `save` writes uncompressed RGB. `tests/test_ocr_integration.py` now saves that same 220 DPI page with `deflate` and `deflate_images`. The generated PDF is 64,510 bytes (0.062 MB). The 10 MB upload limit is unchanged.

Command: `python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py` from the repository root
**2 passed**, 0 failed, 0 skipped.

Command: `python -m pytest` from the repository root
**241 passed, 0 failed, 0 skipped**, 26.23 seconds.

### OCR recall re-check

`TESSERACT_CMD` was set to `C:\Program Files\Tesseract-OCR\tesseract.exe` for this run. `eng.traineddata` is in that install’s `tessdata` folder. No other Tesseract setting was required.

The evaluation already called `analyze_document` on a rendered PNG. Its three lines were 42 letters/digits, under `MIN_MEANINGFUL_CHARS` (50), so `analyze_text` returned `empty` before skills existed and token recall was 0. The fixture now includes the email and an experience line. The Phase 1 `needs_ocr` case for `image_only_scan_like.pdf` was left as it is.

The scanned-PDF helper already saved with `deflate` and `deflate_images`. Regenerating it produced 64,510 bytes (0.062 MB). `test_scanned_pdf_uses_ocr` still asserts that size against the 10 MB limit, and it now also checks that `analyze_document` returns skills.

Command: `python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py -v`
**2 passed**, 0 failed, 0 skipped, 7.38 seconds.

Command: `python -m pytest`
**241 passed, 0 failed, 0 skipped**, 24.91 seconds.

Command: `python research/01_resume_intelligence/evaluation/evaluate_phase2.py`
Exit 0. OCR fixture: **status success, token recall 1.000**, found `python`, `django`, `docker`, `sql`, `flask`, `alex`. Readable fixture success rate 1.000. Expected failed/`needs_ocr` match rate 1.000. Phase 2 native PDF status `success`.

| File | Collected | Result |
|---|---|---|
| `test_parsers.py` | 31 | passed |
| `test_pipeline.py` | 89 | passed (88 before, plus 1 new CLI test) |
| `test_skill_extractor.py` | 66 | passed |
| `test_pdf_layout.py` | 8 | passed |
| `test_vision.py` | 16 | passed |
| `test_phase2_extraction.py` | 27 | passed (25 before, plus 2 new tests) |
| `test_phase2_eval.py` | 2 | passed |
| `test_ocr_integration.py` | 2 | passed (previously skipped; see the re-check above) |

`python evaluation\evaluate_skills.py` and `python evaluation\evaluate_phase2.py` both exited 0. OCR token recall was not computed.

## Issues fixed

| Issue | What changed |
|---|---|
| Repository-root pytest did not register the `integration` marker | Added `pytest.ini` at the repository root with the marker, `testpaths`, and `pythonpath`. The package `pytest.ini` is unchanged for runs started inside the package |
| Phase 1 scan warning said OCR “will be added in Phase 2” even though Phase 2 exists | `parsers/pdf_parser.py` now tells the user to re-run with `--ocr` |
| Phase 2 kept that Phase 1 sentence when OCR failed or was turned off | `extraction/unified.py` drops the Phase 1 “no data extracted” / “would be needed” sentences on the document path. The real status and Tesseract error stay |
| `main.py --ocr` still printed a Phase 1 title | The summary title follows the path that ran |

Regression tests:

- `test_scanned_pdf_failure_drops_the_phase1_future_ocr_warning`
- `test_ocr_off_scan_uses_the_phase2_message`
- `test_ocr_flag_labels_phase2_when_tesseract_is_missing` (uses a missing `--tesseract` path, so it does not pretend a live engine ran)

README setup path `CareerNavigator-AI\...` did not match this folder. It now says to `cd "research\01_resume_intelligence"` from the repository root. The results table matches this re-check.

## Files changed

| File | Reason |
|---|---|
| `pytest.ini` | Register `integration` when pytest starts at the repository root |
| `research/01_resume_intelligence/parsers/pdf_parser.py` | Point the Phase 1 scan warning at the existing `--ocr` path |
| `research/01_resume_intelligence/extraction/unified.py` | Stop showing that Phase 1 sentence after the Phase 2 reader has already run |
| `research/01_resume_intelligence/main.py` | Label the CLI summary Phase 2 when `--ocr` or `--tesseract` is used |
| `research/01_resume_intelligence/tests/test_phase2_extraction.py` | Regression coverage for the warning |
| `research/01_resume_intelligence/tests/test_pipeline.py` | Regression coverage for the CLI title and warning |
| `research/01_resume_intelligence/README.md` | Correct the setup path and the numbers from this run |
| `PROJECT_AUDIT.md` | This report |
| `research/01_resume_intelligence/tests/test_ocr_integration.py` | Compress the synthetic scanned PDF so it stays under the 10 MB limit, require recovered skill tokens, and check that the scan reaches `analyze_document` |
| `research/01_resume_intelligence/evaluation/evaluate_phase2.py` | Render enough text for OCR output to pass the 50-character gate so token recall measures Phase 1 recovery |

No modules, fixtures, taxonomy files, or tests were deleted. The 10 MB limit in `config.py` is unchanged.

## Phase 3 — robustness and evaluation

Audit of the existing tree before these edits: Phase 1 and Phase 2 already covered empty text, missing contact and sections, many heading aliases, two-column layout, UTF-8 and cp1252 decoding, malformed and encrypted files on the Phase 1 path, oversized files in `validate_file`, unsupported extensions, and a missing Tesseract. Those tests were left in place. The 10 MB limit stayed at `config.MAX_FILE_SIZE_MB = 10`.

Gaps that inspection actually showed:

- A heading ending in a period (`Skills.`, `Experience.`) was not recognised, so the resume stayed one header block.
- An unlabelled `City, Region` location rejected accented letters (`São Paulo`).
- The evaluation printed skill scores, fixture rates, and OCR recall, but it did not list expected versus unexpected outcomes or a total processing time.

`TESSERACT_CMD` for this run: `C:\Program Files\Tesseract-OCR\tesseract.exe`.

Command: `python -m pytest research\01_resume_intelligence\tests\test_ocr_integration.py -v`
**2 passed**, 0 failed, 0 skipped, 6.81 seconds.

Command: `python -m pytest`
**253 passed, 0 failed, 0 skipped**, 25.37 seconds. Baseline before these tests was 241 passed. The 12 new tests are in `tests/test_robustness.py`.

Command: `python research\01_resume_intelligence\evaluation\evaluate_phase2.py`
Exit 0. Synthetic only.

| Measure | Result |
|---|---|
| Skill precision / recall / F1 | 0.993 / 0.974 / 0.983 (50 snippets, unchanged) |
| Readable-fixture success rate | 1.000 |
| Expected failed/`needs_ocr` match rate | 1.000 |
| Expected outcomes | 12 |
| Unexpected outcomes | 0 |
| OCR fixture | status `success`, token recall 1.000, tokens `python`, `django`, `docker`, `sql`, `flask`, `alex` |
| Processing time | 8.252 s total, slowest 4.100 s |
| Timed documents | 11 (success/partial 4, empty 2, failed 4, plus `needs_ocr` on the image-only PDF) |
| Peak tracemalloc | 16.05 MB |

Phase 1 on `image_only_scan_like.pdf` is still `needs_ocr`. Digit substitutions such as `Pyth0n` are still not rewritten into taxonomy skills. That is intentional.

### Phase 3 files

| File | Reason |
|---|---|
| `extractors/section_extractor.py` | Treat a trailing period as heading decoration |
| `extractors/entity_extractor.py` | Accept accented letters in an unlabelled `City, Region` location |
| `evaluation/evaluate_phase2.py` | Report success rate, skill P/R/F1, OCR token recall, processing time, and expected versus unexpected outcomes |
| `tests/test_phase2_eval.py` | Lock the new summary fields, including zero unexpected outcomes |
| `tests/test_robustness.py` | New cases listed below |
| `PROJECT_AUDIT.md` | This section |

Tests added in `test_robustness.py`:

- `test_period_terminated_headings_still_split_sections`
- `test_spaced_and_decorated_headings`
- `test_unicode_text_file_round_trip`
- `test_unknown_heading_stays_partial_and_invents_nothing`
- `test_whitespace_file_is_empty`
- `test_very_short_file_is_empty`
- `test_hyphen_breaks_are_rejoined_before_skill_extraction`
- `test_digit_substitutions_are_not_rewritten_into_skills`
- `test_oversized_file_fails_and_the_ten_megabyte_limit_stays`
- `test_unsupported_formats_fail`
- `test_encrypted_pdf_fails_on_the_phase2_path`
- `test_missing_and_malformed_files_do_not_raise`

## Remaining limitations

1. Live OCR is still only the clean synthetic PNG and the compressed one-page PDF. Token recall 1.000 is that page. Noisy, skewed, and photographed scans were not tested. The two integration tests still skip, with the install hint, when Tesseract is missing.

2. Skill F1 0.983, the fixture rates, and the expected/unexpected counts are synthetic. They are not real-world accuracy.

3. OCR confusions other than a hyphen at a line break (for example `Pyth0n`) are not corrected.

4. Documented limits that are still true: English layout heuristics, no proficiency or years-per-skill, no ATS pass/fail, DOCX text boxes unread, PNG/JPEG only, 10 MB upload limit, 30 PDF pages.

5. There is still no web interface, database, trained model, or job-matching phase. `datasets\` and `experiments\` only contain READMEs.

Phase 3 does not block a later phase that calls `analyze_text` or `analyze_document`. It does not make the pipeline validated on real resumes or real scans.

## Phase 4 — local web application

Baseline before this phase: `python -m pytest` — **253 passed, 0 failed, 0 skipped**, 25.53 seconds.

There was no web framework in the tree. The interface is Streamlit. It does not reimplement extraction.

| Upload | Entry point |
|---|---|
| DOCX, TXT | Phase 1 `analyze_resume`, even if the OCR checkbox is on |
| PDF, OCR checkbox off | Phase 1 `analyze_resume`. A scan returns `needs_ocr` and is not read |
| PDF, OCR checkbox on | Phase 2 `analyze_document`, which keeps native text and runs local Tesseract on sparse pages |

The page shows only fields the pipeline returned. Missing contact values stay missing. Skill evidence is `used` or `mentioned`. The success notice says the reading is not a verified fact. Uploads are written to a temporary directory and deleted when the call returns. Nothing is logged, stored in the project, or sent to an external service. `.streamlit/config.toml` binds `127.0.0.1`, turns off Streamlit usage stats, and caps the widget at 10 MB. `config.MAX_FILE_SIZE_MB` is still 10.

### Launch

From `research\01_resume_intelligence`, after `pip install -r requirements.txt` and, for scanned PDFs, the Tesseract setup already in the README:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
python -m streamlit run web\app.py --server.address 127.0.0.1 --server.port 8501
```

### Verification on 17 October 2026

Command: `python -m pytest`
**268 passed, 0 failed, 0 skipped**, 35.83 seconds. The 15 new tests are in `tests/test_web_app.py`.

The server was started and answered `http://127.0.0.1:8501` with HTTP 200. In the browser the page showed the title, the local-only introduction, the PDF/DOCX/TXT uploader, the 10 MB note, the OCR checkbox (unchecked), Analyze, and New upload. Analyze with no file showed “Choose a PDF, DOCX, or TXT resume first.” A 390px-wide viewport stacked the same controls without overlap. The browser file picker could not be driven from here, so the upload-and-extract path was run through Streamlit’s AppTest against the same `web/app.py` script: a synthetic TXT resume showed the email and Python; a blank file, a malformed PDF, an oversized file, a scan without OCR, and New upload were also checked.

### Phase 4 files

| File | Reason |
|---|---|
| `web/service.py` | Validate the upload and call Phase 1 or Phase 2 |
| `web/view_model.py` | Display rows from the analysis object, without filling blanks |
| `web/app.py` | Streamlit page |
| `web/__init__.py` | Package marker |
| `.streamlit/config.toml` | Localhost, no usage stats, 10 MB widget cap |
| `tests/test_web_app.py` | Service, view-model, and AppTest workflow |
| `requirements.txt` | `streamlit>=1.44` |
| `README.md` | Launch command and which entry point each file type uses |
| `PROJECT_AUDIT.md` | This section |

## Remaining limitations

1. Live OCR is still only the clean synthetic PNG and the compressed one-page PDF. Noisy, skewed, and photographed scans were not tested.

2. Skill F1 0.983 and the evaluation counts are synthetic. The web app does not add a real-world accuracy score.

3. OCR confusions other than a hyphen at a line break are not corrected. The page does not invent missing contact, education, or experience fields.

4. The browser check did not include choosing a file through the operating-system picker. That path was covered by AppTest, not by a hand-operated file dialog.

5. There is still no database, account system, or trained model. Job comparison, readiness, recommendations, and the roadmap now exist and are described in the 19 October 2026 section. DOCX text boxes stay unread. PNG and JPEG are not offered in the uploader. The production upload limit remains 10 MB.

## Current status — 19 October 2026

The sections above are the 17 October audit. This section records the later resume-intelligence work and the checks run on 19 October 2026.

The pipeline is still rule-based. OpenCV preprocesses page images. Tesseract performs OCR. No custom model is trained here. Embeddings, OpenAI, LangChain, and LangGraph are not in this package.

### Behavior locked by tests

| Case | Result |
|---|---|
| Two overlapping jobs, Jan 2018–Jan 2024 and Jan 2020–Jan 2026, against "10 years of experience" | The durations are added. The outcome is matched. The match note and the report warning both say the overlap was not removed. Duration logic was not changed |
| Master's degree on the resume against a bachelor's requirement | Missing. A different degree level is not a match. The policy was not changed |
| Heading-free "3 years with React" plus a React project and no dated employment | The years stay indeterminate, are not scored, and produce an unverified-experience recommendation. The React skill can still match from the project |
| Unlabeled Front-End Developer posting (JavaScript, HTML5, CSS3, Webflow) in Streamlit AppTest | JavaScript, HTML, and CSS match. Webflow is missing and unspecified. There is no numeric estimate and the denominator is 0. Webflow is the only recommendation and roadmap milestone |

### Commands and results

From the repository root:

`python -m pytest --tb=line -q --override-ini="addopts="`

**410 passed, 0 failed, 0 skipped, in 73.69s.**

From `research\01_resume_intelligence`:

`python -m compileall -q web pipeline.py assessment github_analysis job_analysis`

Exit 0.

`python -m pytest research/01_resume_intelligence/tests/test_ocr_integration.py -v --override-ini="addopts="`

**2 passed in 6.88s.** Tesseract was installed, so the integration tests ran. They still skip, with an install hint, when it is absent. Token recall on the synthetic page is not real-scan accuracy.

No ruff, mypy, flake8, or pylint configuration exists.

This task did not open a browser, start the Streamlit server, or run a deployment check. A manual browser pass of the unlabeled Webflow posting was reported by the project owner before this task. The AppTest above checks the same visible outcome. The 17 October browser note covered the empty page and a narrow viewport, and it did not drive the operating-system file picker.

### Frontend handoff

Taiba owns the frontend. This package does not contain a React application. The React app has not been connected to the API or tested against it. Streamlit still calls `web/service.py`, which calls `pipeline.py`. The same four functions are now available over HTTP from `api/app.py`.

Inputs the page already accepts:

| Input | Rule |
|---|---|
| Resume file | PDF, DOCX, or TXT. The OCR checkbox applies only to PDF |
| Job description | Pasted text, or a PDF, DOCX, or TXT upload. OCR is not run |
| GitHub | Optional username or profile URL. Only `https://api.github.com` is called. The resume is not sent |
| Weekly hours | Optional positive integer. It adds a planning note and does not set a milestone duration |

Functions a frontend can call without reimplementing extraction:

| Function | Returns |
|---|---|
| `web.service.analyze_upload(filename, data, use_ocr=False)` | `ResumeAnalysis` |
| `web.service.analyze_job_input(text="", filename=None, data=None)` | `JobAnalysis` |
| `web.service.read_github_profile(username_or_url)` | `GitHubAnalysis` |
| `web.service.build_career_report(resume, job=None, github=None, weekly_hours=None)` | `CareerReport` |

`pipeline.py` exposes the same work as `analyze_resume`, `analyze_document`, `analyze_text`, `analyze_job`, `compare`, `analyze_github`, and `career_report`. `compare` returns a `MatchReport` with counts and no score. `career_report` adds readiness, recommendations, and the roadmap. Every result object has `to_dict()`.

Status values:

| Object | Values |
|---|---|
| Resume and job | `success`, `partial`, `failed`, `empty`, `needs_ocr` |
| Comparison outcome | `matched`, `related`, `missing`, `indeterminate` |
| Requirement priority | `required`, `preferred`, `unspecified` |
| GitHub | `success`, `failed`, `rate_limited` |
| Readiness `estimate` | An integer, or `None` when no required item can be scored. The summary then says the denominator is 0 or that no required item could be scored |

Bad files, a missing Tesseract install, and GitHub timeouts, HTTP errors, and rate limits stay inside `status`, `reason`, `errors`, and `warnings`. They do not raise out of these functions. A GitHub failure does not discard the resume or the job comparison. Uploads are written to a temporary directory and deleted when the call returns. Resume text is not written to a project log.

The HTTP layer is `api/app.py`. Launch it from `research\01_resume_intelligence` with `python -m uvicorn api.app:app --host 127.0.0.1 --port 8000`. Set `CAREERNAV_CORS_ORIGINS` to the React dev origin. The default is `http://localhost:5173`. A wildcard is ignored. `http://localhost:3000` must be set explicitly.

| Method and path | Request | HTTP 200 body |
|---|---|---|
| `POST /api/resume` | Multipart `file`, optional `use_ocr` | `ResumeAnalysis.to_dict()` |
| `POST /api/job` | JSON `{"text": "..."}` or multipart `file` | `JobAnalysis.to_dict()` |
| `POST /api/github` | JSON `{"username": "..."}` | `GitHubAnalysis.to_dict()` |
| `POST /api/career-report` | JSON with the stored `resume`, optional `job`, optional `github`, optional `weekly_hours` | `CareerReport.to_dict()` |

Pipeline results stay HTTP 200, including `failed`, `empty`, `needs_ocr`, and GitHub `rate_limited`. HTTP 400 and 415 are only `{"status": "failed", "errors": ["..."]}` when the request itself cannot be read. HTTP 500 uses that same shape and does not include a traceback. The career-report call does not upload the resume again and does not send resume text to an external model. Checked on 19 October 2026: `tests/test_api.py`, 14 passed. The React frontend is not integrated.

### Still unresolved

- Overlapping employment dates are still added. The warning is present. Removing the overlap would change the current total and was not done.
- Real photographed scans still have no accuracy measurement.
- Achievements remain section text, not a separate entity list.
- The React frontend has not been connected to `api/app.py`. The API tests use FastAPI's TestClient. No browser session was opened for the API.
