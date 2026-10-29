"""
core/utils.py

Shared utility helpers: data loading, log file management, ID generation.
"""

import os
import uuid
import pandas as pd
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

CASES_CSV = os.path.join(DATA_DIR, "cases.csv")
AI_DIAGNOSES_CSV = os.path.join(LOGS_DIR, "ai_diagnoses.csv")
HUMAN_REVIEW_CSV = os.path.join(LOGS_DIR, "human_review_log.csv")

AI_DIAGNOSES_COLUMNS = [
    "diagnosis_id", "timestamp", "case_id", "symptom",
    "root_cause", "osi_layer", "confidence", "mode",
]

HUMAN_REVIEW_COLUMNS = [
    "review_id", "diagnosis_id", "timestamp", "case_id",
    "ai_root_cause", "human_final_root_cause", "review_status", "review_comment",
]


def ensure_dirs_and_logs():
    """Create missing folders/log files with correct headers if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    if not os.path.exists(AI_DIAGNOSES_CSV):
        pd.DataFrame(columns=AI_DIAGNOSES_COLUMNS).to_csv(AI_DIAGNOSES_CSV, index=False)

    if not os.path.exists(HUMAN_REVIEW_CSV):
        pd.DataFrame(columns=HUMAN_REVIEW_COLUMNS).to_csv(HUMAN_REVIEW_CSV, index=False)


def load_cases() -> pd.DataFrame:
    """Load the cases.csv dataset. Returns an empty DataFrame with expected columns on failure."""
    expected_cols = [
        "case_id", "symptom", "topology_note", "show_output",
        "expected_fault", "osi_layer", "concept_tag", "severity",
    ]
    try:
        df = pd.read_csv(CASES_CSV)
        # Ensure all expected columns exist even if the CSV is malformed/missing some.
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        df = df.dropna(subset=["case_id"])
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=expected_cols)
    except Exception:
        return pd.DataFrame(columns=expected_cols)


def load_ai_diagnoses() -> pd.DataFrame:
    ensure_dirs_and_logs()
    try:
        df = pd.read_csv(AI_DIAGNOSES_CSV)
        for col in AI_DIAGNOSES_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=AI_DIAGNOSES_COLUMNS)


def load_human_reviews() -> pd.DataFrame:
    ensure_dirs_and_logs()
    try:
        df = pd.read_csv(HUMAN_REVIEW_CSV)
        for col in HUMAN_REVIEW_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=HUMAN_REVIEW_COLUMNS)


def append_ai_diagnosis(row: dict):
    ensure_dirs_and_logs()
    df = load_ai_diagnoses()
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(AI_DIAGNOSES_CSV, index=False)


def append_human_review(row: dict):
    ensure_dirs_and_logs()
    df = load_human_reviews()
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(HUMAN_REVIEW_CSV, index=False)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
