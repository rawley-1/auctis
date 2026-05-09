from __future__ import annotations
import re

from typing import Dict, List, Optional, Any

from doctrine_config import DOCTRINE_LABELS
from rule_units import (
    get_rule_text,
    get_rule_triplet,
    has_rule_units,
    get_core_concept,
)


def synthesize_structured_short_answer(target_lines: List[str]) -> str:
    real_lines = [x for x in target_lines if x != "unknown"]

    if len(real_lines) >= 2:
        line_a, line_b = real_lines[0], real_lines[1]
        label_a = DOCTRINE_LABELS.get(line_a) or line_a.replace("_", " ").title()
        label_b = DOCTRINE_LABELS.get(line_b) or line_b.replace("_", " ").title()
        return f"{label_a} establishes the governing framework for one fiduciary setting, whereas {label_b} governs a distinct one."

    if len(real_lines) == 1:
        label = DOCTRINE_LABELS.get(real_lines[0]) or real_lines[0].replace("_", " ").title()
        return f"{label} supplies the governing doctrinal framework."

    return "The governing doctrinal framework depends on the fiduciary setting."

def dedupe_phrases(text: str) -> str:
    sentences = text.split(". ")
    seen = set()
    out = []
    for s in sentences:
        norm = s.lower().strip()
        if norm not in seen:
            seen.add(norm)
            out.append(s)
    return ". ".join(out)


def synthesize_short_answer(
    target_lines: List[str],
    tree_result: Optional[Dict[str, Any]] = None,
) -> str:
    if "oversight" in target_lines:
        if tree_result is None:
            return "Caremark requires utter failure, whereas Marchand requires good faith monitoring."

        primary_failure = tree_result.get("primary_failure", "")
        outcome = tree_result.get("outcome", "")

        if primary_failure == "utter_failure":
            return "The theory sounds in implementation failure, not monitoring failure."
        if primary_failure == "failure_to_monitor":
            return "The theory sounds in monitoring failure, not implementation failure."
        if primary_failure == "red_flags":
            return "The theory sounds in mission-critical monitoring failure."
        if outcome == "lower_oversight_risk":
            return "The facts suggest lower oversight risk, not a likely Caremark breach."

        return "Caremark requires utter failure, whereas Marchand requires good faith monitoring."

    return synthesize_structured_short_answer(target_lines)


def synthesize_key_distinction(target_lines: List[str]) -> str:
    real_lines = [x for x in target_lines if x != "unknown"]

    if len(real_lines) < 2:
        return "The doctrine identifies the governing fiduciary standard."

    line_a, line_b = real_lines[0], real_lines[1]

    label_a = DOCTRINE_LABELS.get(line_a) or line_a.replace("_", " ").title()
    label_b = DOCTRINE_LABELS.get(line_b) or line_b.replace("_", " ").title()

    concept_a = get_core_concept(line_a)
    concept_b = get_core_concept(line_b)

    if concept_a and concept_b:
        return f"{label_a} doctrine addresses {concept_a}, whereas {label_b} doctrine addresses {concept_b}."

    return f"{label_a} doctrine governs one fiduciary setting, whereas {label_b} doctrine governs a distinct one."


def synthesize_rule_from_quotes(role_quote_map, target_lines=None):
    target_lines = target_lines or []
    if "oversight" in target_lines:
        return (
            "Caremark oversight liability arises where directors make an utter failure to attempt "
            "to assure that a reasonable reporting or information system exists, and Stone further "
            "clarifies that such misconduct constitutes a failure to act in good faith as a subsidiary "
            "element of the duty of loyalty. Marchand further requires directors to make a good faith "
            "effort to implement an oversight system capable of monitoring mission-critical risk."
        )

    quotes = []
    for role in ["foundation", "supreme_refinement", "refinement", "modern_application"]:
        item = (role_quote_map or {}).get(role)
        if isinstance(item, dict) and item.get("quote"):
            quotes.append(item["quote"])

    joined = " ".join(quotes).lower()

    if "best value reasonably available" in joined or "change of control" in joined:
        return (
            "Sale of Control doctrine governs change-of-control transactions, "
            "where once the corporation is for sale, directors must seek the best value "
            "reasonably available to stockholders."
        )

    if "enhanced scrutiny" in joined or "coercive" in joined or "preclusive" in joined:
        return (
            "Takeover Defense doctrine subjects defensive measures to enhanced scrutiny, "
            "requiring directors to identify a legitimate threat and adopt a response "
            "that is neither coercive nor preclusive and falls within a range of reasonableness."
        )

    if "entire fairness" in joined or "fair dealing" in joined or "fair price" in joined:
        return (
            "Entire Fairness requires fiduciaries to prove both fair dealing and fair price "
            "when they stand on both sides of a transaction or operate under a disabling conflict."
        )

    if any(
    phrase in joined
    for phrase in [
        "good faith effort",
        "utter failure",
        "bad faith",
        "failure to act in good faith",
        "duty of loyalty",
        "mission critical",
    ]
):
       return (
    "Oversight liability arises where directors utterly fail to implement "
    "a reasonable reporting or information system or consciously fail to monitor "
    "mission-critical red flags, constituting bad faith under the duty of loyalty."
)
    return ""

