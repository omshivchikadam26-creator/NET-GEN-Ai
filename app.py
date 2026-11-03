"""
NetSage AI - AI-assisted Cisco network troubleshooting system.

Run with:
    streamlit run app.py
"""

import json
import ast
import streamlit as st
import pandas as pd
import plotly.express as px

from core import utils
from core import rule_checker
from core.diagnosis_engine import diagnose_with_ai, get_active_mode

# ---------------------------------------------------------------------------
# Page config & global setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="NetSage AI",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

utils.ensure_dirs_and_logs()

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 6px;
}
.badge-high { background-color: #3a1414; color: #ff8080; border: 1px solid #ff8080; }
.badge-medium { background-color: #3a2e14; color: #ffc266; border: 1px solid #ffc266; }
.badge-low { background-color: #143a1c; color: #7dffa0; border: 1px solid #7dffa0; }
.badge-critical { background-color: #3a1414; color: #ff4d4d; border: 1px solid #ff4d4d; }
.badge-info { background-color: #142a3a; color: #7dc4ff; border: 1px solid #7dc4ff; }
.badge-accepted { background-color: #143a1c; color: #7dffa0; border: 1px solid #7dffa0; }
.badge-edited { background-color: #3a2e14; color: #ffc266; border: 1px solid #ffc266; }
.badge-rejected { background-color: #3a1414; color: #ff8080; border: 1px solid #ff8080; }
.mode-pill {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 14px;
    font-weight: 600;
    font-size: 0.85rem;
    border: 1px solid #7dc4ff;
    color: #7dc4ff;
    background-color: #142a3a;
}
.disclaimer-box {
    border: 1px solid #ffc266;
    background-color: #241d0a;
    padding: 14px 18px;
    border-radius: 8px;
    margin-top: 18px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def severity_badge(sev: str) -> str:
    sev_clean = (sev or "").strip().lower()
    cls = {
        "high": "badge-high",
        "medium": "badge-medium",
        "low": "badge-low",
        "critical": "badge-critical",
        "info": "badge-info",
    }.get(sev_clean, "badge-info")
    return f'<span class="badge {cls}">{sev or "Unknown"}</span>'


def review_badge(status: str) -> str:
    status_clean = (status or "").strip().lower()
    cls = {
        "accepted": "badge-accepted",
        "edited": "badge-edited",
        "rejected": "badge-rejected",
    }.get(status_clean, "badge-info")
    return f'<span class="badge {cls}">{status or "Pending"}</span>'


def parse_listish(value):
    """AI diagnosis fields like 'evidence' / 'fix_steps' are stored as python-list
    strings when logged/round-tripped through session state. This safely parses them
    back into a list for display."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return [text]


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "current_diagnosis" not in st.session_state:
    st.session_state.current_diagnosis = None  # dict: full diagnosis result + metadata
if "logged_diagnosis_ids" not in st.session_state:
    st.session_state.logged_diagnosis_ids = set()

cases_df = utils.load_cases()

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🛰️ NetSage AI")
st.sidebar.caption("AI-assisted Cisco network troubleshooting")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Diagnose Network", "Case Explorer", "Human Review", "Analytics"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
active_mode = get_active_mode()
st.sidebar.markdown(f'<span class="mode-pill">{active_mode}</span>', unsafe_allow_html=True)
if active_mode == "Demo Rule-Assisted Mode":
    st.sidebar.caption("Set LLM_API_KEY to enable AI Provider Mode.")
st.sidebar.markdown("---")
st.sidebar.caption(f"Dataset: {len(cases_df)} cases loaded")


# ---------------------------------------------------------------------------
# DASHBOARD PAGE
# ---------------------------------------------------------------------------

def page_dashboard():
    st.title("📊 Dashboard")
    st.caption("Project-level statistics for NetSage AI")

    ai_df = utils.load_ai_diagnoses()
    review_df = utils.load_human_reviews()

    total_cases = len(cases_df)
    high_crit = 0
    if not cases_df.empty and "severity" in cases_df.columns:
        high_crit = cases_df["severity"].astype(str).str.lower().isin(["high", "critical"]).sum()

    total_diagnoses = len(ai_df)
    accepted = (review_df["review_status"] == "Accepted").sum() if not review_df.empty else 0
    edited = (review_df["review_status"] == "Edited").sum() if not review_df.empty else 0
    rejected = (review_df["review_status"] == "Rejected").sum() if not review_df.empty else 0
    total_reviewed = accepted + edited + rejected
    agreement_rate = (accepted / total_reviewed * 100) if total_reviewed > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases", total_cases)
    c2.metric("High/Critical Severity", int(high_crit))
    c3.metric("AI Diagnoses Generated", total_diagnoses)
    c4.metric("AI-Human Agreement Rate", f"{agreement_rate:.1f}%")

    c5, c6, c7 = st.columns(3)
    c5.metric("Accepted Diagnoses", int(accepted))
    c6.metric("Edited Diagnoses", int(edited))
    c7.metric("Rejected Diagnoses", int(rejected))

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Issue Distribution")
        if not cases_df.empty and "concept_tag" in cases_df.columns:
            tag_counts = cases_df["concept_tag"].value_counts().reset_index()
            tag_counts.columns = ["concept_tag", "count"]
            fig = px.bar(tag_counts, x="concept_tag", y="count", color="concept_tag")
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Cases")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No case data available.")

    with col_right:
        st.subheader("Severity Distribution")
        if not cases_df.empty and "severity" in cases_df.columns:
            sev_counts = cases_df["severity"].value_counts().reset_index()
            sev_counts.columns = ["severity", "count"]
            fig = px.pie(sev_counts, names="severity", values="count", hole=0.45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No case data available.")

    st.subheader("Human Review Distribution")
    if not review_df.empty:
        rev_counts = review_df["review_status"].value_counts().reset_index()
        rev_counts.columns = ["review_status", "count"]
        fig = px.bar(rev_counts, x="review_status", y="count", color="review_status",
                     color_discrete_map={"Accepted": "#2ecc71", "Edited": "#f39c12", "Rejected": "#e74c3c"})
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Diagnoses")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No human review data yet. Run a diagnosis and review it to populate this chart.")


# ---------------------------------------------------------------------------
# DIAGNOSE NETWORK PAGE
# ---------------------------------------------------------------------------

def render_diagnosis_result(symptom, topology_note, show_output, case_id, rule_findings, diagnosis):
    st.markdown("---")
    st.subheader("🧭 Probable Root Cause")
    st.success(diagnosis["root_cause"])

    conf_col, layer_col = st.columns(2)
    with conf_col:
        st.markdown("**Confidence**")
        st.markdown(severity_badge(diagnosis["confidence"]), unsafe_allow_html=True)
    with layer_col:
        st.markdown("**OSI Layer**")
        st.write(diagnosis["osi_layer"])

    st.markdown("**Evidence**")
    for item in diagnosis["evidence"]:
        st.markdown(f"- {item}")

    with st.expander("🔎 Rule Checker Findings (Deterministic)", expanded=True):
        for f in rule_findings:
            st.markdown(
                f"{severity_badge(f['severity'])} **{f['rule_name']}** — {f['message']}",
                unsafe_allow_html=True,
            )
            if f.get("evidence"):
                st.code(f["evidence"], language="text")

    st.markdown("**Recommended Next Command**")
    st.code(diagnosis["next_command"], language="text")

    st.markdown("**Suggested Fix Steps**")
    for i, step in enumerate(diagnosis["fix_steps"], start=1):
        st.markdown(f"{i}. {step}")

    st.markdown("**Reasoning Summary**")
    st.write(diagnosis["reasoning_summary"])

    st.markdown(
        '<div class="disclaimer-box">⚠️ <b>This diagnosis is an AI-assisted recommendation. '
        'Human review is required before applying any network configuration change.</b></div>',
        unsafe_allow_html=True,
    )

    # Log the diagnosis once per run
    diag_id = st.session_state.current_diagnosis["diagnosis_id"]
    if diag_id not in st.session_state.logged_diagnosis_ids:
        utils.append_ai_diagnosis({
            "diagnosis_id": diag_id,
            "timestamp": utils.now_iso(),
            "case_id": case_id or "MANUAL",
            "symptom": symptom,
            "root_cause": diagnosis["root_cause"],
            "osi_layer": diagnosis["osi_layer"],
            "confidence": diagnosis["confidence"],
            "mode": get_active_mode(),
        })
        st.session_state.logged_diagnosis_ids.add(diag_id)


def page_diagnose():
    st.title("🩺 Diagnose Network")
    st.caption(f"Active engine mode: **{get_active_mode()}**")

    mode = st.radio("Select input mode", ["Select Existing Case", "Manual Input"], horizontal=True)

    symptom = topology_note = show_output = ""
    case_id = None
    severity = None

    if mode == "Select Existing Case":
        if cases_df.empty:
            st.warning("No cases available in data/cases.csv.")
            return
        selected_id = st.selectbox("Select a case", cases_df["case_id"].tolist())
        row = cases_df[cases_df["case_id"] == selected_id].iloc[0]
        case_id = row["case_id"]
        symptom = row["symptom"]
        topology_note = row["topology_note"]
        show_output = row["show_output"]
        severity = row["severity"]

        st.markdown(f"**Case ID:** {case_id}")
        st.markdown(f"**Severity:** {severity_badge(severity)}", unsafe_allow_html=True)
        st.markdown("**Symptom**")
        st.write(symptom)
        st.markdown("**Topology Note**")
        st.write(topology_note)
        with st.expander("Cisco Show Output", expanded=False):
            st.code(show_output, language="text")

    else:
        symptom = st.text_area("Symptom", height=100, placeholder="Describe the observed network problem...")
        topology_note = st.text_area("Topology Note", height=100, placeholder="Describe the relevant topology context...")
        show_output = st.text_area(
            "Cisco Show Command Output",
            height=220,
            placeholder="show ip interface brief\n\nGigabitEthernet0/0\nadministratively down",
        )

    st.markdown("---")
    run_clicked = st.button("🚀 RUN DIAGNOSIS", type="primary", use_container_width=True)

    if run_clicked:
        if not (symptom or "").strip() and not (show_output or "").strip():
            st.error("Please provide at least a symptom or show output before running diagnosis.")
            return

        rule_findings = rule_checker.run_all_checks(symptom, topology_note, show_output)
        diagnosis = diagnose_with_ai(symptom, topology_note, show_output, rule_findings)

        diag_id = utils.new_id("DIAG")
        st.session_state.current_diagnosis = {
            "diagnosis_id": diag_id,
            "case_id": case_id,
            "symptom": symptom,
            "topology_note": topology_note,
            "show_output": show_output,
            "rule_findings": rule_findings,
            "diagnosis": diagnosis,
        }

    if st.session_state.current_diagnosis is not None:
        cd = st.session_state.current_diagnosis
        render_diagnosis_result(
            cd["symptom"], cd["topology_note"], cd["show_output"],
            cd["case_id"], cd["rule_findings"], cd["diagnosis"],
        )


# ---------------------------------------------------------------------------
# CASE EXPLORER PAGE
# ---------------------------------------------------------------------------

def page_case_explorer():
    st.title("🗂️ Case Explorer")
    st.caption("Browse the full dataset. Expected fault is ground truth for evaluation only.")

    if cases_df.empty:
        st.warning("No cases available in data/cases.csv.")
        return

    f1, f2, f3 = st.columns(3)
    with f1:
        tags = ["All"] + sorted(cases_df["concept_tag"].dropna().unique().tolist())
        tag_filter = st.selectbox("Concept Tag", tags)
    with f2:
        layers = ["All"] + sorted(cases_df["osi_layer"].dropna().unique().tolist())
        layer_filter = st.selectbox("OSI Layer", layers)
    with f3:
        sevs = ["All"] + sorted(cases_df["severity"].dropna().unique().tolist())
        sev_filter = st.selectbox("Severity", sevs)

    filtered = cases_df.copy()
    if tag_filter != "All":
        filtered = filtered[filtered["concept_tag"] == tag_filter]
    if layer_filter != "All":
        filtered = filtered[filtered["osi_layer"] == layer_filter]
    if sev_filter != "All":
        filtered = filtered[filtered["severity"] == sev_filter]

    st.dataframe(
        filtered[["case_id", "symptom", "osi_layer", "concept_tag", "severity"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    if not filtered.empty:
        selected_id = st.selectbox("View case details", filtered["case_id"].tolist())
        row = filtered[filtered["case_id"] == selected_id].iloc[0]

        st.markdown(f"### {row['case_id']}")
        st.markdown(f"{severity_badge(row['severity'])}", unsafe_allow_html=True)
        st.markdown("**Symptom**")
        st.write(row["symptom"])
        st.markdown("**Topology Note**")
        st.write(row["topology_note"])
        st.markdown("**Show Output**")
        st.code(row["show_output"], language="text")
        st.markdown("**OSI Layer:** " + str(row["osi_layer"]))
        st.markdown("**Concept Tag:** " + str(row["concept_tag"]))
        st.markdown("**Ground Truth / Expected Diagnosis**")
        st.info(row["expected_fault"])
    else:
        st.info("No cases match the selected filters.")


# ---------------------------------------------------------------------------
# HUMAN REVIEW PAGE
# ---------------------------------------------------------------------------

def page_human_review():
    st.title("🧑‍💻 Human Review")
    st.caption("Every AI diagnosis is advisory. A human must Accept, Edit, or Reject it.")

    ai_df = utils.load_ai_diagnoses()
    review_df = utils.load_human_reviews()

    if ai_df.empty:
        st.info("No AI diagnoses have been generated yet. Go to 'Diagnose Network' to create one.")
        return

    reviewed_ids = set(review_df["diagnosis_id"].tolist()) if not review_df.empty else set()
    pending = ai_df[~ai_df["diagnosis_id"].isin(reviewed_ids)]

    if pending.empty:
        st.success("All AI diagnoses have been reviewed. 🎉")
        return

    st.write(f"**{len(pending)} diagnosis(es) pending review**")

    for _, diag in pending.iterrows():
        with st.container(border=True):
            st.markdown(f"#### {diag['diagnosis_id']}  ·  Case: {diag['case_id']}")
            st.markdown(f"**Symptom:** {diag['symptom']}")
            st.markdown(f"**AI Root Cause:** {diag['root_cause']}")
            st.markdown(f"**OSI Layer:** {diag['osi_layer']}")
            st.markdown(f"**Confidence:** {severity_badge(diag['confidence'])}", unsafe_allow_html=True)
            st.caption(f"Generated in {diag['mode']} at {diag['timestamp']}")

            action_key = f"action_{diag['diagnosis_id']}"
            action = st.radio(
                "Review action",
                ["Accept", "Edit", "Reject"],
                key=action_key,
                horizontal=True,
            )

            if action == "Accept":
                if st.button("✅ Confirm Accept", key=f"accept_{diag['diagnosis_id']}"):
                    utils.append_human_review({
                        "review_id": utils.new_id("REV"),
                        "diagnosis_id": diag["diagnosis_id"],
                        "timestamp": utils.now_iso(),
                        "case_id": diag["case_id"],
                        "ai_root_cause": diag["root_cause"],
                        "human_final_root_cause": diag["root_cause"],
                        "review_status": "Accepted",
                        "review_comment": "",
                    })
                    st.success("Diagnosis accepted.")
                    st.rerun()

            elif action == "Edit":
                new_root_cause = st.text_input(
                    "Corrected Root Cause", value=diag["root_cause"], key=f"rc_{diag['diagnosis_id']}"
                )
                new_osi = st.text_input(
                    "Corrected OSI Layer", value=diag["osi_layer"], key=f"osi_{diag['diagnosis_id']}"
                )
                new_fix = st.text_area(
                    "Corrected Fix Steps (one per line)", key=f"fix_{diag['diagnosis_id']}", height=100
                )
                comment = st.text_area("Review Comment", key=f"comment_edit_{diag['diagnosis_id']}", height=80)
                if st.button("✏️ Confirm Edit", key=f"edit_{diag['diagnosis_id']}"):
                    utils.append_human_review({
                        "review_id": utils.new_id("REV"),
                        "diagnosis_id": diag["diagnosis_id"],
                        "timestamp": utils.now_iso(),
                        "case_id": diag["case_id"],
                        "ai_root_cause": diag["root_cause"],
                        "human_final_root_cause": new_root_cause,
                        "review_status": "Edited",
                        "review_comment": comment,
                    })
                    st.success("Diagnosis edited and logged.")
                    st.rerun()

            elif action == "Reject":
                comment = st.text_area(
                    "Reason for rejection (required)", key=f"comment_reject_{diag['diagnosis_id']}", height=80
                )
                if st.button("❌ Confirm Reject", key=f"reject_{diag['diagnosis_id']}"):
                    if not comment.strip():
                        st.error("A comment is required to reject a diagnosis.")
                    else:
                        utils.append_human_review({
                            "review_id": utils.new_id("REV"),
                            "diagnosis_id": diag["diagnosis_id"],
                            "timestamp": utils.now_iso(),
                            "case_id": diag["case_id"],
                            "ai_root_cause": diag["root_cause"],
                            "human_final_root_cause": "",
                            "review_status": "Rejected",
                            "review_comment": comment,
                        })
                        st.success("Diagnosis rejected and logged.")
                        st.rerun()


# ---------------------------------------------------------------------------
# ANALYTICS PAGE
# ---------------------------------------------------------------------------

def page_analytics():
    st.title("📈 Analytics")
    st.caption("Responsible AI: measuring how often human reviewers accept, edit, or reject AI recommendations.")

    review_df = utils.load_human_reviews()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Fault Category Distribution")
        if not cases_df.empty:
            tag_counts = cases_df["concept_tag"].value_counts().reset_index()
            tag_counts.columns = ["concept_tag", "count"]
            fig = px.bar(tag_counts, x="concept_tag", y="count", color="concept_tag")
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Cases")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Severity Distribution")
        if not cases_df.empty:
            sev_counts = cases_df["severity"].value_counts().reset_index()
            sev_counts.columns = ["severity", "count"]
            fig = px.bar(sev_counts, x="severity", y="count", color="severity")
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Cases")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Human Review Distribution")
    if review_df.empty:
        st.info("No review data yet.")
    else:
        rev_counts = review_df["review_status"].value_counts().reset_index()
        rev_counts.columns = ["review_status", "count"]
        fig = px.pie(rev_counts, names="review_status", values="count", hole=0.45,
                     color="review_status",
                     color_discrete_map={"Accepted": "#2ecc71", "Edited": "#f39c12", "Rejected": "#e74c3c"})
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("AI-Human Agreement Metrics")
    if review_df.empty:
        st.info("No reviewed diagnoses yet — metrics will appear once Human Review has data.")
    else:
        total = len(review_df)
        accepted = (review_df["review_status"] == "Accepted").sum()
        edited = (review_df["review_status"] == "Edited").sum()
        rejected = (review_df["review_status"] == "Rejected").sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Agreement Rate", f"{accepted / total * 100:.1f}%")
        m2.metric("Edited Rate", f"{edited / total * 100:.1f}%")
        m3.metric("Rejected Rate", f"{rejected / total * 100:.1f}%")

        st.markdown("---")
        st.subheader("Human-in-the-Loop Correction Log")
        st.caption("Cases where AI was corrected by a human reviewer (Edited or Rejected).")
        corrections = review_df[review_df["review_status"].isin(["Edited", "Rejected"])]
        if corrections.empty:
            st.info("No edited or rejected diagnoses recorded yet.")
        else:
            display_df = corrections[[
                "case_id", "ai_root_cause", "human_final_root_cause", "review_status", "review_comment"
            ]].rename(columns={
                "case_id": "Case ID",
                "ai_root_cause": "AI Diagnosis",
                "human_final_root_cause": "Human Final Diagnosis",
                "review_status": "Review Status",
                "review_comment": "Human Comment",
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

PAGES = {
    "Dashboard": page_dashboard,
    "Diagnose Network": page_diagnose,
    "Case Explorer": page_case_explorer,
    "Human Review": page_human_review,
    "Analytics": page_analytics,
}

try:
    PAGES[page]()
except Exception as e:
    st.error(f"An unexpected error occurred while rendering this page: {e}")
    st.exception(e)
