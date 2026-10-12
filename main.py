import os, pickle, re, sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google import genai
from markitdown import MarkItDown
from pydantic import BaseModel

DB_PATH = Path("./talent_match.db")
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
EMBEDDINGS_FILE = DATA_DIR / "embeddings.pkl"
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 3072  # must match the model's output; a mismatch silently zeroes scores

try:  # GEMINI_API_KEY lives in .env; genai.Client() only reads os.environ
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="Talent Match API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
md = MarkItDown()

# ------------------------------------------------------------- skills
# Closed vocabulary for the keyword half of matching (structured skill lists).
KNOWN_SKILLS = [
    "python", "java", "c++", "c", "javascript", "typescript", "html", "css",
    "react", "angular", "node.js", "express", "fastapi", "django", "flask",
    "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes", "aws", "git",
    "machine learning", "deep learning", "nlp", "pandas", "data analysis", "rest api",
    "rust", "esp32", "stm32", "arduino", "raspberry pi", "embedded systems", "tauri",
    "kalman filter", "computer vision", "sensor fusion", "gnss", "telemetry", "digital logic",
    "linux", "terraform", "ci/cd", "devops", "seo", "content marketing", "figma", "ui/ux",
    "user research", "google ads",
]
_ABBR = {"sql", "aws", "css", "html", "nlp", "c++", "c", "esp32", "stm32", "gnss"}


def format_skill(s: str) -> str:
    s = s.strip()
    return s.upper() if s.lower() in _ABBR else s.title()


def split_skills(csv: str) -> list[str]:
    return [s.strip() for s in csv.split(",") if s.strip()]


def extract_skills(text: str) -> list[str]:
    body = text.lower()
    return sorted(
        format_skill(s) for s in KNOWN_SKILLS
        if re.search(rf"(?<![a-zA-Z0-9_#+]){re.escape(s)}(?![a-zA-Z0-9_#+])", body)
    )


# ------------------------------------------------ embeddings (search)
# Gemini vectors let a recruiter ask for an "STM32 Embedded systems engineer"
# and rank candidates by how closely their resume prose reads like that query.
_client = None
_embs: dict = {}


def client():
    global _client
    if _client is None:
        # Requires GEMINI_API_KEY. Fails loudly at the call site, not silently.
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def embed(text: str) -> np.ndarray:
    if not text.strip():
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)  # empty resume = no signal
    res = client().models.embed_content(model=EMBEDDING_MODEL, contents=text)
    return np.array(res.embeddings[0].values, dtype=np.float32)


def cosine(v1: np.ndarray, v2: np.ndarray) -> float:
    n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


def load_embeddings() -> dict:
    global _embs
    if not _embs and EMBEDDINGS_FILE.exists():
        with open(EMBEDDINGS_FILE, "rb") as f:
            _embs = pickle.load(f)
    return _embs


def save_embeddings() -> None:
    with open(EMBEDDINGS_FILE, "wb") as f:
        pickle.dump(_embs, f)


def resume_text(path: str) -> str:
    try:
        text = md.convert(path).text_content
        if text.strip():
            return text
    except Exception:
        pass
    # markitdown can't parse the hand-built seed PDFs; pull the text-show
    # operators out of the raw stream so backfill embeds real prose, not "".
    try:
        raw = Path(path).read_bytes().decode("latin-1", "replace")
        chunks = re.findall(r"\((.*?)\)\s*Tj", raw)
        return "\n".join(
            c.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
            for c in chunks
        )
    except Exception:
        return ""


def index_candidate(uid: str, text: str) -> np.ndarray:
    """Embed a resume once at upload and cache it under the candidate's uid."""
    vec = embed(text)
    load_embeddings()[uid] = vec
    save_embeddings()
    return vec


