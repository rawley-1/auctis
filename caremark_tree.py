from __future__ import annotations

from typing import Any, Dict


def infer_caremark_facts_from_question(question: str) -> Dict[str, bool]:
    q = (question or "").lower()

    return {
        "has_reporting_system": not any(
            phrase in q
            for phrase in [
                "no reporting system",
                "no compliance system",
                "no oversight system",
                "no controls",
                "utter failure",
                "never implemented",
            ]
        ),
        "monitors_reporting_system": not any(
            phrase in q
            for phrase in [
                "failed to monitor",
                "ignored monitoring",
                "consciously failed to monitor",
                "did not monitor",
                "never reviewed reports",
                "ignored red flags",
                "red flags were ignored",
            ]
        ),
        "mission_critical_risk": any(
            phrase in q
            for phrase in [
                "mission critical",
                "mission-critical",
                "core compliance",
                "core operations",
                "food safety",
                "regulatory risk",
                "safety issue",
                "critical risk",
            ]
        ),
        "red_flags_ignored": any(
            phrase in q
            for phrase in [
                "ignored red flags",
                "red flags",
                "warnings ignored",
                "board ignored warnings",
                "failed to respond to red flags",
                "failed to act on red flags",
            ]
        ),
    }


def evaluate_caremark_tree(facts: Dict[str, bool]) -> Dict[str, Any]:
    has_reporting_system = facts.get("has_reporting_system", False)
    monitors_reporting_system = facts.get("monitors_reporting_system", False)
    mission_critical_risk = facts.get("mission_critical_risk", False)
    red_flags_ignored = facts.get("red_flags_ignored", False)

    result: Dict[str, Any] = {
        "doctrine": "oversight",
        "path": [],
        "outcome": "",
        "risk_level": "",
        "primary_failure": "",
        "reason": "",
    }

    if not has_reporting_system:
        result["path"].append("no_reporting_system")
        result["outcome"] = "potential_oversight_breach"
        result["risk_level"] = "high"
        result["primary_failure"] = "utter_failure"
        result["reason"] = (
            "The facts suggest an utter failure to attempt to assure a reasonable reporting "
            "or information system exists."
        )
        return result

    result["path"].append("reporting_system_exists")

    if not monitors_reporting_system:
        result["path"].append("no_monitoring")
        result["outcome"] = "potential_oversight_breach"
        result["risk_level"] = "high"
        result["primary_failure"] = "failure_to_monitor"
        result["reason"] = (
            "The facts suggest a conscious failure to monitor or oversee an existing "
            "reporting or information system."
        )
        return result

    result["path"].append("monitoring_exists")

    if mission_critical_risk and red_flags_ignored:
        result["path"].append("mission_critical_red_flags")
        result["outcome"] = "heightened_oversight_risk"
        result["risk_level"] = "medium_high"
        result["primary_failure"] = "red_flags"
        result["reason"] = (
            "The board appears to have monitoring structures, but ignored red flags "
            "in a mission-critical area."
        )
        return result

    result["path"].append("basic_oversight_present")
    result["outcome"] = "lower_oversight_risk"
    result["risk_level"] = "low"
    result["primary_failure"] = "none"
    result["reason"] = (
        "The facts suggest the board established and monitored an oversight system, "
        "which weakens an oversight-breach theory."
    )
    return result


def build_caremark_tree_summary(tree_result: Dict[str, Any]) -> str:
    path = " -> ".join(tree_result.get("path", []))
    return (
        f"Doctrine: {tree_result.get('doctrine', '')}\n"
        f"Path: {path}\n"
        f"Outcome: {tree_result.get('outcome', '')}\n"
        f"Risk Level: {tree_result.get('risk_level', '')}\n"
        f"Primary Failure: {tree_result.get('primary_failure', '')}\n"
        f"Reason: {tree_result.get('reason', '')}"
    )