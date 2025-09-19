"""Exception & QA cockpit backed by the CSV store."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from common.db import read_table, toast_info, toast_ok, write_table
from common.etl import add_exception

st.set_page_config(page_title="Exceptions & QA", layout="wide")

st.title("🚨 Exceptions & QA")
st.caption("Review unresolved data issues, add follow-ups, and close out fixes.")


def load_exceptions() -> pd.DataFrame:
    df = read_table("exceptions")
    if df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "timestamp",
                "code",
                "message",
                "severity",
                "context",
                "resolved",
                "resolved_at",
                "resolved_by",
            ]
        )
    df = df.copy()
    for col in ["resolved", "timestamp", "severity", "context", "resolved_at", "resolved_by"]:
        if col not in df.columns:
            df[col] = "" if col != "resolved" else False
    df["resolved"] = (
        df["resolved"].astype(str).str.lower().isin(["true", "1", "yes"])
    )
    df["timestamp"] = df["timestamp"].fillna("")
    df["severity"] = df["severity"].fillna("error")
    df["context"] = df["context"].fillna("")
    df["resolved_at"] = df.get("resolved_at", "").fillna("")
    df["resolved_by"] = df.get("resolved_by", "").fillna("")
    return df


def resolve_exception(exception_id: str) -> None:
    df = load_exceptions()
    mask = df["id"] == exception_id
    if not mask.any():
        toast_info("Exception already cleared.")
        return
    df.loc[mask, "resolved"] = True
    df.loc[mask, "resolved_at"] = datetime.utcnow().isoformat(timespec="seconds")
    df.loc[mask, "resolved_by"] = st.session_state.get("resolved_by", "app_user")
    write_table("exceptions", df)
    toast_ok("Exception resolved")
    st.rerun()


exceptions_df = load_exceptions()
open_issues = exceptions_df[~exceptions_df["resolved"]]
resolved_issues = exceptions_df[exceptions_df["resolved"]]

severity_filter = st.multiselect(
    "Filter by severity",
    options=["error", "warning", "info"],
    default=["error", "warning", "info"],
)

if severity_filter:
    open_issues = open_issues[open_issues["severity"].isin(severity_filter)]

st.subheader("Log manual follow-up")
with st.form("add_exception_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    severity = col1.selectbox("Severity", ["error", "warning", "info"], index=0)
    code = col1.text_input("Code", placeholder="MISSING_PRICE")
    message = col2.text_input("Message", placeholder="Add price to Sysco case 12345")
    context = st.text_area("Context / remediation notes", placeholder="Link to sheet, owner, etc.")
    submitted = st.form_submit_button("Add to log", type="primary")
    if submitted:
        if not code.strip():
            toast_info("Provide a short code for the issue.")
        else:
            add_exception(code=code.strip(), message=message.strip(), severity=severity, context=context.strip())
            toast_ok("Exception logged")
            st.rerun()


st.subheader("Open issues")
if open_issues.empty:
    st.success("All clear — no open exceptions.")
else:
    open_issues = open_issues.sort_values("timestamp", ascending=False)
    for _, issue in open_issues.iterrows():
        header = f"[{issue['severity'].upper()}] {issue['code']}"
        with st.expander(header, expanded=issue["severity"] == "error"):
            st.write(issue.get("message", ""))
            meta_cols = st.columns(3)
            meta_cols[0].markdown(f"**Logged:** {issue.get('timestamp', '')}")
            meta_cols[1].markdown(f"**Context:** {issue.get('context', '') or '—'}")
            meta_cols[2].markdown(f"**ID:** {issue.get('id', '')}")
            if st.button("Mark resolved", key=f"resolve_{issue['id']}"):
                resolve_exception(issue["id"])


st.subheader("Recently resolved")
if resolved_issues.empty:
    st.info("Resolved issues will appear here for traceability.")
else:
    recent = resolved_issues.sort_values("resolved_at", ascending=False).head(20)
    st.dataframe(
        recent[["timestamp", "code", "message", "resolved_at", "resolved_by"]]
        .rename(
            columns={
                "timestamp": "Logged",
                "code": "Code",
                "message": "Message",
                "resolved_at": "Resolved",
                "resolved_by": "By",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
