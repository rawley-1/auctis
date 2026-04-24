from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).parent
INDEX_PATH = BASE_DIR / "index.json"
MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt.txt"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8") if SYSTEM_PROMPT_PATH.exists() else ""

client = OpenAI()

# ============================================================
# LOAD INDEX
# ============================================================


def load_index() -> List[Dict[str, Any]]:
    if not INDEX_PATH.exists():
        raise FileNotFoundError(f"Missing index file: {INDEX_PATH}")
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


INDEX = load_index()

# ============================================================
# METADATA
# ============================================================

from doctrine_config import (
    CASE_ALIASES,
    CASE_ROLES,
    DOCTRINE_KEYWORDS,
    DOCTRINE_LABELS,
    FALLBACK_QUOTES,
    ROLE_PRIORITY,
)

# ============================================================
# BASICS
# ============================================================


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def embed_text(text: str) -> List[float]:
    response = client.embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding


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
    }
    return mapping.get(source, clean_case_name(source))


def infer_doctrine_line_from_source(source: str) -> str:
    s = source.lower()
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
            "caremark", "stone", "marchand", "oversight", "red flags",
            "mission critical", "mission-critical", "monitor", "reporting system",
        ],
        "takeover_defense": [
            "unocal", "unitrin", "airgas", "defensive measures", "poison pill",
            "hostile bid", "coercive", "preclusive", "range of reasonableness",
        ],
        "sale_of_control": [
            "revlon", "qvc", "sale of control", "change of control",
            "best value reasonably available", "auction",
        ],
        "controller_transactions": [
            "kahn", "mfw", "controller", "controlling stockholder",
            "entire fairness", "majority of the minority", "special committee",
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
    q = question.lower()
    matches = [source for alias, source in CASE_ALIASES.items() if alias in q]
    return sorted(set(matches), key=lambda s: ROLE_PRIORITY.get(get_case_role(s), 99))


def is_multi_doctrine_query(query_plan: Dict[str, Any]) -> bool:
    lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
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

# ============================================================
# RETRIEVAL
# ============================================================


def get_retrieval_budget(query_plan: Dict[str, Any]) -> Dict[str, int]:
    query_type = query_plan.get("query_type", "general")
    if query_type == "comparison":
        return {"k": 18, "max_per_source": 4}
    if query_type == "doctrine_evolution":
        return {"k": 20, "max_per_source": 5}
    return {"k": 12, "max_per_source": 4}


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
        score = dot(q_emb, emb)

        if source in named_sources:
            score *= 1.25
        if doctrine_line in target_lines:
            score *= 1.20
        elif multi_doctrine and doctrine_line != "unknown":
            score *= 1.02
        elif doctrine_line == "unknown":
            score *= 0.95
        else:
            score *= 0.85

        if role == "foundation":
            score *= 1.05
        elif role == "supreme_refinement":
            score *= 1.08
        elif role == "modern_application":
            score *= 1.06

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
# AGGREGATION
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
        by_case[source]["case_score"] = max(by_case[source]["case_score"], chunk.get("score", 0.0))

    cases = list(by_case.values())
    cases.sort(key=lambda c: (-c["case_score"], ROLE_PRIORITY.get(c["role"], 99)))
    return cases


def bucket_cases_by_doctrine_line(cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for case in cases:
        line = infer_doctrine_line_from_source(case.get("source", ""))
        buckets.setdefault(line, []).append(case)
    for line, bucket in buckets.items():
        bucket.sort(key=lambda c: (ROLE_PRIORITY.get(c.get("role", "related_case"), 99), -c.get("case_score", 0.0)))
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

# ============================================================
# QUOTES
# ============================================================


def _normalize_quote_text(text: str) -> str:
    text = (text or "").replace("\n", " ").replace("\xad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(' "\'')


def extract_case_quotes_from_text(text: str) -> List[str]:
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean: List[str] = []

    for s in sentences:
        s = _normalize_quote_text(s)
        s_l = s.lower()
        if len(s.split()) < 8:
            continue
        if any(bad in s_l for bad in ["court:", "year:", "doctrine:", "authority:", "key topic:", "section:"]):
            continue
        if any(k in s_l for k in [
            "must", "requires", "good faith", "duty of loyalty",
            "business judgment", "entire fairness", "fully informed",
            "uncoerced", "special committee", "majority of the minority",
            "reporting system", "oversight system", "reasonable doubt",
            "best value reasonably available", "coercive", "preclusive",
        ]):
            clean.append(s)

    return clean


def extract_case_quotes(
    chunks: List[Dict[str, Any]],
    max_quotes_per_case: int = 5,
) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    by_source: Dict[str, List[str]] = {}

    for chunk in chunks:
        source = chunk.get("source", "")
        text = chunk.get("text", "") or ""
        if not source or not text:
            continue
        extracted = extract_case_quotes_from_text(text)
        if not extracted:
            continue
        by_source.setdefault(source, [])
        by_source[source].extend(extracted)

    fallback_quotes = FALLBACK_QUOTES
    all_sources = {chunk.get("source", "") for chunk in chunks if chunk.get("source")}

    for source in all_sources:
        quotes = by_source.get(source, [])
        deduped: List[str] = []
        seen = set()

        for q in quotes:
            q_norm = re.sub(r"\s+", " ", q.strip().lower())
            if not q_norm or q_norm in seen:
                continue
            seen.add(q_norm)
            deduped.append(q.strip())
            if len(deduped) >= max_quotes_per_case:
                break

        if deduped:
            result[source] = deduped
        elif source in fallback_quotes:
            result[source] = [fallback_quotes[source]]

    return result


def is_valid_doctrinal_quote(q: str) -> bool:
    if not q:
        return False
    q_l = q.lower()
    return any(k in q_l for k in [
        "must", "requires", "duty", "standard", "review",
        "fully informed", "uncoerced", "business judgment",
        "entire fairness", "controller", "good faith",
        "oversight system", "reporting system",
    ])


def pick_best_quote(quotes: List[str], source: str = "") -> str:
    if not quotes:
        return ""

    source_l = (source or "").lower()

    def is_garbage(q: str) -> bool:
        q = (q or "").strip()
        q_l = q.lower()
        if not q:
            return True
        if len(q.split()) < 8:
            return True
        if any(k in q_l for k in [
            "court:", "year:", "doctrine:", "authority:", "key topic:", "section:", "case:",
            "the court held", "the court explained", "the court stated",
            "plaintiff", "complaint", "motion to dismiss", "rescissory damages",
        ]):
            return True
        if "\n" in q and ("caremark" in source_l or "stone" in source_l or "kahn" in source_l):
            return True
        return False

    def is_doctrinal(q: str) -> bool:
        q_l = q.lower()
        return any(k in q_l for k in [
            "must", "requires", "business judgment", "entire fairness",
            "fully informed", "uncoerced", "majority of the minority",
            "special committee", "controller", "duty of loyalty",
            "good faith", "monitor", "oversight system", "reporting system",
            "reasonable doubt", "best value reasonably available",
            "range of reasonableness", "coercive", "preclusive",
        ])

    def score(q: str) -> float:
        q_l = q.lower()
        s = 0.0
        n_words = len(q.split())

        if 10 <= n_words <= 40:
            s += 3.0
        elif 8 <= n_words <= 55:
            s += 1.5

        for k in [
            "must", "requires", "business judgment", "entire fairness",
            "fully informed", "uncoerced", "special committee",
            "majority of the minority", "controller", "duty of loyalty",
            "good faith", "monitor", "oversight system", "reporting system",
        ]:
            if k in q_l:
                s += 2.0

        if "caremark" in source_l:
            if "utter failure to attempt to assure" in q_l:
                s += 10
        if "stone" in source_l:
            if "failure to act in good faith" in q_l:
                s += 10
        if "marchand" in source_l:
            if "good faith effort" in q_l:
                s += 10
            if "implement an oversight system" in q_l:
                s += 8
        if "mfw" in source_l:
            if "special committee" in q_l:
                s += 4
            if "majority of the minority" in q_l:
                s += 4
            if "business judgment" in q_l:
                s += 3
        if "corwin" in source_l:
            if "fully informed" in q_l:
                s += 4
            if "uncoerced" in q_l:
                s += 4
            if "business judgment" in q_l:
                s += 4

        return s

    clean = [q.strip() for q in quotes if not is_garbage(q)]
    if not clean:
        return ""

    doctrinal = [q for q in clean if is_doctrinal(q)]
    candidates = doctrinal if doctrinal else clean

    ranked = sorted(candidates, key=score, reverse=True)
    best = ranked[0].strip()
    if best and best[-1] not in ".!?":
        best += "."
    return best


def normalize_quote_fragment(role: str, quote: str) -> str:
    q = _normalize_quote_text(quote).lower()
    patterns_by_role = {
        "foundation": [
            "utter failure to attempt to assure",
            "sustained or systematic failure",
            "reporting or information system exists",
        ],
        "supreme_refinement": [
            "failure to act in good faith",
            "subsidiary element of the duty of loyalty",
            "duty of loyalty",
        ],
        "modern_application": [
            "good faith effort to implement an oversight system",
            "conscious failure to monitor",
            "breach of the duty of loyalty",
            "mission critical",
        ],
    }
    for p in patterns_by_role.get(role, []):
        if p in q:
            return p
    words = re.findall(r"\b[a-z]{4,}\b", q)
    return " ".join(words[:8]).strip()

def build_role_based_quote_map(
    cases: List[Dict[str, Any]],
    case_quotes: Dict[str, List[str]],
    debug: bool = False,
) -> Dict[str, Dict[str, str]]:
    selected: Dict[str, Dict[str, str]] = {}
    seen_quotes: set[str] = set()

    for role in ["foundation", "supreme_refinement", "refinement", "modern_application"]:
        for case in cases:
            source = case.get("source", "")
            case_role = case.get("role", get_case_role(source))
            if case_role != role:
                continue

            qs = case_quotes.get(source, [])

            

            filtered_quotes = [q for q in qs if is_valid_doctrinal_quote(q)]
            best_quote = pick_best_quote(filtered_quotes, source) if filtered_quotes else ""

            if not best_quote:
                continue

            quote_key = best_quote.lower().strip()
            if quote_key in seen_quotes and role != "modern_application":
                continue

            seen_quotes.add(quote_key)
            selected[role] = {
                "case": get_case_display_name({"source": source}).strip() or clean_case_name(source),
                "quote": best_quote if best_quote[-1] in ".!?" else best_quote + ".",
                "source": source,
            }
            break

    return selected

def build_required_quote_fragments_block(role_quote_map, target_lines):
    lines = []

    for role, item in role_quote_map.items():
        fragment = normalize_quote_fragment(role, item.get("quote", ""))
        case = item.get("case", "Unknown")

        if fragment:
            lines.append(f'- {case}: "{fragment}"')

    if not lines:
        if "controller_transactions" in target_lines:
            lines.append('- MFW: "business judgment review applies if conditioned from the outset"')
        if "stockholder_vote_cleansing" in target_lines:
            lines.append('- Corwin: "fully informed, uncoerced vote"')
        if "oversight" in target_lines:
            lines.append('- Marchand: "good faith effort to implement an oversight system"')

    return "\n".join(lines)

# ============================================================
# OUTPUT
# ============================================================


def get_multi_doctrine_labels(query_plan: Dict[str, Any]) -> List[str]:
    lines = [line for line in query_plan.get("target_lines", []) if line != "unknown"]
    return [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in lines[:2]]


def get_answer_template(query_plan):
    query_type = query_plan.get("query_type")
    target_lines = query_plan.get("target_lines", [])
    multi = query_plan.get("multi_doctrine", False)
    target_set = set(target_lines)

    if query_type == "comparison" and multi:
        if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Controller Transactions:
<one paragraph>

Stockholder Vote Cleansing:
<one paragraph>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""
        if {"controller_transactions", "sale_of_control"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Controller Transactions:
<one paragraph>

Sale of Control:
<one paragraph>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""
        if {"oversight", "takeover_defense"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Oversight:
<one paragraph>

Takeover Defense:
<one paragraph>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""
        if {"oversight", "sale_of_control"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Oversight:
<one paragraph>

Sale of Control:
<one paragraph>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""

def synthesize_multi_doctrine_short_answer(target_lines: List[str]) -> str:
    labels = [DOCTRINE_LABELS.get(line, line.replace("_", " ").title()) for line in target_lines if line != "unknown"]
    if len(labels) >= 2:
        return f"{labels[0]} establishes the governing framework for one fiduciary setting, whereas {labels[1]} governs a distinct one."
    return "The answer depends on the governing doctrinal framework."


def synthesize_multi_doctrine_key_distinction(target_lines: List[str]) -> str:
    target_set = set(target_lines)
    if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
        return "MFW governs conflicted controller transactions through dual cleansing protections, whereas Corwin governs the effect of a fully informed and uncoerced stockholder vote."
    if {"oversight", "takeover_defense"} <= target_set:
        return "Caremark addresses internal board oversight obligations, whereas Unocal addresses defensive action in response to external takeover threats."
    if {"oversight", "sale_of_control"} <= target_set:
        return "Caremark addresses the board's obligation to monitor risk, whereas Revlon addresses the board's obligation to maximize value in a sale setting."
    if {"demand_futility", "oversight"} <= target_set:
        return "Demand futility addresses board-level incapacity to consider a demand, whereas Caremark addresses the underlying oversight conduct said to constitute the breach."

    labels = [DOCTRINE_LABELS.get(line, line.replace("_", " ").title()) for line in target_lines if line != "unknown"]
    if len(labels) >= 2:
        return f"{labels[0]} establishes the governing framework for one fiduciary setting, whereas {labels[1]} governs a distinct one."
    return "The doctrines address distinct fiduciary settings, whereas each imposes its own governing standard."


def synthesize_rule_from_quotes(
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: List[str],
) -> str:
    foundation_frag = normalize_quote_fragment("foundation", role_quote_map.get("foundation", {}).get("quote", "")) or "utter failure to attempt to assure"
    refinement_frag = normalize_quote_fragment("supreme_refinement", role_quote_map.get("supreme_refinement", {}).get("quote", "")) or "failure to act in good faith"
    modern_frag = normalize_quote_fragment("modern_application", role_quote_map.get("modern_application", {}).get("quote", "")) or "good faith effort to implement an oversight system"

    if "oversight" in target_lines:
        return (
            "A board breaches the duty of loyalty where either its "
            f"{foundation_frag} "
            "a reasonable reporting or information system exists or its conscious failure to monitor such a system "
            f"constitutes a {refinement_frag}, "
            f"requiring a {modern_frag}."
        )

    if "takeover_defense" in target_lines:
        return (
            "Under Unocal, directors must show that they had reasonable grounds for believing a threat to corporate policy and effectiveness existed, "
            "and that their defensive response was neither coercive nor preclusive and fell within a range of reasonableness."
        )

    if "controller_transactions" in target_lines:
        return (
            "A controller transaction receives business judgment deference only where, from the outset, it is conditioned on approval by both an independent special committee "
            "and an informed, uncoerced majority of the minority stockholders."
        )

    if "stockholder_vote_cleansing" in target_lines:
        return (
            "A fully informed, uncoerced vote of disinterested stockholders generally invokes business judgment review and extinguishes claims subject to Corwin cleansing."
        )

    if "sale_of_control" in target_lines:
        return (
            "Where the corporation is for sale or a transaction will effect a change of control, directors must act reasonably to secure the best value reasonably available to stockholders."
        )

    if "demand_futility" in target_lines:
        return (
            "Demand is excused where the complaint pleads particularized facts supporting a reasonable doubt that a majority of the board could impartially consider a demand."
        )

    return "The governing rule depends on the doctrinal framework identified by the question."


def synthesize_doctrine_section(
    doctrine_line: str,
    doctrine_cases: List[Dict[str, Any]],
    case_quotes: Dict[str, List[str]],
) -> str:
    role_quote_map = build_role_based_quote_map(doctrine_cases, case_quotes)

    if doctrine_line == "oversight":
        return hard_lock_rule(polish_synthesized_rule(compress_rule(synthesize_rule_from_quotes(role_quote_map, ["oversight"]))))

    if doctrine_line == "takeover_defense":
        return "A board's defensive response to a perceived threat is subject to enhanced scrutiny where it identifies a threat to corporate policy and effectiveness and adopts a response that is neither coercive nor preclusive and falls within a range of reasonableness."

    if doctrine_line == "sale_of_control":
        return "Where the corporation is for sale or a transaction will effect a change of control, directors must act reasonably to secure the transaction offering the best value reasonably available to stockholders."

    if doctrine_line == "controller_transactions":
        return "A controller transaction receives business judgment deference only where, from the outset, it is conditioned on approval by both an independent special committee and an informed, uncoerced majority of the minority stockholders."

    if doctrine_line == "demand_futility":
        return "Demand is excused where the complaint pleads particularized facts supporting a reasonable doubt that a majority of the board could impartially consider a demand."

    if doctrine_line == "stockholder_vote_cleansing":
        return "A fully informed, uncoerced vote of disinterested stockholders generally invokes business judgment review and extinguishes claims subject to Corwin cleansing."

    return "The governing rule depends on the doctrinal framework identified by the question."


def synthesize_multi_doctrine_rule_comparison(target_lines: List[str]) -> str:
    target_set = set(target_lines)

    if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
        return (
            "Controller Transactions (MFW) establishes the governing framework for conflicted controller transactions by restoring business judgment review only if the transaction is conditioned from the outset on both special committee approval and a majority-of-the-minority vote. "
            "Stockholder Vote Cleansing (Corwin) defines when business judgment review applies to a non-controller transaction after a fully informed and uncoerced vote of disinterested stockholders. "
            "Taken together, Controller Transactions requires dual cleansing protections for controller conflict, whereas Stockholder Vote Cleansing turns on stockholder approval through a fully informed and uncoerced vote."
        )

    if {"oversight", "takeover_defense"} <= target_set:
        return (
            "Oversight (Caremark) governs board-level monitoring failure by requiring a good faith effort to implement and monitor a reporting system. "
            "Takeover Defense (Unocal) governs defensive action in response to an external threat by requiring a response that is neither coercive nor preclusive and falls within a range of reasonableness. "
            "Taken together, Oversight addresses internal monitoring obligations, whereas Takeover Defense addresses external defensive measures adopted in response to takeover pressure."
        )

    if {"oversight", "sale_of_control"} <= target_set:
        return (
            "Oversight (Caremark) governs the board's obligation to implement and monitor internal reporting systems in good faith. "
            "Sale of Control (Revlon) governs the board's obligation to secure the best value reasonably available once a sale or change of control is underway. "
            "Taken together, Oversight addresses internal monitoring failure, whereas Sale of Control addresses transactional conduct directed toward value maximization."
        )

    if {"demand_futility", "oversight"} <= target_set:
        return (
            "Demand Futility (Aronson/Rales) governs whether the board can impartially consider a stockholder demand. "
            "Oversight (Caremark) governs whether directors failed in good faith to implement or monitor a reporting system. "
            "Taken together, Demand Futility addresses board-level capacity to consider litigation demand, whereas Oversight addresses the underlying fiduciary conduct alleged to be wrongful."
        )

    labels = [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in target_lines if line != "unknown"]
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
    target_set = set(target_lines)

    if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
        return (
            "This matters because controller transactions require approval by both a special committee and a majority-of-the-minority vote, whereas stockholder vote cleansing depends on a fully informed and uncoerced vote of disinterested stockholders. "
            "The significance is that each doctrine invokes business judgment review through a different mechanism tailored to a distinct fiduciary risk. "
            "As a result, the applicable standard of review depends on whether the transaction implicates controller conflict requiring MFW protections or instead turns on stockholder approval under Corwin."
        )

    if {"oversight", "takeover_defense"} <= target_set:
        return (
            "This matters because oversight doctrine focuses on the board's obligation to implement and monitor a reporting system in good faith, whereas takeover-defense doctrine focuses on defensive measures adopted in response to a threat. "
            "The significance is that the doctrines regulate different board functions and apply different standards to internal monitoring failure and external defensive action. "
            "As a result, a board may satisfy one doctrine's requirements while still failing the other."
        )

    if {"oversight", "sale_of_control"} <= target_set:
        return (
            "This matters because oversight doctrine governs the board's obligation to implement and monitor internal reporting systems, whereas sale-of-control doctrine governs the obligation to secure the best value reasonably available in a change-of-control setting. "
            "The significance is that the doctrines address different fiduciary problems and evaluate different forms of board conduct. "
            "As a result, the governing standard depends on whether the alleged failure concerns internal monitoring or transactional value maximization."
        )

    if {"demand_futility", "oversight"} <= target_set:
        return (
            "This matters because demand-futility doctrine addresses whether the board can impartially consider a demand, whereas oversight doctrine addresses whether directors failed in good faith to implement or monitor a reporting system. "
            "The significance is that one doctrine governs board-level decisionmaking capacity and the other governs the underlying oversight conduct. "
            "As a result, a plaintiff must separately address demand futility and the merits of the alleged oversight breach."
        )

    labels = [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in target_lines if line != "unknown"]
    if len(labels) >= 2:
        return (
            f"This matters because {labels[0]} and {labels[1]} regulate different fiduciary settings. "
            f"The significance is that each doctrine applies a different standard or cleansing mechanism to a different form of board conduct. "
            f"As a result, identifying the correct doctrinal bucket is necessary before the governing standard can be applied."
        )

    return (
        "This matters because Delaware fiduciary doctrine is context specific rather than unitary. "
        "The significance is that each doctrine governs a different board function and therefore imposes a different standard of review or obligation. "
        "As a result, identifying the correct doctrinal bucket is necessary before the governing standard can be applied."
    )


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

    return "The answer depends on the governing doctrinal standard."


def synthesize_key_distinction(
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: List[str],
    tree_result: Optional[Dict[str, Any]] = None,
) -> str:
    if "oversight" in target_lines:
        if tree_result is None:
            return "Caremark addresses absence of oversight systems, whereas Marchand addresses failure to monitor implemented systems."
        primary_failure = tree_result.get("primary_failure", "")
        outcome = tree_result.get("outcome", "")
        if primary_failure == "utter_failure":
            return "The present theory sounds in implementation failure, whereas Marchand speaks more directly to monitoring failure."
        if primary_failure == "failure_to_monitor":
            return "The present theory sounds in monitoring failure, whereas Caremark states the implementation baseline."
        if primary_failure == "red_flags":
            return "The present theory sounds in mission-critical monitoring failure, whereas Caremark states the baseline implementation rule."
        if outcome == "lower_oversight_risk":
            return "The facts indicate monitored oversight rather than either a true implementation failure or a true monitoring failure."
        return "Caremark addresses absence of oversight systems, whereas Marchand addresses failure to monitor implemented systems."

    return "The earlier doctrine states the baseline rule, whereas the later doctrine refines its application."


def synthesize_rule_comparison(
    role_quote_map: Dict[str, Dict[str, str]],
    tree_result: Optional[Dict[str, Any]] = None,
) -> str:
    s1 = "Caremark establishes that oversight liability begins with an utter failure to attempt to assure a reasonable reporting or information system exists."
    s2 = "Marchand clarifies, in line with Stone's rule that failure to act in good faith is a breach of the duty of loyalty, that directors must make a good faith effort to implement an oversight system and monitor it."
    s3 = "Taken together, Caremark defines liability at the point of an utter failure to attempt to assure a reasonable reporting or information system exists, whereas Marchand requires good-faith monitoring once an oversight system is implemented."
    return f"{s1} {s2} {s3}"


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

    return (
        "This matters because Delaware doctrine distinguishes baseline fiduciary obligations from conduct that crosses into breach. "
        "The significance is that directors act inconsistently with the duty of loyalty where their conduct constitutes a failure to act in good faith. "
        "As a result, breach arises only when inaction or conscious disregard moves beyond imperfection and into disloyal conduct."
    )


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

# ============================================================
# TEXT HELPERS
# ============================================================


def build_context_from_cases(cases: List[Dict[str, Any]], target_lines: List[str]) -> Tuple[str, str]:
    context_parts: List[str] = []
    timeline_parts: List[str] = []

    for case in cases[:5]:
        source = case.get("source", "")
        role = case.get("role", "related_case")
        display = get_case_display_name(case)
        chunks = case.get("chunks", [])[:2]
        chunk_text = "\n".join(chunk.get("text", "")[:700] for chunk in chunks if chunk.get("text"))
        context_parts.append(f"[{display} | role={role} | source={source}]\n{chunk_text}")
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
            chunk_text = "\n".join(chunk.get("text", "")[:500] for chunk in chunks if chunk.get("text"))
            parts.append(f"{display} | role={role} | source={source}\n{chunk_text}")
        parts.append("")
    return "\n".join(parts).strip()


def build_supporting_cases_block(cases: List[Dict[str, Any]], max_supporting: int = 2) -> str:
    lines: List[str] = []
    seen = set()
    for case in cases:
        source = case.get("source", "")
        role = get_case_role(source)
        if role not in {"related_case", "refinement", "modern_application"}:
            continue
        name = get_case_display_name(case).strip() or clean_case_name(source)
        if name in seen:
            continue
        seen.add(name)
        lines.append(f"- {name}: {role}")
        if len(lines) >= max_supporting:
            break
    return "\n".join(lines)

def remove_section(text: str, section_name: str) -> str:
    pattern = rf"{re.escape(section_name)}\s*:\s*\n?(.*?)(?=\n[A-Z][A-Za-z ]+\s*:|\Z)"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()

def replace_section(answer: str, section_name: str, new_body: str) -> str:
    pattern = rf"({re.escape(section_name)}\s*:\s*)(.*?)(?=\n[A-Z][A-Za-z ]*:\s*|\Z)"
    replacement = rf"\1{new_body.strip()}\n"
    return re.sub(pattern, replacement, answer, flags=re.DOTALL)

def extract_sections(ai_answer: str, query_plan: Dict[str, Any]) -> Dict[str, str]:
    text = (ai_answer or "").strip()

    def section_body(name: str, following: List[str]) -> str:
        if following:
            pattern = rf"{name}\s*:?\s*(.*?)(?=" + "|".join(rf"\b{x}\b\s*:?" for x in following) + r"|$)"
        else:
            pattern = rf"{name}\s*:?\s*(.*)$"
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    sections = {
        "text": text,
        "short_answer": section_body("Short Answer", ["Key Distinction", "Rule Comparison", "Rule", "Analysis", "Confidence"]),
        "key_distinction": section_body("Key Distinction", ["Controller Transactions", "Stockholder Vote Cleansing", "Rule Comparison", "Rule", "Analysis", "Confidence"]),
        "rule_comparison": section_body("Rule Comparison", ["Rule", "Analysis", "Confidence"]),
        "rule": section_body("Rule", ["Analysis", "Confidence"]),
        "analysis": section_body("Analysis", ["Confidence"]),
        "confidence": section_body("Confidence", []),
    }

    if query_plan.get("multi_doctrine"):
        labels = get_multi_doctrine_labels(query_plan)
        if len(labels) >= 1:
            sections[labels[0].lower()] = section_body(labels[0], [labels[1]] + ["Rule Comparison", "Analysis", "Confidence"] if len(labels) >= 2 else ["Rule Comparison", "Analysis", "Confidence"])
        if len(labels) >= 2:
            sections[labels[1].lower()] = section_body(labels[1], ["Rule Comparison", "Analysis", "Confidence"])

    return sections


def enforce_one_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return sentences[0] if sentences else text


def compress_rule(rule_text: str) -> str:
    r = re.sub(r"\s+", " ", (rule_text or "").strip())
    if not r.endswith("."):
        r += "."
    return r


def polish_synthesized_rule(rule_text: str) -> str:
    text = re.sub(r"\s+", " ", (rule_text or "")).strip()
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"[.]+$", "", text).strip()
    return text + "."


def hard_lock_rule(rule_text: str) -> str:
    text = re.sub(r"\s+", " ", (rule_text or "")).strip()
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"[.]+$", "", text).strip()
    return text + "."


def enforce_three_sentences(text: str) -> str:
    parts = [p.strip() for p in text.split(".") if p.strip()]
    if len(parts) < 3:
        return text
    return ". ".join(parts[:3]) + "."


def compress_rule_comparison(text: str) -> str:
    rc = re.sub(r"\s+", " ", (text or "").strip())
    if not rc.endswith("."):
        rc += "."
    return rc


def polish_synthesized_rule_comparison(text: str) -> str:
    rc = re.sub(r"\s+", " ", (text or "")).strip()
    sentences = re.findall(r"[^.!?]+[.!?]", rc)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) >= 3:
        return " ".join(sentences[:3]).strip()
    return rc.rstrip(".") + "."


def enforce_analysis_structure(sentences: List[str]) -> List[str]:
    if len(sentences) < 3:
        return sentences

    def strip_known_prefixes(text: str) -> str:
        t = text.strip()
        prefixes = [
            "This matters because",
            "The significance is that",
            "As a result,",
            "As a result",
        ]
        changed = True
        while changed:
            changed = False
            for p in prefixes:
                if t.startswith(p):
                    t = t[len(p):].strip()
                    changed = True
        return t.rstrip(".")

    s1 = strip_known_prefixes(sentences[0])
    s2 = strip_known_prefixes(sentences[1])
    s3 = strip_known_prefixes(sentences[2])

    return [
        f"This matters because {s1}.",
        f"The significance is that {s2}.",
        f"As a result, {s3}.",
    ]


def polish_synthesized_analysis(text: str) -> str:
    analysis = re.sub(r"\s+", " ", (text or "")).strip()
    analysis = re.sub(r"\b(\w+)\s+\1\b", r"\1", analysis, flags=re.IGNORECASE)
    analysis = re.sub(r"[.]+$", "", analysis).strip()
    return analysis + "."


def hard_lock_analysis(analysis_text: str) -> str:
    text = re.sub(r"\s+", " ", (analysis_text or "")).strip()
    sentences = re.findall(r"[^.!?]+[.!?]", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) >= 3:
        sentences = enforce_analysis_structure(sentences[:3])
        return " ".join(sentences).strip()
    return text


def relock_answer_sections(
    ai_answer: str,
    locked_short_answer: str,
    locked_key_distinction: str,
    locked_rule: str,
    locked_rule_comparison: str,
    locked_analysis: str,
) -> str:
    ai_answer = replace_section(ai_answer, "Short Answer", locked_short_answer)
    ai_answer = replace_section(ai_answer, "Key Distinction", locked_key_distinction)
    ai_answer = replace_section(ai_answer, "Rule", locked_rule)
    ai_answer = replace_section(ai_answer, "Rule Comparison", locked_rule_comparison)
    ai_answer = replace_section(ai_answer, "Analysis", locked_analysis)
    return ai_answer

# ============================================================
# CAREMARK TREE
# ============================================================


def infer_caremark_facts_from_question(question: str) -> Dict[str, bool]:
    q = (question or "").lower()

    has_reporting_system = not any(phrase in q for phrase in [
        "no reporting system",
        "no compliance system",
        "no oversight system",
        "no controls",
        "utter failure",
        "never implemented",
        "no board-level system",
        "no board level system",
    ])

    monitors_reporting_system = not any(phrase in q for phrase in [
        "failed to monitor",
        "failure to monitor",
        "consciously failed to monitor",
        "did not monitor",
        "never reviewed reports",
        "ignored monitoring",
    ])

    mission_critical_risk = any(phrase in q for phrase in [
        "mission critical",
        "mission-critical",
        "core mission",
        "mission",
        "central compliance risk",
        "food safety",
        "core compliance",
        "regulatory risk",
        "safety issue",
    ])

    red_flags_ignored = any(phrase in q for phrase in [
        "red flags",
        "red flag",
        "ignored red flags",
        "ignored red flag",
        "warning signs",
        "warnings ignored",
        "board ignored warnings",
        "ignored warnings",
    ])

    # Red-flags fact patterns are a monitoring failure even if a system exists.
    if red_flags_ignored:
        monitors_reporting_system = False

    return {
        "has_reporting_system": has_reporting_system,
        "monitors_reporting_system": monitors_reporting_system,
        "mission_critical_risk": mission_critical_risk,
        "red_flags_ignored": red_flags_ignored,
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
        result["reason"] = "The facts suggest an utter failure to attempt to assure a reasonable reporting or information system exists."
        return result

    result["path"].append("reporting_system_exists")

    if not monitors_reporting_system:
        result["path"].append("no_monitoring")
        result["outcome"] = "potential_oversight_breach"
        result["risk_level"] = "high"
        result["primary_failure"] = "failure_to_monitor"
        result["reason"] = "The facts suggest a conscious failure to monitor or oversee an existing reporting or information system."
        return result

    result["path"].append("monitoring_exists")

    if mission_critical_risk and red_flags_ignored:
        result["path"].append("mission_critical_red_flags")
        result["outcome"] = "heightened_oversight_risk"
        result["risk_level"] = "medium_high"
        result["primary_failure"] = "red_flags"
        result["reason"] = "The board appears to have monitoring structures, but ignored red flags in a mission-critical area."
        return result

    result["path"].append("basic_oversight_present")
    result["outcome"] = "lower_oversight_risk"
    result["risk_level"] = "low"
    result["primary_failure"] = "none"
    result["reason"] = "The facts suggest the board established and monitored an oversight system, which weakens an oversight-breach theory."
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

# ============================================================
# VALIDATION
# ============================================================


def validate_short_answer(
    sections: Dict[str, str],
    query_type: str,
    target_lines: List[str],
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    short_answer = (sections.get("short_answer", "") or "").strip()
    short_l = short_answer.lower()

    if not short_answer:
        return ["Short Answer is empty"], -12

    real_lines = [x for x in target_lines if x != "unknown"]
    target_set = set(real_lines)

    sentences = [s.strip() for s in short_answer.split(".") if s.strip()]
    if len(sentences) != 1:
        errors.append("Short Answer must be exactly one sentence")
        delta -= 8

    if len(short_answer.split()) > 20:
        errors.append("Short Answer is too long")
        delta -= 6

    for term in ["the court held", "the court explained", "the court stated", "this case shows"]:
        if term in short_l:
            errors.append(f"Short Answer contains forbidden term: '{term}'")
            delta -= 5

    if len(target_set) >= 2:
        labels = [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in real_lines[:2]]
        if len(labels) >= 1 and labels[0].lower() not in short_l:
            errors.append(f"Short Answer must mention {labels[0]}")
            delta -= 5
        if len(labels) >= 2 and labels[1].lower() not in short_l:
            errors.append(f"Short Answer must mention {labels[1]}")
            delta -= 5
        if "whereas" not in short_l:
            errors.append("Short Answer should use 'whereas' in multi-doctrine mode")
            delta -= 4
        return errors, delta

    if target_set == {"oversight"}:
        if not any(term in short_l for term in ["utter failure", "good faith", "monitor", "oversight"]):
            errors.append("Short Answer should capture the controlling oversight distinction")
            delta -= 6

    return errors, delta


def validate_key_distinction(
    sections: Dict[str, str],
    query_type: str,
    target_lines: List[str],
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    if query_type != "comparison":
        return errors, delta

    key_distinction = (sections.get("key_distinction", "") or "").strip()
    kd_l = key_distinction.lower()

    if not key_distinction:
        return ["Key Distinction is empty"], -12

    sentences = re.split(r"[.!?]+", key_distinction)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) != 1:
        errors.append("Key Distinction must be exactly one sentence")
        delta -= 8

    if len(key_distinction.split()) > 38:
        errors.append("Key Distinction is too long")
        delta -= 4

    if "whereas" not in kd_l:
        errors.append("Key Distinction must use 'whereas'")
        delta -= 6

    return errors, delta


def fragment_present(fragment: str, text: str) -> bool:
    fragment = fragment.lower()
    text = text.lower()

    if fragment in text:
        return True

    frag_words = [w for w in re.findall(r"[a-z]+", fragment) if len(w) >= 4]
    text_words = set(re.findall(r"[a-z]+", text))

    hits = sum(1 for w in frag_words if w in text_words)
    return hits >= 2


def validate_rule_comparison_v2(
    sections: Dict[str, str],
    query_type: str,
    tree_result: Optional[Dict[str, Any]] = None,
    target_lines: Optional[List[str]] = None,
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    if query_type != "comparison":
        return errors, delta

    rule_comparison = (sections.get("rule_comparison", "") or "").strip()
    if not rule_comparison:
        return ["Rule Comparison is empty"], -12

    rc_l = rule_comparison.lower()
    target_lines = [x for x in (target_lines or []) if x != "unknown"]
    target_set = set(target_lines)

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", rule_comparison.strip())
        if s.strip()
    ]

    if len(sentences) != 3:
        errors.append("Rule Comparison must be exactly three sentences")
        delta -= 12
        return errors, delta

    s1_l = sentences[0].lower()
    s2_l = sentences[1].lower()
    s3_l = sentences[2].lower()

    if not s3_l.startswith("taken together"):
        errors.append("Rule Comparison sentence 3 must begin with 'Taken together'")
        delta -= 8

    if target_set == {"oversight"}:
        if "caremark" not in rc_l:
            errors.append("Rule Comparison must expressly include Caremark")
            delta -= 8
        if "marchand" not in rc_l:
            errors.append("Rule Comparison must expressly include Marchand")
            delta -= 8
        if "stone" not in rc_l:
            errors.append("Rule Comparison must expressly include Stone")
            delta -= 6
        if not fragment_present("utter failure to attempt to assure", s1_l):
            errors.append("Rule Comparison sentence 1 must state Caremark's utter-failure baseline")
            delta -= 8
        if not fragment_present("good faith effort to implement an oversight system", s2_l):
            errors.append("Rule Comparison missing grounded fragment: Marchand (modern_application) -> \"good faith effort to implement an oversight system\"")
            delta -= 8
        if "monitor" not in s2_l:
            errors.append("Rule Comparison sentence 2 must state Marchand's monitoring requirement")
            delta -= 8
        if "whereas" not in s3_l:
            errors.append("Rule Comparison sentence 3 must contain 'whereas'")
            delta -= 8
        return errors, delta

    if len(target_set) >= 2:
        labels = [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in target_lines[:2]]
        if len(labels) >= 1 and labels[0].lower() not in rc_l:
            errors.append(f"Rule Comparison must expressly include {labels[0]}")
            delta -= 6
        if len(labels) >= 2 and labels[1].lower() not in rc_l:
            errors.append(f"Rule Comparison must expressly include {labels[1]}")
            delta -= 6
        if "whereas" not in s3_l:
            errors.append("Rule Comparison sentence 3 must contain 'whereas'")
            delta -= 6
        return errors, delta

    return errors, delta


def validate_rule_v2(
    sections: Dict[str, str],
    query_type: str,
    target_lines: List[str],
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    rule_text = (sections.get("rule", "") or "").strip()
    rule_l = rule_text.lower()

    if not rule_text:
        return ["Rule is empty"], -12

    real_lines = [x for x in target_lines if x != "unknown"]
    if query_type == "comparison" and len(real_lines) >= 2:
        return errors, delta

    if len(rule_text.split()) < 18:
        errors.append("Rule is too short")
        delta -= 6

    if set(target_lines) == {"oversight"}:
        required_phrases = [
            "utter failure to attempt to assure",
            "failure to act in good faith",
            "good faith effort to implement an oversight system",
            "duty of loyalty",
        ]
        for phrase in required_phrases:
            if phrase not in rule_l:
                errors.append(f"Missing core Rule phrase: {phrase}")
                delta -= 8

    return errors, delta


def validate_analysis(
    sections: Dict[str, str],
    query_type: str,
    target_lines: List[str],
    tree_result: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    analysis = (sections.get("analysis", "") or "").strip()
    analysis_l = analysis.lower()

    if not analysis:
        return ["Analysis is empty"], -12

    sentences = [s.strip() for s in analysis.split(".") if s.strip()]
    if len(sentences) != 3:
        errors.append("Analysis must be exactly three sentences")
        delta -= 10
        return errors, delta

    if not sentences[0].lower().startswith("this matters because"):
        errors.append("Analysis sentence 1 must begin with 'This matters because'")
        delta -= 6
    if not sentences[1].lower().startswith("the significance is that"):
        errors.append("Analysis sentence 2 must begin with 'The significance is that'")
        delta -= 6
    if not sentences[2].lower().startswith("as a result"):
        errors.append("Analysis sentence 3 must begin with 'As a result'")
        delta -= 6

    target_set = set(x for x in target_lines if x != "unknown")

    if target_set == {"oversight"}:
        oversight_markers = [
            "utter failure",
            "good faith",
            "monitor",
            "oversight system",
            "reporting system",
            "duty of loyalty",
        ]
        oversight_hits = sum(1 for marker in oversight_markers if marker in analysis_l)
        if query_type == "comparison":
            if oversight_hits < 1:
                errors.append("Analysis must reflect doctrinal anchor fragments")
                delta -= 6
        else:
            if oversight_hits < 1:
                errors.append("Analysis should integrate at least one doctrinal anchor phrase")
                delta -= 4

    return errors, delta


def validate_quote_grounding(
    sections: Dict[str, str],
    query_type: str,
    role_quote_map: Dict[str, Dict[str, str]],
    target_lines: Optional[List[str]] = None,
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    target_lines = target_lines or []
    role_quote_map = role_quote_map or {}

    if not role_quote_map:
        return errors, delta

    rule_text = (sections.get("rule", "") or "").lower()
    rule_comparison_text = (sections.get("rule_comparison", "") or "").lower()
    analysis_text = (sections.get("analysis", "") or "").lower()

    fragments: Dict[str, Dict[str, str]] = {}
    for role, item in role_quote_map.items():
        fragment = normalize_quote_fragment(role, item.get("quote", ""))
        if fragment:
            fragments[role] = {"case": item.get("case", role), "fragment": fragment}

    if not fragments:
        return errors, delta

    oversight_mode = "oversight" in target_lines and len([x for x in target_lines if x != "unknown"]) <= 1
    if not oversight_mode:
        return errors, delta

    for role, item in fragments.items():
        fragment = item["fragment"]
        case_name = item["case"]

        if fragment_present(fragment, rule_text):
            delta += 4
        else:
            errors.append(f'Rule missing grounded fragment: {case_name} ({role}) -> "{fragment}"')
            delta -= 4

    if query_type == "comparison":
        for role, item in fragments.items():
            fragment = item["fragment"]
            case_name = item["case"]

            if fragment_present(fragment, rule_comparison_text):
                delta += 4
            else:
                errors.append(f'Rule Comparison missing grounded fragment: {case_name} ({role}) -> "{fragment}"')
                delta -= 4

    analysis_hits = 0
    for role, item in fragments.items():
        if fragment_present(item["fragment"], analysis_text):
            analysis_hits += 1

    if query_type == "comparison":
        if analysis_hits >= 1:
            delta += 6
        else:
            errors.append("Analysis must reflect doctrinal anchor fragments")
            delta -= 6
    else:
        if analysis_hits >= 1:
            delta += 3
        else:
            errors.append("Analysis must reflect at least one doctrinal anchor fragment")
            delta -= 3

    return errors, delta


def validate_ai_answer(
    ai_answer: str,
    query_plan: Dict[str, Any],
    role_quote_map: Dict[str, Dict[str, str]],
    tree_result: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[str], int]:
    text = (ai_answer or "").strip()
    if not text:
        return False, ["Empty answer"], 0

    query_type = query_plan.get("query_type", "")
    target_lines = query_plan.get("target_lines", [])

    sections = extract_sections(ai_answer, query_plan)

    errors: List[str] = []
    score = 100

    def apply_result(result: Tuple[List[str], int]) -> None:
        nonlocal score, errors
        section_errors, delta = result
        score += delta
        if delta < 0 and section_errors:
            errors.extend(section_errors)

    required_sections = ["short_answer", "analysis", "confidence"]
    multi_doctrine = query_plan.get("multi_doctrine", False)

    if query_type == "comparison" and multi_doctrine:
        labels = get_multi_doctrine_labels(query_plan)
        label_a = labels[0] if len(labels) >= 1 else "Doctrine A"
        label_b = labels[1] if len(labels) >= 2 else "Doctrine B"
        required_sections.extend(["key_distinction", label_a.lower(), label_b.lower(), "rule_comparison"])
    elif query_type == "comparison":
        required_sections.extend(["key_distinction", "rule", "rule_comparison"])
    else:
        required_sections.append("rule")

    section_name_map = {
        "short_answer": "Short Answer",
        "key_distinction": "Key Distinction",
        "rule": "Rule",
        "rule_comparison": "Rule Comparison",
        "analysis": "Analysis",
        "confidence": "Confidence",
    }

    if query_type == "comparison" and multi_doctrine:
        labels = get_multi_doctrine_labels(query_plan)
        if len(labels) >= 1:
            section_name_map[labels[0].lower()] = labels[0]
        if len(labels) >= 2:
            section_name_map[labels[1].lower()] = labels[1]

    for key in required_sections:
        if not sections.get(key, "").strip():
            section_label = section_name_map.get(key, key.title())
            errors.append(f"Missing section: {section_label}")
            score -= 20

    confidence = sections.get("confidence", "").strip()
    if confidence and confidence not in {"High", "Medium", "Low"}:
        errors.append("Confidence must be exactly one word: High, Medium, or Low")
        score -= 8

    apply_result(validate_short_answer(sections, query_type=query_type, target_lines=target_lines))
    apply_result(validate_key_distinction(sections, query_type=query_type, target_lines=target_lines))

    if query_type == "comparison":
        apply_result(
            validate_rule_comparison_v2(
                sections,
                query_type=query_type,
                tree_result=tree_result,
                target_lines=target_lines,
            )
        )
    else:
        apply_result(
            validate_rule_v2(
                sections,
                query_type=query_type,
                target_lines=target_lines,
            )
        )

    apply_result(
        validate_analysis(
            sections,
            query_type=query_type,
            target_lines=target_lines,
            tree_result=tree_result,
        )
    )

    apply_result(
        validate_quote_grounding(
            sections,
            query_type=query_type,
            role_quote_map=role_quote_map,
            target_lines=target_lines,
        )
    )

    text_l = text.lower()
    if "quoted authority" in text_l:
        errors.append("Model output included Quoted Authority section")
        score -= 10
    if "supporting cases" in text_l:
        errors.append("Model output included Supporting Cases section")
        score -= 6

    deduped_errors: List[str] = []
    seen = set()
    for err in errors:
        if err not in seen:
            deduped_errors.append(err)
            seen.add(err)

    score = max(0, min(100, score))
    return len(deduped_errors) == 0, deduped_errors, score

# ============================================================
# DEBUG / DISPLAY
# ============================================================


def print_query_plan(
    query_plan: Dict[str, Any],
    cases: List[Dict[str, Any]],
    doctrine_buckets: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    doctrine_leaders: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> None:
    print("\nQUERY PLAN:")
    print(f"QUERY TYPE: {query_plan.get('query_type', 'unknown')}")
    print(f"TARGET LINES: {query_plan.get('target_lines', [])}")
    print(f"NAMED SOURCES: {query_plan.get('named_sources', [])}")
    print(f"MULTI-DOCTRINE: {query_plan.get('multi_doctrine', False)}")

    print("\nSHORTLISTED CASES:")
    for case in cases[:8]:
        source = case.get("source", "")
        star = " *" if source in query_plan.get("named_sources", []) else ""
        doctrine_line = infer_doctrine_line_from_source(source)
        print(f"- {source} (case_score={case.get('case_score', 0):.4f}, role={case.get('role', 'related_case')}, line={doctrine_line}){star}")

    if doctrine_buckets:
        print("\nDOCTRINE BUCKETS:")
        for doctrine_line, bucket in doctrine_buckets.items():
            label = DOCTRINE_LABELS.get(doctrine_line, doctrine_line.replace("_", " ").title())
            print(f"- {label}:")
            for case in bucket[:5]:
                print(f"    {case.get('source', '')} ({case.get('role', 'related_case')}, {case.get('case_score', 0):.4f})")

    if doctrine_leaders:
        print("\nDOCTRINE LEADERS:")
        for doctrine_line, leaders in doctrine_leaders.items():
            label = DOCTRINE_LABELS.get(doctrine_line, doctrine_line.replace("_", " ").title())
            print(f"- {label}:")
            for case in leaders:
                print(f"    {case.get('source', '')} (role={case.get('role', 'related_case')}, case_score={case.get('case_score', 0):.4f})")

# ============================================================
# MAIN
# ============================================================


def main() -> None:
    print("Hello! Ask a Delaware law question.\n")

    question = input("Ask a Delaware law question: ").strip()
    if not question:
        print("No question entered.")
        return

    query_plan = build_query_plan_cached(question)

    oversight_debug = "oversight" in query_plan.get("target_lines", [])

    budget = get_retrieval_budget(query_plan)
    

    top_chunks = retrieve(question, k=budget["k"], max_per_source=budget["max_per_source"])
    if not top_chunks:
        print("No chunks retrieved.")
        return

    case_quotes = extract_case_quotes(top_chunks, max_quotes_per_case=5)
    cases = aggregate_by_case(top_chunks)

    doctrine_buckets = bucket_cases_by_doctrine_line(cases)
    doctrine_leaders = select_doctrine_leaders(doctrine_buckets)

    print_query_plan(query_plan, cases, doctrine_buckets=doctrine_buckets, doctrine_leaders=doctrine_leaders)

    role_quote_map = build_role_based_quote_map(cases, case_quotes, debug=oversight_debug)

    tree_result = None
    tree_summary = ""

    if "oversight" in query_plan.get("target_lines", []) and not query_plan.get("multi_doctrine"):
        try:
            facts = infer_caremark_facts_from_question(question)
            tree_result = evaluate_caremark_tree(facts)
            tree_summary = build_caremark_tree_summary(tree_result)
            print("DEBUG CAREMARK TREE:")
            print(tree_summary)
        except Exception as e:
            print("TREE ERROR:", e)
            tree_result = None
            tree_summary = ""

    if query_plan.get("multi_doctrine"):
        context = build_multi_doctrine_context(doctrine_leaders, query_plan.get("target_lines", []))
        timeline = ""
    else:
        context, timeline = build_context_from_cases(cases, query_plan.get("target_lines", []))

    answer_template = get_answer_template(query_plan)
    supporting_cases_block = build_supporting_cases_block(cases, max_supporting=2)

    required_quote_fragments_block = []
    for role, item in role_quote_map.items():
        fragment = normalize_quote_fragment(role, item.get("quote", ""))
        case = item.get("case", "Unknown")
        if fragment:
            required_quote_fragments_block.append(f'- {case}: "{fragment}"')
    if not required_quote_fragments_block and "oversight" in query_plan.get("target_lines", []):
        required_quote_fragments_block.append('- Marchand: "good faith effort to implement an oversight system"')
    required_quote_fragments_block = "\n".join(required_quote_fragments_block)

    print("DEBUG REQUIRED QUOTE FRAGMENTS:")
    print(required_quote_fragments_block)

    locked_short_answer = ""
    locked_key_distinction = ""
    locked_rule = ""
    locked_rule_a = ""
    locked_rule_b = ""
    locked_rule_comparison = ""
    locked_analysis = ""

    label_a = "Doctrine A"
    label_b = "Doctrine B"

    if query_plan.get("multi_doctrine"):
        target_lines = query_plan.get("target_lines", [])
        labels = get_multi_doctrine_labels(query_plan)
        label_a = labels[0] if len(labels) >= 1 else "Doctrine A"
        label_b = labels[1] if len(labels) >= 2 else "Doctrine B"

        locked_short_answer = synthesize_multi_doctrine_short_answer(target_lines)
        locked_key_distinction = synthesize_multi_doctrine_key_distinction(target_lines)

        line_a = target_lines[0] if len(target_lines) >= 1 else "unknown"
        line_b = target_lines[1] if len(target_lines) >= 2 else "unknown"

        doctrine_a_cases = doctrine_leaders.get(line_a, [])
        doctrine_b_cases = doctrine_leaders.get(line_b, [])

        locked_rule_a = synthesize_doctrine_section(line_a, doctrine_a_cases, case_quotes)
        locked_rule_b = synthesize_doctrine_section(line_b, doctrine_b_cases, case_quotes)

        locked_rule_comparison = polish_synthesized_rule_comparison(
            enforce_three_sentences(
                compress_rule_comparison(
                    synthesize_multi_doctrine_rule_comparison(target_lines)
                )
            )
        )

        locked_analysis = hard_lock_analysis(synthesize_multi_doctrine_analysis(target_lines))

        user_content = f"""
QUESTION:
{question}

CONTEXT:
{context}

LOCKED SHORT ANSWER:
{locked_short_answer}

LOCKED KEY DISTINCTION:
{locked_key_distinction}

LOCKED {label_a.upper()}:
{locked_rule_a}

LOCKED {label_b.upper()}:
{locked_rule_b}

LOCKED RULE COMPARISON:
{locked_rule_comparison}

LOCKED ANALYSIS:
{locked_analysis}

ANSWER FORMAT:
{answer_template}

SUPPORTING CASES:
{supporting_cases_block}
""".strip()

    else:
        short_answer_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        locked_short_answer = synthesize_short_answer(query_plan.get("target_lines", []), tree_result=short_answer_tree_result)

        key_distinction_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        locked_key_distinction = enforce_one_sentence(
            synthesize_key_distinction(
                role_quote_map=role_quote_map,
                target_lines=query_plan.get("target_lines", []),
                tree_result=key_distinction_tree_result,
            )
        )

        locked_rule = hard_lock_rule(
            polish_synthesized_rule(
                compress_rule(
                    synthesize_rule_from_quotes(role_quote_map=role_quote_map, target_lines=query_plan.get("target_lines", []))
                )
            )
        )

        comparison_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        locked_rule_comparison = polish_synthesized_rule_comparison(
            enforce_three_sentences(
                compress_rule_comparison(
                    synthesize_rule_comparison(role_quote_map=role_quote_map, tree_result=comparison_tree_result)
                )
            )
        )

        analysis_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        if analysis_tree_result and "oversight" in query_plan.get("target_lines", []):
            locked_analysis = synthesize_analysis_from_tree_and_quotes(
                tree_result=analysis_tree_result,
                role_quote_map=role_quote_map,
                target_lines=query_plan.get("target_lines", []),
            )
        else:
            locked_analysis = synthesize_analysis_from_quotes(
                role_quote_map=role_quote_map,
                target_lines=query_plan.get("target_lines", []),
            )
        target_lines = query_plan.get("target_lines", [])

        if (
    "oversight" in target_lines
    and analysis_tree_result
    and "monitor" in analysis_tree_result.get("primary_failure", "")
):
         locked_analysis = (
        "This matters because oversight liability arises where directors ignore red flags in mission-critical areas. "
        "The significance is that a board’s failure to respond to red flags in a mission critical context supports an inference of bad faith. "
        "As a result, ignoring red flags tied to the company’s core mission may give rise to Caremark liability."
    )

        analysis_sentences = re.findall(r"[^.!?]+[.!?]", locked_analysis)
        analysis_sentences = [s.strip() for s in analysis_sentences if s.strip()]
        if len(analysis_sentences) >= 3:
            analysis_sentences = enforce_analysis_structure(analysis_sentences[:3])
            locked_analysis = " ".join(analysis_sentences)

        locked_analysis = hard_lock_analysis(polish_synthesized_analysis(locked_analysis))

        user_content = f"""
QUESTION:
{question}

CONTEXT:
{context}

DOCTRINE TIMELINE:
{timeline}

DECISION TREE (REFERENCE ONLY):
{tree_summary}

LOCKED SHORT ANSWER:
{locked_short_answer}

LOCKED KEY DISTINCTION:
{locked_key_distinction}

LOCKED RULE:
{locked_rule}

LOCKED RULE COMPARISON:
{locked_rule_comparison}

LOCKED ANALYSIS:
{locked_analysis}

ANSWER FORMAT:
{answer_template}

SUPPORTING CASES:
{supporting_cases_block}
""".strip()

    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )

    ai_answer = response.output_text.strip()

    if query_plan.get("multi_doctrine"):
        ai_answer = replace_section(ai_answer, "Short Answer", locked_short_answer)
        ai_answer = replace_section(ai_answer, "Key Distinction", locked_key_distinction)
        ai_answer = replace_section(ai_answer, label_a, locked_rule_a)
        ai_answer = replace_section(ai_answer, label_b, locked_rule_b)
        ai_answer = replace_section(ai_answer, "Rule Comparison", locked_rule_comparison)
        ai_answer = replace_section(ai_answer, "Analysis", locked_analysis)
    else:
        ai_answer = replace_section(ai_answer, "Short Answer", locked_short_answer)
        ai_answer = replace_section(ai_answer, "Key Distinction", locked_key_distinction)
        ai_answer = replace_section(ai_answer, "Rule", locked_rule)
        ai_answer = replace_section(ai_answer, "Analysis", locked_analysis)

    if query_plan.get("query_type") != "comparison":
        ai_answer = remove_section(ai_answer, "Rule Comparison")

    validation_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
    is_valid, validation_errors, validation_score = validate_ai_answer(
        ai_answer,
        query_plan,
        role_quote_map,
        tree_result=validation_tree_result,
    )

    print(f"VALIDATION SCORE: {validation_score}/100")

    if validation_errors:
        print("VALIDATION ERRORS:")
        for err in validation_errors:
            print("-", err)

    print("\n" + "=" * 60)
    print("AI ANSWER:")
    print("=" * 60 + "\n")
    print(ai_answer)


if __name__ == "__main__":
    main()