# Troubleshooting

## The page says the API is not reachable

Start the API from `research\01_resume_intelligence`:

```powershell
py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Then reload `http://localhost:5173`. The workspace expects the Vite proxy. Opening the built files directly, without `npm run dev` or a proxy, will not reach the API unless `VITE_API_BASE` is set and CORS includes that page's origin.

## `python` is not recognized

Use the Windows launcher:

```powershell
py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

## Port 5173 or 8000 is already in use

Stop the other process. The Vite config uses a fixed port so the documented URL stays `http://localhost:5173`.

## A scanned PDF or a photograph returns `needs_ocr`

Turn on **Use OCR for scanned PDFs and photographed resumes** and analyze again. PNG and JPEG have no text layer, so they need that checkbox. Install Tesseract and, if it is not on `PATH`, set `TESSERACT_CMD` in the same terminal as Uvicorn. DOCX and TXT never use OCR.

If OCR is on and the status is `failed`, the error names a missing Tesseract install or a file that could not be decoded. A low confidence figure is a warning. It is not proof that the words are correct.

## GitHub fails

Invalid usernames, missing users, rate limits, and network errors are shown on GitHub Intelligence. The resume and job results remain. A token in `GITHUB_TOKEN` is optional and only helps the rate limit. Do not paste a token into the page.

## The readiness number is missing

The pipeline omits the number when no required item can be scored, or when the resume or job could not be used. The summary on the job page explains which case it is. Preferred-only postings often have a denominator of 0.

## Delete a previous analysis

Settings → **Delete saved analysis** → **Confirm delete**. That clears local storage for this workspace. It does not delete project files.
