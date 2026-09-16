import os
import pickle
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from markitdown import MarkItDown
import numpy as np

# Configuration
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "candidates.db"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.pkl"

# Configure Gemini API (Ensure GEMINI_API_KEY environment variable is set)
client = genai.Client()
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
EMBEDDING_MODEL = "gemini-embedding-2"

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MarkItDown parser
md = MarkItDown()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            uid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            experience_years REAL NOT NULL,
            contact_no TEXT NOT NULL,
            resume_path TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Helper Functions ---
def load_embeddings_dict() -> dict:
    if EMBEDDINGS_FILE.exists():
        with open(EMBEDDINGS_FILE, "rb") as f:
            return pickle.load(f)
    return {}

def save_embeddings_dict(embeddings_dict: dict):
    with open(EMBEDDINGS_FILE, "wb") as f:
        pickle.dump(embeddings_dict, f)

def get_embedding(text: str) -> np.ndarray:
    if not text.strip():
        return np.zeros(768)
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    ).embeddings[0].values
    # print(response)
    return np.array(response, dtype=np.float32)

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))

# --- API Endpoints ---
@app.post("/api/candidates/upload")
async def upload_candidate(
    name: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    experience_years: float = Form(...),
    contact_no: str = Form(...),
    resume_file: UploadFile = File(...)
):
    print("DATA!")
    try:
        # Generate Unique ID (UID)
        first_name = name.strip().split()[0].lower()
        clean_contact = "".join(filter(str.isalnum, contact_no))
        uid = f"{first_name}_{clean_contact}"

        # Save PDF resume to /data folder
        file_path = DATA_DIR / f"{uid}.pdf"
        file_bytes = await resume_file.read()
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        # Extract text from PDF using MarkItDown
        parse_result = md.convert(str(file_path))
        extracted_text = parse_result.text_content

        # Generate Gemini vector embedding
        vector = get_embedding(extracted_text)

        # Save candidate metadata to SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO candidates 
            (uid, name, age, gender, experience_years, contact_no, resume_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (uid, name, age, gender, experience_years, contact_no, str(file_path))
        )
        conn.commit()
        conn.close()

        # Update and save binary embeddings pickle file
        embeddings_dict = load_embeddings_dict()
        embeddings_dict[uid] = vector
        save_embeddings_dict(embeddings_dict)

        return {"status": "success", "uid": uid, "message": "Candidate processed successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidates/search")
async def search_candidates(
    query: Optional[str] = Query(None),
    min_experience: Optional[float] = Query(None),
    gender: Optional[str] = Query(None),
    limit: int = Query(10)
):
    try:
        # Query SQLite database for metadata filtering
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = "SELECT * FROM candidates WHERE 1=1"
        params = []

        if min_experience is not None:
            sql += " AND experience_years >= ?"
            params.append(min_experience)
        if gender is not None:
            sql += " AND gender = ?"
            params.append(gender)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        candidates = [dict(row) for row in rows]
        if not candidates:
            return []

        # Perform semantic vector similarity search if a search query is provided
        if query and query.strip():
            query_vector = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query
            ).embeddings[0].values
            query_vector = np.array(query_vector, dtype=np.float32)

            embeddings_dict = load_embeddings_dict()

            scored_candidates = []
            for candidate in candidates:
                uid = candidate["uid"]
                cand_vector = embeddings_dict.get(uid)
                if cand_vector is not None:
                    score = cosine_similarity(query_vector, cand_vector)
                else:
                    score = 0.0
                candidate["similarity_score"] = score
                scored_candidates.append(candidate)

            # Sort by highest similarity score
            scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
            return scored_candidates[:limit]

        return candidates[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))