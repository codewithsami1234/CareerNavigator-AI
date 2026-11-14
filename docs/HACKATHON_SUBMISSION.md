# Hackathon submission draft

**Event:** Arbiter Hacks V1
**Track:** General
**Team:** Solo
**Project:** CareerNavigator AI

## Description

CareerNavigator AI is a local career-intelligence workspace. A student or developer uploads a resume, pastes one job description, and sees an explainable comparison: matched skills, missing skills, and a readiness estimate whose denominator is on the page. They can add a public GitHub profile as supporting metadata and export a roadmap and a report built from those same results.

The resume engine reads PDF, DOCX, and TXT, and can OCR a scanned PDF or a PNG or JPEG with local Tesseract when asked. Scoring, gaps, and the roadmap are rule-based. The product does not claim to predict hiring, to pass or fail ATS software, or to search a live job board.

## What to show

1. Synthetic Alex Morgan resume.
2. Synthetic backend posting, with the readiness summary visible.
3. The Kubernetes requirement, which the matcher marks related rather than matched, and the roadmap milestone that follows from it.
4. A public GitHub profile, or the honest error if the API is unavailable.
5. A downloaded report that copies the estimate instead of inventing another one.

## Stack

Python, FastAPI, the existing resume pipeline, React, TypeScript, Tailwind CSS, and Recharts for the requirement counts. Streamlit remains available as the earlier interface.

## Limits to mention

The React workspace has accounts. There is no hosted deployment, no live job listings, and no measured accuracy on real photographed scans. Overlapping employment dates can still inflate a generic experience total, and the result says so.
