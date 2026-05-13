from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from unittest import case


ASK_SCRIPT = Path("ask.py")
OUTPUT_DIR = Path("regression_outputs")


@dataclass
class RegressionCase:
    name: str
    prompt: str
    required_substrings: List[str]
    forbidden_substrings: List[str]
    min_score: int

OVERSIGHT_LEAKAGE_TERMS = [
    "utter failure to attempt to assure",
    "good faith effort to implement an oversight system",
    "failure to act in good faith",
    "Caremark",
    "Marchand",
    "Stone",
]

TEST_CASES: List[RegressionCase] = [
    RegressionCase(
        name="caremark_marchand_comparison",
        prompt="Compare Caremark and Marchand",
        required_substrings=[
            "QUERY TYPE: comparison",
            "TARGET LINES: ['oversight']",
            "MULTI-DOCTRINE: False",
            "Rule Comparison:",
            "Caremark",
            "Marchand",
            "Confidence:",
        ],
        forbidden_substrings=[],
        min_score=90,
    ),
    RegressionCase(
        name="mfw_corwin_comparison",
        prompt="Compare MFW and Corwin",
        required_substrings=[
            "QUERY TYPE: comparison",
            "TARGET LINES: ['controller_transactions', 'stockholder_vote_cleansing']",
            "MULTI-DOCTRINE: True",
            "Controller Transactions:",
            "Stockholder Vote Cleansing:",
            "Rule Comparison:",
            "Confidence:",
        ],
        forbidden_substrings=OVERSIGHT_LEAKAGE_TERMS,

        min_score=75,
    ),
    RegressionCase(
        name="caremark_unocal_comparison",
        prompt="Compare Caremark and Unocal",
        required_substrings=[
            "QUERY TYPE: comparison",
            "MULTI-DOCTRINE: True",
            "Oversight:",
            "Takeover Defense:",
            "Rule Comparison:",
        ],
        forbidden_substrings=[],
        min_score=70,
    ),
    RegressionCase(
        name="controller_vs_sale_of_control",
        prompt="Compare MFW and Revlon",
        required_substrings=[
            "QUERY TYPE: comparison",
            "MULTI-DOCTRINE: True",
            "Controller Transactions:",
            "Sale of Control:",
            "Rule Comparison:",
            "Confidence:",
    ],
    forbidden_substrings=[],
    min_score=75,
),
    RegressionCase(
        name="caremark_revlon_comparison",
        prompt="Compare Caremark and Revlon",
        required_substrings=[
            "QUERY TYPE: comparison",
            "MULTI-DOCTRINE: True",
            "Oversight:",
            "Sale of Control:",
            "Rule Comparison:",
        ],
        forbidden_substrings=[],
        min_score=70,
    ),
    RegressionCase(
        name="aronson_rales_comparison",
        prompt="Compare Aronson and Rales",
        required_substrings=[
            "QUERY TYPE: comparison",
            "demand_futility",
            "Rule Comparison:",
            "Confidence:",
        ],
        forbidden_substrings=[],
        min_score=70,
    ),
    RegressionCase(
        name="caremark_pleading_standard",
        prompt="What must a plaintiff plead to state a Caremark claim?",
        required_substrings=[
            "TARGET LINES: ['oversight']",
            "Short Answer:",
            "Rule:",
            "Analysis:",
            "Confidence:",
        ],
        forbidden_substrings=[],
        min_score=80,
    ),
    RegressionCase(
        name="caremark_evolution",
        prompt="How did Caremark evolve through Stone and Marchand?",
        required_substrings=[
            "TARGET LINES: ['oversight']",
            "Stone",
            "Marchand",
            "Analysis:",
            "Confidence:",
        ],
        forbidden_substrings=[],
        min_score=80,
    ),
    RegressionCase(
        name="red_flags_plus_defensive_measures",
        prompt="Compare oversight and takeover_defense where a board ignored red flags and adopted defensive measures.",
        required_substrings=[
            "oversight",
            "takeover_defense",
        ],
        forbidden_substrings=[],
        min_score=65,
    ),
    RegressionCase(
    name="controller_sale_process_fact_pattern",
    prompt="What standard applies where a controlling stockholder proposes a merger and the board also enters a sale process?",
    required_substrings=[
        "controller_transactions",
        "sale_of_control",
    ],
    forbidden_substrings=[],
    min_score=75,
),
RegressionCase(
    name="controller_corwin_fact_pattern",
    prompt="What standard applies where a board approves a merger not involving a controller and the transaction later receives a fully informed and uncoerced stockholder vote?",
    required_substrings=[
        "stockholder_vote_cleansing",
        "fully informed",
        "uncoerced",
    ],
    forbidden_substrings=[],
    min_score=75,
),


RegressionCase(
    name="oversight_red_flags_fact_pattern",
    prompt="What oversight standard applies where a board had compliance structures on paper but ignored red flags in a mission-critical area?",
    required_substrings=[
        "oversight",
        "red flags",
        "mission",
        "bad faith",   # 🔥 new — forces real doctrinal language
    ],
    forbidden_substrings=[
        "lower oversight risk",  # 🔥 prevents wrong tree branch
    ],
    min_score=75,
),

RegressionCase(
    name="malone_disclosure_loyalty_standard",
    prompt="What is the Delaware disclosure loyalty standard under Malone?",
    required_substrings=[
        "QUERY TYPE: governing_standard",
        "TARGET LINES: ['disclosure_loyalty']",
        "Short Answer:",
        "Rule:",
        "Analysis:",
        "Confidence:",
        "truthfully",
        "materially misleading",
    ],
    forbidden_substrings=[],
    min_score=75,
),

 RegressionCase(
    name="takeover_defense_fact_pattern",
    prompt="What standard applies where a board adopts defensive measures in response to a hostile bid and must justify that response as neither coercive nor preclusive?",
    required_substrings=[
        "takeover_defense",
        "coercive",
        "preclusive",
    ],
    forbidden_substrings=[],
    min_score=75,
),
    

]

