import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "veriscope.db")))

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()

def initialize():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS research (research_id TEXT PRIMARY KEY, generated_at TEXT NOT NULL, original_question TEXT NOT NULL, payload TEXT NOT NULL)")

def save(report: dict):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO research VALUES (?, ?, ?, ?)", (report["research_id"], report["generated_at"], report["original_question"], json.dumps(report)))

def get_report(research_id: str):
    with connect() as db:
        row = db.execute("SELECT payload FROM research WHERE research_id = ?", (research_id,)).fetchone()
    return json.loads(row["payload"]) if row else None

def history(limit: int = 50):
    with connect() as db:
        rows = db.execute("SELECT research_id, generated_at, original_question, payload FROM research ORDER BY generated_at DESC LIMIT ?", (limit,)).fetchall()
    return [{
        "research_id": row["research_id"],
        "generated_at": row["generated_at"],
        "original_question": row["original_question"],
        "source_count": len(json.loads(row["payload"]).get("sources", [])),
    } for row in rows]
