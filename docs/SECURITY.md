# Security notes

Review of the local workspace. This is not a penetration test.

## Controls that are in place

- Resume uploads must use `.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, or `.jpeg`. Job uploads stay on `.pdf`, `.docx`, and `.txt`. The base filename is kept and path separators are stripped in `web.service.safe_filename`.
- The bytes must match the extension: a PDF contains `%PDF-` in the first 1024 bytes, a DOCX is a ZIP package, a PNG or JPEG matches its image signature, and a TXT file is not a PDF, ZIP, image, or `MZ` executable and does not contain a NUL byte in the first 8 KB. A declared content type other than empty or `application/octet-stream` must agree with the extension. The rejected type is not copied into the error.
- Files larger than 10 MB, or empty files, return a failed analysis and are not parsed.
- The upload is written under a fresh temporary directory and that directory is deleted when the call returns.
- API failures are `status`, `errors`, and `reason`. Unexpected exceptions become HTTP 500 with a fixed sentence and no traceback.
- CORS does not accept `*`. Credentials are allowed for the listed origins so the session cookie can be sent. Methods are GET, POST, PUT, PATCH, DELETE, and OPTIONS. Unsafe requests must echo the CSRF cookie in `X-CSRF-Token`.
- `GITHUB_TOKEN` is read from the environment. Error text redacts the token when it appears. The token is not returned in JSON.
- Report labels that are not strings, or that are longer than 200 characters, are rejected. The rejected value is not copied into the error.
- Passwords are hashed with Argon2id. Session tokens are random, and only their SHA-256 hashes are stored. The session cookie is HttpOnly. Set `CAREERNAV_COOKIE_SECURE=1` on HTTPS.
- Sign-in is rate limited. Unknown and known emails get the same failure response. Changing a password revokes existing sessions. There is no email confirmation or emailed password reset.
- Analysis and saved records are loaded for the session's account. A record id from another account returns 404.
- The React app does not ask for a GitHub password and does not store the session token in browser storage. Saved analysis can be deleted from Settings.

## Findings

| Finding | Severity | Notes |
|---|---|---|
| API bound to localhost | Expected for this build | Analysis routes require a session. Bind the API to `127.0.0.1` unless a reverse proxy is the only public entry. Do not expose port 8000 and describe it as private. |
| Saved analysis contains extracted resume text | Medium for a shared computer | It is stored for that account and can be deleted from Settings. Resume files themselves are not stored. Sign out on a shared computer. |
| MIME check allows an empty type and `application/octet-stream` | Low | Browsers label valid DOCX and image files that way. A specific type that disagrees with the extension is rejected. The signature check still runs. |
| The API reads the upload into memory before the size check | Low | The 10 MB limit still rejects the analysis. A hostile client on localhost could send a larger body first. |
| `pip-audit` is not installed | Info | `npm audit` on 4 November 2026 reported 0 vulnerabilities across 244 frontend packages. Python packages were not scanned with a vulnerability database because `pip-audit` is not installed, and it was not added. |
| Sign-in rate limit is kept in this API process | Low | Eight failures per email and client address are remembered for 15 minutes. Restarting the API clears that count. |

The application logger `careernavigator.api` records method, path, HTTP status, upload size, file suffix, and pipeline status. Uvicorn may also log method, path, and status. File names, resume text, job text, GitHub usernames, and tokens are not written by the application logger. There is no project log file.
