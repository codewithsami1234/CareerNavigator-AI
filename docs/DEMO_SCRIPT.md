# Demo script

About two and a half minutes. Use the synthetic sample. Do not upload a real resume.

## Before you start

1. API: `py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000` from `research\01_resume_intelligence`.
2. UI: `npm run dev` from `frontend`.
3. Open `http://localhost:5173`.
4. If a previous analysis is on screen, delete it from Settings so the overview starts empty.

## 0:00 — What it is

On the landing page: CareerNavigator AI connects a resume, one job description, the gaps, and public GitHub metadata. The number you will see is a rule-based estimate, not a claim that someone will be hired.

Open the workspace. Point at the empty overview and the API status. There is no fake user count.

## 0:25 — Resume

Resume Analyzer → **Use synthetic sample** → **Analyze resume**.

Show the email `alex.morgan@example.com`, skills grouped by category, and evidence type `used` or `mentioned`. Say that missing contact fields are listed as not found. Open one extracted section so the text is visible.

## 1:05 — Job match

Job Matcher → **Load synthetic posting** → **Read job description** → **Compare with resume**.

The sample scores 75 / 100 on the current taxonomy: 3 of 4 required skills match. Kubernetes is required and **related**, not matched, because the comparison names Docker as a related skill and related items contribute 0. Docker and React are preferred, so they are not in the denominator. Read the summary under the number rather than only the 75. Show one matched row with resume evidence and the Kubernetes row.

## 1:40 — Gaps and roadmap

Skill Gap Analyzer shows Kubernetes as a related required gap, with the posting text and a practice task. Career Roadmap shows the milestone from that gap. Tick it and say the tick is stored in this browser and is not verified learning. The target career dropdown is a label you chose. It does not change the 75.

## 2:05 — GitHub and the report

GitHub Intelligence → **Read profile** for `octocat`, or any public username. If GitHub rate-limits the call, read the error and continue. The resume is still there.

If the profile loads, show that a shared taxonomy name is labeled as not proof of proficiency.

Reports → **Build report** → show the markdown heading that says the report does not calculate a second score. Download is optional.

## If something fails

Say what the screen says. Do not refresh into a backup screenshot of a different score. The Streamlit app on port 8501 uses the same pipeline if the React page cannot reach the API.
