"""
SQLite persistence layer for BTech-AI-Learner.

Tables:
  users            - registered students
  chat_sessions    - one per PDF-chat conversation
  chat_history     - messages within a chat_session
  quiz_attempts    - every quiz a student takes, with score + full detail
  interview_sessions - mock interview transcripts + final feedback
  notes_cache      - AI-generated notes, cached by (subject, topic) so the
                     same topic isn't regenerated (and re-billed against
                     your Groq quota) every time it's requested
"""

import sqlite3
import os
import uuid
import json

DB_PATH = "database/app.db"
os.makedirs("database", exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            password_hash TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions(
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            subject TEXT,
            topic TEXT,
            score INTEGER,
            total INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS interview_sessions(
            id TEXT PRIMARY KEY,
            user_id TEXT,
            subject TEXT,
            transcript TEXT,
            feedback TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes_cache(
            subject TEXT,
            topic TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (subject, topic)
        )
    """)

    conn.commit()
    conn.close()


create_tables()


##############################################################
# USERS
##############################################################

def create_user(email, password_hash, name):
    user_id = str(uuid.uuid4())
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users(id, email, password_hash, name) VALUES (?, ?, ?, ?)",
        (user_id, email, password_hash, name)
    )
    conn.commit()
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


##############################################################
# CHAT (PDF Q&A) — same pattern as PDF-LEARNER
##############################################################

def create_session(user_id):
    session_id = str(uuid.uuid4())
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_sessions(session_id, user_id, title) VALUES (?, ?, ?)",
        (session_id, user_id, "New Chat")
    )
    conn.commit()
    conn.close()
    return session_id


def get_sessions(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id, title, created_at FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_owner(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM chat_sessions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return row["user_id"] if row else None


def update_session_title(session_id, title):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE chat_sessions SET title = ? WHERE session_id = ?", (title, session_id))
    conn.commit()
    conn.close()


def add_message(session_id, role, content):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_history(session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_chat_history(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY id", (session_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


##############################################################
# QUIZ
##############################################################

def save_quiz_attempt(user_id, subject, topic, score, total, details):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO quiz_attempts(user_id, subject, topic, score, total, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, subject, topic, score, total, json.dumps(details))
    )
    conn.commit()
    conn.close()


def get_recent_quiz_questions(user_id, subject, topic, limit=40, lookback_attempts=8):
    """
    Returns a de-duplicated list of question texts the student has already
    seen for this subject/topic, most recent first — used to steer the
    quiz generator away from repeating itself on retakes.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT details FROM quiz_attempts
           WHERE user_id = ? AND subject = ? AND topic = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, subject, topic, lookback_attempts)
    )
    rows = cur.fetchall()
    conn.close()

    seen = []
    for row in rows:
        try:
            details = json.loads(row["details"])
        except (TypeError, ValueError):
            continue
        for item in details:
            q = item.get("question")
            if q and q not in seen:
                seen.append(q)
            if len(seen) >= limit:
                return seen
    return seen


def get_quiz_attempts(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT subject, topic, score, total, created_at FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


##############################################################
# MOCK INTERVIEW
##############################################################

def create_interview_session(user_id, subject):
    session_id = str(uuid.uuid4())
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO interview_sessions(id, user_id, subject, transcript) VALUES (?, ?, ?, ?)",
        (session_id, user_id, subject, json.dumps([]))
    )
    conn.commit()
    conn.close()
    return session_id


def get_interview_session(session_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM interview_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    data["transcript"] = json.loads(data["transcript"])
    return data


def update_interview_transcript(session_id, transcript):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE interview_sessions SET transcript = ? WHERE id = ?",
        (json.dumps(transcript), session_id)
    )
    conn.commit()
    conn.close()


def save_interview_feedback(session_id, feedback):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE interview_sessions SET feedback = ? WHERE id = ?",
        (feedback, session_id)
    )
    conn.commit()
    conn.close()


##############################################################
# NOTES CACHE
##############################################################

def get_cached_notes(subject, topic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM notes_cache WHERE subject = ? AND topic = ?",
        (subject, topic)
    )
    row = cur.fetchone()
    conn.close()
    return row["content"] if row else None


def save_notes_to_cache(subject, topic, content):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO notes_cache(subject, topic, content) VALUES (?, ?, ?)",
        (subject, topic, content)
    )
    conn.commit()
    conn.close()