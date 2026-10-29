"""
core/rule_checker.py

Deterministic, rule-based Cisco network fault checker.

This module NEVER calls an AI model. It only looks for concrete textual
evidence inside symptom / topology_note / show_output and returns a list
of structured findings. It never claims certainty beyond what is present
in the evidence, and it always returns a list (possibly empty / a single
"no issues detected" finding) so callers can rely on a consistent shape.
"""

import re
from typing import List, Dict


def _finding(rule_name: str, severity: str, message: str, evidence: str) -> Dict:
    return {
        "rule_name": rule_name,
        "severity": severity,
        "message": message,
        "evidence": evidence.strip() if evidence else "",
    }


def _extract_vlans_mentioned(text: str) -> List[str]:
    """Find VLAN numbers mentioned as 'VLAN 10', 'vlan10', etc."""
    return re.findall(r"vlan\s*0*(\d{1,4})", text, flags=re.IGNORECASE)


def _extract_vlan_table_ids(show_output: str) -> List[str]:
    """Pull VLAN IDs that actually appear in a 'show vlan brief' style table."""
    ids = []
    for line in show_output.splitlines():
        m = re.match(r"\s*(\d{1,4})\s+\S+", line)
        if m:
            ids.append(m.group(1))
    return ids


def check_interface_down(show_output: str) -> List[Dict]:
    findings = []
    text = show_output.lower()
    if "administratively down" in text:
        findings.append(_finding(
            "Interface Down",
            "High",
            "An interface is administratively shut down.",
            _grab_line(show_output, "administratively down"),
        ))
    if re.search(r"\bdown\s+down\b", text):
        findings.append(_finding(
            "Interface Down",
            "High",
            "An interface shows down/down status (physical layer + line protocol both down).",
            _grab_line(show_output, "down"),
        ))
    return findings


def check_interface_link_down(show_output: str) -> List[Dict]:
    findings = []
    if re.search(r"is down,\s*line protocol is down", show_output, flags=re.IGNORECASE):
        findings.append(_finding(
            "Interface Link Down",
            "High",
            "Interface line protocol is down, indicating a physical/data-link connectivity problem.",
            _grab_line(show_output, "line protocol is down"),
        ))
    return findings


def check_missing_vlan(symptom: str, topology_note: str, show_output: str) -> List[Dict]:
    findings = []
    combined_context = f"{symptom}\n{topology_note}"
    mentioned = set(_extract_vlans_mentioned(combined_context))
    if not mentioned:
        return findings
    table_ids = set(_extract_vlan_table_ids(show_output))
    missing = [v for v in mentioned if v not in table_ids]
    if missing and table_ids:
        findings.append(_finding(
            "Missing VLAN",
            "Medium",
            f"VLAN(s) {', '.join(sorted(missing))} referenced in symptom/topology but not found in the VLAN table output.",
            _grab_line(show_output, "vlan") or "VLAN table did not list the referenced VLAN(s).",
        ))
    return findings


def check_trunk_problems(symptom: str, topology_note: str, show_output: str) -> List[Dict]:
    findings = []
    text = show_output.lower()
    if "not-trunking" in text:
        findings.append(_finding(
            "Trunk Configuration Problem",
            "High",
            "A switchport that should be a trunk is reporting a not-trunking operational mode.",
            _grab_line(show_output, "not-trunking"),
        ))

    combined_context = f"{symptom}\n{topology_note}"
    mentioned = set(_extract_vlans_mentioned(combined_context))
    trunk_allowed_match = re.search(
        r"(trunking vlans enabled|allowed vlan[s]?)[:\s]*([0-9,\-\s]+)",
        show_output,
        flags=re.IGNORECASE,
    )
    if mentioned and trunk_allowed_match:
        allowed_raw = trunk_allowed_match.group(2)
        allowed_ids = set(re.findall(r"\d+", allowed_raw))
        missing = [v for v in mentioned if v not in allowed_ids]
        if missing:
            findings.append(_finding(
                "Trunk Configuration Problem",
                "Medium",
                f"VLAN(s) {', '.join(sorted(missing))} appear to be missing from the trunk's allowed VLAN list.",
                trunk_allowed_match.group(0),
            ))
    return findings


