<<<<<<< HEAD
# AlertQuest
**Stop Chasing Alerts. Start Solving Problems.**

A local AIOps hackathon MVP: alert deduplication, incident grouping, prioritization, rule-based root-cause hints, acknowledgement history, and CSV reporting.

## Run on Windows
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Python 3.10+ is recommended. No API keys or external AI services are required. Analysis is deterministic and rule-based, not a trained ML model.

## Included
- Exactly four pages: Command Center, Alert Inbox, Incident Workbench, Data & Reports.
- SQLite persistence at `alertquest/alertquest.db`.
- SHA-256 fingerprint from normalized service, host, and message.
- CSV import validation/preview and CSV exports.
- Sample alert dataset in `data/sample_alerts.csv`.

CSV columns: `timestamp, service, host, severity, message`. Severity values: critical, high, medium, low.
=======
# alertquest
Intelligent AI-powered alert correlation and noise reduction system.
>>>>>>> af847692889201adfc7be982292a270d18ed8eeb
