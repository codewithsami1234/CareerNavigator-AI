# CareerNavigator AI 🚀
### An AI-Powered Career Intelligence Platform

CareerNavigator AI is a career intelligence platform designed to help job seekers understand their professional strengths, evaluate their skills, identify career gaps, and make informed career decisions.

The platform analyzes resumes, compares candidate skills against job descriptions, evaluates GitHub profiles, and generates personalized career improvement roadmaps.

Our goal is to make career planning more accessible, practical, and data-driven.

---

## ✨ Key Features

### 📄 Resume Intelligence
- Upload and analyze resumes.
- Extract relevant information and skills.
- Identify skills mentioned and supported by resume evidence.
- Review professional strengths and areas for improvement.

### 🎯 Job Description Matching
- Compare your resume against job descriptions.
- Identify matching and missing skills.
- Understand your suitability for a target role.
- Receive recommendations for improving your job readiness.

### 📊 Skill Gap Analysis
- Identify skills required for your target career.
- Compare existing skills with job requirements.
- Highlight areas that need improvement.
- Get actionable learning recommendations.

### 💻 GitHub Intelligence
- Analyze publicly available GitHub profile information.
- Explore repositories and programming activity.
- Identify technical skills demonstrated through public projects.
- Gain additional insight into your developer profile.

### 🗺️ Personalized Career Roadmap
- Generate structured career improvement plans.
- Organize skill-development priorities.
- Follow actionable recommendations.
- Track your progress toward career goals.

### 📑 Reports and Dashboard
- Access career analysis results.
- Review skill insights and job matching information.
- Explore your career readiness indicators.
- Manage your workspace.

---

## 🛠️ Technology Stack

The project uses the following technologies:

| Component | Technology |
|---|---|
| Frontend | React.js |
| Frontend tooling | Vite |
| Backend | Python |
| API framework | FastAPI |
| Resume processing | PyMuPDF / python-docx |
| Image processing | OpenCV |
| OCR | Tesseract |
| Data processing | Python |
| Database | SQLite |
| Deployment | Docker |

*Technology details should be checked against the current repository before treating this list as final.*

---

## 🏗️ Project Architecture

CareerNavigator AI follows a frontend-backend architecture.

```text
CareerNavigator-AI/
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── research/
│   └── 01_resume_intelligence/
│       ├── api/
│       ├── data/
│       ├── tests/
│       └── ...
│
├── Dockerfile
├── render.yaml
├── .gitignore
└── README.md
```

The React frontend communicates with the Python backend through API endpoints. The backend handles resume analysis, job matching, skill intelligence, and related processing.

---

## 🚀 Getting Started

### Prerequisites

Install the following:

- Python 3.10 or compatible version supported by the project
- Node.js and npm
- Git
- Tesseract OCR (for OCR functionality)

### 1. Clone the Repository

```bash
git clone https://github.com/codewithsami1234/CareerNavigator-AI.git
```

```bash
cd CareerNavigator-AI
```

### 2. Set Up the Backend

Navigate to the backend directory:

```bash
cd research/01_resume_intelligence
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```cmd
.venv\Scripts\activate
```

Install dependencies using the repository's actual requirements file:

```bash
pip install -r requirements.txt
```

Start the backend using the project's configured API entry point:

```bash
python -m uvicorn api.app:app --reload --port 8000
```

### 3. Set Up the Frontend

Open another terminal from the project root:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend and backend should now be available locally according to their configured ports.

---

## 🧪 Testing

The project includes automated tests for backend functionality and frontend behavior.

Run backend tests from the appropriate backend directory:

```bash
python -m pytest
```

Run frontend tests from the frontend directory:

```bash
npm test
```

Build the frontend:

```bash
npm run build
```

Refer to the latest test execution results before reporting test coverage or passing-test counts.

---

## 🌐 Deployment

The repository includes Docker-based deployment configuration.

- `Dockerfile` — container configuration.
- `render.yaml` — Render deployment configuration.

**Deployment status:** Public production deployment is not yet verified.

A working public URL will be added here after successful deployment.

---

## 🔮 Future Improvements

- More advanced semantic skill matching.
- Expanded job-market intelligence.
- Additional resume formats and document processing.
- More personalized career recommendations.
- Improved GitHub project analysis.
- Enhanced reporting and career progress tracking.
- Integration with additional job platforms.

---

## 🎯 Project Vision

CareerNavigator AI aims to bridge the gap between a candidate's current skills and the skills demanded by the job market.

Instead of simply helping people create resumes, the platform helps them understand where they stand, what they need to improve, and how to move toward their career goals.

**Analyze your skills. Discover your gaps. Navigate your career.**

---

## 👩‍💻 Contributors

Developed as an academic and innovation project.

Contributions, suggestions, feedback, and collaboration are welcome.

---

## 📬 Contact

GitHub: [codewithsami1234](https://github.com/codewithsami1234)

Project Repository: [CareerNavigator AI](https://github.com/codewithsami1234/CareerNavigator-AI)

---

*CareerNavigator AI — Navigate Your Future with Intelligence.*