def synthesize_multi_doctrine_rule_comparison(target_lines: List[str]) -> str:
    real_lines = [x for x in target_lines if x != "unknown"]
    target_set = set(real_lines)

    def label(line: str) -> str:
        return DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()

    def triplet(line: str) -> Dict[str, str]:
        return get_rule_triplet(line)

    if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
        ct = triplet("controller_transactions")
        svc = triplet("stockholder_vote_cleansing")
        return (
            f"{label('controller_transactions')} doctrine governs conflicted controller transactions, where {ct['foundation']}, "
            f"but business judgment review may apply only where the transaction is {ct['supreme_refinement']}. "
            f"{label('stockholder_vote_cleansing')} doctrine governs the effect of stockholder approval, where {svc['foundation']}, "
            f"provided that {svc['supreme_refinement']} and {svc['modern_application']}. "
            "Taken together, controller-transactions doctrine addresses controller conflict through dual procedural protections, whereas stockholder-vote cleansing addresses the legal effect of a fully informed and uncoerced stockholder vote."
        )

    if {"oversight", "sale_of_control"} <= target_set:
        return (
            "Oversight doctrine governs board-level monitoring obligations, where Caremark, Stone, and Marchand require directors to act in good faith by implementing and monitoring reporting systems for mission-critical risk. "
            "Sale-of-control doctrine governs transactional conduct once the company enters sale mode or undergoes a change of control, where Revlon and QVC require directors to seek the best value reasonably available to stockholders. "
            "Taken together, oversight doctrine addresses the board's internal monitoring failure, whereas sale-of-control doctrine addresses value maximization in the transaction."
        )

    if {"controller_transactions", "sale_of_control"} <= target_set:
        ct = triplet("controller_transactions")
        soc = triplet("sale_of_control")
        return (
            f"{label('controller_transactions')} doctrine governs conflicted controller transactions, where {ct['foundation']}, "
            f"but business judgment review may apply only where the transaction is {ct['supreme_refinement']}; otherwise, {ct['modern_application']}. "
            f"{label('sale_of_control')} doctrine governs change-of-control transactions, where {soc['foundation']}, "
            f"and where {soc['supreme_refinement']}; accordingly, {soc['modern_application']}. "
            "Taken together, controller-transactions doctrine addresses controller conflict, whereas sale-of-control doctrine addresses value maximization in a change-of-control transaction."
        )

    if {"oversight", "takeover_defense"} <= target_set:
        ov = triplet("oversight")
        td = triplet("takeover_defense")
        return (
            f"{label('oversight')} doctrine governs board-level monitoring obligations, where directors breach the duty of loyalty through {ov['foundation']}, "
            f"and where {ov['supreme_refinement']} includes the obligation to make a {ov['modern_application']}. "
            f"{label('takeover_defense')} doctrine governs defensive action in response to a threat, where directors must show {td['foundation']}, "
            f"and that their response was {td['supreme_refinement']} and {td['modern_application']}. "
            "Taken together, oversight doctrine addresses internal monitoring obligations, whereas takeover-defense doctrine addresses external defensive measures."
        )

    if {"demand_futility", "oversight"} <= target_set:
        df = triplet("demand_futility")
        ov = triplet("oversight")
        return (
            f"{label('demand_futility')} doctrine governs whether stockholders may proceed without making a litigation demand, where {df['foundation']}. "
            f"Rales refines that inquiry by providing that {df['supreme_refinement']}, and Zuckerberg modernizes it by asking whether {df['modern_application']}. "
            f"Taken together, demand-futility doctrine addresses board capacity to consider demand, whereas oversight doctrine addresses whether directors breached fiduciary duties through {ov['foundation']}, {ov['supreme_refinement']}, and the obligation to make a {ov['modern_application']}."
        )

    if len(real_lines) >= 2 and has_rule_units(real_lines[0]) and has_rule_units(real_lines[1]):
        line_a, line_b = real_lines[0], real_lines[1]
        a = triplet(line_a)
        b = triplet(line_b)
        return (
            f"{label(line_a)} doctrine governs one fiduciary setting, where {a['foundation']}. "
            f"{label(line_b)} doctrine governs a distinct fiduciary setting, where {b['foundation']}. "
            f"Taken together, {label(line_a)} addresses one form of board conduct, whereas {label(line_b)} addresses another."
        )

    labels = [label(line) for line in real_lines]
    if len(labels) >= 2:
        return (
            f"{labels[0]} governs one fiduciary setting under its own doctrinal standard. "
            f"{labels[1]} governs a distinct fiduciary setting under a different doctrinal standard. "
            f"Taken together, {labels[0]} addresses one form of board conduct, whereas {labels[1]} addresses another."
        )

    return (
        "Delaware law applies doctrine-specific fiduciary standards to different board settings. "
        "Each doctrine governs its own category of conduct under its own standard of review or obligation. "
        "Taken together, the governing rule depends on the doctrinal framework implicated by the question."
    )
