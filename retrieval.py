from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from doctrine_config import (
    CASE_ALIASES,
    CASE_ROLES,
    DOCTRINE_KEYWORDS,
    DOCTRINE_LABELS,
    ROLE_PRIORITY,
)

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).parent
INDEX_PATH = BASE_DIR / "index.json"
EMBED_CACHE_PATH = BASE_DIR / "embed_cache.json"

EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

client = OpenAI()


# ============================================================
# LOAD INDEX / CACHE
# ============================================================

def load_index() -> List[Dict[str, Any]]:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing index file: {INDEX_PATH}")

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_embed_cache() -> Dict[str, List[float]]:
    if EMBED_CACHE_PATH.exists():
        with open(EMBED_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_embed_cache(cache: Dict[str, List[float]]) -> None:
    with open(EMBED_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


INDEX = load_index()
EMBED_CACHE = load_embed_cache()


# ============================================================
# BASIC HELPERS
# ============================================================

def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def get_case_role(source: str) -> str:
    source_l = (source or "").lower()

    # Foundations
    if any(
        k in source_l
        for k in [
            "caremark",
            "unocal",
            "revlon",
            "aronson",
            "malone",
            "weinberger",
            "schnell",
        ]
    ):
        return "foundation"

    # Supreme refinements
    if any(
        k in source_l
        for k in [
            "stone",
            "unitrin",
            "qvc",
            "rales",
            "corwin",
            "blasius",
        ]
    ):
        return "supreme_refinement"

    # Modern applications
    if any(
        k in source_l
        for k in [
            "marchand",
            "airgas",
            "lyondell",
            "metro",
            "rural metro",
            "mfw",
            "zuckerberg",
            "tesla",
        ]
    ):
        return "modern_application"

    return "related_case"

def clean_case_name(source: str) -> str:
    base = (source or "Unknown").replace(".txt", "")
    return " ".join(part.capitalize() for part in base.split())


def get_case_display_name(case: Dict[str, Any]) -> str:
    source = case.get("source", "")
    mapping = {
        "caremark.txt": "Caremark",
        "stone.txt": "Stone",
        "marchand.txt": "Marchand",
        "disney.txt": "Disney",
        "in re caremark.txt": "In re Caremark",
        "rural metro.txt": "Rural Metro",
        "mfw.txt": "MFW",
        "corwin.txt": "Corwin",
        "kahn.txt": "Kahn",
        "revlon.txt": "Revlon",
        "qvc.txt": "QVC",
        "unocal.txt": "Unocal",
        "unitrin.txt": "Unitrin",
        "aronson.txt": "Aronson",
        "rales.txt": "Rales",
        "zuckerberg.txt": "Zuckerberg",
        "malone.txt": "Malone",
        "airgas.txt": "Airgas",
        "lyondell.txt": "Lyondell",
        "metro.txt": "Metro",
        "tesla.txt": "Tesla",
    }
    return mapping.get(source, clean_case_name(source))

ROLE_PRIORITY = {
    "foundation": 5,
    "supreme_refinement": 4,
    "refinement": 3,
    "modern_application": 2,
    "related_case": 1,
}

def infer_doctrine_line_from_source(source: str) -> str:
    s = (source or "").lower()

    if "malone" in s or "disclosure" in s:
        return "disclosure_loyalty"

    if any(k in s for k in ["caremark", "stone", "marchand"]):
        return "oversight"

    if any(k in s for k in ["unocal", "unitrin", "airgas"]):
        return "takeover_defense"

    if any(k in s for k in ["revlon", "qvc", "lyondell", "metro", "rural metro", "rbc"]):
        return "sale_of_control"

    if any(k in s for k in ["kahn", "mfw", "tesla"]):
        return "controller_transactions"

    if any(k in s for k in ["aronson", "rales", "zuckerberg"]):
        return "demand_futility"

    if "corwin" in s:
        return "stockholder_vote_cleansing"

    if any(k in s for k in ["weinberger", "entire fairness", "fair dealing", "fair price"]):
        return "entire_fairness"

    if any(k in s for k in ["schnell", "blasius", "section 220", "books and records"]):
        return s

    return "unknown"

# ============================================================
# EMBEDDINGS
# ============================================================

def _local_fallback_embedding(text: str, dims: int = 16) -> List[float]:
    """
    Deterministic local fallback so retrieval doesn't crash when API quota fails.
    Not semantically strong, but stable enough for dev/test fallback.
    """
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    raw = [int(h[i:i + 2], 16) / 255.0 for i in range(0, 32, 2)]

    if dims <= len(raw):
        return raw[:dims]

    vec = raw[:]
    while len(vec) < dims:
        vec.extend(raw)
    return vec[:dims]


def embed_text(text: str) -> List[float]:
    if text in EMBED_CACHE:
        return EMBED_CACHE[text]

    try:
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=text,
        )
        vec = response.data[0].embedding
    except Exception as e:
        print("⚠️ Embedding fallback triggered:", e)
        vec = _local_fallback_embedding(text)

    EMBED_CACHE[text] = vec
    save_embed_cache(EMBED_CACHE)
    return vec


# ============================================================
# QUERY PLANNING
# ============================================================

def infer_query_type(question: str) -> str:
    q = (question or "").lower()

    if any(term in q for term in [
        "compare",
        "comparison",
        "distinguish",
        "difference",
        "different",
        "versus",
        " vs ",
        "interact",
        "interaction",
        "overlap",
        "relationship",
    ]):
        return "comparison"

    if any(term in q for term in [
        "evolve",
        "evolution",
        "refine",
        "refined",
        "develop",
        "development",
        "how did",
        "through stone",
        "through marchand",
    ]):
        return "doctrine_evolution"

    if any(term in q for term in [
        "standard",
        "governing",
        "what is the rule",
        "what rule applies",
        "test",
        "plead",
        "pleading",
        "must show",
        "must prove",
    ]):
        return "governing_standard"

    if any(term in q for term in [
        "factor",
        "factors",
        "element",
        "elements",
    ]):
        return "factors"

    return "general"


def infer_target_lines(question: str) -> List[str]:
    q = (question or "").lower()
    matches: List[Tuple[str, int]] = []

    for doctrine_line, terms in DOCTRINE_KEYWORDS.items():
        score = sum(1 for term in terms if term in q)
        if score > 0:
            matches.append((doctrine_line, score))

    if not matches:
        return ["unknown"]

    matches.sort(key=lambda x: x[1], reverse=True)
    top_score = matches[0][1]

    selected = [
        doctrine_line
        for doctrine_line, score in matches
        if score >= max(1, top_score - 1)
    ]

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
    lines = [line for line in query_plan.get("target_lines", []) if line != "unknown"]
    return len(lines) >= 2


def build_query_plan_cached(question: str) -> Dict[str, Any]:
    plan = {
        "question": question,
        "query_type": infer_query_type(question),
        "target_lines": infer_target_lines(question),
        "named_sources": infer_named_sources(question),
    }
    plan["multi_doctrine"] = is_multi_doctrine_query(plan)
    return plan


def get_retrieval_budget(query_plan: Dict[str, Any]) -> Dict[str, int]:
    query_type = query_plan.get("query_type", "general")

    if query_type == "comparison":
        return {"k": 18, "max_per_source": 4}

    if query_type == "doctrine_evolution":
        return {"k": 20, "max_per_source": 5}

    return {"k": 12, "max_per_source": 4}
# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(question: str, k: int = 12, max_per_source: int = 4) -> List[Dict[str, Any]]:
    import re

    ROLE_PRIORITY = {
        "foundation": 5,
        "supreme_refinement": 4,
        "refinement": 3,
        "modern_application": 2,
        "related_case": 1,
        "unknown": 0,
    }

    q_emb = embed_text(question)
    query_plan = build_query_plan_cached(question)

    target_lines = [x for x in query_plan.get("target_lines", ["unknown"]) if x]
    target_set = set(target_lines)

    query_type = query_plan.get("query_type", "general")
    multi_doctrine = query_plan.get("multi_doctrine", False)

    primary_doctrine = query_plan.get("primary_doctrine", "unknown")
    primary_issue = query_plan.get("primary_issue", primary_doctrine)

    secondary_issues = set(query_plan.get("secondary_issues", []))
    contextual_issues = set(query_plan.get("contextual_issues", []))
    secondary_doctrines = set(query_plan.get("secondary_doctrines", []))

    named_sources = set(query_plan.get("named_sources", []))
    preferred_sources = set(query_plan.get("preferred_sources", []))
    suppress_sources = set(query_plan.get("suppress_sources", []))

    issue_priority = query_plan.get("issue_priority", {}) or {}
    has_advisor_conflict = issue_priority.get("has_advisor_conflict", False)

    q_lower = question.lower()

    is_food_safety_red_flags = any(
        phrase in q_lower
        for phrase in [
            "food safety",
            "food-safety",
            "red flag",
            "red flags",
            "mission critical",
            "mission-critical",
        ]
    )

    advisor_conflict_sources = {
        "metro.txt",
        "rural metro.txt",
        "rbc.txt",
        "rbc capital markets.txt",
    }

    takeover_defense_sources = {
        "airgas.txt",
        "unocal.txt",
        "unitrin.txt",
    }

    core_sources_by_doctrine = {
        "oversight": {"caremark.txt", "stone.txt", "marchand.txt"},
        "sale_of_control": {"revlon.txt", "qvc.txt", "lyondell.txt"},
        "takeover_defense": {"unocal.txt", "unitrin.txt", "airgas.txt"},
        "controller_transactions": {"kahn.txt", "mfw.txt", "tesla.txt"},
        "stockholder_vote_cleansing": {"corwin.txt", "mfw.txt"},
        "demand_futility": {"aronson.txt", "rales.txt", "zuckerberg.txt"},
        "disclosure_loyalty": {
            "malone.txt",
            "opinions malone.txt",
            "doctrines disclosure duty malone.txt",
        },
        "entire_fairness": {
            "weinberger.txt",
            "kahn.txt",
            "doctrine entire fairness.txt",
        },
    }

    blocked_sources: set[str] = set()

    if primary_issue == "oversight" and "sale_of_control" in target_set:
        blocked_sources.update(takeover_defense_sources)

        if not has_advisor_conflict:
            blocked_sources.update(advisor_conflict_sources)

    scored: List[Dict[str, Any]] = []

    for chunk in INDEX:
        emb = chunk.get("embedding")
        if not emb:
            continue

        source = chunk.get("source", "")
        source_l = source.lower()

        if source_l in blocked_sources:
            continue

        text = chunk.get("text", "")
        text_l = text.lower()

        if len(text.split()) < 18:
            continue

        if text.count("§") > 3:
            continue

        if text.count("...") > 2:
            continue

        if re.search(r"\b\d{3,}\b", text):
            continue

        if "submitted:" in text_l and "decided:" in text_l:
            continue

        if "before the court" in text_l and len(text) > 1200:
            continue

        if "court below" in text_l and len(text) > 1000:
            continue

        if text_l.startswith("in the supreme court"):
            continue

        doctrine_line = chunk.get("doctrine_line")

        if not doctrine_line or doctrine_line == "unknown":
            doctrine_line = infer_doctrine_line_from_source(source)
        role = chunk.get("role")

        if not role or role in {"unknown", "related_case"}:
            role = get_case_role(source)
        chunk_role = chunk.get("chunk_role", "")

        if "malone" in source_l or "disclosure duty" in source_l:
            doctrine_line = "disclosure_loyalty"
            role = "foundation"

        quality_score = chunk.get("quality_score", 100)
        corrupt = chunk.get("corrupt", False)

        if corrupt or quality_score < 35:
            continue

        if len(q_emb) != len(emb):
            usable = min(len(q_emb), len(emb))
            if usable == 0:
                continue
            score = dot(q_emb[:usable], emb[:usable])
        else:
            score = dot(q_emb, emb)

        if source in named_sources:
            score *= 1.35

        if source in preferred_sources:
            score *= 1.26

        if source in suppress_sources:
            score *= 0.40

        if doctrine_line == primary_issue:
            score *= 1.85
            score += 0.35
        elif doctrine_line in secondary_issues:
            score *= 1.35
            score += 0.22
        elif doctrine_line in contextual_issues:
            score *= 0.92
        elif doctrine_line in target_set:
            score *= 1.16
            score += 0.15
        elif doctrine_line in secondary_doctrines:
            score *= 1.04
        elif doctrine_line == "unknown":
            score *= 0.55
            score -= 0.25
        else:
            score *= 0.45
            score -= 0.18

        if role == "foundation":
            score *= 1.16
            score += 0.22
        elif role == "supreme_refinement":
            score *= 1.14
            score += 0.18
        elif role == "refinement":
            score *= 1.08
            score += 0.10
        elif role == "modern_application":
            score *= 1.04
            score += 0.06
        elif role == "related_case":
            score *= 0.72
            score -= 0.18

        core_sources = core_sources_by_doctrine.get(doctrine_line, set())

        if source_l in core_sources:
            score *= 1.18
            score += 0.18

        if doctrine_line == "unknown" and role == "related_case":
            score *= 0.60
            score -= 0.30

        if primary_issue == "disclosure_loyalty":
            if doctrine_line == "disclosure_loyalty":
                score *= 1.75
                score += 0.50
            else:
                score *= 0.25

        if primary_issue == "controller_transactions":
            if doctrine_line in {"controller_transactions", "stockholder_vote_cleansing"}:
                score *= 1.35
                score += 0.18
            elif doctrine_line in {"sale_of_control", "takeover_defense"}:
                score *= 0.55
            elif doctrine_line == "unknown":
                score *= 0.45

        if is_food_safety_red_flags:
            if doctrine_line == "oversight":
                score *= 1.35
                score += 0.20

            if doctrine_line == "takeover_defense":
                score *= 0.15

            if (
                doctrine_line == "sale_of_control"
                and role in {"modern_application", "related_case"}
                and not has_advisor_conflict
            ):
                score *= 0.50

            if source_l in advisor_conflict_sources and not has_advisor_conflict:
                score *= 0.20

        if primary_issue == "oversight" and "sale_of_control" in target_set:
            if doctrine_line == "oversight":
                score *= 1.25

            if doctrine_line == "sale_of_control":
                if role in {"foundation", "supreme_refinement"}:
                    score *= 1.18
                elif role in {"modern_application", "related_case"} and not has_advisor_conflict:
                    score *= 0.42

        if chunk_role == "rule":
            score *= 1.32
            score += 0.08
        elif chunk_role == "application":
            score *= 1.06
        elif chunk_role == "analysis":
            score *= 1.03
        elif chunk_role == "facts":
            score *= 0.74
        elif chunk_role == "procedural":
            score *= 0.50
        elif chunk_role == "header":
            score *= 0.25

        if quality_score >= 85:
            score *= 1.06
        elif quality_score >= 70:
            score *= 1.02
        elif quality_score < 55:
            score *= 0.70

        if doctrine_line == "unknown" and score < 0.85:
            continue

        enriched = dict(chunk)
        enriched["score"] = score
        enriched["doctrine_line"] = doctrine_line
        enriched["role"] = role
        scored.append(enriched)

    # Pure oversight comparison: remove non-oversight doctrine after scoring.
    if query_type == "comparison" and primary_issue == "oversight" and target_set <= {"oversight", "unknown"}:
        scored = [
            c for c in scored
            if c.get("doctrine_line") == "oversight"
        ]

    # Disclosure loyalty: keep Malone/disclosure sources from being outranked by sale-process noise.
    if primary_issue == "disclosure_loyalty":
        scored = [
            c for c in scored
            if c.get("doctrine_line") == "disclosure_loyalty"
        ]

    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    deduped: List[Dict[str, Any]] = []
    seen_snippets: set[str] = set()

    for chunk in scored:
        text = chunk.get("text", "")
        key = re.sub(r"\s+", " ", text[:220].lower()).strip()

        if key in seen_snippets:
            continue

        seen_snippets.add(key)
        deduped.append(chunk)

    scored = deduped

    selected: List[Dict[str, Any]] = []
    per_source: Dict[str, int] = {}
    selected_ids: set[tuple] = set()

    def chunk_key(chunk: Dict[str, Any]) -> tuple:
        return (
            chunk.get("source", ""),
            chunk.get("chunk_id", ""),
            chunk.get("text", "")[:80],
        )

    def add_chunk(chunk: Dict[str, Any]) -> bool:
        source = chunk.get("source", "")
        source_l = source.lower()

        if source_l in blocked_sources:
            return False

        role = chunk.get("role")

        if not role or role in {"unknown", "related_case"}: 
         role = get_case_role(source)

        dynamic_cap = max_per_source

        if role in {"foundation", "supreme_refinement"}:
            dynamic_cap += 1

        if per_source.get(source, 0) >= dynamic_cap:
            return False

        key = chunk_key(chunk)
        if key in selected_ids:
            return False

        selected.append(chunk)
        selected_ids.add(key)
        per_source[source] = per_source.get(source, 0) + 1

        return True

    guaranteed_doctrines: List[str] = []

    if multi_doctrine:
        guaranteed_doctrines = [primary_issue] + list(secondary_issues)
    elif primary_issue and primary_issue != "unknown":
        guaranteed_doctrines = [primary_issue]

    for doctrine in guaranteed_doctrines:
        if doctrine == "unknown":
            continue

        doctrine_chunks = [
            c for c in scored
            if c.get("doctrine_line") == doctrine
        ]

        doctrine_chunks.sort(
            key=lambda c: (
                ROLE_PRIORITY.get(c.get("role") or "unknown", 0),
                c.get("score", 0.0),
            ),
            reverse=True,
        )

        added = 0
        target_adds = 3 if multi_doctrine else 4

        for chunk in doctrine_chunks:
            if add_chunk(chunk):
                added += 1

            if added >= target_adds:
                break

    allowed_fill_doctrines = (
    set(guaranteed_doctrines)
    | contextual_issues
    | target_set
)

# Pure oversight comparison should remain doctrine-pure.
    if (
    query_type == "comparison"
    and primary_issue == "oversight"
):
        allowed_fill_doctrines = {"oversight"}

    for chunk in scored:
        if len(selected) >= k:
            break

        doctrine_line = chunk.get("doctrine_line", "unknown")
        role = chunk.get("role", "unknown")

        if multi_doctrine:
            if doctrine_line not in allowed_fill_doctrines:
                continue

            if doctrine_line == "unknown" and role == "related_case":
                continue

        add_chunk(chunk)

    return selected

# ============================================================
# AGGREGATION / CONTEXT
# ============================================================

def aggregate_by_case(top_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_case: Dict[str, Dict[str, Any]] = {}

    for chunk in top_chunks:
        source = chunk.get("source", "")
        if not source:
            continue

        if source not in by_case:
            role = chunk.get("role")

            if not role or role in {"unknown", "related_case"}:
                role = get_case_role(source)
            doctrine_line = chunk.get("doctrine_line")

            if not doctrine_line or doctrine_line == "unknown":
                doctrine_line = infer_doctrine_line_from_source(source)

            by_case[source] = {
                "source": source,
                "chunks": [],
                "case_score": 0.0,
                "role": role,
                "doctrine_line": doctrine_line,
            }

        by_case[source]["chunks"].append(chunk)
        by_case[source]["case_score"] = max(
            by_case[source]["case_score"],
            chunk.get("score", 0.0),
        )

    cases = list(by_case.values())
    cases.sort(
        key=lambda c: (
            ROLE_PRIORITY.get(c.get("role", "related_case"), 99),
            -c.get("case_score", 0.0),
        )
    )
    return cases


def bucket_cases_by_doctrine_line(cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}

    for case in cases:
        source = case.get("source", "")
        doctrine_line = case.get("doctrine_line") or infer_doctrine_line_from_source(source)
        buckets.setdefault(doctrine_line, []).append(case)

    for bucket in buckets.values():
        bucket.sort(
            key=lambda c: (
                ROLE_PRIORITY.get(c.get("role", "related_case"), 99),
                -c.get("case_score", 0.0),
            )
        )

    return buckets


def select_doctrine_leaders(
    doctrine_buckets: Dict[str, List[Dict[str, Any]]],
    max_cases_per_line: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    selected: Dict[str, List[Dict[str, Any]]] = {}
    preferred_roles = ["foundation", "supreme_refinement", "modern_application"]

    for doctrine_line, bucket in doctrine_buckets.items():
        chosen: List[Dict[str, Any]] = []
        seen_sources = set()

        for role in preferred_roles:
            for case in bucket:
                source = case.get("source", "")
                if case.get("role") == role and source not in seen_sources:
                    chosen.append(case)
                    seen_sources.add(source)
                    break

        for case in bucket:
            if len(chosen) >= max_cases_per_line:
                break

            source = case.get("source", "")
            if source not in seen_sources:
                chosen.append(case)
                seen_sources.add(source)

        selected[doctrine_line] = chosen[:max_cases_per_line]

    return selected


def build_context_from_cases(
    cases: List[Dict[str, Any]],
    target_lines: List[str],
) -> Tuple[str, str]:
    context_parts: List[str] = []
    timeline_parts: List[str] = []

    target_set = set(target_lines or [])

    filtered_cases = [
        case for case in cases
        if not target_set
        or case.get("doctrine_line") in target_set
        or infer_doctrine_line_from_source(case.get("source", "")) in target_set
    ]

    if not filtered_cases:
        filtered_cases = cases

    for case in filtered_cases[:5]:
        source = case.get("source", "")
        role = case.get("role", "related_case")
        doctrine_line = case.get("doctrine_line") or infer_doctrine_line_from_source(source)
        display = get_case_display_name(case)
        chunks = case.get("chunks", [])[:2]

        chunk_text = "\n".join(
            chunk.get("text", "")[:700]
            for chunk in chunks
            if chunk.get("text")
        )

        context_parts.append(
            f"[{display} | doctrine={doctrine_line} | role={role} | source={source}]\n{chunk_text}"
        )
        timeline_parts.append(f"- {display}: {role}")

    return "\n\n".join(context_parts), "\n".join(timeline_parts)


def build_multi_doctrine_context(
    doctrine_leaders: Dict[str, List[Dict[str, Any]]],
    requested_lines: List[str],
) -> str:
    parts: List[str] = []

    for doctrine_line in requested_lines:
        if doctrine_line == "unknown":
            continue

        cases = doctrine_leaders.get(doctrine_line, [])
        label = DOCTRINE_LABELS.get(
            doctrine_line,
            doctrine_line.replace("_", " ").title(),
        )

        parts.append(f"[DOCTRINE LINE: {label}]")

        for case in cases:
            display = get_case_display_name(case)
            role = case.get("role", "related_case")
            source = case.get("source", "")
            chunks = case.get("chunks", [])[:2]

            chunk_text = "\n".join(
                chunk.get("text", "")[:500]
                for chunk in chunks
                if chunk.get("text")
            )

            parts.append(
                f"{display} | role={role} | source={source}\n{chunk_text}"
            )

        parts.append("")

    return "\n".join(parts).strip()