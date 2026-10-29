"""
core/diagnosis_engine.py

AI diagnosis engine abstraction.

- Demo / Local Mode: a deterministic mock "AI" that reasons purely from
  rule_checker findings + keyword pattern matches in the provided evidence.
  It never looks at expected_fault (ground truth) to produce its answer.
- API Mode: a thin, swappable abstraction for a real LLM API, controlled by
  environment variables LLM_API_KEY / LLM_PROVIDER. Not hardcoded, not
  required for the app to run.

Both modes return a diagnosis dict following the same schema:

{
    "root_cause": str,
    "osi_layer": str,
    "confidence": "High" | "Medium" | "Low",
    "evidence": [str, ...],
    "next_command": str,
    "fix_steps": [str, ...],
    "reasoning_summary": str,
}
"""

import os
import re
from typing import List, Dict, Any


def get_active_mode() -> str:
    """Return 'AI Provider Mode' or 'Demo Rule-Assisted Mode' based on env config."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if api_key:
        return "AI Provider Mode"
    return "Demo Rule-Assisted Mode"


# ---------------------------------------------------------------------------
# Demo / Local deterministic engine
# ---------------------------------------------------------------------------

_OSI_KEYWORDS = [
    ("Layer 1 - Physical", ["administratively down", "cable", "physical", "sfp", "line protocol is down"]),
    ("Layer 2 - Data Link", ["vlan", "trunk", "not-trunking", "switchport", "spanning-tree", "mac address"]),
    ("Layer 3 - Network", ["ip route", "routing", "gateway", "subnet", "ospf", "eigrp", "static route"]),
    ("Layer 4 - Transport", ["tcp", "udp", "port", "access-list", "acl"]),
    ("Layer 7 - Application", ["dns", "http", "application", "name resolution"]),
]


def _infer_osi_layer(text: str) -> str:
    text_lower = text.lower()
    for layer, keywords in _OSI_KEYWORDS:
        for kw in keywords:
            if kw in text_lower:
                return layer
    return "Unknown / Insufficient Evidence"


def _confidence_from_findings(findings: List[Dict]) -> str:
    severities = [f.get("severity", "") for f in findings]
    if any(s == "High" for s in severities):
        return "High"
    if any(s == "Medium" for s in severities):
        return "Medium"
    return "Low"


def _root_cause_from_findings(findings: List[Dict], symptom: str) -> str:
    actionable = [f for f in findings if f.get("rule_name") != "No Deterministic Match"]
    if not actionable:
        return (
            "Insufficient deterministic evidence to identify a specific root cause. "
            "Additional show command output is required."
        )
    top = actionable[0]
    return f"{top['rule_name']}: {top['message']}"


def _next_command_from_findings(findings: List[Dict], show_output: str) -> str:
    rule_names = {f.get("rule_name") for f in findings}
    text = (show_output or "").lower()

    if "Missing VLAN" in rule_names or "Trunk Configuration Problem" in rule_names:
        return "show vlan brief"
    if "Missing Route" in rule_names:
        return "show ip route"
    if "Interface Down" in rule_names or "Interface Link Down" in rule_names:
        return "show interfaces status"
    if "DHCP Problem" in rule_names:
        return "show ip dhcp pool"
    if "Duplicate IP" in rule_names:
        return "show arp"
    if "show run" not in text:
        return "show running-config interface <affected-interface>"
    return "show ip interface brief"


def _fix_steps_from_findings(findings: List[Dict]) -> List[str]:
    steps = []
    rule_names = {f.get("rule_name") for f in findings}

    if "Interface Down" in rule_names:
        steps.append("Verify the interface configuration and issue 'no shutdown' if administratively down.")
        steps.append("Confirm physical cabling and SFP/port status.")
    if "Interface Link Down" in rule_names:
        steps.append("Check the physical cable, port, and remote-end interface for a link-layer mismatch.")
    if "Missing VLAN" in rule_names:
        steps.append("Create or correct the VLAN on the switch and reassign the correct access port.")
    if "Trunk Configuration Problem" in rule_names:
        steps.append("Reconfigure the port as a trunk (switchport mode trunk) and add the required VLAN to the allowed list.")
    if "Missing Route" in rule_names:
        steps.append("Add the missing static route or verify the dynamic routing protocol is advertising the network.")
    if "DHCP Problem" in rule_names:
        steps.append("Review and correct the DHCP pool configuration, including network, default-router, and address range.")
    if "Duplicate IP" in rule_names:
        steps.append("Identify the conflicting devices and reassign a unique IP address to one of them.")

    if not steps:
        steps.append("Gather additional show command output before proposing a fix; current evidence is insufficient.")

    steps.append("Human reviewer must validate this recommendation before any configuration change is applied.")
    return steps


def _reasoning_summary(findings: List[Dict], root_cause: str) -> str:
    actionable = [f for f in findings if f.get("rule_name") != "No Deterministic Match"]
    if not actionable:
        return (
            "No deterministic rule pattern matched the provided symptom, topology note, or show output. "
            "The recommendation reflects low confidence based on limited evidence."
        )
    names = ", ".join(sorted({f["rule_name"] for f in actionable}))
    return (
        f"Deterministic rule checks flagged: {names}. The most severe finding was used to derive the "
        f"probable root cause: '{root_cause}'. This reasoning is based only on the evidence provided, "
        "without reference to any ground-truth answer."
    )


def _evidence_list(findings: List[Dict]) -> List[str]:
    ev = []
    for f in findings:
        if f.get("rule_name") == "No Deterministic Match":
            continue
        piece = f.get("evidence") or f.get("message")
        if piece and piece not in ev:
            ev.append(piece)
    if not ev:
        ev.append("No specific line-level evidence matched; diagnosis based on general absence of expected configuration.")
    return ev


def demo_diagnose(symptom: str, topology_note: str, show_output: str, rule_results: List[Dict]) -> Dict[str, Any]:
    """
    Deterministic mock AI diagnosis engine. Uses ONLY rule_results + textual
    keyword patterns from the provided evidence. Never references dataset
    ground truth (expected_fault).
    """
    combined_text = f"{symptom}\n{topology_note}\n{show_output}"

    root_cause = _root_cause_from_findings(rule_results, symptom)
    osi_layer = _infer_osi_layer(combined_text)
    confidence = _confidence_from_findings(rule_results)
    evidence = _evidence_list(rule_results)
    next_command = _next_command_from_findings(rule_results, show_output)
    fix_steps = _fix_steps_from_findings(rule_results)
    reasoning_summary = _reasoning_summary(rule_results, root_cause)

    return {
        "root_cause": root_cause,
        "osi_layer": osi_layer,
        "confidence": confidence,
        "evidence": evidence,
        "next_command": next_command,
        "fix_steps": fix_steps,
        "reasoning_summary": reasoning_summary,
    }


# ---------------------------------------------------------------------------
# API Mode (pluggable, not required to run the app)
# ---------------------------------------------------------------------------

def api_diagnose(symptom: str, topology_note: str, show_output: str, rule_results: List[Dict]) -> Dict[str, Any]:
    """
    Placeholder abstraction for a real LLM API call.

    Reads LLM_API_KEY / LLM_PROVIDER from the environment. If a request
    library or provider SDK is unavailable, or the call fails for any
    reason, falls back to the demo engine and marks confidence as Low
    with an explanatory reasoning summary so the UI never crashes.
    """
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    api_key = os.environ.get("LLM_API_KEY", "").strip()

    if not api_key:
        # No key configured - should not normally be called (see diagnose_with_ai),
        # but guard anyway.
        return demo_diagnose(symptom, topology_note, show_output, rule_results)

    try:
        if provider in ("anthropic", "", "claude"):
            return _call_anthropic(symptom, topology_note, show_output, rule_results, api_key)
        else:
            # Unknown provider configured - fail safe to demo mode.
            result = demo_diagnose(symptom, topology_note, show_output, rule_results)
            result["reasoning_summary"] = (
                f"LLM_PROVIDER '{provider}' is not recognized by this build. "
                "Falling back to rule-assisted demo reasoning. " + result["reasoning_summary"]
            )
            return result
    except Exception as e:
        result = demo_diagnose(symptom, topology_note, show_output, rule_results)
        result["confidence"] = "Low"
        result["reasoning_summary"] = (
            f"AI provider call failed ({type(e).__name__}); falling back to rule-assisted demo reasoning. "
            + result["reasoning_summary"]
        )
        return result


def _call_anthropic(symptom, topology_note, show_output, rule_results, api_key) -> Dict[str, Any]:
    """
    Example real API integration using the Anthropic Messages API.
    Imports are done lazily so the app runs even if the 'anthropic' or
    'requests' packages aren't installed in Demo Mode.
    """
    import json
    import requests

    findings_text = "\n".join(
        f"- [{f.get('severity')}] {f.get('rule_name')}: {f.get('message')} (evidence: {f.get('evidence')})"
        for f in rule_results
    )

    system_prompt = (
        "You are a Cisco network troubleshooting assistant. Use ONLY the evidence provided. "
        "Never invent configuration that isn't shown. Respond ONLY with a JSON object matching this schema: "
        '{"root_cause": "", "osi_layer": "", "confidence": "High|Medium|Low", "evidence": [], '
        '"next_command": "", "fix_steps": [], "reasoning_summary": ""}'
    )

    user_prompt = f"""
