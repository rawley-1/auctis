from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import difflib
import re
from synthesis import synthesize_memo_answer

from openai import OpenAI


from doctrine_config import (
    DOCTRINE_LABELS,
    FALLBACK_QUOTES,
    ROLE_PRIORITY,
)

from planning import (
    get_case_role,
    infer_doctrine_line_from_source,
    build_query_plan_cached,
)

from quotes import (
    extract_case_quotes,
    normalize_quote_fragment,
    build_role_based_quote_map,
    gatekeep_case_quotes,
)

from synthesis import (
    synthesize_structured_short_answer,
    synthesize_short_answer,
    synthesize_key_distinction,
    synthesize_rule_from_quotes,
    synthesize_multi_doctrine_rule_comparison,
    synthesize_multi_doctrine_analysis,
    synthesize_analysis_from_quotes,
    synthesize_analysis_from_tree_and_quotes,
    synthesize_structured_doctrine_section,
    synthesize_structured_single_doctrine_analysis,
    synthesize_memo_answer,
    synthesize_opinion_answer,
)

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

STOPWORDS = {
    "and", "or", "the", "is", "are", "what", "how", "why",
    "compare", "with", "vs", "versus", "of", "in", "to",
}

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
# OUTPUT
# ============================================================


def get_multi_doctrine_labels(query_plan: Dict[str, Any]) -> List[str]:
    lines = [line for line in query_plan.get("target_lines", []) if line != "unknown"]
    return [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in lines[:2]]


