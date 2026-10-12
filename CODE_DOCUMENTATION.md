# Talent Match — Complete Code Documentation

**Intelligent Candidate ↔ Company Skill Matching System**

Full technical reference for the Talent Match codebase: architecture, database schema, every endpoint, matching algorithm, transaction semantics, security posture, and extension points. Written to be read top-to-bottom alongside `DBMS_MAPPING.md` (syllabus mapping) and `README.md` (run instructions).

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [File Inventory](#3-file-inventory)
4. [The Database (`talent_match.db`)](#4-the-database-talent_matchdb)
5. [Backend: `main.py` Line-by-Line](#5-backend-mainpy-line-by-line)
6. [API Reference](#6-api-reference)
7. [Frontend Portals](#7-frontend-portals)
8. [Matching Algorithm (Scoring Model)](#8-matching-algorithm-scoring-model)
9. [Transactions & Concurrency](#9-transactions--concurrency)
10. [Physical Data Organization & Indexing](#10-physical-data-organization--indexing)
11. [Security Considerations](#11-security-considerations)
12. [Known Limitations & Failure Envelopes](#12-known-limitations--failure-envelopes)
13. [Extension Roadmap](#13-extension-roadmap)
14. [Syllabus Concept → Code Index](#14-syllabus-concept--code-index)

---

## 1. System Overview

**Talent Match** is a three-tier web application that performs two-way skill matching:

- **Candidate side** — register, upload a PDF resume, auto-extract skills, receive a ranked Top-3 company recommendation list with *missing skills to acquire*.
- **Recruiter side** — register/login a company with hiring criteria, then view all candidates ranked by match score against that specific requirement.
- **Admin side (hidden)** — a live database inspector exposing tables, the view, and the trigger log for evaluators.

| Property | Value |
|---|---|
| Backend | Python 3 + FastAPI (`main.py`, 326 lines) |
| Database | SQLite file `talent_match.db` (WAL-capable, single-file, zero-config) |
| ORM | None — raw `sqlite3` with parameterized queries |
| Frontend | Static HTML + vanilla CSS + vanilla ES-module JavaScript (no build step) |
| Resume parsing | `markitdown[pdf]` → plaintext → regex skill extraction |
| HTTP ports | Backend `:8000`, Frontend static server `:3000` |
| Total LOC | ~1,650 across all source files |

### Core Design Principles

1. **Zero-overhead architecture** — no ORM, no framework frontend, no bundler.
2. **Role isolation** — candidate portal never links to recruiter/admin; recruiter portal never links to admin.
3. **Constraint-first integrity** — validity enforced in DDL (`CHECK`, `NOT NULL`, `FOREIGN KEY`, `UNIQUE`), not only in UI validation.
4. **Explicit transactions** — multi-statement writes wrapped in `commit()`/`rollback()` blocks.
5. **Semantic transparency** — schema, view, trigger, and index DDL are all visible in `init_db()` for academic inspection.

---

## 2. Architecture & Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  BROWSER (static server, port 3000)                              │
│                                                                  │
│  candidate.html ─┐                                               │
│  recruiter.html ─┼──► api.js (fetch wrappers, ES modules)        │
│  recruiter_login─┤                                               │
│  admin_db.html ──┘                                               │
│         │  multipart/form-data  or  application/json             │
└─────────┼────────────────────────────────────────────────────────┘
          │  CORS (allow_origins: ["*"])
          ▼
┌──────────────────────────────────────────────────────────────────┐
│  FASTAPI (uvicorn, port 8000)  — main.py                        │
│                                                                  │
│  upload_candidate ──► save PDF ──► MarkItDown ──► extract_skills │
│          │                                                      │
│          ▼                                                      │
│  get_db() ──► BEGIN TRANSACTION                                  │
│               1. INSERT OR REPLACE INTO candidates              │
│               2. sync_matches_for_candidate()                   │
│                     for each COMPANY row:                       │
│                        compute_match()                          │
│                        INSERT OR REPLACE INTO applications      │
│               COMMIT  (or ROLLBACK on any exception)            │
└──────────┬───────────────────────────────────────────────────────┘
           │  sqlite3 driver, parameter binding (?)
           ▼
┌──────────────────────────────────────────────────────────────────┐
│  talent_match.db  (SQLite B-Tree file)                          │
│  Tables: candidates, COMPANY, applications, audit_log           │
│  Index:  idx_candidates_exp, idx_app_company_score              │
│  View:   v_matched_profiles                                     │
│  Trigger: trg_candidate_audit  ──► audit_log                    │
└──────────────────────────────────────────────────────────────────┘
```

### End-to-End Data Flow (candidate registration)

1. `candidate.html` validates client-side (age ≥ 18, ≥10-digit phone, `.pdf` extension).
2. `api.js: uploadCandidate()` posts `FormData` to `/api/candidates/upload`.
3. Backend derives a deterministic `uid` = `{first_name}_{digits_of_phone}` (e.g. `alex_9876543210`).
4. Raw PDF bytes are written to `./data/{uid}.pdf` (unstructured store).
5. `MarkItDown` converts PDF → plaintext; `extract_skills()` regex-matches against a 28-entry `KNOWN_SKILLS` vocabulary.
6. Transaction opens:
   - `INSERT OR REPLACE INTO candidates` (upsert keyed on `uid`).
   - For every company: `compute_match()` → score stored via `INSERT OR REPLACE INTO applications`.
   - **AFTER INSERT trigger** `trg_candidate_audit` fires → writes to `audit_log`.
7. `conn.commit()` — all-or-nothing.
8. Top-3 query via `JOIN applications × COMPANY ORDER BY match_score DESC LIMIT 3`.
9. Response JSON → rendered as ranked cards showing matched and missing skills.

### Concurrency / State Model

- **Stateless backend** — every request opens its own `sqlite3.connect(DB_PATH)`; no connection pooling, no session memory.
- **Stateful frontend** — recruiter identity stored in `localStorage.activeCompany` (a JSON blob) to survive page navigation without server sessions.
- **Locking** — SQLite default journal mode with `PRAGMA foreign_keys = ON`; single-writer lock means concurrent writes serialize (this is a feature, not a bottleneck, at this scale).

### Complexity

| Operation | Time | Notes |
|---|---|---|
| Skill extraction | O(K·L) | K = 28 known skills, L = resume length (regex per skill) |
| Match computation | O(C·S) | C = companies, S = skills per company |
| Ranked top-3 lookup | O(log N + log M) | B-Tree index on `(company_id, match_score)` |
| Semantic search | O(F·D) | F = filtered rows, D = embedding dim (3072); one API call + F dot-products |

---

## 3. File Inventory

| File | LOC | Role |
|---|---|---|
| `main.py` | 461 | FastAPI app; DDL bootstrap; 7 REST endpoints; skill extraction; keyword scoring; Gemini vector search; transactions |
| `candidate.html` | 152 | Candidate registration form + Top-3 results renderer |
| `recruiter_login.html` | 158 | Company select / new-company registration form |
| `recruiter.html` | 149 | Applicant evaluation grid, search bar, resume viewer |
| `admin_db.html` | 94 | Live DB inspector: 5 tabs (tables, view, trigger log) |
| `api.js` | 65 | 5 fetch wrappers (`uploadCandidate`, `registerCompany`, `getCompanyList`, `getCompanyApplicants`, `searchCandidates`, `getResumeUrl`) |
| `index.html` | 89 | Project home — links to the Candidate, Recruiter and Admin portals |
| `styles.css` | 331 | Design system: cards, forms, buttons, badges, tables |
| `talent_match.db` | 40 KB | SQLite database file |
| `DBMS_MAPPING.md` | 162 | Syllabus → code conceptual mapping |
| `README.md` | 82 | Quick-start run guide |
| `seed.py` | 250 | Seeds 6 candidates (Govind G, Karthik M Raj, Vinayak H, Rahul Menon, Ananya Sharma, Sneha Iyer) spanning engineering, DevOps, marketing and UI/UX — each with a generated resume PDF, extracted skills and a cached embedding |
| `requirements.txt` | 7 | `fastapi, uvicorn, python-multipart, google-genai, markitdown[pdf], numpy, python-dotenv` |
| `./data/{uid}.pdf` | — | Uploaded resumes (unstructured store, git-ignored) |

---

## 4. The Database (`talent_match.db`)

### 4.1 Entity-Relationship Overview

```
 ┌────────────────────┐            ┌────────────────────┐
 │     CANDIDATE      │            │      COMPANY       │
 ├────────────────────┤            ├────────────────────┤
 │ uid (PK, TEXT)     │            │ company_id (PK, AI)│
 │ name               │            │ company_name       │
 │ age  CHECK >= 18   │            │ role_title         │
 │ gender             │            │ experience_type    │
 │ experience_years   │            │ min_experience     │
 │ contact_no         │            │ skills_expected    │
 │ skills (CSV)       │            │ location           │
 │ resume_path        │            │ created_at         │
 │ created_at         │            └─────────┬──────────┘
 └─────────┬──────────┘                      │
           │            ┌────────────────────┤
           │            │    APPLICATIONS    │
           └────────────┤  (M:N junction)    │
            FK ON DELETE │                    │
             CASCADE     │ id (PK, AI)        │
                         │ candidate_uid (FK) │
                         │ company_id (FK)    │
                         │ match_score        │
                         │ matching_skills    │
                         │ missing_skills     │
                         │ status             │
                         │ matched_at         │
                         │ UNIQUE(cand, comp) │
                         └────────────────────┘

 ┌────────────────────┐      ┌─────────────────────────────┐
 │     AUDIT_LOG      │      │  v_matched_profiles (VIEW)  │
 ├────────────────────┤      │  3-way JOIN, virtual table  │
 │ log_id (PK, AI)    │      └─────────────────────────────┘
 │ action             │
 │ details            │      trg_candidate_audit (TRIGGER)
 │ logged_at          │      AFTER INSERT ON candidates
 └────────────────────┘      → INSERT INTO audit_log
```

### 4.2 Table: `candidates`

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `uid` | `TEXT` | **PRIMARY KEY** | Deterministic id: `{first_name_lower}{phone_digits}` |
| `name` | `TEXT` | `NOT NULL` | Full legal name |
| `age` | `INTEGER` | `NOT NULL CHECK (age >= 18)` | Domain constraint — adult only |
| `gender` | `TEXT` | `NOT NULL` | `male` / `female` / `other` |
| `experience_years` | `REAL` | `NOT NULL DEFAULT 0.0 CHECK (experience_years >= 0)` | Non-negative work experience |
| `contact_no` | `TEXT` | `NOT NULL` | 10-digit phone |
| `skills` | `TEXT` | `NOT NULL DEFAULT ''` | Comma-separated extracted skills (semi-structured) |
| `resume_path` | `TEXT` | `NOT NULL` | Filesystem path to unstructured PDF |
| `work_preference` | `TEXT` | `NOT NULL DEFAULT 'Flexible'` | `Remote` \| `Hybrid` \| `On-site` \| `Flexible` — added by migration |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Registration time |

> **Migration (module 1 — physical organisation):** `init_db()` runs an idempotent check on every boot —
> `PRAGMA table_info(candidates)` → if `work_preference` absent, `ALTER TABLE ... ADD COLUMN` with the
> `'Flexible'` default, then `DROP VIEW IF EXISTS v_matched_profiles` + recreate so the view picks up
> the new column. Existing rows are back-filled by the `DEFAULT`, satisfying `NOT NULL` in one statement.

### 4.3 Table: `COMPANY`

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `company_id` | `INTEGER` | **PRIMARY KEY AUTOINCREMENT** | Surrogate key |
| `company_name` | `TEXT` | `NOT NULL` | Recruiter's org name |
| `role_title` | `TEXT` | `NOT NULL` | Job designation |
| `experience_type` | `TEXT` | `NOT NULL` | `Fresher` \| `Experienced` |
| `min_experience` | `REAL` | `NOT NULL DEFAULT 0.0` | Minimum years gate |
| `skills_expected` | `TEXT` | `NOT NULL` | Comma-separated required skills |
| `location` | `TEXT` | `DEFAULT 'Remote'` | Work location |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Posting time |

### 4.4 Table: `applications` (M:N junction)

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Surrogate application id |
| `candidate_uid` | `TEXT` | `NOT NULL`, **FK → candidates.uid ON DELETE CASCADE** | Dangling-reference prevention |
| `company_id` | `INTEGER` | `NOT NULL`, **FK → COMPANY.company_id ON DELETE CASCADE** | Dangling-reference prevention |
| `match_score` | `REAL` | `NOT NULL` | 0–100 computed score |
| `matching_skills` | `TEXT` | `NOT NULL` | CSV of skills that matched |
| `missing_skills` | `TEXT` | `NOT NULL` | CSV of skills to acquire |
| `status` | `TEXT` | `DEFAULT 'Recommended'` | Workflow state |
| `matched_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Score computation time |
| — | — | **`UNIQUE(candidate_uid, company_id)`** | Prevents duplicate scoring pairs |

### 4.5 Table: `audit_log`

| Column | Type | Constraints |
|---|---|---|
| `log_id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` |
| `action` | `TEXT` | `NOT NULL` (e.g. `CANDIDATE_REGISTERED`) |
| `details` | `TEXT` | `NOT NULL` (e.g. `New applicant added: Alex`) |
| `logged_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` |

> Only one action type is currently emitted (`CANDIDATE_REGISTERED`), because only one trigger exists. Extending triggers to `UPDATE`/`DELETE` on all four tables would turn this into a full write-ahead audit trail.

### 4.6 Integrity Constraints Summary

| Constraint | Class | Location |
|---|---|---|
| `uid TEXT PRIMARY KEY` | Entity integrity | `candidates` |
| `company_id INTEGER PRIMARY KEY` | Entity integrity | `COMPANY` |
| `FOREIGN KEY(candidate_uid) REFERENCES candidates(uid)` | Referential integrity | `applications` |
| `FOREIGN KEY(company_id) REFERENCES COMPANY(company_id)` | Referential integrity | `applications` |
| `ON DELETE CASCADE` (both FKs) | Referential integrity | `applications` |
| `CHECK (age >= 18)` | Domain integrity | `candidates` |
| `CHECK (experience_years >= 0)` | Domain integrity | `candidates` |
| `NOT NULL` on every non-timestamp column | Entity integrity | all tables |
| `UNIQUE(candidate_uid, company_id)` | Key integrity | `applications` |
| `PRAGMA foreign_keys = ON` | Runtime enforcement | `get_db()` |

> **Critical implementation note:** SQLite disables foreign-key enforcement *per-connection* by default. The pragma in `get_db()` (`main.py:134`) is what actually makes `ON DELETE CASCADE` real. Without it the FK clauses are parsed but never checked.

---

## 5. Backend: `main.py` Line-by-Line

### 5.1 Module Setup (`main.py:1-60`)

```python
DB_PATH = Path("./talent_match.db")     # single-file DB at repo root
DATA_DIR = Path("./data")               # unstructured resume store
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Talent Match API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)   # dev-only wildcard
md = MarkItDown()                        # PDF → plaintext converter instance
```

- **`KNOWN_SKILLS`** (`main.py:33-42`) — 52-token closed vocabulary: languages, frameworks, databases, infra, ML topics. Everything not in this list is invisible to the matcher.
- **`format_skill()`** (`main.py:44-47`) — canonical casing: `SQL`, `AWS`, `CSS`, `HTML`, `NLP`, `C++`, `C` uppercase; everything else Title Case. Prevents `"python"` vs `"Python"` from being treated as different skills.
- **`extract_skills(text)`** (`main.py:53-59`) — for each known skill, runs a boundary-aware regex:
  ```python
  re.search(r'(?<![a-zA-Z0-9_#+])' + re.escape(s) + r'(?![a-zA-Z0-9_#+])', text.lower())
  ```
  The lookbehind/lookahead prevents `"c"` from matching inside `"csv"` or `"react"` from matching inside `"reactnative"`. Returns a **sorted** list for deterministic output.
- **`get_db()`** (`main.py:131-135`) — new connection per call, `Row` factory (dict-like access), `PRAGMA foreign_keys = ON`.

### 5.2 Schema + `init_db()` (`main.py:161-251`)

Executed **once at import time** (`main.py:251`), idempotent via `IF NOT EXISTS` everywhere.

| Step | DDL | Lines |
|---|---|---|
| 1 | `CREATE TABLE candidates` | 50-62 |
| 2 | `CREATE TABLE COMPANY` | 65-76 |
| 3 | `CREATE TABLE applications` (FKs + UNIQUE) | 79-93 |
| 4 | `CREATE TABLE audit_log` | 96-103 |
| 5 | `CREATE INDEX idx_candidates_exp ON candidates(experience_years)` | 106 |
| 6 | `CREATE INDEX idx_app_company_score ON applications(company_id, match_score)` | 107 |
| 7 | `CREATE VIEW v_matched_profiles` (3-way JOIN) | 110-131 |
| 8 | `CREATE TRIGGER trg_candidate_audit AFTER INSERT ON candidates` | 134-141 |
| 9 | Seed 5 companies if `COUNT(*) = 0` | 143-155 |

**Seed data** (only on a fresh database): Google, Microsoft, Amazon, Tesla, Deloitte — covering both Fresher and Experienced paths so a new installation is immediately demonstrable.

**The Trigger** (`main.py:205-211`):
```sql
CREATE TRIGGER IF NOT EXISTS trg_candidate_audit
AFTER INSERT ON candidates
BEGIN
    INSERT INTO audit_log (action, details)
    VALUES ('CANDIDATE_REGISTERED', 'New applicant added: ' || NEW.name);
END;
```
- Event-driven; `NEW` is the row just inserted. No Python code touches `audit_log`.
- Note: because `INSERT OR REPLACE` is used in the upload path, SQLite treats a REPLACE as `DELETE` + `INSERT` when a PK conflict occurs — so the trigger **does** fire on re-upload of an existing candidate (creating a second audit row).

**The View** (`main.py:212-220`) — `v_matched_profiles` flattens the 3-way join into one virtual table with columns: `application_id, candidate_uid, candidate_name, age, gender, experience_years, contact_no, company_id, company_name, role_title, skills_expected, match_score, matching_skills, missing_skills, status`.

### 5.3 `compute_match()` — Scoring Function (`main.py:263-270`)

```python
def compute_match(cand_skills, cand_exp, comp_skills_str, min_exp):
    expected   = [format_skill(s) for s in comp_skills_str.split(",") if s.strip()]
    c_set      = {s.lower() for s in cand_skills}
    matching   = [s for s in expected if s.lower() in c_set]
    missing    = [s for s in expected if s.lower() not in c_set]
    skill_pct  = len(matching) / len(expected) if expected else 1.0
    exp_factor = 1.0 if cand_exp >= min_exp or min_exp == 0 \
                 else max(0.65, cand_exp / min_exp)
    return round(min(100.0, (skill_pct * 0.75 + exp_factor * 0.25) * 100), 1), matching, missing
```

**Formula:** `score = min(100, (0.75 × skill_match_ratio + 0.25 × experience_factor) × 100)`

- Skills dominate (75% weight); experience gates 25%.
- `exp_factor` is **floored at 0.65** — a candidate slightly under the requirement still scores at least 65% of the experience component (soft gate, not hard reject).
- `min_exp == 0` short-circuits to `1.0` (freshers).
- Returns `(score, matching_list, missing_list)` as a 3-tuple.

**Worked example:** Candidate with `Python, SQL, Docker`, 1.5 yrs vs Google (`Python, React, FastAPI, Machine Learning, Docker, SQL`, min 2.0):
- `matching = [Python, Docker, SQL]` → `skill_pct = 3/6 = 0.5`
- `exp_factor = max(0.65, 1.5/2.0) = 0.75`
- `score = (0.5×0.75 + 0.75×0.25)×100 = (0.375 + 0.1875)×100 = 56.3`

### 5.4 `sync_matches()` (`main.py:274-282`)

Reads all `COMPANY` rows, computes a score for each, then upserts:
```python
INSERT OR REPLACE INTO applications (candidate_uid, company_id, match_score, matching_skills, missing_skills)
VALUES (?, ?, ?, ?, ?)
```
- Runs **inside the caller's transaction** — candidate + all applications commit atomically.
- `INSERT OR REPLACE` + the `UNIQUE(candidate_uid, company_id)` constraint = idempotent re-scoring.

### 5.5 Pydantic Model (`main.py:285-293`)

`CompanyCreate` — validated request body for company registration: `company_name`, `role_title`, `experience_type` (default `"Fresher"`), `min_experience` (default `0.0`), `skills_expected`, `location` (default `"Remote"`).

---

## 6. API Reference

Base URL: `http://localhost:8000`

### 6.1 `POST /api/candidates/upload`

Multi-part form upload. Registers a candidate, parses resume, scores against all companies.

**Request (FormData):**

| Field | Type | Required |
|---|---|---|
| `name` | text | ✅ |
| `age` | int | ✅ (must be ≥18 at DDL level) |
| `gender` | text | ✅ |
| `experience_years` | float | ✅ |
| `contact_no` | text | ✅ |
| `resume_file` | PDF file | ✅ |

**Processing pipeline** (`main.py:300-330`):
1. `uid = f"{name.split()[0].lower()}_{digits(contact_no)}"` (deterministic upsert key)
2. Write PDF → `./data/{uid}.pdf`
3. `md.convert(path).text_content` → `extract_skills()` (fallback: name, on parse failure)
4. **Transaction**: `INSERT OR REPLACE candidates` + `sync_matches_for_candidate` → `commit()`; any exception → `rollback()` + HTTP 500
5. Top-3 query with `JOIN ... ORDER BY match_score DESC LIMIT 3`

**Response:**
```json
{
  "status": "success",
  "uid": "alex_9876543210",
  "extracted_skills": ["Docker", "Python", "SQL"],
  "top_companies": [
    {
      "company_name": "Google",
      "role_title": "Full Stack AI Engineer",
      "experience_type": "Experienced",
      "min_experience": 2.0,
      "match_score": 56.3,
      "matching_skills": ["Python", "Docker", "SQL"],
      "missing_skills": ["React", "FastAPI", "Machine Learning"]
    }
  ]
}
```

### 6.2 `POST /api/company/register`

JSON body (`CompanyCreate`). Registers a company and **re-scores every existing candidate** against it.

- `INSERT INTO COMPANY` → captures `cur.lastrowid`
- Loops over all `candidates` rows, computes match, `INSERT OR REPLACE` into `applications`
- Single `commit()`; rollback on exception; `finally: conn.close()`

**Response:** `{ "status": "success", "company_id": 6, "company_name": "Nvidia" }`

### 6.3 `GET /api/company/list`

Returns all companies `ORDER BY company_id DESC` as a JSON array. Used to populate the recruiter "select existing company" dropdown.

### 6.4 `GET /api/company/{company_id}/applicants`

```sql
SELECT * FROM v_matched_profiles WHERE company_id = ? ORDER BY match_score DESC
```
Uses the **SQL VIEW** — this is the endpoint the recruiter portal calls for "View Best Suited Applicants". Served by the `(company_id, match_score)` index.

### 6.5 `GET /api/candidates/search?query=&min_experience=&gender=&work_preference=`

Two-stage: a **parameterised SQL facet filter**, then a **cosine re-rank** over Gemini embeddings.

```python
sql = "SELECT * FROM candidates WHERE 1=1"
if min_experience is not None: sql += " AND experience_years >= ?"; params.append(...)
if gender:                      sql += " AND gender = ?";          params.append(...)
if work_preference:            sql += " AND work_preference = ?";  params.append(...)
rows = fetch(sql, params)                 # stage 1: structured facets

if q := query.strip():
    qv = embed(q)                          # stage 2: one Gemini call
    vectors = search_vectors(rows)         # cached per uid, backfills stale rows
    for r in rows:
        r["similarity_score"] = round(cosine(qv, vectors[r["uid"]]), 4)
    rows.sort(key=lambda r: -r["similarity_score"])
```

`WHERE 1=1` is a no-op that simplifies `AND` concatenation. Every facet value is bound as a parameter — no string interpolation of user input.

**Why cosine rather than `LIKE`:** `"STM32 Embedded systems engineer"` matches Govind's resume on *prose*, not on a literal substring. His biodata never contains that exact phrase, yet he ranks first (0.66) because the vector sits near the query. A `LIKE '%STM32%'` scan would miss Karthik entirely even though he works on ESP32 sensor-fusion hardware.

**`similarity_score`** is returned in `0..1` on every row and rendered as a `% Vector` badge by `recruiter.html` — including `0.0` for a candidate whose resume shares nothing with the query.

### 6.6 `GET /api/candidates/{uid}/resume`

Returns `./data/{uid}.pdf` as `FileResponse` with `media_type="application/pdf"`. 404 if absent.

### 6.7 `GET /api/admin/tables`

Fan-out query over 5 relations, used by the DB inspector:
```python
{t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()]
 for t in ["COMPANY","candidates","applications","audit_log","v_matched_profiles"]}
```
> ⚠️ The `f-string` is safe **only** because `t` comes from a hardcoded list, never from user input. This pattern must never be generalized to accept a request parameter.

### Endpoint Summary Table

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| 1 | POST | `/api/candidates/upload` | none | Register candidate + score |
| 2 | POST | `/api/company/register` | none | Create company + re-score all |
| 3 | GET | `/api/company/list` | none | List companies |
| 4 | GET | `/api/company/{id}/applicants` | none | Ranked applicants (view) |
| 5 | GET | `/api/candidates/search` | none | Filter candidates |
| 6 | GET | `/api/candidates/{uid}/resume` | none | Serve PDF |
| 7 | GET | `/api/admin/tables` | none | Full DB dump |

---

## 7. Frontend Portals

### 7.1 `candidate.html` — Candidate Portal

- Single card layout with `Registration Form`.
- **Client-side validation** mirrors DDL constraints (age ≥ 18, non-negative experience, 10-digit phone, `.pdf` extension) for fast feedback — but the DB re-checks via `CHECK` (defense in depth).
- On submit → disables button, shows "Processing Resume..." → calls `uploadCandidate()`.
- Renders **Top 3 Best Companies** as ranked cards: rank number, match % badge, matched skills (green), missing skills (amber "Skills to Acquire" box).
- **Isolation:** contains no links to recruiter or admin pages.

### 7.2 `recruiter_login.html` — Company Select / Register

Two paths in one screen:
1. **Select existing** — `<select>` populated from `GET /api/company/list`; `Login` button writes `localStorage.activeCompany` and redirects to `recruiter.html`.
2. **Register new** — form → `POST /api/company/register`; on success, also writes `localStorage.activeCompany` and redirects.

Conditional UI: the "Min Experience" input only appears when `Hiring Level = Experienced` (toggle listener at `recruiter_login.html:96-99`).

### 7.3 `recruiter.html` — Applicant Evaluation

- **Company banner** reads `localStorage.activeCompany`; falls back to Google (`company_id: 1`) if unset.
- **"View Best Suited Applicants"** → `GET /api/company/{id}/applicants` (the view).
- **Search bar** → `GET /api/candidates/search?query=...`; Enter key also triggers.
- **Candidate cards** show name, match badge, experience, age, gender, contact, matched/missing skills, plus two actions: *View Resume PDF* (opens endpoint) and *Copy Contact* (clipboard).
- `renderCandidates()` handles the empty state ("No Applicants Found").

### 7.4 `admin_db.html` — Database Inspector (hidden)

- 5 tab-chips: `COMPANY`, `candidates`, `applications`, `v_matched_profiles (VIEW)`, `audit_log (TRIGGER)`.
- Fetches `GET /api/admin/tables` once, renders dynamically by building `<thead>` from `Object.keys(rows[0])`.
- `↻ Refresh` re-fetches. Not linked from any other page — intended for evaluators.
- Demonstrates that the **view returns joined rows** and the **trigger has populated audit_log**.

### 7.5 `api.js` — Client Transport Layer

Five exported functions; all normalize errors by throwing `Error(err.detail)`. `getResumeUrl()` builds a direct link rather than fetching binary through JSON.

### 7.6 `styles.css` — Design System (331 lines)

| Token | Value | Usage |
|---|---|---|
| Card | `#fff`, `1px #e2e8f0`, `radius 12px` | `.card` |
| Primary button | `#5a4ff5` → hover `#493ecc` | `.btn-primary` |
| Accent / match badge | `bg #eef2ff`, `border #c7d2fe`, `text #4338ca` | `.match-badge` |
| Active tab | `bg #eef2ff`, `border #6366f1` | `.tab-chip.active` |
| Body font | Tahoma, Verdana | global |
| Heading font | Arial Rounded MT Bold, Futura | h1-h3 |

Responsive: `.form-row` collapses to one column below 520px; `.container-wide` maxes at 880px.

---

## 8. Matching Algorithm (Scoring Model)

There are **two distinct scoring paths** — they are not interchangeable:

| Path | Triggered by | Input | Output | Used by |
|---|---|---|---|---|
| **Keyword `compute_match`** | Company registration / upload | CSV skills + experience floats | `match_score` %, `matching_skills`, `missing_skills` | `v_matched_profiles`, "Best Suited Applicants" |
| **Cosine vector search** | Recruiter free-text query | Natural-language prose | `similarity_score` ∈ 0..1 | `/api/candidates/search`, `% Vector` badge |

Company scoring stays keyword-based on purpose: it must name *which* skills matched and which are missing,
and it must produce a human-predictable percentage. A cosine value cannot be decomposed into a per-skill
explanation, so swapping it in would destroy `matching_skills`/`missing_skills` and the hand-derivable
worked example below.

### 8.1 Keyword path — worked derivation

Full worked derivation (recruiter can predict scores by hand):

```
Inputs:
  cand_skills = {python, sql, docker}
  cand_exp    = 1.5
  expected    = [Python, React, FastAPI, Machine Learning, Docker, SQL]
  min_exp     = 2.0

Step 1 — Set intersection (case-insensitive):
  matching = [Python, Docker, SQL]        → 3
  missing  = [React, FastAPI, Machine Learning] → 3

Step 2 — Skill ratio:
  skill_pct = 3 / 6 = 0.50

Step 3 — Experience factor (floored):
  1.5 < 2.0, min_exp != 0
  exp_factor = max(0.65, 1.5 / 2.0) = max(0.65, 0.75) = 0.75

Step 4 — Weighted combination:
  raw = (0.50 × 0.75) + (0.75 × 0.25)
      = 0.375 + 0.1875
      = 0.5625
  score = min(100, 0.5625 × 100) = 56.3
```

**Properties:**
- **Monotonic** in both skill overlap and experience.
- **Bounded** to `[0, 100]` via `min()`.
- **Never zero for qualified-ish candidates** — the 0.65 floor means experience shortfall alone cannot drag the experience component below 65%.
- **100% cap reached** when all skills match and experience meets min (`1.0×0.75 + 1.0×0.25 = 1.0`).

**Known modeling gap:** missing skills contribute nothing *negatively* beyond reducing `skill_pct`; there is no penalty for extra/irrelevant candidate skills (correct behavior) and no weight for skill criticality (all skills equal).

---

## 9. Transactions & Concurrency

### 9.1 ACID in Practice

| Property | Enforcement | Code |
|---|---|---|
| **Atomicity** | Candidate insert + all application rows in one `try/commit → except/rollback` | `main.py:141-148` (context manager), invoked at `main.py:315` |
| **Consistency** | `CHECK`, `NOT NULL`, `FOREIGN KEY`, `UNIQUE` + `PRAGMA foreign_keys=ON` | DDL in `init_db()` |
| **Isolation** | SQLite single-writer locking; each request gets its own connection | `get_db()` |
| **Durability** | Committed pages written to `talent_match.db` on disk | SQLite journal/WAL |

### 9.2 Transaction Block (canonical pattern)

```python
conn = get_db()
try:
    conn.execute("INSERT OR REPLACE INTO candidates ...")
    sync_matches_for_candidate(conn, uid, skills, experience_years)
    conn.commit()                       # ← single atomic boundary
except Exception as e:
    conn.rollback()                     # ← all-or-nothing
    raise HTTPException(status_code=500, detail=str(e)
```

**Why this matters:** if `sync_matches_for_candidate` fails halfway (e.g. disk full at company #3 of 5), rollback removes the partially-scored candidate — never leaving an orphan candidate with an incomplete recommendation set.

### 9.3 Concurrency Behavior

- **Writes serialize.** SQLite permits one writer at a time; concurrent POSTs queue on the file lock. Under FastAPI's threadpool this is transparent.
- **Reads can proceed concurrently** with each other; a read during a write sees the pre-write snapshot (no dirty reads).
- **Serializability:** because each request performs its read-modify-write inside one transaction and SQLite locks the DB for the write, two concurrent candidate uploads cannot interleave their `applications` inserts — the schedule is effectively serial.
- **No explicit checkpointing** is configured — SQLite's default journal handles it. For sustained high write throughput, `PRAGMA journal_mode=WAL` + periodic `PRAGMA wal_checkpoint(TRUNCATE)` would be the upgrade.

### 9.4 Log-Based Recovery Model

The `audit_log` table stands in for the *system log* concept:
- Trigger-generated rows carry `action`, `details`, `logged_at`.
- It records **what happened** but not **before-images** — so it is an *audit trail*, not a full undo/redo log. True log-based recovery (deferred modification with LSNs) would require storing `before`/`after` images per column.

---

## 10. Physical Data Organization & Indexing

### 10.1 Storage Layers

| Layer | Realization |
|---|---|
| Physical record | A row serialized into a SQLite page (default 4096 bytes) |
| Blocking factor | Rows per page = `page_size / avg_row_size` (SQLite-computed, invisible to SQL) |
| Heap file | `candidates` and `COMPANY` grow via overflow/free-list pages — sequential heap organization |
| Pinned/unpinned | SQLite pins pages holding latched B-Tree nodes during traversal; managed internally |
| Unstructured store | `./data/*.pdf` — raw filesystem, referenced by `resume_path` column |

### 10.2 Indices

```sql
CREATE INDEX idx_candidates_exp      ON candidates(experience_years);
CREATE INDEX idx_app_company_score   ON applications(company_id, match_score);
```

| Index | Structure | Serves | Complexity |
|---|---|---|---|
| `idx_candidates_exp` | Single-level B-Tree on `experience_years` | `WHERE experience_years >= ?` range scans | `O(log N)` vs `O(N)` table scan |
| `idx_app_company_score` | Composite B-Tree on `(company_id, match_score)` | **Covering index** for `WHERE company_id = ? ORDER BY match_score DESC` | index-only scan — no table lookup needed |

**Multi-level index intuition:** each B-Tree node is itself a page of key/pointer pairs; the root is the top-level index, internal nodes the second level, leaves the third — exactly the textbook multi-level index, with automatic rebalancing on insert/delete.

**Numerical example:** with 10,000 application rows, a scan touches ~10,000 rows; the B-Tree descent touches ~3–4 pages (assuming ~100 keys/node, `log₁₀₀(10⁴) ≈ 2` levels + root).

**What is *not* indexed (honest gaps):**
- `candidates.name` / `candidates.skills` — no longer queried directly; free-text now goes through the vector path.
- `COMPANY.company_name` — no lookup by name exists.
- `audit_log.logged_at` — no time-range queries yet.

### 10.3 Blocking Factor Reasoning

If an `applications` row is ~120 bytes and a page is 4096 bytes with ~40 bytes header → `(4096-40)/120 ≈ 33` rows per page. Fetching 33 rows costs **1 page read** instead of 33 — this is precisely why the composite index (which stores only `(company_id, match_score, rowid)` ≈ 20 bytes → ~200 entries/page) is so much denser than the heap.

---

## 11. Security Considerations

| Area | Status | Detail |
|---|---|---|
| SQL injection | ✅ Protected | All user values bound with `?` placeholders (`main.py:403-410, 370, 318`) |
| SQL injection (admin) | ⚠️ Constrained | `f"SELECT * FROM {t}"` — safe only because `t` is from a hardcoded 5-element list |
| CORS | ⚠️ Dev-open | `allow_origins=["*"]` — must be restricted to `http://localhost:3000` in production |
| Authentication | ❌ None | No login, no sessions, no tokens; role separation is *page-level*, not enforced server-side |
| Authorization | ❌ None | `GET /api/admin/tables` is public — exposes all PII to anyone who reaches port 8000 |
| Input validation | ⚠️ Dual-layer | Pydantic on `CompanyCreate`; raw `Form` fields on upload (DDL `CHECK` is the backstop) |
| File upload safety | ⚠️ Partial | Extension check exists client-side; server accepts any bytes as "PDF" (no magic-number sniffing) |
| Path traversal | ✅ Guarded | Upload-derived `uid` is constrained by construction (`filter(str.isalnum, contact_no)` + `split()[0].lower()`); the resume endpoint independently validates `uid` against `[A-Za-z0-9_]+` **and** re-checks `.resolve()` stays inside `./data` (`main.py:432-436`) |
| Resume serving | ⚠️ Unauthenticated | Any known `uid` can fetch that candidate's resume |
| Secrets | ✅ None present | No API keys in code; `requirements.txt` trimmed to the 4 packages actually imported |
| HTML injection (XSS) | ✅ Escaped | All DB-sourced values interpolated into `innerHTML` pass through `esc()` in `recruiter.html`, `candidate.html`, `admin_db.html`; the clipboard action uses `data-contact` + a delegated listener instead of an inline `onclick` string |

**Production hardening checklist:** bind CORS → add auth (JWT/OAuth) → gate `/api/admin/tables` → validate PDF magic bytes (`%PDF-`) → rate-limit uploads → switch to WAL mode.

---

## 12. Known Limitations & Failure Envelopes

| # | Limitation | Trigger / Failure Mode | Mitigation |
|---|---|---|---|
| 1 | Closed 28-skill vocabulary | A resume listing `Rust`/`Kubernetes` variants not in `KNOWN_SKILLS` silently extracts nothing | Extend `KNOWN_SKILLS` or move to embedding-based extraction |
| 2 | `skills` stored as CSV text | Not atomic — technically violates 1NF spirit; cannot index individual skills | Normalize to `candidate_skills(uid, skill)` junction table |
| 3 | Deterministic `uid` collision | `Alex Morgan` + `9876543210` vs `Alex Gupta` + `9876543210` → second silently overwrites first via `INSERT OR REPLACE` | Add a random suffix or use UUID |
| 4 | `INSERT OR REPLACE` semantics | REPLACE = DELETE+INSERT → cascades fire, audit trigger double-fires, `created_at` resets | Use `ON CONFLICT ... DO UPDATE` instead |
| 5 | Embedding is a network round-trip | `embed()` blocks the request until Gemini answers; a Gemini outage fails every search (no offline fallback, by design) | Queue embeddings at upload only, or cache aggressively |
| 6 | Per-request connection | 1 connection open/close per API call; under load = syscall churn | `sqlite3` connection pool / `check_same_thread=False` singleton |
| 7 | `./data/` growth | One PDF per uid, never garbage-collected | Lifecycle policy / object storage |
| 8 | Single-writer ceiling | >~1 write transaction at a time; SQLite file lock serializes them | Fine to ~hundreds of writes/sec; beyond that → PostgreSQL |
| 9 | No authn/authz | Anyone can call admin/recruiter endpoints | Middleware auth |
| 10 | CORS wildcard | Any origin may call the API | Restrict origins |
| 11 | No migrations | Schema changes require manual `ALTER` or DB deletion | Alembic-style migration ledger |
| 12 | PDF parse failure is silent | `resume_text()` returns `""` on a corrupt PDF → zero vector → permanent 0% for that candidate | Surface a warning in the API response |

### Bugs Fixed (this revision)

| Bug | Symptom | Fix |
|---|---|---|
| Whitespace-only `name` | `name.strip().split()[0]` → `IndexError` → **HTTP 500** on `POST /api/candidates/upload` | Validate `name.split()` and `contact_no` before building `uid`; return **422** (`main.py:304-307`) |
| Connection leak on error | `upload_candidate` raised `HTTPException` after `rollback()` without `conn.close()`; the Top-3 query also ran outside the `try` | Top-3 query moved inside the `try`; `finally: conn.close()` guarantees release |
| Stored XSS | Recruiter-entered `company_name` / candidate `name` were interpolated raw into `innerHTML` in all three portals | Added `esc()` HTML-entity encoder; applied to every DB-sourced interpolation in `recruiter.html`, `candidate.html`, `admin_db.html` |
| Inline `onclick` injection | `onclick="...writeText('${c.contact_no}')..."` broke on quotes in `contact_no` | Replaced with `data-contact` attribute + one delegated `resultsGrid` click listener |
| Path traversal on resume | `/api/candidates/{uid}/resume` joined raw path input onto `./data` | `re.fullmatch(r"[A-Za-z0-9_]+", uid)` + `.resolve()` parent check inside `./data` (`main.py:311-317`) |
| Lost vector search | Commit `7ab8a00` deleted the GenAI embedding layer, leaving keyword-only search | Restored `embed()` / `cosine()` / `embeddings.pkl` and wired it into `/api/candidates/search` |
| Embedding dimension mismatch | `EMBEDDING_DIM` was `768` but the model returns `3072`-dim vectors; the `np.zeros(768)` fallback short-circuited `cosine()` to `0.0`, pinning uncached candidates at the bottom | `EMBEDDING_DIM = 3072` (`main.py:19`) |
| Seed PDFs unreadable | `markitdown` returned `""` for the hand-built seed PDFs, so any rebuilt cache embedded empty text and zeroed every score | `resume_text()` falls back to extracting the PDF's `(...)Tj` text operators (`main.py:105`) |
| `.env` never loaded | `GEMINI_API_KEY` sat in `.env` but `genai.Client()` only reads `os.environ` | `load_dotenv()` at import (`main.py:21-23`) |
| No facet filters | Recruiter UI offered free-text search only | Added Experience / Gender / Work Mode dropdowns bound to new `work_preference` column |

### Performance Ceiling Estimate

- 5 companies × 1,000 candidates = 5,000 `applications` rows → trivial for SQLite.
- Match computation is `O(C)` per candidate (C = companies); adding a 10,000-company table makes registration `O(10⁴)` writes per upload — batch inside one transaction and it still completes in well under a second, but the lock hold time grows linearly.
- Descriptor exhaustion: each request opens 1 file descriptor; FastAPI's default threadpool (40) bounds simultaneous connections to ~40 + worker count — far below `ulimit -n`.

---

## 13. Extension Roadmap

| Phase | Change | Syllabus concepts touched |
|---|---|---|
| 1 | Normalize `skills` to a junction table `candidate_skills` / `company_skills` | 1NF→2NF, M:N mapping |
| 2 | Add `roles` table + `users` table with auth | Three-schema external level, security |
| 3 | Move embedding generation off the request path (background worker) | Physical organization, throughput |
| 4 | Add `WAL` mode + connection pooling | Concurrency control, transaction throughput |
| 5 | Implement full audit (`BEFORE UPDATE/DELETE` triggers with before-images) | System log, log-based recovery |
| 6 | Add a Redis cache layer for hot candidate profiles | NoSQL key-value characteristics |
| 7 | Offload resume blobs to MongoDB/S3 (document store) | Document DB characteristics |
| 8 | Graph view of skill co-occurrence (candidates → skills → companies) | Graph DB characteristics |
| 9 | Migration framework + CI schema tests | Integrity, DDL evolution |
| 10 | UUID primary keys, `ON CONFLICT DO UPDATE` | Entity integrity, upsert correctness |

---

## 14. Syllabus Concept → Code Index

Direct file:line lookups for every major syllabus topic (cross-reference `DBMS_MAPPING.md` for prose).

### Module 1 — Concepts, ER Model, Physical Organization

| Concept | Where in code |
|---|---|
| Structured data | DDL `main.py:162-196` (typed columns) |
| Semi-structured data | CSV `skills` fields `main.py:169, 180`; JSON API responses throughout |
| Unstructured data | `./data/{uid}.pdf` `main.py:308` |
| Three-schema: internal | SQLite file `talent_match.db`, B-Tree pages |
| Three-schema: conceptual | `init_db()` DDL `main.py:161-211` |
| Three-schema: external | `candidate.html` view, `recruiter.html` view, `v_matched_profiles` |
| Database languages (DDL/DML) | DDL `main.py:162-211`; DML `main.py:318, 364, 253-255` |
| ER entity sets | `candidates`, `COMPANY` tables |
| ER attributes + key attribute | `uid` PK `main.py:163`; `company_id` PK `main.py:175` |
| Relationships (M:N) | `applications` `main.py:184-196` |
| Cardinality / participation | FKs with `ON DELETE CASCADE` (total participation) `main.py:193-194` |
| Degree-3 relationship | Implicit in `v_matched_profiles` 3-way join `main.py:212-220` |
| Weak entities | *(not modeled — `applications` has its own surrogate PK)* |
| Heap files / physical records | SQLite page storage of `candidates`/`COMPANY` |
| Blocking factor | Page-size / row-size ratio (see §10.3) |
| Single-level index | `idx_candidates_exp` `main.py:197` |
| Multi-level index (B-Tree) | Both indices; SQLite auto-balances |
| Numerical index example | §10.2 (10,000 rows → 3–4 page reads) |

### Module 2 — Relational Model, SQL, Views, Triggers

| Concept | Where in code |
|---|---|
| Entity integrity | `PRIMARY KEY` `main.py:163, 175, 185, 200` |
| Referential integrity | `FOREIGN KEY ... ON DELETE CASCADE` `main.py:193-194` |
| Domain integrity | `CHECK (age >= 18)`, `CHECK (experience_years >= 0)` `main.py:165, 167` |
| Key/UNIQUE constraint | `UNIQUE(candidate_uid, company_id)` `main.py:195` |
| ER → relational synthesis | M:N → junction `applications` (§4.1) |
| DDL: CREATE / DROP / ALTER | `CREATE TABLE/INDEX/VIEW/TRIGGER IF NOT EXISTS` `main.py:162-220` + `ALTER TABLE ... ADD COLUMN` `main.py:236-239` |
| DML: INSERT | `main.py:243, 318, 364, 253, 207` |
| DML: UPDATE (upsert) | `INSERT OR REPLACE` `main.py:318, 253` |
| DML: DELETE | Implicit via `ON DELETE CASCADE` (no direct `DELETE` statement yet) |
| Single-table SELECT | `main.py:403-410, 241, 385` |
| Multi-table JOIN | 3-way JOIN `main.py:214-218`; 2-way `main.py:370-377` |
| Non-correlated subquery | *(not used)* |
| Correlated subquery | *(not used)* |
| Aggregation / grouping | `SELECT 1 FROM COMPANY LIMIT 1` guard `main.py:241` |
| ORDER BY / LIMIT | `main.py:385, 390, 241` |
| LIKE pattern matching | *(replaced by vector search — `main.py:396-427`)* |
| Views | `v_matched_profiles` `main.py:212-220`, consumed at `main.py:390` |
| Assertions | *(SQLite lacks `CREATE ASSERTION` — emulated by `CHECK` constraints)* |
| Triggers | `trg_candidate_audit` `main.py:205-211` |
| SQL data types | `TEXT, INTEGER, REAL, TIMESTAMP` throughout DDL |
| Recursive queries | *(not used — CTEs like `WITH RECURSIVE` are supported by SQLite but unexercised)* |
| SQL from a programming language | Python `sqlite3` with `?` binding, `sqlite3.Row` factory `main.py:131-135` |
| Parameterized queries (injection safety) | Every dynamic statement `main.py:318, 370, 403-410, 390` |

### Module 3 — Normalization & Functional Dependencies

| Concept | Where in code / analysis |
|---|---|
| Insertion anomaly | Solved: add company without candidates (`POST /api/company/register`) |
| Deletion anomaly | Solved: cascade deletes only `applications`, never the parent |
| Update anomaly | Solved: `company_name` stored once in `COMPANY`, not duplicated per application |
| 1NF | Atomic columns; CSV `skills` is the **known 1NF deviation** (see §12 #2) |
| 2NF | `applications(id, ...)` — no partial dependency: all attributes depend on the full PK; company facts isolated in `COMPANY` |
| 3NF | No transitive dependency: `role_title → location` lives in `COMPANY` keyed by `company_id` |
| BCNF | Every determinant is a candidate key: `uid → *` in `candidates`; `company_id → *` in `COMPANY`; both are PKs → BCNF holds |
| Functional dependency | `uid → name, age, gender, experience_years, contact_no, skills, resume_path` |
| Armstrong's axioms | Reflexivity/transitivity evident in `company_id → skills_expected` and key inference |
| Closures | Attribute closure of `{uid}` = all `candidates` columns |
| Minimal cover | Achieved by splitting entities (company attributes not repeated in `applications`) |
| Lossless join | Verified: `applications ⋈ candidates ⋈ COMPANY` on FK pairs reconstructs base relations without spurious tuples (join attributes are keys of both sides) |
| Dependency preserving | Every base FD enforced by some table's constraints (PK/FK/CHECK) |
| LJ check algorithm | Binary decomposition test: `R1 ∩ R2 → R1` or `R1 ∩ R2 → R2` holds for both joins since the intersection is a key |
| DP check algorithm | Projection of FDs onto each fragment — each FD lands in exactly one fragment here |

### Module 4 — Transactions, Concurrency, Recovery, NoSQL

| Concept | Where in code / analysis |
|---|---|
| Transaction model | Explicit `try / commit / rollback` in `db()` `main.py:141-148` |
| Transaction states | Active → Partially committed → Committed (or → Failed → Aborted via rollback) |
| Atomicity | Single `commit()` covers candidate + all applications |
| Consistency | `CHECK`/`NOT NULL`/`FOREIGN KEY` invariants |
| Isolation | SQLite single-writer lock; no dirty reads |
| Durability | Page write to `talent_match.db` on commit |
| Significance of concurrency control | Concurrent uploads cannot interleave `applications` inserts |
| System log | `audit_log` table `main.py:199-204` + trigger `main.py:205-211` |
| Desirable properties (ACID) | §9.1 table |
| Serial schedules | Each request's transaction is self-contained → effectively serial |
| Conflict serializability | Guaranteed by SQLite's writer lock (no conflicting interleavings possible) |
| Recoverable / cascade-less | Single-writer ⇒ trivially recoverable; no dirty reads ⇒ cascade-less |
| Locking | SQLite file-level write lock + page latches |
| Two-phase locking | Implicit: SQLite holds write locks until commit (growing phase) then releases (shrinking) — **strict 2PL** |
| Log-based recovery | *Modeled, not implemented* — `audit_log` has no before-images (§9.4) |
| Deferred database modification | SQLite buffers dirty pages in cache; only `commit()` forces write-out — deferred modification in practice |
| Check-pointing | SQLite auto-checkpoints the journal; not explicitly invoked |
| NoSQL: Key-value (Redis) | *(contrast)* `localStorage.activeCompany` is a KV pair; `applications` keyed lookup via composite index |
| NoSQL: Document (MongoDB) | *(contrast)* `resume_path` blob + `skills` CSV behaves like a semi-structured document |
| NoSQL: Column-family (Cassandra) | *(contrast)* `idx_app_company_score` is a column-ordered composite index — wide-column-like access pattern |
| NoSQL: Graph (ArangoDB) | *(contrast)* Candidate→Skill→Company is a natural traversal graph currently flattened into CSV |

---

## Appendix A — Command Reference

```bash
# Install dependencies
pip install -r requirements.txt

# Start backend (auto-reload, port 8000)
uvicorn main:app --port 8000 --reload

# Start static frontend (port 3000)
python -m http.server 3000

# Open portals
# http://localhost:3000/index.html
# http://localhost:3000/candidate.html
# http://localhost:3000/recruiter_login.html
# http://localhost:3000/recruiter.html
# http://localhost:3000/admin_db.html

# Reset database (drop and re-bootstrap with seed data)
rm talent_match.db && python -c "import main"

# Seed 6 realistic candidates across engineering, DevOps, marketing, UI/UX
#   - writes resume PDFs to ./data
#   - extracts skills from the prose
#   - caches their Gemini embeddings in ./data/embeddings.pkl
GEMINI_API_KEY=your_key python seed.py

# With a key, start the backend (loads .env automatically)
uvicorn main:app --port 8000

# Inspect DB from terminal
sqlite3 talent_match.db ".schema"
sqlite3 talent_match.db "SELECT * FROM v_matched_profiles ORDER BY match_score DESC LIMIT 10;"
sqlite3 talent_match.db "SELECT * FROM audit_log ORDER BY logged_at DESC LIMIT 10;"
```

## Appendix B — Environment & Versions

| Component | Version / Value |
|---|---|
| Python | 3.10+ (uses `Path`, type hints) |
| FastAPI | latest (from `requirements.txt`) |
| Uvicorn | ASGI server |
| SQLite | 3.x (bundled with Python) |
| markitdown[pdf] | PDF → Markdown/text extraction |
| CORS | wildcard (dev) |
| DB file | `./talent_match.db` (40 KB at rest with seed data) |
| Resume store | `./data/` |

---

*Documentation generated for the Talent Match codebase. Cross-reference `DBMS_MAPPING.md` for syllabus mapping and `README.md` for quick-start instructions.*