def synthesize_multi_doctrine_analysis(target_lines: List[str]) -> str:
    target_set = set(x for x in target_lines if x != "unknown")

    if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
        ct_foundation = get_rule_text("controller_transactions", "foundation")
        ct_refinement = get_rule_text("controller_transactions", "supreme_refinement")
        svc_foundation = get_rule_text("stockholder_vote_cleansing", "foundation")

        return (
            "This matters because controller-transactions doctrine addresses transactions involving controller conflict, where "
            f"{ct_foundation} and business judgment review is restored only if the transaction is {ct_refinement}. "
            "The significance is that stockholder-vote cleansing doctrine instead asks whether "
            f"{svc_foundation}. "
            "As a result, controller-transactions doctrine governs conflict cleansing in controller deals, whereas stockholder-vote cleansing governs the legal effect of stockholder approval."
        )

    if {"oversight", "sale_of_control"} <= target_set:
        return (
            "This matters because repeated food-safety red flags principally implicate oversight doctrine, where Caremark, Stone, and Marchand ask whether the board acted in bad faith by failing to implement or monitor a reporting system for mission-critical risk. "
            "The significance is that the simultaneous sale process separately may implicate sale-of-control doctrine, where Revlon and QVC require directors to seek the best value reasonably available once the company enters sale mode or undergoes a change of control. "
            "As a result, the same facts can implicate both doctrines, but oversight doctrine addresses the internal monitoring failure while sale-of-control doctrine addresses value maximization in the transaction."
        )

    if {"oversight", "takeover_defense"} <= target_set:
        ov_foundation = get_rule_text("oversight", "foundation")
        ov_refinement = get_rule_text("oversight", "supreme_refinement")
        ov_modern = get_rule_text("oversight", "modern_application")

        td_foundation = get_rule_text("takeover_defense", "foundation")
        td_refinement = get_rule_text("takeover_defense", "supreme_refinement")
        td_modern = get_rule_text("takeover_defense", "modern_application")

        return (
            "This matters because oversight doctrine addresses internal board monitoring, where directors breach the duty of loyalty through "
            f"{ov_foundation}, and where {ov_refinement} includes the obligation to make a {ov_modern}. "
            "The significance is that takeover-defense doctrine instead addresses external defensive action, where directors must show "
            f"{td_foundation}, and that their response was {td_refinement} and {td_modern}. "
            "As a result, oversight doctrine governs internal monitoring obligations, whereas takeover-defense doctrine governs defensive responses to takeover threats."
        )

    if {"controller_transactions", "sale_of_control"} <= target_set:
        ct_foundation = get_rule_text("controller_transactions", "foundation")
        ct_refinement = get_rule_text("controller_transactions", "supreme_refinement")
        ct_modern = get_rule_text("controller_transactions", "modern_application")

        soc_foundation = get_rule_text("sale_of_control", "foundation")
        soc_refinement = get_rule_text("sale_of_control", "supreme_refinement")
        soc_modern = get_rule_text("sale_of_control", "modern_application")

        return (
            "This matters because controller-transactions doctrine addresses controller conflict, where "
            f"{ct_foundation}, but business judgment review may apply only where the transaction is {ct_refinement}; otherwise, {ct_modern}. "
            "The significance is that sale-of-control doctrine instead governs whether directors acted reasonably to maximize value, where "
            f"{soc_foundation}, and where {soc_refinement}; accordingly, {soc_modern}. "
            "As a result, controller-transactions doctrine governs conflict cleansing in controller deals, whereas sale-of-control doctrine governs value maximization in a change-of-control transaction."
        )

    if {"demand_futility", "oversight"} <= target_set:
        return (
            "This matters because demand-futility doctrine governs whether a majority of the board can impartially consider a litigation demand. "
            "The significance is that oversight doctrine instead governs whether directors failed in good faith to implement or monitor a reporting system. "
            "As a result, demand-futility doctrine addresses board capacity to consider demand, whereas oversight doctrine addresses the underlying fiduciary conduct alleged to be wrongful."
        )

    labels = [
        DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()
        for line in target_lines
        if line != "unknown"
    ]

    if len(labels) >= 2:
        return (
            f"This matters because {labels[0]} and {labels[1]} regulate different fiduciary settings. "
            "The significance is that each doctrine applies a different standard or cleansing mechanism to a different form of board conduct. "
            "As a result, identifying the correct doctrinal framework is necessary before the governing standard can be applied."
        )

    return (
        "This matters because Delaware fiduciary doctrine is context specific rather than unitary. "
        "The significance is that each doctrine governs a different board function and therefore imposes a different standard of review or obligation. "
        "As a result, identifying the correct doctrinal framework is necessary before the governing standard can be applied."
    )
def synthesize_structured_single_doctrine_analysis(target_lines: List[str]) -> str:
    real_lines = [x for x in target_lines if x != "unknown"]
    if not real_lines:
        return (
            "This matters because Delaware fiduciary doctrine is context specific rather than unitary. "
            "The significance is that each doctrine governs a different board function and therefore imposes a different standard of review or obligation. "
            "As a result, identifying the correct doctrinal framework is necessary before the governing standard can be applied."
        )

    line = real_lines[0]
    label = DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()

    if line == "takeover_defense":
        foundation = get_rule_text("takeover_defense", "foundation")
        refinement = get_rule_text("takeover_defense", "supreme_refinement")
        modern = get_rule_text("takeover_defense", "modern_application")
        return (
            f"This matters because {label} doctrine governs defensive responses to takeover threats, where directors must show {foundation}. "
            f"The significance is that the response must be {refinement} and {modern}. "
            "As a result, Delaware law subjects takeover defenses to enhanced scrutiny rather than ordinary business judgment review."
        )

    if line == "controller_transactions":
        foundation = get_rule_text("controller_transactions", "foundation")
        refinement = get_rule_text("controller_transactions", "supreme_refinement")
        modern = get_rule_text("controller_transactions", "modern_application")
        return (
            f"This matters because {label} doctrine governs conflicted controller transactions, where {foundation}. "
            f"The significance is that business judgment review is restored only where the transaction is {refinement}, and otherwise {modern}. "
            "As a result, Delaware law treats controller conflict as a distinct fiduciary problem requiring dual cleansing protections."
        )

    if line == "stockholder_vote_cleansing":
        foundation = get_rule_text("stockholder_vote_cleansing", "foundation")
        refinement = get_rule_text("stockholder_vote_cleansing", "supreme_refinement")
        modern = get_rule_text("stockholder_vote_cleansing", "modern_application")
        return (
            f"This matters because {label} doctrine governs the effect of stockholder approval, where {foundation}. "
            f"The significance is that the vote must satisfy both conditions that {refinement} and {modern}. "
            "As a result, a fully informed and uncoerced stockholder vote can restore business judgment review."
        )

    if line == "sale_of_control":
        foundation = get_rule_text("sale_of_control", "foundation")
        refinement = get_rule_text("sale_of_control", "supreme_refinement")
        modern = get_rule_text("sale_of_control", "modern_application")
        return (
            f"This matters because {label} doctrine governs transactions that place the company in sale mode, where {foundation}. "
            f"The significance is that the duty is triggered where {refinement}, and then {modern}. "
            "As a result, directors must focus on value maximization once a sale or change-of-control transaction is underway."
        )

    if line == "demand_futility":
        foundation = get_rule_text("demand_futility", "foundation")
        refinement = get_rule_text("demand_futility", "supreme_refinement")
        modern = get_rule_text("demand_futility", "modern_application")
        return (
            f"This matters because {label} doctrine governs whether stockholders may proceed without making a litigation demand, where {foundation}. "
            f"The significance is that the inquiry was refined by {refinement} and modernized by {modern}. "
            "As a result, Delaware law focuses on whether the board could exercise independent and disinterested judgment in responding to a demand."
        )

    if line == "disclosure_loyalty":
        foundation = get_rule_text("disclosure_loyalty", "foundation")
        refinement = get_rule_text("disclosure_loyalty", "supreme_refinement")
        modern = get_rule_text("disclosure_loyalty", "modern_application")
        return (
            f"This matters because {label} doctrine governs what directors owe when communicating with stockholders, where {foundation}. "
            f"The significance is that {refinement}. "
            f"As a result, {modern}."
        )

    return (
        f"This matters because {label} doctrine supplies the governing fiduciary framework for this category of conduct. "
        f"The significance is that {label} applies a doctrine-specific standard rather than a generalized fiduciary rule. "
        "As a result, the analysis turns on the elements of that doctrinal framework."
    )


