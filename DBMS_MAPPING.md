# Database Management Systems (DBMS) — Syllabus Mapping & Implementation Guide

This document maps the **Talent Match** project directly to your academic DBMS syllabus across all 4 units, demonstrating how each theoretical concept is realized in practical code.

---

## Unit 1: Concepts, Data Models, ER Modeling & Physical Organization

### 1. Characteristics of Database Systems & Data Categorization
* **Structured Data**: Stored in relational SQLite tables (`candidates`, `COMPANY`, `applications`, `audit_log`) with strict typed columns (`INTEGER`, `REAL`, `TEXT`, `TIMESTAMP`).
* **Semi-Structured Data**: Comma-separated extracted skills and JSON payloads exchanged between the FastAPI backend and vanilla JavaScript frontend.
* **Unstructured Data**: Raw candidate resume PDF files stored in `./data/{uid}.pdf`, parsed into plaintext using `MarkItDown`.

### 2. Three-Schema Architecture
1. **Internal / Physical Level**: The physical SQLite B-Tree file (`talent_match.db`), filesystem disk layout, binary storage, and index files.
2. **Conceptual / Logical Level**: The relational schema defined in `main.py` via DDL statements (`candidates`, `COMPANY`, `applications`, integrity constraints).
3. **External / View Level**: 
   * **Candidate View**: Candidates only see their registration form and their top 3 recommended companies with missing skills.
   * **Recruiter View**: Recruiters see their company profile, job requirements, and candidate match scores.
   * **SQL View (`v_matched_profiles`)**: Virtual abstraction joining the tables for easy query access.

### 3. ER Model to Relational Schema Synthesis
* **Entity Sets**:
  * `CANDIDATE` (Attributes: `uid` [Key], `name`, `age`, `gender`, `experience_years`, `contact_no`, `skills`, `resume_path`)
  * `COMPANY` (Attributes: `company_id` [Key], `company_name`, `role_title`, `experience_type`, `min_experience`, `skills_expected`, `location`)
* **Relationship**:
  * `APPLIES_TO / MATCHES` (Relationship connecting `CANDIDATE` and `COMPANY`).
  * **Cardinality**: Many-to-Many ($M:N$). One candidate can match multiple companies; one company can receive multiple candidate applications.
  * **Relationship Attributes**: `match_score`, `matching_skills`, `missing_skills`, `status`, `matched_at`.
  * **Relational Mapping**: Synthesized into the junction table `applications` using Foreign Keys referencing both parent tables.

### 4. Physical Data Organization & Indexing
* **Heap Files & Records**: SQLite stores records sequentially in database pages (heap organization).
* **Single-Level & Multi-Level Indices (B-Tree)**:
  * Created dedicated B-Tree indices in `main.py`:
    ```sql
    CREATE INDEX idx_candidates_exp ON candidates(experience_years);
    CREATE INDEX idx_app_company_score ON applications(company_id, match_score);
    ```
  * **Why**: Avoids full-table linear scans ($O(N)$) when recruiters filter by minimum experience or rank by highest match score, optimizing lookup time to $O(\log N)$.

---

## Unit 2: Relational Databases, SQL DDL, DML, Joins, Views & Triggers

### 1. Integrity Constraints
* **Primary Key (Entity Integrity)**: `uid TEXT PRIMARY KEY` in `candidates`; `company_id INTEGER PRIMARY KEY AUTOINCREMENT` in `COMPANY`. Ensures each tuple is unique and non-null.
* **Referential Integrity (Foreign Keys)**:
  ```sql
  FOREIGN KEY(candidate_uid) REFERENCES candidates(uid) ON DELETE CASCADE,
  FOREIGN KEY(company_id) REFERENCES COMPANY(company_id) ON DELETE CASCADE
  ```
  Guarantees that an application record cannot reference a non-existent candidate or company. If a candidate/company is removed, associated applications cascade delete.
* **Domain & Check Constraints**:
  * `age INTEGER NOT NULL CHECK (age >= 18)` (Candidate must be an adult)
  * `experience_years REAL NOT NULL DEFAULT 0.0 CHECK (experience_years >= 0)` (Non-negative experience)
* **Unique Constraint**: `UNIQUE(candidate_uid, company_id)` prevents duplicate matching records between the same pair.

### 2. SQL DDL (Data Definition Language)
* Table creation using `CREATE TABLE IF NOT EXISTS`.
* Index definition using `CREATE INDEX IF NOT EXISTS`.
* View definition using `CREATE VIEW IF NOT EXISTS`.
* Trigger definition using `CREATE TRIGGER IF NOT EXISTS`.