def extract_validation_score(output: str) -> Optional[int]:
    marker = "VALIDATION SCORE:"
    for line in output.splitlines():
        if marker not in line:
            continue
        try:
            tail = line.split(marker, 1)[1].strip()
            value = tail.split("/", 1)[0].strip()
            return int(value)
        except (IndexError, ValueError):
            return None
    return None


def run_case(case: RegressionCase) -> tuple[bool, str]:
    if not ASK_SCRIPT.exists():
        return False, f"Missing {ASK_SCRIPT}"

    proc = subprocess.run(
        [sys.executable, str(ASK_SCRIPT)],
        input=case.prompt + "\n",
        text=True,
        capture_output=True,
    )

    output = proc.stdout + "\n" + proc.stderr
    output = proc.stdout + "\n" + proc.stderr

    print("\n================ DEBUG OUTPUT ================\n")
    print(f"CASE: {case.name}")
    print(output)
    print("\n==============================================\n")

    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{case.name}.txt").write_text(output, encoding="utf-8")

    errors: List[str] = []

    for needle in case.required_substrings:
        if needle not in output:
            errors.append(f"Missing required substring: {needle}")

    for needle in case.forbidden_substrings:
        if needle in output:
            errors.append(f"Found forbidden substring: {needle}")

    score = extract_validation_score(output)
    if score is None:
        errors.append("Could not find validation score")
    elif score < case.min_score:
        errors.append(f"Validation score {score} below minimum {case.min_score}")

    if proc.returncode != 0:
        errors.append(f"ask.py exited with code {proc.returncode}")

    if errors:
        joined = "\n".join(f"- {e}" for e in errors)
        return False, f"{case.name} FAILED\n{joined}\n"

    return True, f"{case.name} PASSED (score={score})\n"


def main() -> None:
    passed = 0
    failed = 0

    print("=" * 72)
    print("RUNNING DELAWARE AI REGRESSION SUITE")
    print("=" * 72)

    for case in TEST_CASES:
        ok, message = run_case(case)
        print(message)
        if ok:
            passed += 1
        else:
            failed += 1

    print("=" * 72)
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print("=" * 72)

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()