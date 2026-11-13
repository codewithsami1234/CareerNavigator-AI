# Baseline audit — 2 November 2026

Audit taken before the hackathon workspace was added. Statuses: `PASS`, `MISSING`.

## Workspace

| Item | Finding |
|---|---|
| Git | `MISSING`. The folder is not a Git repository. No branches were created or deleted. |
| Frontend | `MISSING` before this pass. No React app was in the tree. |
| Backend | `PASS`. `research/01_resume_intelligence` is one Python package. |
| FastAPI | `PASS`. `POST /api/resume`, `/api/job`, `/api/github`, `/api/career-report`. CORS default origin `http://localhost:5173`. Wildcard rejected. |
| Streamlit | `PASS`. `web/app.py` calls `web/service.py`. |
| Resume parsing | `PASS`. PDF, DOCX, TXT. `analyze_resume` does not OCR. Scanned PDFs return `needs_ocr`. |
| OCR | `PASS` in the existing suite when Tesseract is installed. Provenance methods include `native_pdf`, `native_docx`, `native_text`, and `ocr`. |
| Taxonomy | `PASS`. `data/skills_taxonomy.json`, previously counted at 215 skills. Not re-counted in this audit. |
| Job match and roadmap | `PASS` as Python modules and Streamlit views. Comparison outcomes have no separate match percentage. Readiness is the scored estimate. |
| GitHub | `PASS` as a public API client. No credentials are required. |
| Tests | `PASS`. `py -3 -m pytest --override-ini="addopts="` collected **424 passed** in 72.38s before these edits. |
| Persistence | `MISSING`. No database. |
| Deployment | `MISSING`. Nothing was deployed. |

`PROJECT_AUDIT.md` records older runs, including 410 passed on 19 October 2026. The 424 count above is the baseline for this pass.

## Preservation

The resume engine, Streamlit page, and existing tests were kept. New HTTP routes are `GET /api/health` and `POST /api/report`. The four original routes still return the same objects.
