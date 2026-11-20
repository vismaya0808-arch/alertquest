import streamlit as st
import pandas as pd
import plotly.express as px
from alertquest.db import initialize_db, seed_if_empty, get_connection, acknowledge_incident, reset_database
from alertquest.engine import validate_alert_dataframe, ingest_dataframe, export_alerts, export_incidents

st.set_page_config(page_title="AlertQuest | AIOps Command Center", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
initialize_db()
seed_if_empty()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background:#F3F6FB; color:#182338; }
section[data-testid="stSidebar"] { background:#14243B; }
section[data-testid="stSidebar"] * { color:#F4F7FC !important; }
.block-container { padding-top:1.8rem; padding-bottom:3rem; max-width:1500px; }
.hero,.panel,.metric,.incident-card { background:#fff; border:1px solid #E5EAF2; border-radius:14px; box-shadow:0 4px 15px rgba(20,36,59,.045); }
.hero { padding:22px 26px; margin-bottom:18px; }
.hero-kicker { color:#C64D35; font-szize:12px; font-weight:800; letter-spacing:1.4px; }
.hero h1 { color:#182338; font-size:30px; margin:4px 0 2px; font-weight:800; }
.hero p,.small-muted { color:#738096; font-size:13px; margin:0; }
.metric { padding:17px 18px; min-height:112px; }
.metric-label { color:#68758A; font-size:12px; font-weight:700; letter-spacing:.7px; }
.metric-value { color:#182338; font-size:30px; font-weight:800; margin-top:5px; }
.metric-note { color:#8792A4; font-size:12px; }
.panel { padding:18px 20px; margin:10px 0 16px; }
.incident-card { border-left:5px solid #D3AD42; padding:17px 19px; margin:10px 0 14px; }
.pill { display:inline-block; border-radius:20px; padding:4px 10px; font-size:11px; font-weight:800; background:#EEF2F7; color:#40506A; }
.stButton>button { border-radius:9px; font-weight:700; }
.stButton>button[kind="primary"] { background:#C64D35; color:white; border:0; }
</style>
""", unsafe_allow_html=True)

def load_data():
    with get_connection() as con:
        a = pd.read_sql_query("SELECT * FROM alerts ORDER BY timestamp DESC,id DESC", con)
        i = pd.read_sql_query("SELECT * FROM incidents ORDER BY created_at DESC", con)
        h = pd.read_sql_query("SELECT * FROM acknowledgements ORDER BY acknowledged_at DESC", con)
    return a, i, h

def hero(kicker, title, subtitle):
    st.markdown(f'<div class="hero"><div class="hero-kicker">{kicker}</div><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

def metric(label, value, note, accent="#182338"):
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value" style="color:{accent}">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

def sev_color(s):
    return {"Critical":"#D64545","High":"#E58B35","Medium":"#D3AD42","Low":"#4D9B79"}.get(s,"#8792A4")

with st.sidebar:
    st.markdown("## 🛡️ AlertQuest")
    st.caption("AIOps · Intelligent Alert Management")
    st.markdown("---")
    page = st.radio("WORKSPACE", ["Command Center","Alert Inbox","Incident Workbench","Data & Reports"])
    alerts, incidents, history = load_data()
    st.metric("Open incidents", int((incidents.status=="Open").sum()) if not incidents.empty else 0)
    st.caption("Local workspace · SQLite")
    if st.button("↻ Reset demo database", use_container_width=True):
        reset_database()
        initialize_db()
        seed_if_empty()
        st.rerun()
    st.markdown("<div style='margin-top:25px;color:#AAB8CC;font-size:11px'>ALERTQUEST MVP · RULE-BASED ANALYSIS</div>", unsafe_allow_html=True)

alerts, incidents, history = load_data()

if page == "Command Center":
    hero("OPERATIONS OVERVIEW","Command Center","A clear view of alert noise, active incidents, and what needs attention.")
    total = len(alerts)
    critical = int((alerts.severity=="Critical").sum()) if total else 0
    duplicates = int(alerts.is_duplicate.sum()) if total else 0
    opened = int((incidents.status=="Open").sum()) if not incidents.empty else 0
    cols = st.columns(4)
    for c, args in zip(cols,[("Alerts received",total,"All ingested events"),("Critical alerts",critical,"Require immediate review","#D64545"),("Duplicates detected",duplicates,"Repeated SHA-256 fingerprints","#C64D35"),("Open incidents",opened,"Awaiting acknowledgement","#E58B35")]):
        with c: metric(*args)
    left,right = st.columns([1,1.35])
    with left:
        st.markdown('<div class="panel"><h3>Severity distribution</h3>',unsafe_allow_html=True)
        if total:
            counts = alerts.severity.value_counts().reindex(["Critical","High","Medium","Low"],fill_value=0).rename_axis("Severity").reset_index(name="Alerts")
            fig = px.pie(counts,names="Severity",values="Alerts",hole=.62,color="Severity",color_discrete_map={"Critical":"#D64545","High":"#E58B35","Medium":"#D3AD42","Low":"#4D9B79"})
            fig.update_layout(height=280,margin=dict(t=5,b=5,l=5,r=5),paper_bgcolor="rgba(0,0,0,0)",legend_title=None)
            st.plotly_chart(fig,use_container_width=True)
        else: st.info("No alerts yet. Import a CSV to get started.")
        st.markdown("</div>",unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel"><h3>Needs your attention</h3>',unsafe_allow_html=True)
        todo = incidents[(incidents.status=="Open") & incidents.priority.isin(["Critical","High"])] if not incidents.empty else incidents
        if todo.empty: st.success("No unacknowledged critical or high-priority incidents.")
        else:
            for _,r in todo.head(5).iterrows():
                st.markdown(f"**{r.incident_id} · {r.service}**  \n<span style='color:{sev_color(r.priority)}'>● {r.priority}</span> · {r.alert_count} related alerts · {r.host}",unsafe_allow_html=True)
        st.markdown("</div>",unsafe_allow_html=True)
    st.markdown('<div class="panel"><h3>Recent incidents</h3>',unsafe_allow_html=True)
    if incidents.empty: st.info("No incidents recorded.")
    else: st.dataframe(incidents.head(6)[["incident_id","service","host","priority","alert_count","duplicate_count","status"]],use_container_width=True,hide_index=True)
    st.markdown("</div>",unsafe_allow_html=True)
    st.markdown('<div class="panel"><h3>Alert-to-action workflow</h3><p class="small-muted">Events become grouped, prioritized work.</p>',unsafe_allow_html=True)
    cols=st.columns(5)
    for c,(n,label) in zip(cols,[("01","Alert received"),("02","Duplicate detection"),("03","Incident grouping"),("04","Priority assignment"),("05","Recommended action")]):
        with c: st.markdown(f'<div style="background:#F3F6FB;border-radius:10px;padding:13px;text-align:center"><b style="color:#C64D35">{n}</b><div style="font-size:13px;font-weight:700">{label}</div></div>',unsafe_allow_html=True)
    st.markdown("</div>",unsafe_allow_html=True)
    st.markdown("### Recommended next steps")
    st.write("1. Review the highest-priority open incident in Incident Workbench.")
    st.write("2. Follow the suggested action, then acknowledge the incident when it is being handled.")

elif page == "Alert Inbox":
    hero("EVENT STREAM","Alert Inbox","Search, filter, inspect, and export the raw alerts received by AlertQuest.")
    if alerts.empty: st.info("No alerts available. Import a CSV in Data & Reports."); st.stop()
    a,b,c=st.columns([1.5,1,1])
    with a: query=st.text_input("Search service, host, or message",placeholder="Search alerts…")
    with b: sev=st.multiselect("Severity",["Critical","High","Medium","Low"])
    with c: services=st.multiselect("Service",sorted(alerts.service.unique()))
    shown=alerts.copy()
    if query:
        mask=shown[["service","host","message"]].astype(str).apply(lambda x:x.str.contains(query,case=False,na=False)).any(axis=1)
        shown=shown[mask]
    if sev: shown=shown[shown.severity.isin(sev)]
    if services: shown=shown[shown.service.isin(services)]
    st.caption(f"Showing {len(shown)} of {len(alerts)} alerts · Duplicate events remain visible for auditability.")
    st.dataframe(shown[["timestamp","service","host","severity","message","is_duplicate","fingerprint"]],use_container_width=True,hide_index=True,height=470,
                 column_config={"message":st.column_config.TextColumn("Alert message",width="large"),"fingerprint":st.column_config.TextColumn("SHA-256 fingerprint",width="medium"),"is_duplicate":st.column_config.CheckboxColumn("Duplicate")})
    st.download_button("⬇ Export filtered alerts CSV",shown.to_csv(index=False).encode("utf-8"),"alertquest_filtered_alerts.csv","text/csv",type="primary")

elif page == "Incident Workbench":
    hero("INVESTIGATION","Incident Workbench","Related alerts are grouped into incidents with a priority, root-cause hint, and next action.")
    if incidents.empty: st.info("No incidents yet. Import alert data to begin."); st.stop()
    filt=st.selectbox("Show incidents",["All incidents","Open incidents","Acknowledged incidents","Critical","High","Medium","Low"])
    shown=incidents.copy()
    if filt=="Open incidents": shown=shown[shown.status=="Open"]
    elif filt=="Acknowledged incidents": shown=shown[shown.status=="Acknowledged"]
    elif filt in ["Critical","High","Medium","Low"]: shown=shown[shown.priority==filt]
    st.caption(f"{len(shown)} incidents match this view.")
    for _,r in shown.iterrows():
        color=sev_color(r.priority)
        st.markdown(f'<div class="incident-card" style="border-left-color:{color}"><div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><div><span class="small-muted">{r.incident_id}</span><h3 style="margin:3px 0;color:#182338">{r.service} <span style="font-size:14px;color:#738096;font-weight:500">· {r.host}</span></h3></div><div><span class="pill" style="background:{color}18;color:{color}">{r.priority.upper()}</span> &nbsp; <span class="pill">{r.status.upper()}</span></div></div><div class="small-muted">{r.alert_count} related alerts · {r.duplicate_count} duplicate alerts · Created {r.created_at}</div><hr style="border:0;border-top:1px solid #EDF0F5;margin:12px 0"><b>Possible root cause</b><div style="margin:4px 0 10px;color:#43516A">{r.root_cause}</div><b>Recommended action</b><div style="margin:4px 0;color:#43516A">{r.recommended_action}</div></div>',unsafe_allow_html=True)
        with st.expander(f"Original alert messages · {r.incident_id}"):
            with get_connection() as con:
                related=pd.read_sql_query("SELECT timestamp,severity,message,is_duplicate FROM alerts WHERE incident_id=? ORDER BY timestamp DESC",con,params=(r.incident_id,))
            st.dataframe(related,use_container_width=True,hide_index=True)
        if r.status=="Open":
            if st.button("✓ Acknowledge incident",key=f"ack_{r.incident_id}",type="primary"):
                acknowledge_incident(r.incident_id)
                st.success(f"{r.incident_id} acknowledged.")
                st.rerun()
        else: st.caption(f"✓ Acknowledged at {r.acknowledged_at}")

elif page == "Data & Reports":
    hero("DATA MANAGEMENT","Data & Reports","Import alert events, preview and validate the file, then export operational reports.")
    st.markdown('<div class="panel"><h3>Import alert CSV</h3><p class="small-muted">Required columns: timestamp, service, host, severity, message</p>',unsafe_allow_html=True)
    uploaded=st.file_uploader("Choose a CSV file",type=["csv"])
    if uploaded is not None:
        try:
            incoming=pd.read_csv(uploaded)
            valid,errors,cleaned=validate_alert_dataframe(incoming)
            if valid:
                st.success(f"File validated · {len(cleaned)} rows ready to import.")
                st.dataframe(cleaned.head(15),use_container_width=True,hide_index=True)
                if st.button("Import alerts",type="primary"):
                    n=ingest_dataframe(cleaned)
                    st.success(f"Imported {n} alert records. Duplicate detection and incident grouping applied.")
                    st.rerun()
            else:
                st.error("This file cannot be imported yet:")
                for error in errors: st.write(f"• {error}")
        except Exception as exc: st.error(f"Could not read this CSV: {exc}")
    st.markdown("</div>",unsafe_allow_html=True)
    x,y=st.columns(2)
    with x:
        st.markdown('<div class="panel"><h4>All alerts</h4><p class="small-muted">Raw events, duplicate flags, and SHA-256 fingerprints.</p>',unsafe_allow_html=True)
        st.download_button("Download all alerts CSV",export_alerts(),"alertquest_all_alerts.csv","text/csv",use_container_width=True)
        st.markdown("</div>",unsafe_allow_html=True)
    with y:
        st.markdown('<div class="panel"><h4>Incident report</h4><p class="small-muted">Priority, grouping, root-cause hints, and acknowledgement status.</p>',unsafe_allow_html=True)
        st.download_button("Download incident report CSV",export_incidents(),"alertquest_incident_report.csv","text/csv",use_container_width=True)
        st.markdown("</div>",unsafe_allow_html=True)
    st.markdown("### Acknowledgement history")
    if history.empty: st.info("No incidents have been acknowledged yet.")
    else: st.dataframe(history,use_container_width=True,hide_index=True)
    st.caption("Records are stored locally in SQLite and persist after restarting the app.")
