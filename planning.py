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

    if "entire fairness" in q:
        return ["entire_fairness"]

    doctrine_term_map: Dict[str, List[str]] = {
        "oversight": [
            "caremark", "stone", "marchand", "oversight",
            "red flags", "mission critical", "mission-critical",
            "monitor", "reporting system",
        ],
        "takeover_defense": [
            "unocal", "unitrin", "airgas",
            "defensive measures", "poison pill",
            "hostile bid", "coercive", "preclusive",
            "range of reasonableness",
        ],
        "sale_of_control": [
            "revlon", "qvc",
            "sale of control", "change of control",
            "best value reasonably available", "auction",
        ],
        "controller_transactions": [
            "kahn", "mfw",
            "controller", "controlling stockholder",
            "majority of the minority", "special committee",
        ],
        "demand_futility": [
            "aronson", "rales", "zuckerberg",
            "demand futility", "reasonable doubt",
            "impartially consider",
        ],
        "stockholder_vote_cleansing": [
            "corwin", "fully informed",
            "uncoerced vote", "stockholder vote cleansing",
        ],

        # 🔥 NEW DOCTRINES

        "entire_fairness": [
            "entire fairness", "fair dealing", "fair price",
            "weinberger", "kahn v lynch", "lynch",
            "self dealing", "self-dealing",
            "conflicted transaction",
        ],

        "disclosure": [
            "malone", "disclosure", "misleading",
            "duty to disclose", "material omission",
            "materially misleading", "informed vote",
        ],

        "shareholder_franchise": [
            "blasius", "shareholder franchise",
            "stockholder franchise", "voting rights",
            "compelling justification", "interfere with vote",
        ],

        "equitable_intervention": [
            "schnell", "inequitable", "equity",
            "legally possible", "improper purpose",
            "corporate machinery",
        ],

        "books_and_records": [
            "section 220", "dgcl 220", "220",
            "books and records", "inspection demand",
            "proper purpose", "credible basis",
        ],
    }

    matches: List[Tuple[str, int]] = []

    for line, terms in doctrine_term_map.items():
        score = sum(1 for term in terms if term in q)
        if score > 0:
            matches.append((line, score))

    # 🔥 SMART FALLBACKS
    if "fairness" in q:
        matches.append(("entire_fairness", 1))

    if "vote" in q and "corwin" in q:
        matches.append(("stockholder_vote_cleansing", 1))

    if "books" in q and "records" in q:
        matches.append(("books_and_records", 1))

    if not matches:
        return ["unknown"]

    # sort by score
    matches.sort(key=lambda x: x[1], reverse=True)

    top_score = matches[0][1]

    # keep near-top matches
    selected = [
        line for line, score in matches
        if score >= max(1, top_score - 1)
    ]

    # 🔥 IMPORTANT: DOCTRINE PRIORITY (prevents bad collisions)
    priority_order = [
        "entire_fairness",
        "controller_transactions",
        "oversight",
        "takeover_defense",
        "sale_of_control",
        "shareholder_franchise",
        "equitable_intervention",
        "books_and_records",
        "disclosure",
        "stockholder_vote_cleansing",
        "demand_futility",
    ]

    # preserve priority ordering
    ordered = sorted(set(selected), key=lambda x: priority_order.index(x))

    return ordered

def infer_named_sources(question: str) -> List[str]:
    q = (question or "").lower()
    matches = [source for alias, source in CASE_ALIASES.items() if alias in q]
    return sorted(set(matches), key=lambda s: ROLE_PRIORITY.get(get_case_role(s), 99))


def is_multi_doctrine_query(query_plan: Dict[str, Any]) -> bool:
    lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
    return len(lines) >= 2


def build_query_plan(question: str) -> Dict[str, Any]:
    q = (question or "").strip()

    query_type = infer_query_type(q)
    target_lines = infer_target_lines(q)
    named_sources = infer_named_sources(q)

    real_target_lines = [line for line in target_lines if line != "unknown"]

    plan = {
        "question": q,
        "query_type": query_type,
        "target_lines": target_lines,
        "named_sources": named_sources,
        "recognized_doctrine": bool(real_target_lines),
        "primary_doctrine": real_target_lines[0] if real_target_lines else "unknown",
        "multi_doctrine": len(real_target_lines) > 1,
        "new_doctrine_enabled": any(
            line in {
                "entire_fairness",
                "disclosure",
                "shareholder_franchise",
                "equitable_intervention",
                "books_and_records",
            }
            for line in real_target_lines
        ),
    }

    if query_type == "comparison" and len(named_sources) >= 2:
        plan["multi_doctrine"] = True

    if query_type == "comparison" and len(plan["target_lines"]) == 1:
        plan["target_lines"] = plan["target_lines"] * 2

    try:
        plan["multi_doctrine"] = plan["multi_doctrine"] or is_multi_doctrine_query(plan)
    except Exception:
        pass

    return plan


def build_query_plan_cached(question: str) -> Dict[str, Any]:
    # Keeping behavior identical to your current code.
    # You can add lru_cache later if you want.
    return build_query_plan(question)