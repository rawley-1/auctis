from __future__ import annotations

from typing import Any, Dict, List, Tuple

from doctrine_config import CASE_ALIASES, CASE_ROLES, ROLE_PRIORITY


def get_case_role(source: str) -> str:
    return CASE_ROLES.get(source, "related_case")


def infer_doctrine_line_from_source(source: str) -> str:
    s = (source or "").lower()

    if s in {"caremark.txt", "stone.txt", "marchand.txt", "disney.txt", "in re caremark.txt"}:
        return "oversight"
    if s in {"unocal.txt", "unitrin.txt", "airgas.txt"}:
        return "takeover_defense"
    if s in {"revlon.txt", "qvc.txt", "lyondell.txt", "rural metro.txt", "metro.txt"}:
        return "sale_of_control"
    if s in {"kahn.txt", "mfw.txt", "tesla.txt"}:
        return "controller_transactions"
    if s in {"aronson.txt", "rales.txt", "zuckerberg.txt"}:
        return "demand_futility"
    if s == "corwin.txt":
        return "stockholder_vote_cleansing"
    if s == "malone.txt":
        return "disclosure_loyalty"

    return "unknown"


def infer_query_type(question: str) -> str:
    q = (question or "").lower()

    if any(term in q for term in ["compare", "versus", " vs ", "distinguish", "difference"]):
        return "comparison"

    if any(term in q for term in ["evolve", "evolution", "refine", "through stone", "through marchand"]):
        return "doctrine_evolution"

    if any(term in q for term in ["standard", "test", "must plead", "must show", "rule applies"]):
        return "governing_standard"

    return "general"


def infer_target_lines(question: str) -> List[str]:
    q = (question or "").lower()

    doctrine_term_map: Dict[str, List[str]] = {
        "oversight": [
            "caremark",
            "stone",
            "marchand",
            "oversight",
            "red flags",
            "mission critical",
            "mission-critical",
            "monitor",
            "reporting system",
        ],
        "takeover_defense": [
            "unocal",
            "unitrin",
            "airgas",
            "defensive measures",
            "poison pill",
            "hostile bid",
            "coercive",
            "preclusive",
            "range of reasonableness",
        ],
        "sale_of_control": [
            "revlon",
            "qvc",
            "sale of control",
            "change of control",
            "best value reasonably available",
            "auction",
        ],
        "controller_transactions": [
            "kahn",
            "mfw",
            "controller",
            "controlling stockholder",
            "entire fairness",
            "majority of the minority",
            "special committee",
        ],
        "demand_futility": [
            "aronson",
            "rales",
            "zuckerberg",
            "demand futility",
            "reasonable doubt",
            "impartially consider",
        ],
        "stockholder_vote_cleansing": [
            "corwin",
            "fully informed",
            "uncoerced vote",
            "stockholder vote cleansing",
        ],
        "disclosure_loyalty": [
            "malone",
            "disclosure",
            "misleading shareholders",
        ],
    }

    matches: List[Tuple[str, int]] = []
    for line, terms in doctrine_term_map.items():
        score = sum(1 for term in terms if term in q)
        if score > 0:
            matches.append((line, score))

    if not matches:
        return ["unknown"]

    matches.sort(key=lambda x: x[1], reverse=True)
    top_score = matches[0][1]
    selected = [line for line, score in matches if score >= max(1, top_score - 1)]

    priority_order = [
        "oversight",
        "takeover_defense",
        "sale_of_control",
        "controller_transactions",
        "demand_futility",
        "stockholder_vote_cleansing",
        "disclosure_loyalty",
    ]

    return sorted(set(selected), key=lambda x: priority_order.index(x))


def infer_named_sources(question: str) -> List[str]:
    q = (question or "").lower()
    matches = [source for alias, source in CASE_ALIASES.items() if alias in q]
    return sorted(set(matches), key=lambda s: ROLE_PRIORITY.get(get_case_role(s), 99))


def is_multi_doctrine_query(query_plan: Dict[str, Any]) -> bool:
    lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
    return len(lines) >= 2


def build_query_plan(question: str) -> Dict[str, Any]:
    plan = {
        "question": question,
        "query_type": infer_query_type(question),
        "target_lines": infer_target_lines(question),
        "named_sources": infer_named_sources(question),
    }
    plan["multi_doctrine"] = is_multi_doctrine_query(plan)
    return plan


def build_query_plan_cached(question: str) -> Dict[str, Any]:
    # Keeping behavior identical to your current code.
    # You can add lru_cache later if you want.
    return build_query_plan(question)