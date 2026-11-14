/** Synthetic walkthrough data. These people and companies are fictional. */

export const SAMPLE_RESUME_NAME = "alex-morgan-synthetic.txt"

export const SAMPLE_RESUME = `Alex Morgan
Lahore, Pakistan | alex.morgan@example.com | +92 300 0000000 | github.com/alexmorgan-demo | linkedin.com/in/alexmorgan-demo

Summary
Final-year IT student interested in machine learning and web development.

Skills
Programming Languages: Python, Java, JavaScript, SQL
Frameworks: Django, React, scikit-learn, OpenCV
Tools: Git, Docker, Postman

Education
Bachelor of Science in Information Technology, Example University of Technology (2021 - 2025)
CGPA: 3.4/4.0
Intermediate in Pre-Engineering, Sample Government College (2019 - 2021)

Experience
Software Engineering Intern | Acme Software Solutions | Jun 2024 - Aug 2024
- Built REST API endpoints with Django and PostgreSQL for an internal tool
- Containerized the service using Docker and wrote unit tests with pytest

Junior Web Developer, Demo Technologies Ltd (Jan 2023 - Present)
- Developed responsive pages with React and CSS
- Used Git and GitHub for code review

Projects
Smart Attendance System | Python, OpenCV
- Built a face-recognition attendance tool using OpenCV and Flask
- Stored records in SQLite

Resume Screening Assistant
- Trained a text classifier with scikit-learn and NLTK to rank resumes

Certifications
- Google Data Analytics Professional Certificate - Coursera (2023)
- AWS Cloud Practitioner Essentials, Amazon Web Services

Courses
- Machine Learning Specialization by Stanford Online

Achievements
- Winner, Example University Hackathon 2024

Languages
English, Urdu
`

export const SAMPLE_JOB_TITLE = "Backend Developer"
export const SAMPLE_COMPANY = "Example Labs"
export const SAMPLE_TARGET = "Software engineering"

export const SAMPLE_JOB = `Required qualifications
- Python
- Django
- SQL
- Kubernetes

Preferred qualifications
- Docker
- React
`

export function sampleResumeFile() {
  return new File([SAMPLE_RESUME], SAMPLE_RESUME_NAME, { type: "text/plain" })
}

export const CAREER_GOALS = [
  "Software engineering",
  "Data and machine learning",
  "Web development",
  "DevOps and cloud",
] as const

export const SCORING_METHOD = [
  "The number on the job page is the pipeline readiness estimate, copied from the career report. This screen does not calculate a second percentage.",
  "A matched required item contributes 1. A related or missing required item contributes 0. The estimate is the nearest integer of 100 × earned ÷ scored required items.",
  "Preferred items, unspecified items, and unverified experience are shown and left out of the denominator. If nothing can be scored, no number is assigned.",
  "Related skills are alternatives named by the matcher. They are not matches.",
  "Public GitHub observations are listed separately and do not change the estimate.",
  "The estimate is not a prediction of hiring and it is not an ATS score.",
]