def search_vectors(rows: list[dict]) -> dict:
    """uid -> vector for this result set, backfilling candidates that were
    uploaded before embeddings existed (re-reads their stored PDF)."""
    cached = load_embeddings()
    stale = [r for r in rows if r["uid"] not in cached]
    for r in stale:
        cached[r["uid"]] = embed(resume_text(r["resume_path"]))
    if stale:
        save_embeddings()
    return cached


# ---------------------------------------------------------------- db
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows_of(conn, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


def fetch(sql: str, params=()) -> list[dict]:
    with db() as conn:
        return rows_of(conn, sql, params)


# ----------------------------------------------------------- schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    uid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 18),
    gender TEXT NOT NULL,
    experience_years REAL NOT NULL DEFAULT 0.0 CHECK (experience_years >= 0),
    contact_no TEXT NOT NULL,
    work_preference TEXT NOT NULL DEFAULT 'Flexible',
    skills TEXT NOT NULL DEFAULT '',
    resume_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS COMPANY (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    experience_type TEXT NOT NULL,
    min_experience REAL NOT NULL DEFAULT 0.0,
    skills_expected TEXT NOT NULL,
    location TEXT DEFAULT 'Remote',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_uid TEXT NOT NULL,
    company_id INTEGER NOT NULL,
    match_score REAL NOT NULL,
    matching_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    status TEXT DEFAULT 'Recommended',
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_uid) REFERENCES candidates(uid) ON DELETE CASCADE,
    FOREIGN KEY(company_id) REFERENCES COMPANY(company_id) ON DELETE CASCADE,
    UNIQUE(candidate_uid, company_id)
);
CREATE INDEX IF NOT EXISTS idx_candidates_exp ON candidates(experience_years);
CREATE INDEX IF NOT EXISTS idx_app_company_score ON applications(company_id, match_score);
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER IF NOT EXISTS trg_candidate_audit
AFTER INSERT ON candidates BEGIN
    INSERT INTO audit_log (action, details)
    VALUES ('CANDIDATE_REGISTERED', 'New applicant added: ' || NEW.name);
END;
"""

VIEW_SQL = """CREATE VIEW IF NOT EXISTS v_matched_profiles AS
    SELECT app.id AS application_id, cand.uid AS candidate_uid, cand.name AS candidate_name,
           cand.age, cand.gender, cand.experience_years, cand.contact_no, cand.work_preference,
           comp.company_id, comp.company_name, comp.role_title, comp.skills_expected,
           app.match_score, app.matching_skills, app.missing_skills, app.status
    FROM applications app
    JOIN candidates cand ON app.candidate_uid = cand.uid
    JOIN COMPANY comp ON app.company_id = comp.company_id;
