<<<<<<< HEAD
# NetSage AI

**AI-assisted Cisco network troubleshooting system for junior network engineers.**

## Problem Statement

Junior network engineers often struggle to translate Cisco `show` command
output and symptom descriptions into an accurate root-cause diagnosis.
NetSage AI combines deterministic rule-based checks with AI-assisted
reasoning to propose a probable diagnosis — but the AI **never applies a
fix automatically**. A human reviewer always makes the final call.

```text
Problem
   ↓
Evidence Collection
   ↓
Rule-Based Checks
   +
AI Diagnosis
   ↓
Human Review
   ↓
Accept / Edit / Reject
   ↓
Final Recommendation
```

## Features

- **Dashboard** — project-level KPIs: case counts, severity breakdown,
  diagnosis counts, human review outcomes, AI-human agreement rate.
- **Diagnose Network** — pick an existing dataset case or enter a symptom /
  topology note / Cisco show output manually, then run a structured
  diagnosis.
- **Deterministic rule checker** — flags interface-down conditions, missing
  VLANs, trunk misconfiguration, missing routes, DHCP problems, duplicate
  IPs, and link-down interfaces from raw text evidence.
- **AI diagnosis engine** — structured root cause, OSI layer, confidence,
  evidence, next recommended command, fix steps, and reasoning summary.
  Runs in **Demo Rule-Assisted Mode** with no API key, or **AI Provider
  Mode** once `LLM_API_KEY` is set.
- **Case Explorer** — browse and filter all dataset cases; ground-truth
  `expected_fault` is clearly labeled and hidden during live diagnosis.
- **Human Review** — Accept / Edit / Reject every AI diagnosis, with
  mandatory comments on rejection and full edit history logged.
- **Analytics** — fault category and severity distributions, review
  outcome breakdown, agreement/edit/reject rates, and a correction log
  table showing every case where a human overruled or modified the AI.

## Architecture

```text
Problem → Evidence → Rule-Based Check + AI Analysis → Diagnosis → Human Review → Final Decision
```

The AI never automatically applies a network fix. It only proposes a
diagnosis and recommended remediation steps; a human must accept, edit,
or reject that proposal before any change would ever be applied outside
this tool.

## Technology Stack

- Python 3
- Streamlit (UI)
- Pandas (data processing, CSV logging)
- Plotly (charts)
- Standard library + `requests` (only used in optional AI Provider Mode)

## Folder Structure

```text
NetSage_AI/
│
├── app.py
├── requirements.txt
├── README.md
│
├── data/
│   └── cases.csv
│
├── core/
│   ├── __init__.py
│   ├── rule_checker.py
│   ├── diagnosis_engine.py
│   └── utils.py
│
├── prompts/
│   └── diagnose_prompt.md
│
└── logs/
    ├── ai_diagnoses.csv
    └── human_review_log.csv
```

`logs/` and its CSV files are created automatically on first run if
missing.

## Installation

```bash
cd NetSage_AI
pip install -r requirements.txt
```

## How to Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. It works fully in **Demo
Rule-Assisted Mode** with zero configuration.

### Optional: Enable AI Provider Mode

```bash
export LLM_API_KEY="your-api-key"
export LLM_PROVIDER="anthropic"
streamlit run app.py
```

If `LLM_API_KEY` is unset, the app automatically uses the deterministic
Demo Rule-Assisted engine — no external calls are made.

## Dataset

`data/cases.csv` contains 30 network troubleshooting cases with columns:

```text
case_id, symptom, topology_note, show_output, expected_fault,
osi_layer, concept_tag, severity
```

`expected_fault` is ground truth used only for dataset exploration and
evaluation (Case Explorer) — it is never shown during live diagnosis and
is never used by the AI engine to generate its answer.

## Human-in-the-Loop Workflow

1. A diagnosis is generated (rule checker + AI reasoning) and logged to
   `logs/ai_diagnoses.csv` with a unique diagnosis ID.
2. The diagnosis appears in **Human Review** as pending.
3. A reviewer chooses:
   - **Accept** — the AI diagnosis is correct as-is.
   - **Edit** — the reviewer corrects the root cause, OSI layer, and/or
     fix steps; both the original AI answer and the human's final answer
     are stored.
   - **Reject** — the reviewer disagrees entirely and must supply a
     comment explaining why.
4. Every review outcome is logged to `logs/human_review_log.csv`.
5. **Analytics** computes the AI-Human Agreement Rate
   (`Accepted / Total Reviewed × 100`), Edited Rate, and Rejected Rate,
   and displays a full correction table for transparency.

## Responsible AI Approach

- The AI diagnosis engine only reasons from evidence explicitly provided
  in the current request (symptom, topology note, show output, rule
  checker findings). It never has access to `expected_fault` when
  producing a live diagnosis.
- Confidence is explicitly downgraded to Medium/Low whenever evidence is
  incomplete, rather than guessing.
- The AI is instructed to always suggest a next diagnostic command when
  evidence is insufficient, instead of fabricating a root cause.
- Every diagnosis carries a persistent on-screen disclaimer: **"This
  diagnosis is an AI-assisted recommendation. Human review is required
  before applying any network configuration change."**
- No code path in this application executes or applies a network
  configuration change — the system is diagnostic and advisory only.
=======
# NET-GEN-Ai
>>>>>>> 2b40e1a2bbbff51077f1eeb0409962c80cbd3fd0
