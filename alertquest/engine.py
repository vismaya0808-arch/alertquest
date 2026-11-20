import hashlib
import re
import pandas as pd
from .db import get_connection, upsert_incident

REQUIRED_COLUMNS = ["timestamp", "service", "host", "severity", "message"]
SEVERITIES = {"critical", "high", "medium", "low"}

def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def alert_fingerprint(service, host, message):
    payload = "|".join([normalize(service), normalize(host), normalize(message)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def classify_root_cause(message):
    text = normalize(message)
    rules = [
        (("connection pool", "too many connections", "database connection", "db connection"), "Database connection exhaustion", "Check database availability and connection limits; inspect pool usage, slow queries, and recent connection spikes."),
        (("cpu", "processor", "load average"), "High CPU utilization", "Inspect top processes, recent deployments, and traffic spikes; scale only after identifying the workload."),
        (("memory", "out of memory", "oom", "heap"), "Memory pressure", "Inspect memory and heap metrics, check for leaks, and review recent workload or deployment changes."),
        (("disk", "storage", "filesystem", "no space"), "Disk or storage capacity pressure", "Check filesystem usage and growth, rotate or archive logs, and verify available volume capacity."),
        (("timeout", "latency", "slow response", "response time"), "Service latency or timeout", "Check upstream dependencies, request latency, error rates, and recent network or deployment changes."),
        (("5xx", "http 500", "http 502", "http 503", "error rate"), "Elevated application errors", "Inspect application logs and traces around the event time; verify dependent services and recent releases."),
        (("certificate", "tls", "ssl", "expired"), "TLS certificate issue", "Verify certificate validity and chain, then renew or reload the certificate through the approved process."),
        (("unreachable", "health check failed", "service down", "connection refused"), "Service availability failure", "Check host and process health, network reachability, and dependency status; inspect recent service logs."),
    ]
    for keywords, cause, action in rules:
        if any(word in text for word in keywords):
            return cause, action
    return "Unclassified service or infrastructure alert", "Inspect service logs and metrics for the event window, compare with recent changes, and verify dependent components."

def incident_key(service, host, root_cause):
    raw = "|".join([normalize(service), normalize(host), normalize(root_cause)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()

def validate_alert_dataframe(df):
    errors = []
    if not isinstance(df, pd.DataFrame):
        return False, ["The uploaded file could not be interpreted as a CSV table."], None
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return False, [f"Missing required column(s): {', '.join(missing)}."], None
    cleaned = df[REQUIRED_COLUMNS].copy()
    if cleaned.empty:
        return False, ["The CSV contains no alert rows."], None
    for col in REQUIRED_COLUMNS:
        cleaned[col] = cleaned[col].fillna("").astype(str).str.strip()
    if (cleaned[["service", "host", "message", "timestamp"]] == "").any().any():
        errors.append("Every row must include timestamp, service, host, and message.")
    bad = sorted(set(cleaned["severity"].str.lower()) - SEVERITIES)
    if bad:
        errors.append(f"Unsupported severity value(s): {', '.join(bad)}. Use critical, high, medium, or low.")
    parsed = pd.to_datetime(cleaned["timestamp"], errors="coerce")
    if parsed.isna().any():
        errors.append("One or more timestamps are invalid. Use a recognizable date/time such as 2026-11-19 10:30:00.")
    cleaned["severity"] = cleaned["severity"].str.title()
    return len(errors) == 0, errors, cleaned if not errors else None

def ingest_dataframe(df):
    valid, errors, cleaned = validate_alert_dataframe(df)
    if not valid:
        raise ValueError("; ".join(errors))
    added = 0
    with get_connection() as con:
        for _, row in cleaned.iterrows():
            service, host, message = row["service"], row["host"], row["message"]
            fingerprint = alert_fingerprint(service, host, message)
            root_cause, action = classify_root_cause(message)
            key = incident_key(service, host, root_cause)
            incident_id = "INC-" + key
            severity = row["severity"].title()
            duplicate = con.execute("SELECT COUNT(*) FROM alerts WHERE fingerprint=?", (fingerprint,)).fetchone()[0] > 0
            con.execute("""INSERT INTO alerts(timestamp,service,host,severity,message,fingerprint,is_duplicate,incident_id)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (row["timestamp"], service, host, severity, message, fingerprint, int(duplicate), incident_id))
            upsert_incident(con, incident_id, key, service, host, severity, root_cause, action, row["timestamp"])
            added += 1
    return added

def export_alerts():
    with get_connection() as con:
        return pd.read_sql_query("SELECT * FROM alerts ORDER BY timestamp DESC", con).to_csv(index=False).encode("utf-8")

def export_incidents():
    with get_connection() as con:
        return pd.read_sql_query("SELECT * FROM incidents ORDER BY created_at DESC", con).to_csv(index=False).encode("utf-8")

def export_history():
    with get_connection() as con:
        return pd.read_sql_query("SELECT * FROM acknowledgements ORDER BY acknowledged_at DESC", con).to_csv(index=False).encode("utf-8")