### 3. SQL DML (Data Manipulation Language)
* **INSERT**: `INSERT INTO COMPANY (...) VALUES (...)`
* **INSERT OR REPLACE**: Atomic upsert for candidate profiles and application match scores.
* **SELECT (Single & Multiple Tables)**:
  * Filtering: `WHERE experience_years >= ? AND gender = ?`
  * Text Pattern Matching: `WHERE name LIKE '%...%' OR skills LIKE '%...%'`
  * Sorting: `ORDER BY match_score DESC LIMIT 3`

### 4. Join Operations
* **3-Way INNER JOIN**:
  ```sql
  SELECT app.id, cand.name, comp.company_name, comp.role_title, app.match_score
  FROM applications app
  JOIN candidates cand ON app.candidate_uid = cand.uid
  JOIN COMPANY comp ON app.company_id = comp.company_id
  ORDER BY app.match_score DESC;
  ```
  Combines records across applicant profiles, job vacancies, and scoring metrics.

### 5. Views (`CREATE VIEW`)
* Created `v_matched_profiles` as a virtual table:
  ```sql
  CREATE VIEW IF NOT EXISTS v_matched_profiles AS
  SELECT app.id AS application_id, cand.uid AS candidate_uid, cand.name AS candidate_name,
         cand.age, cand.gender, cand.experience_years, cand.contact_no,
         comp.company_id, comp.company_name, comp.role_title, comp.skills_expected,
         app.match_score, app.matching_skills, app.missing_skills, app.status
  FROM applications app
  JOIN candidates cand ON app.candidate_uid = cand.uid
  JOIN COMPANY comp ON app.company_id = comp.company_id;
  ```
  Simplifies recruiter queries into a clean single-statement query:
  `SELECT * FROM v_matched_profiles WHERE company_id = ? ORDER BY match_score DESC`

### 6. Triggers (`CREATE TRIGGER`)
* Created automated event-driven trigger for database auditing:
  ```sql
  CREATE TRIGGER IF NOT EXISTS trg_candidate_audit
  AFTER INSERT ON candidates
  BEGIN
      INSERT INTO audit_log (action, details)
      VALUES ('CANDIDATE_REGISTERED', 'New applicant added: ' || NEW.name);
  END;
  ```
  Whenever a new row is inserted into `candidates`, SQLite automatically logs an entry into `audit_log` without manual application code.

### 7. Accessing SQL from a Programming Language
* Uses Python's standard `sqlite3` module with parameter binding (`?`) to prevent SQL injection vulnerabilities.

---

## Unit 3: Normalization & Functional Dependencies

### 1. Database Normalization (1NF, 2NF, 3NF)
* **First Normal Form (1NF)**:
  * Every attribute contains atomic (indivisible) values.
  * Every table has a clearly defined primary key.
  * No repeating groups of columns.
* **Second Normal Form (2NF)**:
  * Meets 1NF.
  * Eliminates **Partial Functional Dependencies**: All non-key attributes fully depend on the complete primary key.
  * In the composite table `applications(id, candidate_uid, company_id)`, company attributes (`company_name`, `role_title`, `location`) are not stored here; they are isolated in `COMPANY`.
* **Third Normal Form (3NF)**:
  * Meets 2NF.
  * Eliminates **Transitive Dependencies** ($X \rightarrow Y$ and $Y \rightarrow Z$):
    Non-key attributes depend only on the primary key, never on other non-key attributes.
* **Anomaly Prevention**:
  * **Insertion Anomaly Solved**: A new company can be added without needing an applicant to exist first.
  * **Deletion Anomaly Solved**: Deleting a candidate does not erase the company record.
  * **Update Anomaly Solved**: Updating a company's required skills updates a single row in `COMPANY`, not across thousands of application rows.

---

## Unit 4: Transaction Processing & Recovery

### 1. ACID Properties Implementation
* **Atomicity**:
  When a candidate registers, their details must be inserted into `candidates` **AND** matches calculated across all companies in `applications`.
  We wrap both in an explicit transaction:
  ```python
  conn = get_db()
  try:
      # Step 1: Insert Candidate
      conn.execute("INSERT OR REPLACE INTO candidates ...")
      # Step 2: Compute and Insert Applications
      sync_matches_for_candidate(conn, uid, skills, experience_years)
      # All steps succeeded -> Commit
      conn.commit()
  except Exception as e:
      # Any failure -> Rollback completely (All or Nothing)
      conn.rollback()
  ```
* **Consistency**: Enforced through `CHECK (age >= 18)`, `NOT NULL`, and Foreign Key constraints.
* **Isolation**: SQLite handles serializable / WAL locking ensuring concurrent reads/writes do not produce dirty reads.
* **Durability**: Committed transactions are written to `talent_match.db` disk storage.

### 2. System Log / Audit Log
* Modeled through the `audit_log` table, recording operations (`CANDIDATE_REGISTERED`, timestamps, and record details) corresponding to write-ahead / transaction logging concepts.
