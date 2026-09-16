# Talent Match — Vector Database Candidate Search

## Setup
Clone the repo
```bash
git clone https://github.com/govindgcoder/talent-match.git
cd talent-match
```

### Backend (FastAPI)
once cloned, run
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
Then open a new terminal window,
```bash
cd your/path/to/talent-match

# Option 1: Python
python -m http.server 3000

# or

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
