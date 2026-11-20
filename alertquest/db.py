import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "alertquest.db"
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / "data" / "sample_alerts.csv"

def get_connection():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def initialize_db():
    with get_connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            service TEXT NOT NULL, host TEXT NOT NULL, severity TEXT NOT NULL,
            message TEXT NOT NULL, fingerprint TEXT NOT NULL,
            is_duplicate INTEGER NOT NULL DEFAULT 0, incident_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_alerts_incident ON alerts(incident_id);
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY, incident_key TEXT NOT NULL,
            service TEXT NOT NULL, host TEXT NOT NULL, priority TEXT NOT NULL,
            alert_count INTEGER NOT NULL DEFAULT 0, duplicate_count INTEGER NOT NULL DEFAULT 0,
            root_cause TEXT NOT NULL, recommended_action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open', created_at TEXT NOT NULL, acknowledged_at TEXT
        );
        CREATE TABLE IF NOT EXISTS acknowledgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL,
            service TEXT NOT NULL, priority TEXT NOT NULL, acknowledged_at TEXT NOT NULL
        );
        """)

def upsert_incident(con, incident_id, key, service, host, severity, root_cause, action, timestamp):
    current = con.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
    rank = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    if current:
        priority = severity if rank[severity] > rank[current["priority"]] else current["priority"]
        counts = con.execute("SELECT COUNT(*), COALESCE(SUM(is_duplicate),0) FROM alerts WHERE incident_id=?", (incident_id,)).fetchone()
        con.execute("UPDATE incidents SET priority=?, alert_count=?, duplicate_count=?, root_cause=?, recommended_action=? WHERE incident_id=?",
                    (priority, counts[0], counts[1], root_cause, action, incident_id))
    else:
        con.execute("""INSERT INTO incidents(incident_id,incident_key,service,host,priority,alert_count,duplicate_count,
                       root_cause,recommended_action,status,created_at) VALUES(?,?,?,?,?,1,0,?,?,'Open',?)""",
                    (incident_id, key, service, host, severity, root_cause, action, timestamp))
        counts = con.execute("SELECT COUNT(*), COALESCE(SUM(is_duplicate),0) FROM alerts WHERE incident_id=?", (incident_id,)).fetchone()
        con.execute("UPDATE incidents SET alert_count=?, duplicate_count=? WHERE incident_id=?", (counts[0], counts[1], incident_id))

def acknowledge_incident(incident_id):
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with get_connection() as con:
        row = con.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if not row or row["status"] == "Acknowledged":
            return False
        con.execute("UPDATE incidents SET status='Acknowledged', acknowledged_at=? WHERE incident_id=?", (now, incident_id))
        con.execute("INSERT INTO acknowledgements(incident_id,service,priority,acknowledged_at) VALUES(?,?,?,?)",
                    (incident_id, row["service"], row["priority"], now))
    return True

def reset_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

def seed_if_empty(force=False):
    with get_connection() as con:
        count = con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    if count == 0 and SAMPLE_PATH.exists():
        df = pd.read_csv(SAMPLE_PATH)
        from .engine import ingest_dataframe
        ingest_dataframe(df)
