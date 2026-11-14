# Features

Statuses describe the hackathon workspace, not a future design.

| Module | Status | What it uses |
|---|---|---|
| Resume intelligence | Complete | PDF, DOCX, and TXT parsers. OCR, when the checkbox is on, uses `analyze_document` for a scanned PDF and for a PNG or JPEG. An image with OCR off returns `needs_ocr`. |
| Job matching | Complete | Existing job reader and comparison. The number on screen is `readiness.estimate`. |
| Skill gaps | Complete | `recommend_gaps` from the comparison. Reasons quote the posting outcome. |
| GitHub | Complete when the network allows | `github_analysis` against `https://api.github.com`. Failures stay in the response. |
| Roadmap | Complete | `build_roadmap` from the same recommendations. Browser checkboxes are local and labeled as unverified. |
| Guidance | Complete | `build_guidance` after the comparison. Partial support, skills to strengthen, project ideas, path labels, near-term and later milestones, and focus slots. It does not rescore. |
| Reports | Complete | `POST /api/report` markdown, JSON, and CSV. Progress ticks are appended in the browser under their own heading. |
| Landing and workspace UI | Complete | React routes for overview, resume, job, gaps, GitHub, roadmap, reports, and settings. Light and dark theme. |
| Accounts | Not implemented | One browser profile. The UI says so. |
| Live job board | Not implemented | The user pastes one description. |
| Public deployment | Not implemented | Local processes only. |

## Honesty rules in the interface

- Contact fields that were not extracted are listed as missing. They are not filled in.
- Skill evidence stays `used` or `mentioned`.
- Related skills are not shown as matches. Mention-only matches are called partial support and still count as matches.
- A career-path label appears only when the resume already has enough skills in that category group. The job text alone cannot create one.
- GitHub skill names are quoted separately and are not used to choose a path.
- A GitHub language list is not treated as a skill by itself. The overlap panel compares taxonomy names already returned by the two analyses and states that a shared name is not proof of proficiency.
- Job title, company, and target career are labeled as text the user typed.
- No course URLs or certificates are invented.