def synthesize_analysis_from_quotes(
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: List[str],
) -> str:
    if "oversight" in target_lines:
        return (
            "This matters because utter failure to attempt to assure a reasonable reporting or information system states the baseline implementation failure, whereas the later cases clarify the distinct monitoring branch. "
            "The significance is that directors act inconsistently with the duty of loyalty where good faith effort to implement an oversight system is absent or their conduct constitutes a failure to act in good faith. "
            "As a result, oversight liability may arise both from the absence of a reporting system and from a failure to monitor or respond in good faith once such a system exists."
        )

    return synthesize_structured_single_doctrine_analysis(target_lines)


def synthesize_analysis_from_tree_and_quotes(
    tree_result: Dict[str, Any],
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: List[str],
) -> str:
    if "oversight" in target_lines:
        primary_failure = (tree_result or {}).get("primary_failure", "")
        path = set((tree_result or {}).get("path", []))
        outcome = (tree_result or {}).get("outcome", "")

        if primary_failure == "red_flags" or "mission_critical_red_flags" in path:
            return (
                "This matters because oversight liability may arise where directors ignore red flags in a mission-critical area. "
                "The significance is that a board's failure to respond to red flags affecting the company's mission supports an inference of bad faith. "
                "As a result, ignoring red flags tied to a mission critical risk may give rise to Caremark liability."
            )

        if primary_failure == "failure_to_monitor":
            return (
                "This matters because oversight liability may arise where directors fail to monitor an existing reporting system and ignore red flags in a mission-critical area. "
                "The significance is that a board's failure to respond to red flags affecting the company's mission supports an inference of bad faith. "
                "As a result, ignoring red flags tied to a mission critical risk may give rise to Caremark liability."
            )

        if primary_failure == "utter_failure":
            return (
                "This matters because Caremark liability begins where directors make an utter failure to attempt to assure that a reasonable reporting or information system exists. "
                "The significance is that such a failure to act in good faith implicates the duty of loyalty at the implementation stage before later monitoring failures are even reached. "
                "As a result, the theory sounds in implementation failure rather than a later failure to monitor an existing system."
            )

        if outcome == "lower_oversight_risk":
            return (
                "This matters because Caremark liability begins with an utter failure to attempt to assure a reasonable reporting or information system exists or a later failure to monitor such a system in good faith. "
                "The significance is that where the board appears to have implemented and monitored an oversight system, the duty of loyalty theory is materially weaker. "
                "As a result, the alleged facts suggest lower oversight risk rather than a strong inference of disloyal oversight failure."
            )

    return synthesize_analysis_from_quotes(role_quote_map, target_lines)