Symptom: {symptom}

Topology Note: {topology_note}

Show Output:
{show_output}

Rule Checker Findings:
{findings_text}

Return only the JSON object, no other text.
"""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    raw_text = "\n".join(text_blocks).strip()
    raw_text = re.sub(r"^```json|```$", "", raw_text, flags=re.MULTILINE).strip()
    parsed = json.loads(raw_text)

    # Normalize / guard against missing keys
    return {
        "root_cause": parsed.get("root_cause", "Unknown"),
        "osi_layer": parsed.get("osi_layer", "Unknown"),
        "confidence": parsed.get("confidence", "Low"),
        "evidence": parsed.get("evidence", []) or [],
        "next_command": parsed.get("next_command", ""),
        "fix_steps": parsed.get("fix_steps", []) or [],
        "reasoning_summary": parsed.get("reasoning_summary", ""),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def diagnose_with_ai(symptom: str, topology_note: str, show_output: str, rule_results: List[Dict]) -> Dict[str, Any]:
    """
    Main entry point used by the UI. Routes to API mode if LLM_API_KEY is
    configured, otherwise uses the deterministic demo engine. Always
    returns a dict matching the diagnosis schema; never raises.
    """
    symptom = symptom or ""
    topology_note = topology_note or ""
    show_output = show_output or ""
    rule_results = rule_results or []

    try:
        if get_active_mode() == "AI Provider Mode":
            return api_diagnose(symptom, topology_note, show_output, rule_results)
        return demo_diagnose(symptom, topology_note, show_output, rule_results)
    except Exception as e:
        return {
            "root_cause": "Diagnosis engine error - unable to generate a recommendation.",
            "osi_layer": "Unknown",
            "confidence": "Low",
            "evidence": [f"Internal error: {type(e).__name__}"],
            "next_command": "show running-config",
            "fix_steps": ["Gather additional evidence and retry diagnosis."],
            "reasoning_summary": "An internal error occurred while generating the diagnosis.",
        }
