# InterviewIQ — Backend (FastAPI)

Modular FastAPI backend service for the InterviewIQ platform.

## Architecture

- **Framework**: FastAPI (Python 3.14+)
- **Server**: Uvicorn (ASGI)
- **Settings & Schemas**: Pydantic v2 & Pydantic Settings
- **Database Driver**: Motor (AsyncIOMotorClient) with MongoDB Atlas lifecycle
- **AI Engine**: Groq Cloud SDK (prepared for Phase 2 intelligence modules)
- **Testing**: Pytest & FastAPI TestClient

## Project Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py         # Pydantic Settings reading .env & system env
│   │   ├── database.py       # Async Motor MongoDB Atlas lifecycle & ping health
│   │   └── groq_client.py    # Secure Groq client manager (Phase 1 validation)
│   ├── routers/
│   │   └── health.py         # GET /health, GET /health/db, GET /health/groq
│   ├── schemas/
│   │   └── health.py         # Pydantic response models
│   └── main.py               # FastAPI entry point, CORS middleware, lifespan events
├── tests/
│   ├── conftest.py           # Pytest test client fixtures
│   └── test_health.py        # Health, DB, Groq & CORS unit tests
├── .env.example              # Environment variables template
├── .gitignore                # Python and secrets ignore patterns
├── requirements.txt          # Production and testing dependencies
└── README.md                 # Setup and run guide
```

## Setup & Running Locally

### 1. Create and Activate Virtual Environment

Windows PowerShell:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example configuration file:
```powershell
cp .env.example .env
```

Edit `.env` and provide your credentials:
```ini
ENVIRONMENT=development
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# MongoDB Atlas URI (leave blank or provide actual connection string)
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=interviewiq

# Groq API Key
GROQ_API_KEY=gsk_...
```

*Note: If `MONGODB_URI` or `GROQ_API_KEY` are not set, the server runs in unconfigured mode and responds clearly on `/health/db` and `/health/groq` without crashing or falling back to localhost/mock data.*

### 4. Run the Backend Server

From the `backend/` directory:
```powershell
uvicorn app.main:app --reload --port 8000
```
Or from the project root:
```powershell
& "backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The API will be available at:
- **Base URL**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Database Health**: http://localhost:8000/health/db
- **Interactive Swagger Docs**: http://localhost:8000/docs

### 5. Run Backend Tests

From the project root:
```powershell
& "backend\.venv\Scripts\python.exe" -m pytest backend\tests
```
