import os
import time

import httpx
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Agentic ETL Lab", layout="wide")
st.title("Agentic ETL — Instagram Export Pipeline")
st.caption("Upload an Instagram Data Export ZIP or sample JSON and watch the agent pipeline run.")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded = st.file_uploader("Upload .zip or .json", type=["zip", "json"])
    simulate_failure = st.checkbox("Simulate silver failure (self-healing demo)", value=False)

with col2:
    st.markdown("**Pipeline steps**")
    st.markdown("1. Ingestion\n2. Profiler\n3. Engineer\n4. Executor\n5. Validator\n6. Human review")
    st.info("No Celery worker needed — jobs run in the API process.", icon="ℹ️")

if uploaded and st.button("Run ETL Pipeline", type="primary"):
    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
    params = {"simulate_failure": str(simulate_failure).lower()}
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{API_BASE}/ingest/export", files=files, params=params)
            response.raise_for_status()
            job = response.json()
            st.session_state["job_id"] = job["id"]
            st.success(f"Job started: `{job['id']}`")
    except httpx.ConnectError:
        st.error(f"Cannot reach API at {API_BASE}. Start it with: `uvicorn app.main:app --reload --port 8000`")
    except httpx.HTTPStatusError as exc:
        st.error(f"Upload failed: {exc.response.text}")

job_id = st.session_state.get("job_id")
if job_id:
    st.divider()
    st.subheader(f"Job `{job_id}`")

    try:
        with httpx.Client(timeout=30.0) as client:
            detail = client.get(f"{API_BASE}/ingest/jobs/{job_id}").json()
    except httpx.ConnectError:
        st.error("Lost connection to API.")
        st.stop()

    status = detail.get("status")
    st.metric("Status", status)

    if detail.get("error_message"):
        st.error(detail["error_message"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Bronze records", detail.get("bronze_count", 0))
    c2.metric("Silver records", detail.get("silver_count", 0))
    c3.metric(
        "Quality",
        detail.get("taste_profile", {}).get("quality_score", 0) if detail.get("taste_profile") else 0,
    )

    if detail.get("agent_runs"):
        st.markdown("**Agent run logs**")
        latest = detail["agent_runs"][-1]
        st.json(
            {
                "thread_id": latest["thread_id"],
                "status": latest["status"],
                "step": latest["current_step"],
                "logs": latest.get("logs"),
            }
        )

    if status == "awaiting_approval":
        st.warning("Pipeline awaiting human approval.")
        approve_col1, approve_col2 = st.columns(2)
        with approve_col1:
            if st.button("Approve gold write", type="primary"):
                with httpx.Client(timeout=30.0) as client:
                    client.post(f"{API_BASE}/ingest/jobs/{job_id}/approve", json={"approved": True})
                st.rerun()
        with approve_col2:
            if st.button("Reject"):
                with httpx.Client(timeout=30.0) as client:
                    client.post(f"{API_BASE}/ingest/jobs/{job_id}/approve", json={"approved": False})
                st.rerun()

    taste = detail.get("taste_profile")
    if taste:
        st.subheader("Taste Profile (Gold Layer)")
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("**Top topics**")
            st.dataframe(taste.get("top_topics", []), use_container_width=True)
        with t2:
            st.markdown("**Top hooks**")
            st.dataframe(taste.get("top_hooks", []), use_container_width=True)
        st.json(taste.get("engagement_summary", {}))

    if status in {"pending", "running"}:
        with st.spinner("Pipeline running…"):
            time.sleep(2)
        st.rerun()
