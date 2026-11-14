# CareerNavigator AI

An explainable career-intelligence workspace for students, graduates, and developers. It reads a resume, compares that resume with a job description you paste, lists the skill gaps, optionally reads a public GitHub profile, and turns those results into a roadmap and a downloadable report.

The analysis is rule-based. It is not a trained hiring model, and the readiness number is not an ATS score or a prediction that someone will be hired. Guidance added on top of a comparison explains mention-only matches, related skills, and category labels. It uses the same objects and does not calculate a second score.

This repository is prepared for **Arbiter Hacks V1, General Track**, as a solo project. It has not been deployed to a public host.

## What you are running

| Piece | Role |
|---|---|
| `research/01_resume_intelligence` | Resume parser, OCR, job comparison, GitHub client, readiness, roadmap, FastAPI, and the original Streamlit page |
| `frontend` | React workspace that calls that API |
| `PROJECT_AUDIT.md` | Earlier audit of the resume engine |

The React app does not reimplement parsing or scoring. `POST /api/report` copies the readiness estimate into a document. It does not calculate a second score.

## Setup

Python 3.10 or newer and Node.js 22 are enough for the demo. Tesseract is required only for scanned PDFs. A GitHub token is optional.

```powershell
cd "research\01_resume_intelligence"
py -3 -m pip install -r requirements.txt
```

If `python` is on your `PATH`, use `python` instead of `py -3`.

```powershell
cd frontend
npm install
```

Optional environment variables are listed in [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example). The demo does not need them.

## Start

Use two terminals. Both stay running.

**API** — from `research\01_resume_intelligence`:

```powershell
py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

**Workspace** — from `frontend`:

```powershell
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The workspace routes are `/dashboard`, `/resume-analyzer`, `/job-matcher`, `/skill-gap`, `/github-intelligence`, `/career-roadmap`, `/reports`, and `/settings`. Older `/app/...` addresses redirect to those pages.

The Vite server proxies `/api` to `http://127.0.0.1:8000`. `npm run preview` uses the same proxy and the same port, so stop `npm run dev` first. Interactive API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

The original Streamlit page is still available from `research\01_resume_intelligence`:

```powershell
py -3 -m streamlit run web\app.py --server.address 127.0.0.1 --server.port 8501
```

## Synthetic walkthrough

On Resume Analyzer, choose **Use synthetic sample** and then **Analyze resume**. The sample is the fictional Alex Morgan resume already used by the test suite. **Use synthetic PDF**, **Use synthetic DOCX**, **Use synthetic scan**, and **Use synthetic photograph** load the same fictional resume in those formats. The scan and the photograph are rendered pages, not camera photos of a real resume. The scan and the photograph turn OCR on.

The job description box starts empty. On Job Matcher, choose **Load synthetic posting**, then **Read job description**, then **Compare with resume**. With the current taxonomy that posting scores **75 / 100**: Python, Django, and SQL match as required skills. Kubernetes is required and comes back **related**, not matched, because the comparison names Docker as a related skill, so it contributes 0. Docker and React are preferred and stay out of the denominator. If you change the taxonomy, trust the number and the outcome labels on the page rather than this paragraph.

GitHub Intelligence can read a public profile such as `octocat`. That call needs a network connection to `api.github.com`. A rate limit or a missing user is shown as an error, and the resume result stays.

## Tests

```powershell
py -3 -m pytest
cd frontend
npm test
```

## More documentation

| Guide | Path |
|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Features | [docs/FEATURES.md](docs/FEATURES.md) |
| Tests | [docs/TESTING.md](docs/TESTING.md) |
| Security notes | [docs/SECURITY.md](docs/SECURITY.md) |
| Accounts and sign-in | [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) |
| Troubleshooting | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Demo script | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| Submission draft | [docs/HACKATHON_SUBMISSION.md](docs/HACKATHON_SUBMISSION.md) |
| Engine reference | [research/01_resume_intelligence/README.md](research/01_resume_intelligence/README.md) |

## Local production-style run

This repository is not deployed to a public host. To serve the built workspace against the local API, keep the API running and, from `frontend`, stop the dev server first:

```powershell
npm run build
npm run preview
```

Preview listens on [http://localhost:5173](http://localhost:5173) and proxies `/api` to `http://127.0.0.1:8000`. Bind the API to `127.0.0.1`. Do not publish port 8000 and describe it as a private service.

## Known limits

- Overlapping jobs can inflate a generic years-of-experience total. The comparison warns when that happens.
- OCR was measured on synthetic rendered pages, including a PNG and a text-free PDF of the fictional Alex Morgan resume. Accuracy on camera photos and noisy scans was not measured.
- DOCX text boxes are read. A heading that shares a table cell with other text can still sit on that cell's line.
- PNG and JPEG resumes are accepted. They are read only when OCR is on. A photograph with OCR off returns `needs_ocr`.
- The React workspace has accounts. Saved analysis belongs to the signed-in person. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md). Streamlit does not sign in.
- There is no live job board.
- The app has not been deployed.
- A mention-only skill can still be a match. The guidance layer calls that partial support and leaves the estimate unchanged.
- A career-path label needs extracted skills in the mapped categories. Fewer skills produce no label.
- Focus slots are roadmap order plus the weekly hours you typed. They are not a measured study plan.
- Repository language counts are how many read repositories list that language. Commit history and source code are not downloaded.
