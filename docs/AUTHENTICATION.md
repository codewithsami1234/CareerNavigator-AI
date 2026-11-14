# Accounts and sign-in

CareerNavigator AI keeps accounts in a local SQLite file. The React app sends the session cookie. It does not store a password or a session token in `localStorage` or `sessionStorage`.

There is no email confirmation, password-reset email, SMTP setup, or hosted login service. After registration, the person is signed in.

Streamlit still calls the analysis code directly and does not sign in.

## Local database

The database file is:

`research/01_resume_intelligence/data/careernavigator.sqlite`

That folder is gitignored. Starting the API creates missing tables. It does not delete the file.

An older account file is updated in place:

- Existing people are copied into `users` with `id`, `full_name`, `email`, `password_hash`, and `created_at`.
- Existing sessions, saved analysis records, and workspaces are kept.
- Email-token and sign-in-attempt tables are removed, because those features are no longer used.

Apply the tables from `research/01_resume_intelligence`:

```cmd
py -3 -m accounts.migrate
```

The API also applies them when it starts.

Passwords are hashed with Argon2id. The session cookie is `HttpOnly` and `SameSite=Lax`. Only a SHA-256 hash of the session token is stored. A session lasts 14 days and is replaced on each sign-in. Sign-out revokes it. Unsafe requests must send the CSRF cookie back in `X-CSRF-Token`.

Set `CAREERNAV_COOKIE_SECURE=1` only on HTTPS. A secure cookie is not stored by the browser on `http://localhost`.

## Run it locally

Use two Command Prompt windows.

API:

```cmd
cd /d "C:\Users\DELL\Desktop\CareerNavigator AI\research\01_resume_intelligence"
py -3 -m accounts.migrate
py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Workspace:

```cmd
cd /d "C:\Users\DELL\Desktop\CareerNavigator AI\frontend"
npm run dev
```

Open `http://localhost:5173`.

`GET /api/health` stays public. Resume, job, GitHub, roadmap, and report routes require a signed-in session. Each account can read only its own saved analysis.

## What a person can do

Create an account, sign in immediately, refresh the page and stay signed in, change the password from Settings, and sign out. Sign-out revokes the server session. An account cannot read another account's records by changing an id.
