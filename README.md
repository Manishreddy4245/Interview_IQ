# InterviewIQ

InterviewIQ is an AI-powered technical interview preparation and assessment platform featuring an adaptive multimodal workspace, real-time code execution, live proctoring (visual & communication integrity), and role-tailored skill evaluation.

---

## Repository Structure

The project is organized as a clean decoupled monorepo:

```text
interviewiq/
├── frontend/             # Next.js 16 frontend application
│   ├── app/              # App router routes (admin, candidate, reviewer, workspace, auth)
│   ├── components/       # UI components & Multimodal IDE
│   ├── lib/              # Client API layer, proctoring trackers, problem catalog
│   ├── public/           # Static assets and icons
│   ├── tests/            # Frontend unit and E2E test suites
│   ├── .env.example      # Frontend environment template
│   ├── package.json      # Frontend dependencies & scripts
│   └── tsconfig.json     # TypeScript configuration
├── backend/              # FastAPI backend service
│   ├── app/              # FastAPI application (routers, schemas, services, core)
│   ├── ml/               # Machine learning notebooks & models
│   ├── tests/            # Pytest backend test suite
│   ├── .env.example      # Backend environment template
│   ├── requirements.txt  # Python dependencies
│   └── README.md         # Detailed backend documentation
├── .gitignore            # Shared Git ignore rules
└── README.md             # Project-level overview & quickstart
```

---

## Quickstart

### 1. Backend (FastAPI)

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Set up Python virtual environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   Copy `backend/.env.example` to `backend/.env` and supply your MongoDB Atlas URI, Groq API key, and JWT Secret:
   ```bash
   cp .env.example .env
   ```

5. **Run backend development server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Run backend tests**:
   ```bash
   pytest tests/
   ```

---

### 2. Frontend (Next.js)

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment**:
   Copy `frontend/.env.example` to `frontend/.env.local`:
   ```bash
   cp .env.example .env.local
   ```
   Set `NEXT_PUBLIC_API_URL=http://localhost:8000` (or your deployed backend URL in production).

4. **Run frontend development server**:
   ```bash
   npm run dev
   ```
   Access the web application at `http://localhost:3000`.

5. **Run frontend unit & integration tests**:
   ```bash
   npm run test:all
   # Or run specific test suites:
   npm run test
   ```

6. **Create production build**:
   ```bash
   npm run build
   ```

---

## Environment Variables

| Variable | Location | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Base URL of the FastAPI backend service |
| `ENVIRONMENT` | `backend/.env` | Runtime environment (`development` or `production`) |
| `PORT` | `backend/.env` | Backend port (default `8000`) |
| `CORS_ORIGINS` | `backend/.env` | Allowed origins (e.g., `http://localhost:3000`) |
| `MONGODB_URI` | `backend/.env` | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | `backend/.env` | Database name (e.g., `interviewiq`) |
| `GROQ_API_KEY` | `backend/.env` | Groq Cloud API key for LLM generation |
| `JWT_SECRET` | `backend/.env` | Secret key for JWT token signing |
