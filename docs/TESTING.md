# Testing

## Backend

From the repository root:

```powershell
py -3 -m pytest --tb=line -q --override-ini="addopts="
```

Baseline before this hackathon pass, on 2 November 2026: **424 passed**.

The suite already covered PDF, DOCX, and TXT parsing, scanned-PDF `needs_ocr` behavior, OCR integration when Tesseract is installed, unsupported and oversized files, job comparison, skill gaps, GitHub error handling with a fake transport, roadmap generation, and the original four API routes.

This pass added `tests/test_hackathon_api.py`:

- `GET /api/health` and CORS rejection of an unlisted origin
- report markdown copies the pipeline estimate and includes a typed job title
- a non-string label is rejected without echoing the value
- an unsupported upload produces a report that does not invent skills
- a resume-only report has no numeric estimate

After the hackathon pass, the same command collected **429 passed** in 60.92s. That is the previous 424 plus the five tests in `test_hackathon_api.py`.

Before the guidance pass on 3 November 2026, the same command collected **429 passed** in 74.84s, and `npm test` in `frontend` collected **10 passed**.

This pass added `tests/test_guidance.py` and `tests/test_api_logging.py`:

- mention-only matches are labeled partial support and the readiness estimate stays the same
- related skills are labeled partial support and still earn no credit
- career-path labels require extracted category evidence and ignore GitHub-only names
- a failed resume produces no paths or skills to strengthen
- resume request logs omit the file name and the resume text
- a rejected GitHub username is logged as a status, without the username or `GITHUB_TOKEN`

After the guidance pass, the same command collected **434 passed**. A later upload pass added image routing, content-signature rejection, and a Streamlit notice for photographs.

On 6 November 2026 the same command collected **453 passed**, including registration, session, password change, migration, and cross-user checks in `tests/test_auth.py`. Tesseract was installed, so the OCR integration tests ran. `npm test` collected **22 passed**. `npm run build` is the TypeScript check plus the production bundle. Do not quote an older `PROJECT_AUDIT.md` count as the current total.

The two new backend tests check that a PNG or JPEG upload calls `analyze_document`, that OCR off returns `needs_ocr`, that a mismatched image signature, content type, DOCX package, or disguised TXT file is rejected, and that a rejected file is not written to a temporary directory. The frontend tests check an unsupported extension, a content type that disagrees with the extension, and the progress indicator shown while a resume request is in flight.

## Frontend

From `frontend`:

```powershell
npm test
npm run build
```

`npm test` runs Vitest. It covers the landing page, workspace navigation, the synthetic resume request, the empty job description, stored guidance and partial-support panels, and the skill-overlap and progress helpers. `npm run build` runs the TypeScript project build and the Vite production build.

## What the automated tests do not do

- They do not call the live GitHub API. GitHub tests use a fake transport or a username rejected before the network.
- They do not measure accuracy on camera photos or noisy scans. The OCR integration tests use a synthetic rendered page. The workspace samples under `frontend/public/samples` are the same fictional resume rendered as a PNG and a text-free PDF.
- The responsive layout is checked in a browser, not by asserting CSS breakpoints in jsdom.
