from __future__ import annotations

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


def synthesize_rule_from_quotes(
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: List[str],
) -> str:
    target_set = set(x for x in target_lines if x != "unknown")

    if "oversight" in target_set:
        foundation_frag = get_rule_text("oversight", "foundation")
        refinement_frag = get_rule_text("oversight", "supreme_refinement")
        modern_frag = get_rule_text("oversight", "modern_application")

        return (
            "A board breaches the duty of loyalty where there is an "
            f"{foundation_frag}, or where a {refinement_frag} includes the conscious failure to monitor such a system once implemented, "
            f"because directors must make a {modern_frag}."
        )

    if "takeover_defense" in target_set:
        foundation_frag = get_rule_text("takeover_defense", "foundation")
        refinement_frag = get_rule_text("takeover_defense", "supreme_refinement")
        modern_frag = get_rule_text("takeover_defense", "modern_application")

        return (
            "Under Unocal, directors must show that they had "
            f"{foundation_frag}, and that their defensive response was {refinement_frag} "
            f"and {modern_frag}."
        )

    if "controller_transactions" in target_set:
        foundation_frag = get_rule_text("controller_transactions", "foundation")
        refinement_frag = get_rule_text("controller_transactions", "supreme_refinement")
        modern_frag = get_rule_text("controller_transactions", "modern_application")

        return (
            "In a controller transaction, "
            f"{foundation_frag}, but business judgment review may apply only where the transaction is {refinement_frag}; "
            f"otherwise, {modern_frag}."
        )

    if "stockholder_vote_cleansing" in target_set:
        foundation_frag = get_rule_text("stockholder_vote_cleansing", "foundation")
        refinement_frag = get_rule_text("stockholder_vote_cleansing", "supreme_refinement")
        modern_frag = get_rule_text("stockholder_vote_cleansing", "modern_application")

        return (
            "Under Corwin, "
            f"{foundation_frag}, provided that {refinement_frag} and {modern_frag}."
        )

    if "sale_of_control" in target_set:
        foundation_frag = get_rule_text("sale_of_control", "foundation")
        refinement_frag = get_rule_text("sale_of_control", "supreme_refinement")
        modern_frag = get_rule_text("sale_of_control", "modern_application")

        return (
            "Under Revlon and QVC, "
            f"{foundation_frag}, and {refinement_frag}; "
            f"accordingly, {modern_frag}."
        )

    if "demand_futility" in target_set:
        foundation_frag = get_rule_text("demand_futility", "foundation")
        refinement_frag = get_rule_text("demand_futility", "supreme_refinement")
        modern_frag = get_rule_text("demand_futility", "modern_application")

        return (
            "Under Aronson, Rales, and Zuckerberg, "
            f"{foundation_frag}; {refinement_frag}; and {modern_frag}."
        )

    if "disclosure_loyalty" in target_set:
        foundation_frag = get_rule_text("disclosure_loyalty", "foundation")
        refinement_frag = get_rule_text("disclosure_loyalty", "supreme_refinement")
        modern_frag = get_rule_text("disclosure_loyalty", "modern_application")

        return (
            "Under Malone, "
            f"{foundation_frag}, and {refinement_frag}; accordingly, {modern_frag}."
        )
    
    if "entire_fairness" in target_set:
        return (
            "Entire fairness is Delaware’s most rigorous standard of review and requires fiduciaries to demonstrate "
            "both fair dealing and fair price where they stand on both sides of a transaction or otherwise face disabling conflicts."
        )
    if "disclosure" in target_set or "disclosure_loyalty" in target_set:
        return (
            "Under Delaware law, directors have a duty to communicate truthfully with stockholders, and materially "
            "misleading statements or omissions may constitute a breach of fiduciary duty, particularly where "
            "stockholder action depends on a fully informed vote."
        )
    if "shareholder_franchise" in target_set:
        return (
            "Under Blasius, board action taken for the primary purpose of interfering with the stockholder franchise "
            "requires a compelling justification."
        )
    if "equitable_intervention" in target_set:
        return (
            "Under Schnell, inequitable conduct does not become permissible simply because it is legally authorized, "
            "and Delaware courts may restrain corporate action taken for an improper purpose."
        )
    if "books_and_records" in target_set:
        return (
            "Under DGCL Section 220, a stockholder may inspect books and records upon demonstrating a proper purpose "
            "reasonably related to stockholder status, supported by a credible basis where wrongdoing is alleged."
        )
    
    return "The governing rule depends on the doctrinal framework identified by the question."


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

    if {"oversight", "sale_of_control"} <= target_set:
        ov = triplet("oversight")
        soc = triplet("sale_of_control")
        return (
            f"{label('oversight')} doctrine governs board-level monitoring obligations, where directors breach the duty of loyalty through {ov['foundation']}, "
            f"and where {ov['supreme_refinement']} includes the obligation to make a {ov['modern_application']}. "
            f"{label('sale_of_control')} doctrine governs change-of-control transactions, where {soc['foundation']}, "
            f"and where {soc['supreme_refinement']}; accordingly, {soc['modern_application']}. "
            "Taken together, oversight doctrine addresses internal monitoring failure, whereas sale-of-control doctrine addresses value maximization in a change-of-control setting."
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

    if {"oversight", "sale_of_control"} <= target_set:
        ov_foundation = get_rule_text("oversight", "foundation")
        ov_refinement = get_rule_text("oversight", "supreme_refinement")
        ov_modern = get_rule_text("oversight", "modern_application")

        soc_foundation = get_rule_text("sale_of_control", "foundation")
        soc_refinement = get_rule_text("sale_of_control", "supreme_refinement")
        soc_modern = get_rule_text("sale_of_control", "modern_application")

        return (
            "This matters because oversight doctrine governs whether directors made a good-faith effort to implement and monitor reporting systems, beginning with "
            f"{ov_foundation}, and refined through {ov_refinement} and {ov_modern}. "
            "The significance is that sale-of-control doctrine instead governs transactional conduct once the company is for sale, where "
            f"{soc_foundation}, and where {soc_refinement}; accordingly, {soc_modern}. "
            "As a result, oversight doctrine addresses internal monitoring failure, whereas sale-of-control doctrine addresses value maximization in a change-of-control setting."
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
            f"The significance is that each doctrine applies a different standard or cleansing mechanism to a different form of board conduct. "
            f"As a result, identifying the correct doctrinal framework is necessary before the governing standard can be applied."
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
        foundation = get_rule_text("oversight", "foundation")
        refinement = get_rule_text("oversight", "supreme_refinement")
        modern = get_rule_text("oversight", "modern_application")
        return (
            f"{label} doctrine addresses board-level monitoring obligations, where liability begins with an {foundation}. "
            f"Stone links that doctrine to the duty of loyalty through {refinement}. "
            f"Marchand clarifies that directors must make a {modern}."
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
        "Entire fairness is Delaware’s most exacting standard of review and requires fiduciaries "
        "to demonstrate both fair dealing and fair price when they stand on both sides of a transaction "
        "or otherwise operate under a disabling conflict."
    )

    return f"{label} doctrine supplies the governing doctrinal framework for this category of conduct."
import re
from typing import Dict, Any


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
    Deterministic memo-style paragraph.
    Built purely from validated sections.
    """

    query_type = query_plan.get("query_type", "")
    multi = query_plan.get("multi_doctrine", False)

    short_answer = _clean_sentence(sections.get("short_answer", ""))
    key_distinction = _clean_sentence(sections.get("key_distinction", ""))
    rule = _clean_sentence(sections.get("rule", ""))
    rule_comparison = _clean_sentence(sections.get("rule_comparison", ""))
    analysis = sections.get("analysis", "")

    analysis_sentences = [
        _clean_sentence(s)
        for s in re.split(r"(?<=[.!?])\s+", analysis)
        if s.strip()
    ]

    # ========================
    # STRUCTURE LOGIC
    # ========================

    if query_type == "comparison":
        lead = key_distinction or short_answer
        governing_rule = rule_comparison or rule
    else:
        lead = short_answer
        governing_rule = rule

    parts = []

    if lead:
        parts.append(lead)

    if governing_rule:
        parts.append(governing_rule)

    # add 3 analysis sentences
    for sentence in analysis_sentences[:3]:
        if sentence:
            parts.append(sentence)

    memo = " ".join(
        part.rstrip(".") + "." for part in parts if part.strip()
    )

    # final cleanup
    memo = re.sub(
        r"\b(Short Answer|Rule|Rule Comparison|Analysis|Confidence):",
        "",
        memo,
    )
    memo = re.sub(r"\s+", " ", memo).strip()

    return memo
def synthesize_opinion_answer(
    sections: Dict[str, str],
    query_plan: Dict[str, Any],
) -> str:
    """
    Deterministic opinion-style output.
    More formal than Memo Mode, but still built only from validated sections.
    """

    query_type = query_plan.get("query_type", "")

    short_answer = _clean_sentence(sections.get("short_answer", ""))
    key_distinction = _clean_sentence(sections.get("key_distinction", ""))
    rule = _clean_sentence(sections.get("rule", ""))
    rule_comparison = _clean_sentence(sections.get("rule_comparison", ""))
    analysis = sections.get("analysis", "")

    analysis_sentences = [
        _clean_sentence(s)
        for s in re.split(r"(?<=[.!?])\s+", analysis)
        if s.strip()
    ]

    if query_type == "comparison":
        opening = key_distinction or short_answer
        governing_rule = rule_comparison or rule
    else:
        opening = short_answer
        governing_rule = rule

    parts = []

    if opening:
        parts.append(f"The question is governed by a settled Delaware doctrinal distinction: {opening}")

    if governing_rule:
        parts.append(f"That distinction matters because {governing_rule}")

    if len(analysis_sentences) >= 1:
        parts.append(f"Applied here, {analysis_sentences[0]}")

    if len(analysis_sentences) >= 2:
        parts.append(f"The doctrinal significance is that {analysis_sentences[1]}")

    if len(analysis_sentences) >= 3:
        parts.append(f"Accordingly, {analysis_sentences[2]}")

    opinion = " ".join(
        part.rstrip(".") + "." for part in parts if part.strip()
    )

    opinion = re.sub(
        r"\b(Short Answer|Rule|Rule Comparison|Analysis|Confidence):",
        "",
        opinion,
    )
    opinion = re.sub(r"\s+", " ", opinion).strip()

    return opinion