def get_answer_template(query_plan):
    query_type = query_plan.get("query_type")
    target_lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]
    multi = query_plan.get("multi_doctrine", False)
    target_set = set(target_lines)

    # -------------------------
    # Multi-doctrine comparison templates
    # -------------------------
    if query_type == "comparison" and multi:
        if {"controller_transactions", "stockholder_vote_cleansing"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Controller Transactions:
<one paragraph on controller conflict and MFW cleansing>

Stockholder Vote Cleansing:
<one paragraph on fully informed and uncoerced stockholder approval>

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
<one paragraph on controller conflict and MFW protections>

Sale of Control:
<one paragraph on best value reasonably available and change of control>

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
<one paragraph on oversight systems, good faith, and monitoring>

Takeover Defense:
<one paragraph on threat perception, coercive/preclusive limits, and reasonableness>

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
<one paragraph on oversight systems, good faith, and monitoring>

Sale of Control:
<one paragraph on best value reasonably available and change of control>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""

        if {"demand_futility", "oversight"} <= target_set:
            return """Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

Demand Futility:
<one paragraph on board capacity to consider demand>

Oversight:
<one paragraph on oversight systems, good faith, and monitoring>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""

        # generic multi-doctrine fallback
        labels = [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in target_lines[:2]]
        label_a = labels[0] if len(labels) >= 1 else "Doctrine A"
        label_b = labels[1] if len(labels) >= 2 else "Doctrine B"

        return f"""Short Answer:
<one sentence>

Key Distinction:
<one sentence using whereas>

{label_a}:
<one paragraph>

{label_b}:
<one paragraph>

Rule Comparison:
<three sentences>

Analysis:
<three sentences>

Confidence:
High
"""

    # -------------------------
    # Single-doctrine templates
    # -------------------------
    if target_set == {"oversight"}:
        return """Short Answer:
<one sentence on implementation failure, monitoring failure, or lower oversight risk>

Rule:
<one paragraph using utter failure / failure to act in good faith / good faith effort to implement an oversight system>

Analysis:
<three sentences on implementation vs monitoring vs red flags / mission-critical risk>

Confidence:
High
"""

    if target_set == {"takeover_defense"}:
        return """Short Answer:
<one sentence on enhanced scrutiny for defensive measures>

Rule:
<one paragraph using threat to corporate policy and effectiveness, coercive/preclusive limits, and range of reasonableness>

Analysis:
<three sentences on threat perception, proportionality, and enhanced scrutiny>

Confidence:
High
"""

    if target_set == {"controller_transactions"}:
        return """Short Answer:
<one sentence on controller conflict and MFW cleansing>

Rule:
<one paragraph using entire fairness, special committee, and majority-of-the-minority approval>

Analysis:
<three sentences on controller conflict, cleansing protections, and standard of review>

Confidence:
High
"""

    if target_set == {"stockholder_vote_cleansing"}:
        return """Short Answer:
<one sentence on Corwin cleansing>

Rule:
<one paragraph using fully informed and uncoerced vote of disinterested stockholders>

Analysis:
<three sentences on stockholder approval, cleansing effect, and business judgment review>

Confidence:
High
"""

    if target_set == {"sale_of_control"}:
        return """Short Answer:
<one sentence on Revlon duties>

Rule:
<one paragraph using best value reasonably available and change-of-control trigger>

Analysis:
<three sentences on sale mode, triggering event, and value maximization>

Confidence:
High
"""

    if target_set == {"demand_futility"}:
        return """Short Answer:
<one sentence on whether demand is excused>

Rule:
<one paragraph using reasonable doubt, board impartiality, and director-by-director review>

Analysis:
<three sentences on board capacity, demand excusal, and modern unified framework>

Confidence:
High
"""

    if target_set == {"disclosure_loyalty"}:
        return """Short Answer:
<one sentence on truthful stockholder communications>

Rule:
<one paragraph using truthfully, completely, and materially misleading disclosure>

Analysis:
<three sentences on truthful disclosure, loyalty implications, and false information to stockholders>

Confidence:
High
"""

    # -------------------------
    # Default single-doctrine fallback
    # -------------------------
    return """Short Answer:
<one sentence>

Rule:
<one paragraph>

Analysis:
<three sentences>

Confidence:
High
"""

# ============================================================
# TEXT HELPERS
# ============================================================

LEGAL_TERMS = [
    "caremark",
    "marchand",
    "stone",
    "unocal",
    "revlon",
    "mfw",
    "corwin",
    "qvc",
    "unitrin",
    "airgas",
    "aronson",
    "rales",
    "zuckerberg",
    "malone",
    "tesla",
    "oversight",
    "controller",
    "transactions",
    "stockholder",
    "cleansing",
    "takeover",
    "defense",
    "sale",
    "control",
    "demand",
    "futility",
    "fiduciary",
    "duty",
    "board",
    "director",
    "liability",
    "doctrine",
    "standard",
]
import difflib
import re

STOPWORDS = {
    "and", "or", "the", "is", "are", "what", "how", "why",
    "compare", "with", "vs", "versus", "of", "in", "to",
}

LEGAL_TERMS = [
    "caremark",
    "marchand",
    "stone",
    "unocal",
    "revlon",
    "mfw",
    "corwin",
    "qvc",
    "unitrin",
    "airgas",
    "aronson",
    "rales",
    "zuckerberg",
    "malone",
    "tesla",
    "oversight",
    "controller",
    "transactions",
    "stockholder",
    "cleansing",
    "takeover",
    "defense",
    "sale",
    "control",
    "demand",
    "futility",
    "fiduciary",
    "duty",
    "board",
    "director",
    "liability",
    "doctrine",
    "standard",
]


def autocorrect_legal_query(question: str) -> tuple[str, list[tuple[str, str]]]:
    if not question:
        return question, []

    tokens = re.findall(r"\w+|\W+", question)
    corrections: list[tuple[str, str]] = []
    corrected_tokens: list[str] = []

    for token in tokens:
        if not re.match(r"^\w+$", token):
            corrected_tokens.append(token)
            continue

        lower = token.lower()

        # Leave very short tokens alone
        if len(lower) <= 2:
            corrected_tokens.append(token)
            continue

        # Don't autocorrect common connector words
        if lower in STOPWORDS:
            corrected_tokens.append(token)
            continue

        # Exact match: keep as-is
        if lower in LEGAL_TERMS:
            corrected_tokens.append(token)
            continue

        # More forgiving for short legal names like Crmk -> Caremark
        cutoff = 0.60 if len(lower) <= 5 else 0.72
        match = difflib.get_close_matches(lower, LEGAL_TERMS, n=1, cutoff=cutoff)

        if match:
            corrected = match[0]

            if token.isupper():
                corrected_token = corrected.upper()
            elif token[0].isupper():
                corrected_token = corrected.capitalize()
            else:
                corrected_token = corrected

            corrections.append((token, corrected_token))
            corrected_tokens.append(corrected_token)
        else:
            corrected_tokens.append(token)

    corrected_question = "".join(corrected_tokens)
    return corrected_question, corrections

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

def build_sections_from_answer(ai_answer: str) -> dict:
    text = (ai_answer or "").strip()
    sections = {}

    patterns = {
        "Short Answer": r"Short Answer:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Key Distinction": r"Key Distinction:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Controller Transactions": r"Controller Transactions:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Stockholder Vote Cleansing": r"Stockholder Vote Cleansing:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Oversight": r"Oversight:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Takeover Defense": r"Takeover Defense:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Sale of Control": r"Sale of Control:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Demand Futility": r"Demand Futility:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Rule Comparison": r"Rule Comparison:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Rule": r"Rule:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Analysis": r"Analysis:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
        "Confidence": r"Confidence:\s*(.*?)(?=\n[A-Z][A-Za-z ]+:\s*|\Z)",
    }

    for name, pattern in patterns.items():
        m = re.search(pattern, text, flags=re.DOTALL)
        if m:
            sections[name] = m.group(1).strip()

    return sections

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
        header = rf"(?mi)^\s*{re.escape(name)}\s*:\s*"
        if following:
            next_headers = "|".join(
                rf"^\s*{re.escape(x)}\s*:" for x in following
            )
            pattern = header + rf"(.*?)(?=(?:{next_headers})|\Z)"
        else:
            pattern = header + r"(.*)\Z"

        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
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
            sections[labels[0].lower()] = section_body(
                labels[0],
                [labels[1]] + ["Rule Comparison", "Analysis", "Confidence"] if len(labels) >= 2 else ["Rule Comparison", "Analysis", "Confidence"],
            )
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

def assess_retrieval_confidence(
    top_chunks: List[Dict[str, Any]],
    query_plan: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    target_lines = query_plan.get("target_lines", [])
    recognized_doctrine = bool(target_lines) and "unknown" not in target_lines

    if not top_chunks:
        return "low", {
            "top_scores": [],
            "top_doctrines": [],
            "doctrine_counts": {},
            "recognized_doctrine": recognized_doctrine,
            "top_score": 0.0,
            "score_gap": 0.0,
        }

    inspected = top_chunks[:5]

    top_scores = [float(chunk.get("score", 0.0)) for chunk in inspected]
    top_doctrines = [chunk.get("doctrine_line", "unknown") for chunk in inspected]

    doctrine_counts: Dict[str, int] = {}
    for doctrine in top_doctrines:
        doctrine_counts[doctrine] = doctrine_counts.get(doctrine, 0) + 1

    sorted_scores = sorted(top_scores, reverse=True)
    top_score = sorted_scores[0] if sorted_scores else 0.0
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
    score_gap = top_score - second_score

    if doctrine_counts:
        dominant_doctrine = sorted(
        doctrine_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )[0][0]
    else:
        dominant_doctrine = "unknown"
    dominant_count = doctrine_counts.get(dominant_doctrine, 0)
    doctrine_agreement_ratio = dominant_count / max(len(top_doctrines), 1)

    # Confidence logic:
    # 1. If doctrine isn't recognized, confidence should be low.
    # 2. If top results mostly agree on one doctrine, confidence rises.
    # 3. If scores are close and doctrines are mixed, confidence drops.
    if not recognized_doctrine:
        status = "low"
    elif top_score < 0.60:
        status = "low"
    elif doctrine_agreement_ratio >= 0.80 and top_score >= 0.80:
        status = "high"
    elif doctrine_agreement_ratio >= 0.60 and top_score >= 0.68:
        status = "medium"
    elif score_gap < 0.03 and doctrine_agreement_ratio < 0.60:
        status = "low"
    else:
        status = "medium"

    diagnostics = {
        "top_scores": [round(s, 4) for s in top_scores],
        "top_doctrines": top_doctrines,
        "doctrine_counts": doctrine_counts,
        "dominant_doctrine": dominant_doctrine,
        "doctrine_agreement_ratio": round(doctrine_agreement_ratio, 4),
        "recognized_doctrine": recognized_doctrine,
        "top_score": round(top_score, 4),
        "score_gap": round(score_gap, 4),
    }

    return status, diagnostics

def is_nonsense_query(query, retrieved_chunks):
    if not query or len(query.strip()) < 5:
        return True

    # if nothing meaningful retrieved
    max_score = max([c.get("score", 0) for c in retrieved_chunks], default=0)

    if max_score < 0.75:
     return True

    return False

def run_query(question: str):
    question = (question or "").strip()

    corrected_question, corrections = autocorrect_legal_query(question)
    question_for_engine = corrected_question

    if not question:
        return {
            "answer": "",
            "validation_score": 0,
            "validation_errors": ["Empty question"],
            "query_plan": {},
            "cases": [],
        }

    query_plan = build_query_plan_cached(question_for_engine)

    budget = get_retrieval_budget(query_plan)
    top_chunks = retrieve(question_for_engine, k=budget["k"], max_per_source=budget["max_per_source"])
    recognized_doctrine = any(
        line != "unknown"
        for line in query_plan.get("target_lines", [])
    )

    if not recognized_doctrine and is_nonsense_query(question_for_engine, top_chunks):
        return {
            "query_plan": query_plan,
            "cases": [],
            "answer": "",
            "sections": {},
            "validation_score": 0,
            "validation_errors": ["Query did not map to a recognized Delaware doctrine."],
            "retrieval_confidence": "low",
            "retrieval_diagnostics": {
                "reason": "No recognized Delaware doctrine detected."
            },
            "corrected_question": "",
            "corrections": [],
            "legal_corrections": [],
            "rejected": True,
            "rejection_message": "Auctis could not identify a Delaware corporate law doctrine in that question.",
        }
    
    if not top_chunks and not recognized_doctrine:
        return {
        "query_plan": query_plan,
        "cases": [],
        "answer": "",
        "validation_score": 0,
        "validation_errors": ["No doctrinal match"],
        "rejected": True,
    }

    case_quotes = extract_case_quotes(
    top_chunks,
    fallback_quotes=FALLBACK_QUOTES,
    max_quotes_per_case=5,
)

    case_quotes = extract_case_quotes(
        top_chunks,
        fallback_quotes=FALLBACK_QUOTES,
        max_quotes_per_case=5,
    )

    case_quotes = gatekeep_case_quotes(case_quotes)

    cases = aggregate_by_case(top_chunks)
    doctrine_buckets = bucket_cases_by_doctrine_line(cases)
    doctrine_leaders = select_doctrine_leaders(doctrine_buckets)

    role_quote_map = build_role_based_quote_map(
        cases,
        case_quotes,
        get_case_role=get_case_role,
        get_case_display_name=get_case_display_name,
    )

    tree_result = None
    tree_summary = ""

    if "oversight" in query_plan.get("target_lines", []) and not query_plan.get("multi_doctrine"):
        try:
            facts = infer_caremark_facts_from_question(question_for_engine)
            tree_result = evaluate_caremark_tree(facts)
            tree_summary = build_caremark_tree_summary(tree_result)
        except Exception:
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

        locked_short_answer = synthesize_structured_short_answer(target_lines)
        locked_key_distinction = synthesize_key_distinction(target_lines)

        line_a = target_lines[0] if len(target_lines) >= 1 else "unknown"
        line_b = target_lines[1] if len(target_lines) >= 2 else "unknown"

        locked_rule_a = synthesize_structured_doctrine_section(line_a)
        locked_rule_b = synthesize_structured_doctrine_section(line_b)

        locked_rule_comparison = polish_synthesized_rule_comparison(
            enforce_three_sentences(
                compress_rule_comparison(
                    synthesize_multi_doctrine_rule_comparison(target_lines)
                )
            )
        )

        locked_analysis = hard_lock_analysis(
            synthesize_multi_doctrine_analysis(target_lines)
        )

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
        locked_short_answer = synthesize_short_answer(
            query_plan.get("target_lines", []),
            tree_result=short_answer_tree_result,
        )

        target_lines = query_plan.get("target_lines", [])
        locked_key_distinction = synthesize_key_distinction(target_lines)

        line = target_lines[0] if target_lines else "unknown"
        locked_rule = hard_lock_rule(
            polish_synthesized_rule(
                compress_rule(
                    synthesize_structured_doctrine_section(line)
                )
            )
        )

        locked_rule_comparison = polish_synthesized_rule_comparison(
            enforce_three_sentences(
                compress_rule_comparison(
                    synthesize_multi_doctrine_rule_comparison(
                        query_plan.get("target_lines", [])
                    )
                )
            )
        )

        analysis_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        target_lines = query_plan.get("target_lines", [])

        if analysis_tree_result and "oversight" in target_lines:
            locked_analysis = synthesize_analysis_from_tree_and_quotes(
                tree_result=analysis_tree_result,
                role_quote_map=role_quote_map,
                target_lines=target_lines,
            )
        else:
            locked_analysis = synthesize_structured_single_doctrine_analysis(target_lines)

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
        ai_answer = replace_section(ai_answer, "Rule", locked_rule)
        ai_answer = replace_section(ai_answer, "Analysis", locked_analysis)

    if query_plan.get("query_type") != "comparison":
        ai_answer = remove_section(ai_answer, "Rule Comparison")
        ai_answer = remove_section(ai_answer, "Key Distinction")

    validation_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
    is_valid, validation_errors, validation_score = validate_ai_answer(
        ai_answer,
        query_plan,
        role_quote_map,
        tree_result=validation_tree_result,
    )
    sections_for_display = extract_sections(ai_answer, query_plan)

    memo_answer = synthesize_memo_answer(sections_for_display, query_plan)

    opinion_answer = synthesize_opinion_answer(
    role_quote_map=role_quote_map,
    target_lines=query_plan.get("target_lines", []),
    question=question,
)

        # --- Retrieval confidence ---
    top_scores = [float(c.get("score", 0.0)) for c in cases[:3]]

    if not top_scores:
        retrieval_confidence = "low"
    elif len(top_scores) >= 2 and (top_scores[0] - top_scores[1]) < 0.05:
        retrieval_confidence = "medium"
    elif top_scores[0] > 0.80:
        retrieval_confidence = "high"
    elif top_scores[0] > 0.60:
        retrieval_confidence = "medium"
    else:
        retrieval_confidence = "low"

    retrieval_diagnostics = {
        "top_scores": top_scores,
        "top_case": cases[0].get("source") if cases else None,
        "num_cases": len(cases),
        "target_lines": query_plan.get("target_lines", []),
    }

    retrieval_confidence, retrieval_diagnostics = assess_retrieval_confidence(
        top_chunks,
        query_plan,
    )
    sections = build_sections_from_answer(ai_answer)

    return {
        "query_plan": query_plan,
        "cases": cases,
        "doctrine_buckets": doctrine_buckets,
        "doctrine_leaders": doctrine_leaders,
        "answer": ai_answer,
        "memo_answer": memo_answer,
        "opinion_answer": opinion_answer,
        "sections": sections,
        "validation_score": validation_score,
        "validation_errors": validation_errors,
        "retrieval_confidence": retrieval_confidence,
        "retrieval_diagnostics": retrieval_diagnostics,
        "corrected_question": corrected_question,
        "corrections": corrections,
        "legal_corrections": [
            (old, new)
            for old, new in corrections
            if new.lower() in LEGAL_TERMS and old.lower() not in STOPWORDS
        ],
    }

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

    case_quotes = extract_case_quotes(
    top_chunks,
    fallback_quotes=FALLBACK_QUOTES,
    max_quotes_per_case=5,
)
    cases = aggregate_by_case(top_chunks)

    doctrine_buckets = bucket_cases_by_doctrine_line(cases)
    doctrine_leaders = select_doctrine_leaders(doctrine_buckets)

    print_query_plan(query_plan, cases, doctrine_buckets=doctrine_buckets, doctrine_leaders=doctrine_leaders)

    role_quote_map = build_role_based_quote_map(
    cases,
    case_quotes,
    get_case_role=get_case_role,
    get_case_display_name=get_case_display_name,
)

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

        locked_short_answer = synthesize_structured_short_answer(target_lines)
        locked_key_distinction = synthesize_key_distinction(target_lines)

        line_a = target_lines[0] if len(target_lines) >= 1 else "unknown"
        line_b = target_lines[1] if len(target_lines) >= 2 else "unknown"

        locked_rule_a = synthesize_structured_doctrine_section(line_a)
        locked_rule_b = synthesize_structured_doctrine_section(line_b)

        locked_rule_comparison = polish_synthesized_rule_comparison(
    enforce_three_sentences(
        compress_rule_comparison(
            synthesize_multi_doctrine_rule_comparison(target_lines)
        )
    )
)
        locked_analysis = hard_lock_analysis(
            synthesize_multi_doctrine_analysis(target_lines)
)


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
        target_lines = query_plan.get("target_lines", [])
        locked_key_distinction = synthesize_key_distinction(target_lines)

        target_lines = query_plan.get("target_lines", [])
        line = target_lines[0] if target_lines else "unknown"

        locked_rule = hard_lock_rule(
        polish_synthesized_rule(
            compress_rule(
                synthesize_structured_doctrine_section(line)
        )
    )
)
        comparison_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        
        locked_rule_comparison = polish_synthesized_rule_comparison(    
            enforce_three_sentences(
                compress_rule_comparison(
                    synthesize_multi_doctrine_rule_comparison(
                        query_plan.get("target_lines", [])
            )
        )
    )
)

        analysis_tree_result = None if query_plan.get("query_type") == "comparison" else tree_result
        target_lines = query_plan.get("target_lines", [])

        if analysis_tree_result and "oversight" in target_lines:
            locked_analysis = synthesize_analysis_from_tree_and_quotes(
        tree_result=analysis_tree_result,
        role_quote_map=role_quote_map,
        target_lines=target_lines,
    )
        else:
            locked_analysis = synthesize_structured_single_doctrine_analysis(target_lines)

            target_lines = query_plan.get("target_lines", [])

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
        ai_answer = replace_section(ai_answer, "Rule", locked_rule)
        ai_answer = replace_section(ai_answer, "Analysis", locked_analysis)

    if query_plan.get("query_type") != "comparison":
        ai_answer = remove_section(ai_answer, "Rule Comparison")

    if query_plan.get("query_type") != "comparison":
        ai_answer = remove_section(ai_answer, "Key Distinction")

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