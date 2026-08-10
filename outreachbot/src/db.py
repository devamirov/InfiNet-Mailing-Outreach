"""SQLite database for leads, emails_sent, suppression, run_state."""
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

DB_NAME = "outreach.db"


def _db_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / DB_NAME


def get_conn() -> sqlite3.Connection:
    path = _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    close = False
    if conn is None:
        conn = get_conn()
        close = True
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                address TEXT,
                city TEXT,
                country TEXT,
                phone TEXT,
                email TEXT,
                website TEXT,
                industry TEXT,
                raw_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS emails_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS sms_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                sent_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS suppression (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_or_phone TEXT UNIQUE NOT NULL,
                reason TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS run_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_leads_place_id ON leads(place_id);
            CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
            CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression(email_or_phone);
            CREATE INDEX IF NOT EXISTS idx_sms_sent_lead ON sms_sent(lead_id);
        """)
        conn.commit()
    finally:
        if close:
            conn.close()


def insert_lead(
    place_id: str,
    name: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    industry: Optional[str] = None,
    raw_json: Optional[str] = None,
) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO leads (place_id, name, address, city, country, phone, email, website, industry, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (place_id, name, address or "", city or "", country or "", phone or "", email or "", website or "", industry or "", raw_json or ""),
        )
        conn.commit()
        if cur.lastrowid and cur.lastrowid > 0:
            return cur.lastrowid
        cur = conn.execute("SELECT id FROM leads WHERE place_id = ?", (place_id,))
        row = cur.fetchone()
        return row["id"] if row else 0
    finally:
        conn.close()


def get_leads_with_email_not_sent(limit: int) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT l.id, l.place_id, l.name, l.address, l.city, l.country, l.phone, l.email, l.website, l.industry
            FROM leads l
            WHERE l.email IS NOT NULL AND l.email != ''
            AND NOT EXISTS (SELECT 1 FROM suppression s WHERE s.email_or_phone = LOWER(TRIM(l.email)))
            AND NOT EXISTS (SELECT 1 FROM emails_sent e WHERE e.lead_id = l.id)
            ORDER BY l.id
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def record_email_sent(lead_id: int, email: str, subject: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO emails_sent (lead_id, email, subject) VALUES (?, ?, ?)",
            (lead_id, email, subject),
        )
        conn.commit()
    finally:
        conn.close()


def get_leads_with_phone_not_sent_sms(limit: int) -> list[dict]:
    """Leads that have a non-empty phone and no row in sms_sent for that lead."""
    conn = get_conn()
    try:
        cur = conn.execute(
            """
            SELECT l.id, l.place_id, l.name, l.address, l.city, l.country, l.phone
            FROM leads l
            WHERE l.phone IS NOT NULL AND TRIM(l.phone) != ''
            AND NOT EXISTS (SELECT 1 FROM sms_sent s WHERE s.lead_id = l.id)
            ORDER BY l.id
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def record_sms_sent(lead_id: int, phone: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO sms_sent (lead_id, phone) VALUES (?, ?)",
            (lead_id, phone),
        )
        conn.commit()
    finally:
        conn.close()


def count_sms_sent_today() -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT COUNT(*) AS n FROM sms_sent WHERE date(sent_at) = date('now')"
        )
        row = cur.fetchone()
        return row["n"] or 0
    finally:
        conn.close()


def add_to_suppression(email_or_phone: str, reason: str = "manual") -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO suppression (email_or_phone, reason) VALUES (?, ?)",
            (email_or_phone.strip().lower(), reason),
        )
        conn.commit()
    finally:
        conn.close()


def is_suppressed(email_or_phone: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT 1 FROM suppression WHERE email_or_phone = ?",
            (email_or_phone.strip().lower(),),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def get_run_state(key: str) -> Optional[str]:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT value FROM run_state WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_run_state(key: str, value: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO run_state (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def count_emails_sent_today() -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT COUNT(*) AS n FROM emails_sent WHERE date(sent_at) = date('now')"
        )
        row = cur.fetchone()
        return row["n"] or 0
    finally:
        conn.close()


def count_leads() -> int:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT COUNT(*) AS n FROM leads")
        row = cur.fetchone()
        return (row["n"] if row else 0) or 0
    finally:
        conn.close()


def count_leads_with_email() -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE email IS NOT NULL AND email != ''"
        )
        row = cur.fetchone()
        return (row["n"] if row else 0) or 0
    finally:
        conn.close()


def count_emails_sent_total() -> int:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT COUNT(*) AS n FROM emails_sent")
        row = cur.fetchone()
        return (row["n"] if row else 0) or 0
    finally:
        conn.close()
