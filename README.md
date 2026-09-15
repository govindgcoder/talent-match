# Talent Match — Vector Database Candidate Search

## Setup

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
# Option 1: Python
cd frontend
python -m http.server 3000

# Option 2: Node
npx serve frontend -p 3000
```

Open `http://localhost:3000` in your browser.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/candidates/upload` | Register a candidate with resume PDF |
| GET | `/api/candidates/search` | Hybrid semantic + relational search |

## Configuration

Backend URL defaults to `http://localhost:8000`. To change it, edit the `API_BASE` constant in `api.js`.
