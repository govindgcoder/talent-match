import sqlite3, re
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from markitdown import MarkItDown

# Database & File Storage paths
DB_PATH = Path("./talent_match.db")
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Talent Match API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
md = MarkItDown()

# Technical skills vocabulary
KNOWN_SKILLS = [
    "python", "java", "c++", "c", "javascript", "typescript", "html", "css",
    "react", "angular", "node.js", "express", "fastapi", "django", "flask",
    "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes", "aws", "git",
    "machine learning", "deep learning", "nlp", "pandas", "data analysis", "rest api"
]

def format_skill(s: str) -> str:
    s = s.strip()
    return s.upper() if s.lower() in ["sql", "aws", "css", "html", "nlp", "c++", "c"] else s.title()

def extract_skills(text: str):
    found = set()
    for s in KNOWN_SKILLS:
        if re.search(r'(?<![a-zA-Z0-9_#+])' + re.escape(s) + r'(?![a-zA-Z0-9_#+])', text.lower()):
            found.add(format_skill(s))
    return sorted(list(found))

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# --- Database Setup (DDL: Tables, Constraints, Indexes, Views, Triggers) ---
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. CANDIDATES Table (Entity with Primary Key & Check Constraints)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            uid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL CHECK (age >= 18),
            gender TEXT NOT NULL,
            experience_years REAL NOT NULL DEFAULT 0.0 CHECK (experience_years >= 0),
            contact_no TEXT NOT NULL,
            skills TEXT NOT NULL DEFAULT '',
            resume_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. COMPANY Table (Entity with Autoincrement PK)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS COMPANY (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            role_title TEXT NOT NULL,
            experience_type TEXT NOT NULL,
            min_experience REAL NOT NULL DEFAULT 0.0,
            skills_expected TEXT NOT NULL,
            location TEXT DEFAULT 'Remote',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. APPLICATIONS Table (Relationship Junction with Referential Integrity)
    cursor.execute("""
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
        )
    """)

    # 4. AUDIT_LOG Table (Tracks DML mutations via Triggers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 5. INDEXES (Physical Data Organization & Performance)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_exp ON candidates(experience_years)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_company_score ON applications(company_id, match_score)")

    # 6. SQL VIEW (Virtual Table for Relational 3-Way Join)
    cursor.execute("""
        CREATE VIEW IF NOT EXISTS v_matched_profiles AS
        SELECT 
            app.id AS application_id,
            cand.uid AS candidate_uid,
            cand.name AS candidate_name,
            cand.age,
            cand.gender,
            cand.experience_years,
            cand.contact_no,
            comp.company_id,
            comp.company_name,
            comp.role_title,
            comp.skills_expected,
            app.match_score,
            app.matching_skills,
            app.missing_skills,
            app.status
        FROM applications app
        JOIN candidates cand ON app.candidate_uid = cand.uid
        JOIN COMPANY comp ON app.company_id = comp.company_id
    """)

    # 7. SQL TRIGGER (Automated Execution on Candidate Insert)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_candidate_audit
        AFTER INSERT ON candidates
        BEGIN
            INSERT INTO audit_log (action, details)
            VALUES ('CANDIDATE_REGISTERED', 'New applicant added: ' || NEW.name);
        END;
    """)

    # Seed starter companies if empty
    cursor.execute("SELECT COUNT(*) FROM COMPANY")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO COMPANY (company_name, role_title, experience_type, min_experience, skills_expected, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("Google", "Full Stack AI Engineer", "Experienced", 2.0, "Python, React, FastAPI, Machine Learning, Docker, SQL", "Bangalore / Remote"),
            ("Microsoft", "Junior Python Developer", "Fresher", 0.0, "Python, SQL, HTML, CSS, Git", "Hyderabad / Remote"),
            ("Amazon", "Cloud Backend Engineer", "Experienced", 3.0, "Python, AWS, PostgreSQL, Docker, REST API", "Pune / Remote"),
            ("Tesla", "Embedded & AI Specialist", "Experienced", 2.0, "C++, Python, RTOS, Machine Learning", "Bangalore / Hybrid"),
            ("Deloitte", "Data Analyst", "Fresher", 0.0, "Python, SQL, Pandas, Data Analysis, Git", "Mumbai / Remote")
        ])

    conn.commit()
    conn.close()

init_db()

def compute_match(cand_skills, cand_exp, comp_skills_str, min_exp):
    expected = [format_skill(s) for s in comp_skills_str.split(",") if s.strip()]
    c_set = {s.lower() for s in cand_skills}
    matching = [s for s in expected if s.lower() in c_set]
    missing = [s for s in expected if s.lower() not in c_set]
    skill_pct = len(matching) / len(expected) if expected else 1.0
    exp_factor = 1.0 if cand_exp >= min_exp or min_exp == 0 else max(0.65, cand_exp / min_exp)
    return round(min(100.0, (skill_pct * 0.75 + exp_factor * 0.25) * 100), 1), matching, missing

def sync_matches_for_candidate(conn, uid, cand_skills, cand_exp):
    companies = conn.execute("SELECT * FROM COMPANY").fetchall()
    for c in companies:
        score, matching, missing = compute_match(cand_skills, cand_exp, c["skills_expected"], c["min_experience"])
        conn.execute("""
            INSERT OR REPLACE INTO applications 
            (candidate_uid, company_id, match_score, matching_skills, missing_skills)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, c["company_id"], score, ", ".join(matching), ", ".join(missing)))