def check_missing_route(symptom: str, topology_note: str, show_output: str) -> List[Dict]:
    findings = []
    if "show ip route" not in show_output.lower():
        return findings

    # Look for an IP/subnet mentioned in symptom/topology that doesn't appear in the route table
    combined_context = f"{symptom}\n{topology_note}"
    referenced_networks = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})(?:/(\d{1,2}))?\b", combined_context)

    route_section = show_output
    for net, mask in referenced_networks:
        octets = net.split(".")
        network_prefix = ".".join(octets[:3])
        if network_prefix not in route_section:
            findings.append(_finding(
                "Missing Route",
                "High",
                f"Network {net}{'/' + mask if mask else ''} referenced in the symptom/topology is not present in the routing table.",
                _grab_line(show_output, "show ip route") or "show ip route output did not list the expected network.",
            ))
    return findings


def check_dhcp_problems(show_output: str) -> List[Dict]:
    findings = []
    text = show_output.lower()

    if "dhcp" in text or "ip helper-address" in text:
        if "no ip dhcp pool" in text or ("dhcp" in text and "pool" not in text and "ip helper-address" not in text):
            findings.append(_finding(
                "DHCP Problem",
                "Medium",
                "No DHCP pool configuration appears to be present where DHCP service is expected.",
                _grab_line(show_output, "dhcp"),
            ))

        if re.search(r"0\s+leases?\s+available|pool.*exhaust|no addresses available", text):
            findings.append(_finding(
                "DHCP Problem",
                "High",
                "DHCP pool appears to be exhausted (no addresses available).",
                _grab_line(show_output, "exhaust") or _grab_line(show_output, "available"),
            ))

        default_router_match = re.search(r"default-router\s+(\d{1,3}(?:\.\d{1,3}){3})", show_output, flags=re.IGNORECASE)
        network_match = re.search(r"network\s+(\d{1,3}(?:\.\d{1,3}){3})", show_output, flags=re.IGNORECASE)
        if default_router_match and network_match:
            dr_prefix = ".".join(default_router_match.group(1).split(".")[:3])
            net_prefix = ".".join(network_match.group(1).split(".")[:3])
            if dr_prefix != net_prefix:
                findings.append(_finding(
                    "DHCP Problem",
                    "High",
                    f"DHCP default-router {default_router_match.group(1)} does not appear to be on the same subnet as the configured DHCP network {network_match.group(1)}.",
                    f"{default_router_match.group(0)} / {network_match.group(0)}",
                ))
    return findings


def check_duplicate_ip(show_output: str) -> List[Dict]:
    findings = []
    ips = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", show_output)
    seen = {}
    for ip in ips:
        seen[ip] = seen.get(ip, 0) + 1
    duplicates = [ip for ip, count in seen.items() if count > 1]
    if duplicates:
        findings.append(_finding(
            "Duplicate IP",
            "High",
            f"IP address(es) {', '.join(duplicates)} appear more than once in the provided device output, suggesting a possible duplicate IP assignment.",
            _grab_line(show_output, duplicates[0]),
        ))
    return findings


def _grab_line(text: str, keyword: str) -> str:
    """Return the first line containing keyword (case-insensitive), for evidence display."""
    if not keyword:
        return ""
    for line in text.splitlines():
        if keyword.lower() in line.lower():
            return line.strip()
    return ""


def run_all_checks(symptom: str, topology_note: str, show_output: str) -> List[Dict]:
    """
    Run every deterministic rule check and return a combined list of findings.
    Always returns a list. If nothing is detected, returns a single
    informational finding stating that no rule matched.
    """
    symptom = symptom or ""
    topology_note = topology_note or ""
    show_output = show_output or ""

    findings: List[Dict] = []
    findings.extend(check_interface_down(show_output))
    findings.extend(check_interface_link_down(show_output))
    findings.extend(check_missing_vlan(symptom, topology_note, show_output))
    findings.extend(check_trunk_problems(symptom, topology_note, show_output))
    findings.extend(check_missing_route(symptom, topology_note, show_output))
    findings.extend(check_dhcp_problems(show_output))
    findings.extend(check_duplicate_ip(show_output))

    if not findings:
        findings.append(_finding(
            "No Deterministic Match",
            "Info",
            "No deterministic rule pattern matched the provided evidence. This does not rule out a fault; "
            "it means the available text did not match a known signature.",
            "",
        ))

    return findings