"""

SEED_COMPANIES = [
    ("Google", "Full Stack AI Engineer", "Experienced", 2.0, "Python, React, FastAPI, Machine Learning, Docker, SQL", "Bangalore / Remote"),
    ("Microsoft", "Junior Python Developer", "Fresher", 0.0, "Python, SQL, HTML, CSS, Git", "Hyderabad / Remote"),
    ("Amazon", "Cloud Backend Engineer", "Experienced", 3.0, "Python, AWS, PostgreSQL, Docker, REST API", "Pune / Remote"),
    ("Tesla", "Embedded & AI Specialist", "Experienced", 2.0, "C++, Python, RTOS, Machine Learning", "Bangalore / Hybrid"),
    ("Deloitte", "Data Analyst", "Fresher", 0.0, "Python, SQL, Pandas, Data Analysis, Git", "Mumbai / Remote"),
]


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        # Migrate pre-existing databases up to the current schema.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(candidates)")}
        if "work_preference" not in cols:
            conn.execute("ALTER TABLE candidates "
                         "ADD COLUMN work_preference TEXT NOT NULL DEFAULT 'Flexible'")
        conn.execute("DROP VIEW IF EXISTS v_matched_profiles")
        conn.executescript(VIEW_SQL)
        if not conn.execute("SELECT 1 FROM COMPANY LIMIT 1").fetchone():
            conn.executemany(
                "INSERT INTO COMPANY (company_name, role_title, experience_type, "
                "min_experience, skills_expected, location) VALUES (?,?,?,?,?,?)",
                SEED_COMPANIES,
            )


init_db()


# ----------------------------------------------------------- matching
UPSERT_APP = """INSERT OR REPLACE INTO applications
    (candidate_uid, company_id, match_score, matching_skills, missing_skills)
    VALUES (?,?,?,?,?)"""

TOP_SQL = """SELECT c.company_name, c.role_title, c.experience_type, c.min_experience,
                    a.match_score, a.matching_skills, a.missing_skills
             FROM applications a JOIN COMPANY c ON a.company_id = c.company_id
             WHERE a.candidate_uid = ? ORDER BY a.match_score DESC LIMIT 3"""


def compute_match(cand_skills: list[str], cand_exp: float, comp_skills: str, min_exp: float):
    expected = [format_skill(s) for s in split_skills(comp_skills)]
    have = {s.lower() for s in cand_skills}
    matching = [s for s in expected if s.lower() in have]
    missing = [s for s in expected if s.lower() not in have]
    skill_pct = len(matching) / len(expected) if expected else 1.0
    exp_factor = 1.0 if min_exp == 0 or cand_exp >= min_exp else max(0.65, cand_exp / min_exp)
    score = round(min(100.0, (skill_pct * 0.75 + exp_factor * 0.25) * 100), 1)
    return score, matching, missing


def sync_matches(conn, uid: str, cand_skills: list[str], cand_exp: float, companies: list[dict]):
    conn.executemany(UPSERT_APP, [_app_row(uid, cand_skills, cand_exp, c) for c in companies])


def _app_row(uid: str, cand_skills, cand_exp, comp: dict) -> tuple:
    score, matching, missing = compute_match(cand_skills, cand_exp,
                                             comp["skills_expected"], comp["min_experience"])
    return uid, comp["company_id"], score, ", ".join(matching), ", ".join(missing)


# ------------------------------------------------------------- model
class CompanyCreate(BaseModel):
    company_name: str
    role_title: str
    experience_type: str = "Fresher"
    min_experience: float = 0.0
    skills_expected: str
    location: Optional[str] = "Remote"


# ----------------------------------------------------- candidate API
@app.post("/api/candidates/upload")
async def upload_candidate(
    name: str = Form(...), age: int = Form(...), gender: str = Form(...),
    experience_years: float = Form(...), contact_no: str = Form(...),
    work_preference: str = Form("Flexible"), resume_file: UploadFile = File(...),
):
    name = name.strip()
    phone = "".join(filter(str.isalnum, contact_no))
    # name.split() is empty for whitespace-only input, which would 500 on [0]
    if not name.split() or not phone:
        raise HTTPException(422, "name and contact_no are required")

    uid = f"{name.split()[0].lower()}_{phone}"
    path = DATA_DIR / f"{uid}.pdf"
    path.write_bytes(await resume_file.read())

    text = resume_text(str(path)) or name
    skills = extract_skills(text)
    index_candidate(uid, text)

    try:
        with db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO candidates "
                "(uid, name, age, gender, experience_years, contact_no, work_preference, "
                "skills, resume_path) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, name, age, gender, experience_years, contact_no.strip(),
                 work_preference.strip() or "Flexible", ", ".join(skills), str(path)),
            )
            sync_matches(conn, uid, skills, experience_years,
                         rows_of(conn, "SELECT * FROM COMPANY"))
            top = conn.execute(TOP_SQL, (uid,)).fetchall()
    except Exception as e:
        raise HTTPException(500, str(e))

    return {
        "status": "success",
        "uid": uid,
        "extracted_skills": skills,
        "top_companies": [
            {
                "company_name": r["company_name"],
                "role_title": r["role_title"],
                "experience_type": r["experience_type"],
                "min_experience": r["min_experience"],
                "match_score": r["match_score"],
                "matching_skills": split_skills(r["matching_skills"]),
                "missing_skills": split_skills(r["missing_skills"]),
            }
            for r in top
        ],
    }



# ------------------------------------------------------ recruiter API
@app.post("/api/company/register")
async def register_company(data: CompanyCreate):
    payload = {
        "company_name": data.company_name.strip(),
        "role_title": data.role_title.strip(),
        "experience_type": data.experience_type.strip(),
        "min_experience": data.min_experience,
        "skills_expected": ", ".join(format_skill(s) for s in split_skills(data.skills_expected)),
        "location": (data.location or "Remote").strip(),
    }
    try:
        with db() as conn:
            comp_id = conn.execute(
                "INSERT INTO COMPANY (company_name, role_title, experience_type, "
                "min_experience, skills_expected, location) "
                "VALUES (:company_name, :role_title, :experience_type, "
                ":min_experience, :skills_expected, :location)",
                payload,
            ).lastrowid
            comp = dict(conn.execute("SELECT * FROM COMPANY WHERE company_id = ?", (comp_id,)).fetchone())
            # Re-evaluate every existing candidate against the new requirement.
            rows = [
                _app_row(cand["uid"], split_skills(cand["skills"]),
                         cand["experience_years"], comp)
                for cand in conn.execute("SELECT uid, skills, experience_years FROM candidates")
            ]
            conn.executemany(UPSERT_APP, rows)
        return {"status": "success", "company_id": comp_id, "company_name": payload["company_name"]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/company/list")
async def list_companies():
    return fetch("SELECT * FROM COMPANY ORDER BY company_id DESC")


@app.get("/api/company/{company_id}/applicants")
async def get_company_applicants(company_id: int):
    return fetch("SELECT * FROM v_matched_profiles WHERE company_id = ? ORDER BY match_score DESC",
                 (company_id,))


# --------------------------------------------- semantic candidate search
@app.get("/api/candidates/search")
async def search_candidates(query: Optional[str] = Query(None),
                            min_experience: Optional[float] = Query(None),
                            gender: Optional[str] = Query(None),
                            work_preference: Optional[str] = Query(None)):
    """Natural-language search: rank resumes by cosine similarity to `query`.
    "STM32 Embedded systems engineer" surfaces candidates whose resume prose
    talks about the same things, not just ones listing that exact string."""
    sql, params = "SELECT * FROM candidates WHERE 1=1", []
    if min_experience is not None:
        sql += " AND experience_years >= ?"
        params.append(min_experience)
    if gender:
        sql += " AND gender = ?"
        params.append(gender)
    if work_preference:
        sql += " AND work_preference = ?"
        params.append(work_preference)
    rows = fetch(sql, params)

    q = (query or "").strip()
    if not q:
        return rows

    # Rank the filtered set by cosine(resume, query) so every row carries a
    # visible 0..1 score, even when the resume shares no keyword with `q`.
    query_vec = embed(q)
    vectors = search_vectors(rows)
    for r in rows:
        r["similarity_score"] = round(cosine(query_vec, vectors.get(r["uid"], np.zeros(EMBEDDING_DIM))), 4)
    rows.sort(key=lambda r: -r["similarity_score"])
    return rows


# ------------------------------------------------------- resume + admin
@app.get("/api/candidates/{uid}/resume")
async def get_candidate_resume(uid: str):
    if not re.fullmatch(r"[A-Za-z0-9_]+", uid):  # uid is user input: no traversal
        raise HTTPException(404, "Resume PDF not found")
    path = (DATA_DIR / f"{uid}.pdf").resolve()
    if path.parent != DATA_DIR.resolve() or not path.exists():
        raise HTTPException(404, "Resume PDF not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{uid}_resume.pdf")


TABLES = ("COMPANY", "candidates", "applications", "audit_log", "v_matched_profiles")


@app.get("/api/admin/tables")
async def get_admin_tables():
    with db() as conn:
        return {t: rows_of(conn, f"SELECT * FROM {t}") for t in TABLES}