def synthesize_structured_doctrine_section(doctrine_line: str) -> str:
    label = DOCTRINE_LABELS.get(doctrine_line) or doctrine_line.replace("_", " ").title()

    if doctrine_line == "oversight":
        return (
            "Oversight doctrine addresses board-level monitoring obligations, where liability begins "
            "with an utter failure to attempt to assure that a reasonable reporting or information system exists. "
            "Stone links that doctrine to the duty of loyalty through a failure to act in good faith. "
            "Marchand clarifies that directors must make a good faith effort to implement an oversight system."
        )

    if doctrine_line == "takeover_defense":
        foundation = get_rule_text("takeover_defense", "foundation")
        refinement = get_rule_text("takeover_defense", "supreme_refinement")
        modern = get_rule_text("takeover_defense", "modern_application")
        return (
            f"{label} doctrine governs defensive action in response to takeover threats, where directors must show {foundation}. "
            f"The defensive response must be {refinement}. "
            f"It also must fall {modern}."
        )

    if doctrine_line == "controller_transactions":
        foundation = get_rule_text("controller_transactions", "foundation")
        refinement = get_rule_text("controller_transactions", "supreme_refinement")
        modern = get_rule_text("controller_transactions", "modern_application")
        return (
            f"{label} doctrine governs conflicted controller transactions, where {foundation}. "
            f"Business judgment review may apply only where the transaction is {refinement}. "
            f"Otherwise, {modern}."
        )

    if doctrine_line == "stockholder_vote_cleansing":
        foundation = get_rule_text("stockholder_vote_cleansing", "foundation")
        refinement = get_rule_text("stockholder_vote_cleansing", "supreme_refinement")
        modern = get_rule_text("stockholder_vote_cleansing", "modern_application")
        return (
            f"{label} doctrine governs the effect of stockholder approval, where {foundation}. "
            f"The cleansing vote must satisfy the condition that {refinement}. "
            f"It also must satisfy the condition that {modern}."
        )

    if doctrine_line == "sale_of_control":
        foundation = get_rule_text("sale_of_control", "foundation")
        refinement = get_rule_text("sale_of_control", "supreme_refinement")
        modern = get_rule_text("sale_of_control", "modern_application")
        return (
            f"{label} doctrine governs change-of-control transactions, where {foundation}. "
            f"The doctrine is triggered where {refinement}. "
            f"Once triggered, {modern}."
        )

    if doctrine_line == "demand_futility":
        foundation = get_rule_text("demand_futility", "foundation")
        refinement = get_rule_text("demand_futility", "supreme_refinement")
        modern = get_rule_text("demand_futility", "modern_application")
        return (
            f"{label} doctrine governs whether stockholders may proceed without making a litigation demand, where {foundation}. "
            f"Rales refines the inquiry by providing that {refinement}. "
            f"Zuckerberg modernizes the framework by asking whether {modern}."
        )

    if doctrine_line == "disclosure_loyalty":
        foundation = get_rule_text("disclosure_loyalty", "foundation")
        refinement = get_rule_text("disclosure_loyalty", "supreme_refinement")
        modern = get_rule_text("disclosure_loyalty", "modern_application")
        return (
            f"{label} doctrine governs what directors owe when communicating with stockholders, where {foundation}. "
            f"It also recognizes that {refinement}. "
            f"Accordingly, {modern}."
        )

    if doctrine_line == "entire_fairness":
        return (
            "Entire fairness is Delaware's most exacting standard of review and requires fiduciaries "
            "to demonstrate both fair dealing and fair price when they stand on both sides of a transaction "
            "or otherwise operate under a disabling conflict."
        )

    return f"{label} doctrine supplies the governing doctrinal framework for this category of conduct."


