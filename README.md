# Talent Match — Intelligent Candidate & Company Skill Matcher

A clean, lightweight web application backed by a relational SQLite database (`talent_match.db`) and a Python FastAPI backend. It features two-way matching: candidates discover their top hiring companies along with skills to acquire, while recruiters evaluate best-suited applicants for their job vacancies.

---

## What the Project Does

1. **Candidate Registration & Career Recommendation**:
   * Applicants register their details and submit a PDF resume.
   * The system automatically parses technical skills from the resume.
   * Ranks all registered companies and displays the **Top 3 Best Companies** with the highest placement probability.
   * Clearly shows which skills match and **which missing skills to acquire** to maximize selection chances.

2. **Recruiter Requirements & Applicant Ranking**:
   * Recruiters log in or register their company with hiring criteria: hiring level (Freshers vs. Experienced, min years) and expected skills.
   * Company data is saved into the relational **`COMPANY`** table in `talent_match.db`.
   * Recruiters can view all applicants scored against their specific requirement using a database SQL VIEW / JOIN.

3. **Strict Role Separation**:
   * **Candidate Side**: Dedicated only to candidate profile registration and recommendations. No recruiter links or administrative access.
   * **Recruiter Side**: Dedicated only to recruiter login, company requirement setup, and applicant evaluation.

4. **Zero Overhead & Minimalist Architecture**:
   * Relational database stored directly in the project root as **`talent_match.db`**.
   * Clean, lightweight frontend: pure semantic HTML, minimal vanilla CSS ([styles.css](file:///c:/Users/user/OneDrive/Desktop/talent-match/styles.css)) under 250 lines, and plain vanilla JavaScript (`document.getElementById`).
   * Clean typography using system fonts (Arial Rounded MT Bold, Futura, Tahoma, Verdana).
   * Compact, readable codebase: Python backend is ~300 lines; HTML portals are ~100–150 lines each.

---

## Project Structure & File Guide

| File | Purpose / What it Contains |
|------|----------------------------|
| [talent_match.db](file:///c:/Users/user/OneDrive/Desktop/talent-match/talent_match.db) | **SQLite Database** file right in the project root containing all relational tables (`candidates`, `COMPANY`, `applications`, `audit_log`), indices, triggers, and views. |
| [main.py](file:///c:/Users/user/OneDrive/Desktop/talent-match/main.py) | **FastAPI Backend**: Database initialization, DDL/DML execution, resume text extraction, skill matching, transaction handling, and REST endpoints. |
| [candidate.html](file:///c:/Users/user/OneDrive/Desktop/talent-match/candidate.html) | **Candidate Portal**: Minimalist form for registration and PDF resume upload. Renders the Top 3 company matches and skills to acquire. |
| [recruiter_login.html](file:///c:/Users/user/OneDrive/Desktop/talent-match/recruiter_login.html) | **Recruiter Login**: Form where recruiters choose an existing company or register a new requirement into the `COMPANY` table. |
| [recruiter.html](file:///c:/Users/user/OneDrive/Desktop/talent-match/recruiter.html) | **Recruiter Portal**: View best-suited applicants for the logged-in company, search candidates by skill/name, and inspect resume PDFs. |
| [admin_db.html](file:///c:/Users/user/OneDrive/Desktop/talent-match/admin_db.html) | **Internal Evaluator / Professor Panel**: Private page to inspect live database tables, views, triggers, and new entries. Not linked from candidate or recruiter portals. |
| [api.js](file:///c:/Users/user/OneDrive/Desktop/talent-match/api.js) | **Frontend API Client**: Lightweight fetch helper functions. |
| [styles.css](file:///c:/Users/user/OneDrive/Desktop/talent-match/styles.css) | **Design System**: Lightweight, elegant minimalist UI styling (under 250 lines). |
| [DBMS_MAPPING.md](file:///c:/Users/user/OneDrive/Desktop/talent-match/DBMS_MAPPING.md) | **Academic Syllabus Mapping**: Comprehensive guide mapping the syllabus units (ER Modeling, Relational SQL, Normalization, ACID Transactions, Views, Triggers, Indexes) directly to the code. |
| [requirements.txt](file:///c:/Users/user/OneDrive/Desktop/talent-match/requirements.txt) | Python dependencies (`fastapi`, `uvicorn`, `python-multipart`, `google-genai`, `markitdown[pdf]`, `numpy`). |

---

## Relational Database Schema (`talent_match.db`)

1. **`candidates`**:
   * `uid` (TEXT, PK), `name` (TEXT), `age` (INTEGER, CHECK >= 18), `gender` (TEXT), `experience_years` (REAL, CHECK >= 0), `contact_no` (TEXT), `skills` (TEXT), `resume_path` (TEXT), `created_at` (TIMESTAMP).
2. **`COMPANY`**:
   * `company_id` (INTEGER, PK AUTOINCREMENT), `company_name` (TEXT), `role_title` (TEXT), `experience_type` (TEXT), `min_experience` (REAL), `skills_expected` (TEXT), `location` (TEXT), `created_at` (TIMESTAMP).
3. **`applications`**:
   * `id` (INTEGER, PK AUTOINCREMENT), `candidate_uid` (FK -> candidates), `company_id` (FK -> COMPANY), `match_score` (REAL), `matching_skills` (TEXT), `missing_skills` (TEXT), `status` (TEXT), `matched_at` (TIMESTAMP).
4. **`audit_log`**:
   * `log_id` (INTEGER, PK AUTOINCREMENT), `action` (TEXT), `details` (TEXT), `logged_at` (TIMESTAMP).
5. **Views & Triggers**:
   * View **`v_matched_profiles`**: Virtual 3-way join of applications, candidates, and companies.
   * Trigger **`trg_candidate_audit`**: Automatically logs candidate insertions into `audit_log`.

---

## How to Run

### Step 1: Start Backend (Port 8000)
```bash
.venv\Scripts\uvicorn main:app --port 8000 --reload
```

### Step 2: Start Frontend (Port 3000)
Open a new terminal in the `talent-match` directory:
```bash
python -m http.server 3000
```

### Step 3: Open in Browser
* **Candidate Portal**: [http://localhost:3000/candidate.html](http://localhost:3000/candidate.html)
* **Recruiter Login**: [http://localhost:3000/recruiter_login.html](http://localhost:3000/recruiter_login.html)
* **Recruiter Portal**: [http://localhost:3000/recruiter.html](http://localhost:3000/recruiter.html)
* **Database Inspector**: [http://localhost:3000/admin_db.html](http://localhost:3000/admin_db.html)
