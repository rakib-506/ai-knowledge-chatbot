"""SQLite database: users, documents, chat sessions and messages."""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DATA_DIR

DB_PATH = DATA_DIR / "app.db"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            source_type TEXT NOT NULL,
            chunks INTEGER NOT NULL,
            words INTEGER NOT NULL,
            added_by TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources TEXT,
            created_at TEXT NOT NULL
        );
        """)


# ---------- users ----------
def create_user(username: str, password_hash: str, role: str = "user") -> int:
    with get_db() as db:
        cur = db.execute("INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                         (username, password_hash, role, now()))
        return cur.lastrowid


def get_user_by_name(username: str):
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def list_users():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()]


# ---------- documents ----------
def add_document(doc_id, name, source_type, chunks, words, added_by):
    with get_db() as db:
        db.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (doc_id, name, source_type, chunks, words, added_by, now()))


def get_document_by_name(name: str):
    with get_db() as db:
        return db.execute("SELECT * FROM documents WHERE name = ?", (name,)).fetchone()


def get_document(doc_id: str):
    with get_db() as db:
        return db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()


def list_documents():
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()]


def delete_document_row(doc_id: str):
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ---------- chat sessions and messages ----------
def create_session(user_id: int, title: str) -> str:
    sid = str(uuid.uuid4())
    with get_db() as db:
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (sid, user_id, title[:60], now()))
    return sid


def get_session(session_id: str, user_id: int):
    with get_db() as db:
        return db.execute("SELECT * FROM sessions WHERE id = ? AND user_id = ?",
                          (session_id, user_id)).fetchone()


def list_sessions(user_id: int):
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()]


def delete_session(session_id: str, user_id: int) -> bool:
    with get_db() as db:
        cur = db.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        return cur.rowcount > 0


def add_message(session_id: str, role: str, content: str, sources: str | None = None):
    with get_db() as db:
        db.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?)",
                   (session_id, role, content, sources, now()))


def get_messages(session_id: str, limit: int | None = None):
    with get_db() as db:
        rows = db.execute("SELECT role, content, sources, created_at FROM messages "
                          "WHERE session_id = ? ORDER BY id", (session_id,)).fetchall()
    rows = [dict(r) for r in rows]
    return rows[-limit:] if limit else rows


def count_rows(table: str) -> int:
    assert table in {"users", "documents", "sessions", "messages"}
    with get_db() as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