class CompanyCreate(BaseModel):
    company_name: str
    role_title: str
    experience_type: str = "Fresher"
    min_experience: float = 0.0
    skills_expected: str
    location: Optional[str] = "Remote"

# --- Candidate API (Isolated from Recruiter & DB Admin) ---
@app.post("/api/candidates/upload")
async def upload_candidate(
    name: str = Form(...), age: int = Form(...), gender: str = Form(...),
    experience_years: float = Form(...), contact_no: str = Form(...),
    resume_file: UploadFile = File(...)
):
    uid = f"{name.strip().split()[0].lower()}_{''.join(filter(str.isalnum, contact_no))}"
    file_path = DATA_DIR / f"{uid}.pdf"
    with open(file_path, "wb") as f:
        f.write(await resume_file.read())

    try:
        extracted_text = md.convert(str(file_path)).text_content
    except Exception:
        extracted_text = name

    skills = extract_skills(extracted_text)
    conn = get_db()
    try:
        # Atomic Transaction
        conn.execute("""
            INSERT OR REPLACE INTO candidates (uid, name, age, gender, experience_years, contact_no, skills, resume_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, name.strip(), age, gender, experience_years, contact_no.strip(), ", ".join(skills), str(file_path)))
        sync_matches_for_candidate(conn, uid, skills, experience_years)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    # Top 3 Companies query using JOIN
    top = conn.execute("""
        SELECT c.company_name, c.role_title, c.experience_type, c.min_experience,
               a.match_score, a.matching_skills, a.missing_skills
        FROM applications a JOIN COMPANY c ON a.company_id = c.company_id
        WHERE a.candidate_uid = ? ORDER BY a.match_score DESC LIMIT 3
    """, (uid,)).fetchall()
    conn.close()

    return {
        "status": "success", "uid": uid, "extracted_skills": skills,
        "top_companies": [{
            "company_name": r["company_name"], "role_title": r["role_title"],
            "experience_type": r["experience_type"], "min_experience": r["min_experience"],
            "match_score": r["match_score"],
            "matching_skills": [s.strip() for s in r["matching_skills"].split(",") if s.strip()],
            "missing_skills": [s.strip() for s in r["missing_skills"].split(",") if s.strip()]
        } for r in top]
    }

# --- Recruiter API (Company Setup, Suited Applicants & Search) ---
@app.post("/api/company/register")
async def register_company(data: CompanyCreate):
    conn = get_db()
    cleaned_skills = ", ".join([format_skill(s) for s in data.skills_expected.split(",") if s.strip()])
    try:
        cur = conn.execute("""
            INSERT INTO COMPANY (company_name, role_title, experience_type, min_experience, skills_expected, location)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data.company_name.strip(), data.role_title.strip(), data.experience_type.strip(), data.min_experience, cleaned_skills, data.location.strip()))
        comp_id = cur.lastrowid
        # Re-evaluate all existing candidates
        for cand in conn.execute("SELECT uid, skills, experience_years FROM candidates").fetchall():
            c_skills = [s.strip() for s in cand["skills"].split(",") if s.strip()]
            score, matching, missing = compute_match(c_skills, cand["experience_years"], cleaned_skills, data.min_experience)
            conn.execute("""
                INSERT OR REPLACE INTO applications (candidate_uid, company_id, match_score, matching_skills, missing_skills)
                VALUES (?, ?, ?, ?, ?)
            """, (cand["uid"], comp_id, score, ", ".join(matching), ", ".join(missing)))
        conn.commit()
        return {"status": "success", "company_id": comp_id, "company_name": data.company_name}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/company/list")
async def list_companies():
    conn = get_db()
    res = [dict(r) for r in conn.execute("SELECT * FROM COMPANY ORDER BY company_id DESC").fetchall()]
    conn.close()
    return res

@app.get("/api/company/{company_id}/applicants")
async def get_company_applicants(company_id: int):
    conn = get_db()
    # Uses SQL VIEW v_matched_profiles
    res = [dict(r) for r in conn.execute("""
        SELECT * FROM v_matched_profiles WHERE company_id = ? ORDER BY match_score DESC
    """, (company_id,)).fetchall()]
    conn.close()
    return res

@app.get("/api/candidates/search")
async def search_candidates(query: Optional[str] = Query(None), min_experience: Optional[float] = Query(None), gender: Optional[str] = Query(None)):
    conn = get_db()
    sql = "SELECT * FROM candidates WHERE 1=1"
    params = []
    if min_experience is not None:
        sql += " AND experience_years >= ?"
        params.append(min_experience)
    if gender:
        sql += " AND gender = ?"
        params.append(gender)
    if query and query.strip():
        sql += " AND (name LIKE ? OR skills LIKE ?)"
        q = f"%{query.strip()}%"
        params.extend([q, q])
    res = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return res

@app.get("/api/candidates/{uid}/resume")
async def get_candidate_resume(uid: str):
    file_path = DATA_DIR / f"{uid}.pdf"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume PDF not found")
    return FileResponse(path=file_path, media_type="application/pdf", filename=f"{uid}_resume.pdf")

@app.get("/api/admin/tables")
async def get_admin_tables():
    conn = get_db()
    res = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()] for t in ["COMPANY", "candidates", "applications", "audit_log", "v_matched_profiles"]}
    conn.close()
    return res