def _clean_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())

    # remove analysis prefixes
    text = re.sub(
        r"^(This matters because|The significance is that|As a result,|As a result)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.rstrip(".")


def synthesize_memo_answer(
    sections: Dict[str, str],
    query_plan: Dict[str, Any],
) -> str:
    """
    Deterministic memo paragraph.

    Enforces:
    - no labels
    - no filler phrases
    - no repeated rule language
    - rule -> trigger -> consequence
    - max 3 sentences
    """

    target_lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
    target_set = set(target_lines)

    def clean(text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())

        text = re.sub(
            r"\b(Short Answer|Rule|Analysis|Key Distinction|Rule Comparison|Confidence)\s*:\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\b(This matters because|The significance is that|As a result,?|Accordingly,?)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r"\s+", " ", text).strip()
        return text.rstrip(".")

    def doctrine_label() -> str:
        if not target_lines:
            return "The doctrine"
        line = target_lines[0]
        return DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()

    def semantic_key(text: str) -> str:
        text = re.sub(r"[^a-z0-9\s]", "", text.lower())

        # collapse common doctrinal equivalents
        replacements = {
            "governs transactions that place the company in sale mode": "sale of control",
            "governs changeofcontrol transactions": "sale of control",
            "change of control": "change control",
            "will result in": "results in",
            "must seek the best value reasonably available": "best value",
            "secure the best value reasonably available": "best value",
            "focus on securing the best value reasonably available": "best value",
            "fiduciary framework": "framework",
            "doctrinal framework": "framework",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        stop = {
            "the", "and", "that", "this", "where", "when", "with",
            "under", "doctrine", "directors", "board", "corporation",
            "transaction", "transactions", "stockholders", "available",
            "reasonably", "supplies", "governs",
        }

        words = [w for w in text.split() if len(w) > 3 and w not in stop]
        return " ".join(words[:10])

    def dedupe(sentences: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()

        for s in sentences:
            s = clean(s)
            if not s:
                continue

            key = semantic_key(s)
            if key in seen:
                continue

            # extra overlap check
            s_words = set(key.split())
            duplicate = False
            for existing in out:
                e_words = set(semantic_key(existing).split())
                if s_words and e_words:
                    overlap = len(s_words & e_words) / max(1, min(len(s_words), len(e_words)))
                    if overlap >= 0.65:
                        duplicate = True
                        break

            if duplicate:
                continue

            seen.add(key)
            out.append(s)

        return out

    def trigger_sentence() -> str:
        if "sale_of_control" in target_set:
            return (
                "Because the transaction results in a change of control, "
                "the board’s duty is to secure the best value reasonably available."
            )

        if "entire_fairness" in target_set:
            return (
                "Because the fiduciary stands on both sides of the transaction, "
                "the analysis turns on whether the process and price were entirely fair."
            )

        if "controller_transactions" in target_set:
            return (
                "Because the transaction involves a controlling stockholder, "
                "the standard of review depends on whether procedural protections restore business judgment review."
            )

        if "stockholder_vote_cleansing" in target_set:
            return (
                "Because the transaction was approved by stockholders, "
                "the analysis turns on whether the vote was fully informed and uncoerced."
            )

        if "oversight" in target_set:
            return (
                "Because the claim sounds in oversight, liability turns on whether the board failed "
                "to implement or consciously disregarded a reporting system."
            )

        if "takeover_defense" in target_set:
            return (
                "Because the board adopted defensive measures, the response must fall within "
                "a range of reasonableness relative to the threat."
            )

        if "demand_futility" in target_set:
            return (
                "Because the claim is derivative, the analysis turns on whether the board "
                "could have impartially considered demand."
            )

        return ""

    def conclusion_sentence() -> str:
        if "sale_of_control" in target_set:
            return "Accordingly, once Revlon duties are triggered, directors must focus on securing that value."

        if "entire_fairness" in target_set:
            return "Accordingly, fiduciaries must prove that both the process and price were entirely fair."

        if "controller_transactions" in target_set:
            return "Accordingly, the standard of review turns on whether the transaction was properly cleansed."

        if "stockholder_vote_cleansing" in target_set:
            return "Accordingly, business judgment review depends on a fully informed and uncoerced vote."

        if "oversight" in target_set:
            return "Accordingly, liability depends on a failure to implement or monitor oversight systems."

        if "takeover_defense" in target_set:
            return "Accordingly, the board’s actions must be proportionate to the threat."

        if "demand_futility" in target_set:
            return "Accordingly, demand is excused only if the board cannot act impartially."

        return ""

    short_answer = clean(sections.get("short_answer", ""))
    rule = clean(sections.get("rule", ""))

    parts: List[str] = []

    parts.append(short_answer or f"{doctrine_label()} supplies the governing doctrinal framework.")

    # Only use the rule if it adds something new.
    if rule:
        parts.append(rule)

    trigger = trigger_sentence()
    if trigger:
        parts.append(trigger)

    conclusion = conclusion_sentence()
    if conclusion:
        parts.append(conclusion)

    parts = dedupe(parts)

    # Hard cap memo mode to 3 sentences.
    parts = parts[:3]

    paragraph = " ".join(p.rstrip(".") + "." for p in parts)

    paragraph = re.sub(r"\s+", " ", paragraph).strip()
    paragraph = re.sub(r"\.\.+", ".", paragraph)
    paragraph = re.sub(r"\s+\.", ".", paragraph)

    return paragraph

PINPOINT_CITES = {
    "Revlon": "Revlon, 506 A.2d 173",
    "QVC": "QVC, 637 A.2d 34",
    "Unocal": "Unocal, 493 A.2d 946",
    "Unitrin": "Unitrin, 651 A.2d 1361",
    "Weinberger": "Weinberger, 457 A.2d 701",
    "MFW": "MFW, 88 A.3d 635",
    "Corwin": "Corwin, 125 A.3d 304",
    "Caremark": "Caremark, 698 A.2d 959",
    "Stone": "Stone, 911 A.2d 362",
    "Marchand": "Marchand, 212 A.3d 805",
    "Aronson": "Aronson, 473 A.2d 805",
    "Rales": "Rales, 634 A.2d 927",
    "Zuckerberg": "Zuckerberg, 262 A.3d 1034",
}

def synthesize_opinion_answer(
    sections: Dict[str, str],
    query_plan: Dict[str, Any],
    role_quote_map: Dict[str, Dict[str, str]] | None = None,
) -> str:
    role_quote_map = role_quote_map or {}
    target_lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
    target_set = set(target_lines)

    def clean(text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())
        text = re.sub(
            r"\b(Short Answer|Rule|Analysis|Confidence|Rule Comparison|Key Distinction)\s*:\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(This matters because|The significance is that|The significance is|As a result,?|Accordingly,?)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\b(Recent decisions, including|Cases like|Courts have also held|This means that|In simple terms)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s+", " ", text).strip()
        return text.rstrip(".")

    def cite(cases: List[str]) -> str:
        cases = [c.strip() for c in cases if c and c.strip()]
        cases = list(dict.fromkeys(cases))

        if not cases:
            return "."

        formatted = [PINPOINT_CITES.get(c, c) for c in cases[:3]]
        return f" ({'; '.join(formatted)})."

    def with_cite(sentence: str, cases: List[str]) -> str:
        sentence = clean(sentence)
        if not sentence:
            return ""

        if re.search(r"\([A-Za-z0-9;,\.\s]+\)$", sentence):
            return sentence + "."

        return sentence.rstrip(".") + cite(cases)

    def cases_for_citation() -> List[str]:
        cases: List[str] = []

        if "oversight" in target_set:
            cases.extend(["Caremark", "Stone", "Marchand"])

        if "sale_of_control" in target_set:
            cases.extend(["Revlon", "QVC"])

        if "takeover_defense" in target_set:
            cases.extend(["Unocal", "Unitrin"])

        if "controller_transactions" in target_set:
            cases.append("MFW")

        if "stockholder_vote_cleansing" in target_set:
            cases.append("Corwin")

        if "entire_fairness" in target_set:
            cases.append("Weinberger")

        if "demand_futility" in target_set:
            cases.extend(["Aronson", "Rales", "Zuckerberg"])

        if not cases:
            for role in ["foundation", "supreme_refinement", "refinement", "modern_application"]:
                item = role_quote_map.get(role) or {}
                case = clean(item.get("case", ""))
                if case:
                    cases.append(case)

        return list(dict.fromkeys(cases))

    def sentence_key(text: str) -> str:
        text = clean(text).lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)

        replacements = {
            "best value reasonably available to stockholders": "best value",
            "best value reasonably available": "best value",
            "highest value reasonably attainable": "best value",
            "change of control": "change control",
            "business judgment review": "business judgment",
            "business judgment deference": "business judgment",
            "fully informed and uncoerced": "informed uncoerced",
            "majority of the minority": "minority vote",
            "entire fairness remains the governing standard": "entire fairness",
            "range of reasonableness": "reasonableness",
            "mission critical": "mission critical",
            "red flags": "red flags",
            "bad faith oversight": "bad faith",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        stop = {
            "the", "and", "that", "this", "where", "when", "with", "under",
            "doctrine", "directors", "director", "board", "corporation",
            "transaction", "transactions", "stockholders", "stockholder",
            "available", "reasonably", "establish", "establishes",
            "because", "thus", "claim", "claims",
        }

        words = [w for w in text.split() if len(w) > 3 and w not in stop]
        return " ".join(words[:12])

    def dedupe(sentences: List[str]) -> List[str]:
        out: List[str] = []

        for sentence in sentences:
            s = clean(sentence)
            if not s:
                continue

            key = sentence_key(s)
            s_words = set(key.split())
            duplicate = False

            for existing in out:
                e_words = set(sentence_key(existing).split())
                if s_words and e_words:
                    overlap = len(s_words & e_words) / max(1, min(len(s_words), len(e_words)))
                    if overlap >= 0.72:
                        duplicate = True
                        break

            if not duplicate:
                out.append(s)

        return out

    def final_cleanup(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\.\.+", ".", text)
        text = re.sub(r"\s+\.", ".", text)
        text = re.sub(r"\.\s+\(", " (", text)

        text = re.sub(
            r"\b[A-Z][A-Za-z ]+ supplies the governing doctrinal framework\.\s*",
            "",
            text,
        )
        text = re.sub(
            r"\b[A-Z][A-Za-z ]+ doctrine governs[^.]*\.\s*",
            "",
            text,
        )
        text = re.sub(
            r"\b(This matters because|The significance is that|The significance is|As a result,?)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def assemble(parts: List[str], max_sentences: int = 4) -> str:
        parts = dedupe(parts)[:max_sentences]
        paragraph = " ".join(part.rstrip(".") + "." for part in parts if part)
        return final_cleanup(paragraph)

    # =========================================================
    # UPGRADE 3: MULTI-DOCTRINE OPINION SYNTHESIS
    # =========================================================

    if {"oversight", "sale_of_control"} <= target_set:
        parts = [
            with_cite(
                (
                    "Under Caremark, Stone, and Marchand, a board that ignores repeated red flags "
                    "in a mission-critical area may face oversight liability because the claim sounds "
                    "in bad faith monitoring failure rather than ordinary negligence"
                ),
                ["Caremark", "Stone", "Marchand"],
            ),
            with_cite(
                (
                    "At the same time, where the board is negotiating a sale or change-of-control "
                    "transaction, Revlon and QVC require the directors to focus on securing the best "
                    "value reasonably available to stockholders"
                ),
                ["Revlon", "QVC"],
            ),
            (
                "Those doctrines address distinct fiduciary problems: oversight doctrine concerns "
                "the board's failure to monitor mission-critical risk, while sale-of-control doctrine "
                "concerns the board's conduct in pursuing a value-maximizing transaction"
            ),
            (
                "Thus, the food-safety red flags principally implicate Caremark oversight duties, "
                "but the simultaneous sale process may also require Revlon scrutiny if the transaction "
                "places the company in sale mode or results in a change of control"
            ),
        ]

        return assemble(parts, max_sentences=4)

    if {"oversight", "takeover_defense"} <= target_set:
        parts = [
            with_cite(
                (
                    "Under Caremark, Stone, and Marchand, oversight liability turns on whether "
                    "directors acted in bad faith by utterly failing to implement reporting systems "
                    "or consciously disregarding red flags"
                ),
                ["Caremark", "Stone", "Marchand"],
            ),
            with_cite(
                (
                    "By contrast, under Unocal and Unitrin, defensive measures are subject to enhanced "
                    "scrutiny and must be neither coercive nor preclusive and must fall within a range "
                    "of reasonableness"
                ),
                ["Unocal", "Unitrin"],
            ),
            (
                "The two doctrines therefore regulate different conduct: oversight doctrine addresses "
                "internal monitoring failures, while takeover-defense doctrine addresses defensive "
                "responses to an external threat"
            ),
            (
                "Thus, the board's exposure depends on whether the challenged conduct is a failure "
                "to monitor risk, a defensive response to a threat, or both"
            ),
        ]

        return assemble(parts, max_sentences=4)

    if {"controller_transactions", "sale_of_control"} <= target_set:
        parts = [
            with_cite(
                (
                    "Under MFW, controller-transaction doctrine addresses conflicted controller deals "
                    "and permits business judgment review only when dual procedural protections are "
                    "in place from the outset"
                ),
                ["MFW"],
            ),
            with_cite(
                (
                    "Under Revlon and QVC, sale-of-control doctrine addresses whether directors must "
                    "seek the best value reasonably available once the company enters sale mode or "
                    "undergoes a change of control"
                ),
                ["Revlon", "QVC"],
            ),
            (
                "Those doctrines may overlap in a sale process, but they answer different questions: "
                "MFW addresses controller conflict and cleansing, while Revlon addresses value "
                "maximization in the transaction"
            ),
            (
                "Thus, a controller sale may require both conflict-cleansing analysis and sale-process "
                "scrutiny unless the governing standard is altered by effective procedural protections"
            ),
        ]

        return assemble(parts, max_sentences=4)

    if {"demand_futility", "oversight"} <= target_set:
        parts = [
            with_cite(
                (
                    "Under Aronson, Rales, and Zuckerberg, demand futility asks whether the board "
                    "can exercise independent and disinterested judgment in deciding whether to "
                    "pursue the claim"
                ),
                ["Aronson", "Rales", "Zuckerberg"],
            ),
            with_cite(
                (
                    "Under Caremark, Stone, and Marchand, the underlying oversight claim turns on "
                    "whether directors acted in bad faith by failing to implement or monitor a "
                    "reporting system"
                ),
                ["Caremark", "Stone", "Marchand"],
            ),
            (
                "The doctrines are related but distinct: demand futility concerns whether stockholders "
                "may sue derivatively without making demand, while oversight doctrine concerns the "
                "fiduciary breach alleged"
            ),
            (
                "Thus, a plaintiff must plead both demand futility and a viable bad-faith oversight "
                "theory when asserting derivative Caremark claims"
            ),
        ]

        return assemble(parts, max_sentences=4)

    # =========================================================
    # SINGLE-DOCTRINE OPINION SYNTHESIS
    # =========================================================

    def doctrine_voice_block() -> Dict[str, str]:
        if "sale_of_control" in target_set:
            return {
                "authority": "Under Revlon and its progeny,",
                "rule": (
                    "once the corporation is for sale, the directors must seek the best value "
                    "reasonably available to stockholders"
                ),
                "trigger": "That obligation is triggered when the transaction results in a change of control",
                "consequence": (
                    "Where the transaction constitutes such a change, the board must focus on value "
                    "maximization rather than ordinary business strategy"
                ),
                "disposition": (
                    "Thus, once Revlon duties attach, the directors must pursue the transaction reasonably "
                    "designed to produce the highest value reasonably attainable"
                ),
            }

        if "takeover_defense" in target_set:
            return {
                "authority": "Under Unocal and Unitrin,",
                "rule": (
                    "defensive measures are subject to enhanced scrutiny because directors resisting "
                    "a threat may also be acting to entrench themselves"
                ),
                "trigger": (
                    "That standard requires the board to identify a legitimate threat to corporate "
                    "policy and effectiveness"
                ),
                "consequence": (
                    "In that posture, the response must be neither coercive nor preclusive and must "
                    "fall within a range of reasonableness"
                ),
                "disposition": (
                    "Thus, the measure is valid only if the threat is real and the response is proportionate"
                ),
            }

        if "controller_transactions" in target_set:
            return {
                "authority": "Under MFW,",
                "rule": (
                    "business judgment review applies only where dual procedural protections replicate "
                    "arm's-length bargaining from the outset"
                ),
                "trigger": (
                    "Those protections require an empowered independent committee and an informed, "
                    "uncoerced majority-of-the-minority vote"
                ),
                "consequence": (
                    "Because controller influence otherwise disables ordinary deference, strict compliance "
                    "is necessary to change the standard of review"
                ),
                "disposition": (
                    "Thus, absent effective MFW cleansing, entire fairness remains the governing standard"
                ),
            }

        if "entire_fairness" in target_set:
            return {
                "authority": "Under Weinberger,",
                "rule": (
                    "entire fairness is Delaware's most exacting standard, requiring fiduciaries to prove "
                    "both fair dealing and fair price"
                ),
                "trigger": (
                    "That standard applies when fiduciary conflict disables the ordinary presumption "
                    "of business judgment"
                ),
                "consequence": (
                    "Because the burden rests on the fiduciaries, the court examines process and price "
                    "as a unitary fairness inquiry"
                ),
                "disposition": (
                    "Thus, conflicted fiduciaries must prove that the transaction was entirely fair"
                ),
            }

        if "oversight" in target_set:
            return {
                "authority": "Under Caremark, Stone, and Marchand,",
                "rule": (
                    "oversight liability is not ordinary negligence, but a narrow bad-faith theory "
                    "requiring an utter failure to implement reporting systems or a conscious failure "
                    "to monitor them"
                ),
                "trigger": (
                    "That inquiry is most serious where mission-critical risk or red flags make "
                    "board-level attention necessary"
                ),
                "consequence": (
                    "Because the claim sounds in loyalty, liability turns on scienter, not on whether "
                    "directors made a poor business judgment"
                ),
                "disposition": (
                    "Thus, a Caremark claim survives only where the pleaded facts support a reasonable "
                    "inference of bad-faith oversight failure"
                ),
            }

        if "stockholder_vote_cleansing" in target_set:
            return {
                "authority": "Under Corwin,",
                "rule": (
                    "a fully informed and uncoerced vote of disinterested stockholders restores "
                    "business judgment deference"
                ),
                "trigger": (
                    "That cleansing effect depends on disclosure sufficient to permit stockholders "
                    "to make an informed choice"
                ),
                "consequence": (
                    "Because the stockholders have approved the transaction, judicial review becomes "
                    "deferential unless waste is pleaded"
                ),
                "disposition": (
                    "Thus, Corwin cleansing ordinarily forecloses post-closing damages claims"
                ),
            }

        if "demand_futility" in target_set:
            return {
                "authority": "Under Aronson, Rales, and Zuckerberg,",
                "rule": (
                    "demand futility asks whether the board can exercise independent and disinterested "
                    "judgment in deciding whether to pursue the claim"
                ),
                "trigger": "That inquiry is conducted director by director",
                "consequence": (
                    "Because derivative litigation belongs to the corporation, demand is excused only "
                    "when board impartiality is disabled"
                ),
                "disposition": (
                    "Thus, the complaint must plead particularized facts showing that demand would "
                    "have been futile"
                ),
            }

        fallback_rule = clean(sections.get("rule", ""))
        return {
            "authority": "Under Delaware fiduciary law,",
            "rule": fallback_rule[0].lower() + fallback_rule[1:] if fallback_rule else "the governing standard follows from the fiduciary setting",
            "trigger": "",
            "consequence": "",
            "disposition": "Thus, the doctrine determines the applicable standard of review and fiduciary burden",
        }

    voice = doctrine_voice_block()
    citation_cases = cases_for_citation()

    parts = [
        with_cite(f"{voice['authority']} {voice['rule']}", citation_cases[:3]),
        with_cite(voice.get("trigger", ""), citation_cases[1:3] or citation_cases[:1]),
        voice.get("consequence", ""),
        voice.get("disposition", ""),
    ]

    return assemble(parts, max_sentences=4)