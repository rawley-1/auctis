from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


ASK_SCRIPT = Path("ask.py")
OUTPUT_DIR = Path("regression_outputs")

CASE_ROLES = {
    "caremark.txt": "foundation",
    "stone.txt": "supreme_refinement",
    "marchand.txt": "modern_application",
    "disney.txt": "related_case",
    "in re caremark.txt": "related_case",
    "aronson.txt": "foundation",
    "rales.txt": "refinement",
    "zuckerberg.txt": "supreme_refinement",
    "malone.txt": "foundation",
    "unocal.txt": "foundation",
    "unitrin.txt": "supreme_refinement",
    "airgas.txt": "modern_application",
    "revlon.txt": "foundation",
    "qvc.txt": "supreme_refinement",
    "lyondell.txt": "modern_application",
    "rural metro.txt": "related_case",
    "metro.txt": "modern_application",
    "kahn.txt": "foundation",
    "mfw.txt": "supreme_refinement",
    "tesla.txt": "modern_application",
    "corwin.txt": "supreme_refinement",
}

ROLE_PRIORITY = {
    "foundation": 1,
    "supreme_refinement": 2,
    "refinement": 3,
    "modern_application": 4,
    "related_case": 5,
}

CASE_ALIASES = {
    "caremark": "caremark.txt",
    "stone": "stone.txt",
    "marchand": "marchand.txt",
    "disney": "disney.txt",
    "in re caremark": "in re caremark.txt",
    "aronson": "aronson.txt",
    "rales": "rales.txt",
    "zuckerberg": "zuckerberg.txt",
    "malone": "malone.txt",
    "unocal": "unocal.txt",
    "unitrin": "unitrin.txt",
    "airgas": "airgas.txt",
    "revlon": "revlon.txt",
    "qvc": "qvc.txt",
    "lyondell": "lyondell.txt",
    "rural metro": "rural metro.txt",
    "metro": "metro.txt",
    "kahn": "kahn.txt",
    "mfw": "mfw.txt",
    "tesla": "tesla.txt",
    "corwin": "corwin.txt",
}

DOCTRINE_LABELS = {
    "oversight": "Oversight",
    "takeover_defense": "Takeover Defense",
    "sale_of_control": "Sale of Control",
    "controller_transactions": "Controller Transactions",
    "demand_futility": "Demand Futility",
    "stockholder_vote_cleansing": "Stockholder Vote Cleansing",
    "disclosure_loyalty": "Disclosure Loyalty",
}

DOCTRINE_KEYWORDS = {
    "oversight": [
        "caremark", "stone", "marchand", "oversight", "red flags",
        "mission critical", "mission-critical", "monitor", "reporting system",
    ],
    "takeover_defense": [
    "unocal",
    "unitrin",
    "airgas",
    "poison pill",
    "hostile bid",
    "defensive measures",
    "defensive measure",
    "coercive",
    "preclusive",
    "range of reasonableness",
    "takeover defense",
    "takeover",
    ],
    "sale_of_control": [
        "revlon", "qvc", "sale of control", "change of control",
        "auction", "best value reasonably available",
    ],
    "controller_transactions": [
        "kahn", "mfw", "controller", "entire fairness",
        "special committee", "majority of the minority",
    ],
    "demand_futility": [
        "aronson", "rales", "zuckerberg", "demand futility",
        "reasonable doubt", "impartially consider",
    ],
    "stockholder_vote_cleansing": [
        "corwin", "fully informed", "uncoerced vote", "stockholder vote cleansing",
    ],
    "disclosure_loyalty": [
        "malone", "disclosure", "misleading shareholders",
    ],
}

FALLBACK_QUOTES = {
    "caremark.txt": "Only a sustained or systematic failure of the board to exercise oversight—such as an utter failure to attempt to assure a reasonable information and reporting system exists—will establish the lack of good faith that is a necessary condition to liability.",
    "stone.txt": "The failure to act in good faith may result in liability because the requirement to act in good faith is a subsidiary element of the duty of loyalty.",
    "marchand.txt": "Directors must make a good faith effort to implement an oversight system and then monitor it.",
    "mfw.txt": "Business judgment review applies if the transaction is conditioned from the outset on both special committee approval and a majority-of-the-minority vote.",
    "corwin.txt": "Business judgment review applies after a fully informed, uncoerced vote of disinterested stockholders in a non-controller transaction.",
    "stone.txt": "Failure to act in good faith may result in liability because the requirement to act in good faith is a subsidiary element of the duty of loyalty.",
}


@dataclass
class RegressionCase:
    name: str
    prompt: str
    required_substrings: List[str]
    forbidden_substrings: List[str]
    min_score: int


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
        forbidden_substrings=[
            "utter failure to attempt to assure",
            "good faith effort to implement an oversight system",
        ],
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
        prompt="What standard applies when a board ignored red flags and adopted defensive measures?",
        required_substrings=[
            "oversight",
            "takeover_defense",
        ],
        forbidden_substrings=[],
        min_score=65,
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
