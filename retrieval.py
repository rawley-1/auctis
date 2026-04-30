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
    return CASE_ROLES.get(source, "related_case")

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


def infer_doctrine_line_from_source(source: str) -> str:
    s = (source or "").lower()

    if any(k in s for k in ["caremark", "stone", "marchand"]):
        return "oversight"

    if any(k in s for k in ["unocal", "unitrin", "airgas"]):
        return "takeover_defense"

    if any(k in s for k in ["revlon", "qvc", "lyondell", "metro"]):
        return "sale_of_control"

    if any(k in s for k in ["kahn", "mfw", "tesla"]):
        return "controller_transactions"

    if any(k in s for k in ["aronson", "rales", "zuckerberg"]):
        return "demand_futility"

    if "corwin" in s:
        return "stockholder_vote_cleansing"

    if "malone" in s:
        return "disclosure_loyalty"

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
    q_emb = embed_text(question)
    query_plan = build_query_plan_cached(question)
    target_lines = query_plan.get("target_lines", ["unknown"])
    named_sources = set(query_plan.get("named_sources", []))
    multi_doctrine = query_plan.get("multi_doctrine", False)

    scored: List[Dict[str, Any]] = []

    for chunk in INDEX:
        emb = chunk.get("embedding")
        if not emb:
            continue

        source = chunk.get("source", "")
        doctrine_line = chunk.get("doctrine_line") or infer_doctrine_line_from_source(source)
        role = get_case_role(source)
        chunk_role = chunk.get("chunk_role", "")

        if len(q_emb) != len(emb):
            usable = min(len(q_emb), len(emb))
            if usable == 0:
                continue
            score = dot(q_emb[:usable], emb[:usable])
        else:
            score = dot(q_emb, emb)

        if source in named_sources:
            score *= 1.25

        if doctrine_line in target_lines:
            score *= 1.45
        elif doctrine_line == "unknown":
            score *= 0.85
        else:
         score *= 0.70

        if role == "foundation":
            score *= 1.05
        elif role == "supreme_refinement":
            score *= 1.08
        elif role == "modern_application":
            score *= 1.06
        elif role == "refinement":
            score *= 1.03

        if chunk_role == "rule":
            score *= 1.18
        elif chunk_role == "application":
            score *= 1.05
        elif chunk_role == "facts":
            score *= 0.92
        elif chunk_role == "procedural":
            score *= 0.90

        enriched = dict(chunk)
        enriched["score"] = score
        enriched["doctrine_line"] = doctrine_line
        enriched["role"] = role
        scored.append(enriched)
        
    print("TARGET_LINES:", target_lines)
    print("TOP ENTIRE FAIRNESS CHUNKS:", [
    (c.get("source"), c.get("doctrine_line"), round(c.get("score", 0), 4))
    for c in scored
    if c.get("doctrine_line") == "entire_fairness"
][:10])
    scored.sort(key=lambda x: x["score"], reverse=True)

    selected: List[Dict[str, Any]] = []
    per_source: Dict[str, int] = {}

    for chunk in scored:
        source = chunk.get("source", "")
        if per_source.get(source, 0) >= max_per_source:
            continue

        selected.append(chunk)
        per_source[source] = per_source.get(source, 0) + 1

        if len(selected) >= k:
            break

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
            role = get_case_role(source)
            by_case[source] = {
                "source": source,
                "chunks": [],
                "case_score": 0.0,
                "role": role,
            }

        by_case[source]["chunks"].append(chunk)
        by_case[source]["case_score"] = max(
            by_case[source]["case_score"],
            chunk.get("score", 0.0),
        )

    cases = list(by_case.values())
    cases.sort(key=lambda c: (-c["case_score"], ROLE_PRIORITY.get(c["role"], 99)))
    return cases


def bucket_cases_by_doctrine_line(cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}

    for case in cases:
        source = case.get("source", "")
        doctrine_line = infer_doctrine_line_from_source(source)
        buckets.setdefault(doctrine_line, []).append(case)

    for doctrine_line, bucket in buckets.items():
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
                if case.get("role") == role and case.get("source") not in seen_sources:
                    chosen.append(case)
                    seen_sources.add(case.get("source"))
                    break

        for case in bucket:
            if len(chosen) >= max_cases_per_line:
                break
            if case.get("source") not in seen_sources:
                chosen.append(case)
                seen_sources.add(case.get("source"))

        selected[doctrine_line] = chosen

    return selected


def build_context_from_cases(
    cases: List[Dict[str, Any]],
    target_lines: List[str],
) -> Tuple[str, str]:
    context_parts: List[str] = []
    timeline_parts: List[str] = []

    for case in cases[:5]:
        source = case.get("source", "")
        role = case.get("role", "related_case")
        display = get_case_display_name(case)
        chunks = case.get("chunks", [])[:2]

        chunk_text = "\n".join(
            chunk.get("text", "")[:700]
            for chunk in chunks
            if chunk.get("text")
        )

        context_parts.append(
            f"[{display} | role={role} | source={source}]\n{chunk_text}"
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
        label = DOCTRINE_LABELS.get(doctrine_line, doctrine_line.replace("_", " ").title())

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

            parts.append(f"{display} | role={role} | source={source}\n{chunk_text}")

        parts.append("")

    return "\n".join(parts).strip()