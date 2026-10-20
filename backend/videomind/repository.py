"""SQLite repository. Each operation owns its connection; worker claims are atomic."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


TERMINAL = {"completed", "failed", "cancelled"}


class QueueFull(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class JobRepository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, stage TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', error TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def add(self, job_id: str, payload: dict, max_jobs: int):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
            if count >= max_jobs:
                raise QueueFull("The local queue is full. Try again after a job finishes.")
            timestamp = now()
            db.execute("INSERT INTO jobs(id,state,stage,payload,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                       (job_id, "queued", "queued", json.dumps(payload), timestamp, timestamp))

    def get(self, job_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        for field in ("payload", "metadata", "error"):
            result[field] = json.loads(result[field]) if result[field] else None
        result["cancel_requested"] = bool(result["cancel_requested"])
        return result

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET state='running',stage='ingesting',updated_at=? WHERE id=?",
                       (now(), row[0]))
        return self.get(row[0])

    def progress(self, job_id: str, stage: str, progress: int, metadata: dict | None = None):
        with self.connect() as db:
            if metadata is not None:
                db.execute("UPDATE jobs SET metadata=? WHERE id=? AND state='running'", (json.dumps(metadata), job_id))
            db.execute("UPDATE jobs SET stage=?,progress=MAX(progress,?),updated_at=? WHERE id=? AND state='running'",
                       (stage, min(99, progress), now(), job_id))

    def finish(self, job_id: str, state: str, error: dict | None = None):
        if state not in TERMINAL:
            raise ValueError("Expected a terminal job state")
        with self.connect() as db:
            db.execute("""UPDATE jobs SET
                state=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE ? END,
                stage=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE ? END,
                progress=CASE WHEN ?='completed' AND cancel_requested=0 THEN 100 ELSE progress END,
                error=?,updated_at=? WHERE id=? AND state='running'""",
                       (state, state, state, json.dumps(error) if error else None, now(), job_id))

    def cancel(self, job_id: str):
        with self.connect() as db:
            db.execute("""UPDATE jobs SET cancel_requested=1,
                state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END,
                stage=CASE WHEN state='queued' THEN 'cancelled' ELSE stage END,
                updated_at=? WHERE id=? AND state IN ('queued','running')""", (now(), job_id))

    def recover(self):
        with self.connect() as db:
            db.execute("""UPDATE jobs SET state=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE 'failed' END,
                stage='interrupted',error=?,updated_at=? WHERE state='running'""",
                       (json.dumps({"code": "interrupted", "message": "The previous worker stopped. Submit a new job to retry."}), now()))
