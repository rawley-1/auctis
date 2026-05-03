from __future__ import annotations

import re
from typing import Any, Dict, List, Set


# ============================================================
# BASIC CLEANING
# ============================================================

def _normalize_quote_text(text: str) -> str:
    text = (text or "").replace("\n", " ").replace("\xad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" \"'")


def clean_doctrinal_quote(quote: str) -> str:
    q = _normalize_quote_text(quote)

    if not q:
        return ""

    # Normalize punctuation / spacing
    q = q.replace("“", '"').replace("”", '"').replace("’", "'")
    q = re.sub(r"\s+", " ", q).strip()

    # Remove citation / reporter / WL noise
    q = re.sub(r"\b\d+\s+A\.?2d\s+\d+\b", " ", q, flags=re.IGNORECASE)
    q = re.sub(r"\b\d+\s+A\.?3d\s+\d+\b", " ", q, flags=re.IGNORECASE)
    q = re.sub(r"\b\d{1,4}\s*WL\s*\d+\b", " ", q, flags=re.IGNORECASE)
    q = re.sub(r"\([^\)]*\d{3,}[^\)]*\)", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    if not q:
        return ""

    words = q.split()

    # Hard length gate: avoid fragments and stitched paragraphs
    if len(words) < 8 or len(words) > 48:
        return ""

    # Must start like a real sentence
    if not q[0].isupper():
        return ""

    q_l = q.lower()

    # Reject metadata, OCR, secondary-source, and litigation-noise fragments
    bad_markers = [
        "court:",
        "year:",
        "doctrine:",
        "authority:",
        "key topic:",
        "section:",
        "case:",
        "plaintiff",
        "defendant",
        "complaint",
        "motion to dismiss",
        "rescissory damages",
        "j.corp.law",
        "corp.law",
        "supr.",
        "blatt",
        "zelett",
        "strip-casting",
        "in this views",
        "found application",
        "ha-",
        "id.",
        "fordham",
        "law review",
        "laster",
        "article",
        "journal",
        "citation",
        "supra",
        "infra",
        "appellant",
        "appellee",
    ]

    if any(marker in q_l for marker in bad_markers):
        return ""

    # Reject overly stitched sentences
    if q.count(",") > 3:
        return ""

    if q.count(";") > 1:
        return ""

    # Reject ellipsis / obvious truncation
    if "..." in q or q.endswith(("...", "…")):
        return ""

    # Reject OCR-ish word salad
    weird_tokens = re.findall(r"\b[a-zA-Z]{1,2}[-']?[a-zA-Z]?\b", q)
    allowed_short = {
        "a", "an", "as", "at", "be", "by", "if", "in", "is",
        "it", "of", "on", "or", "to", "we", "do", "no"
    }
    weird_count = sum(1 for w in weird_tokens if w.lower() not in allowed_short)
    if weird_count >= 4:
        return ""

    # Must contain doctrinal signal language
    doctrinal_markers = [
        "must",
        "requires",
        "require",
        "standard",
        "review",
        "business judgment",
        "entire fairness",
        "fair dealing",
        "fair price",
        "fully informed",
        "uncoerced",
        "special committee",
        "majority of the minority",
        "controller",
        "controlling stockholder",
        "duty of loyalty",
        "good faith",
        "oversight system",
        "reporting system",
        "information system",
        "reasonable doubt",
        "best value reasonably available",
        "range of reasonableness",
        "coercive",
        "preclusive",
        "change of control",
        "proper purpose",
        "credible basis",
        "compelling justification",
        "inequitable",
        "stockholder franchise",
        "truthfully",
        "materially misleading",
    ]

    if not any(marker in q_l for marker in doctrinal_markers):
        return ""

    # Must read as a complete legal sentence
    complete_sentence_pattern = (
        r"^[A-Z][^.!?]*\b("
        r"must|requires|require|is|are|was|were|turns|applies|depends|"
        r"constitutes|invokes|restores|precludes|governs"
        r")\b[^.!?]*[.!?]?$"
    )

    if not re.match(complete_sentence_pattern, q):
        return ""

    # Add final punctuation only after structural checks
    if q[-1] not in ".!?":
        q += "."

    return q

# backwards compatibility with your previous function name
def clean_doctrinal_sentence(quote: str) -> str:
    return clean_doctrinal_quote(quote)


# ============================================================
# EXTRACTION
# ============================================================

def extract_case_quotes_from_text(text: str) -> List[str]:
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean: List[str] = []

    for sentence in sentences:
        cleaned = clean_doctrinal_quote(sentence)
        if cleaned:
            clean.append(cleaned)

    return clean


def extract_case_quotes(
    chunks: List[Dict[str, Any]],
    fallback_quotes: Dict[str, str],
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

    all_sources = {chunk.get("source", "") for chunk in chunks if chunk.get("source")}

    for source in all_sources:
        quotes = by_source.get(source, [])
        deduped: List[str] = []
        seen: Set[str] = set()

        for quote in quotes:
            cleaned = clean_doctrinal_quote(quote)
            if not cleaned:
                continue

            quote_key = re.sub(r"\s+", " ", cleaned.lower()).strip()
            if quote_key in seen:
                continue

            seen.add(quote_key)
            deduped.append(cleaned)

            if len(deduped) >= max_quotes_per_case:
                break

        if deduped:
            result[source] = deduped
        elif source in fallback_quotes:
            fallback = clean_doctrinal_quote(fallback_quotes[source])
            result[source] = [fallback or fallback_quotes[source]]

    return result


# ============================================================
# QUOTE SCORING
# ============================================================

def is_valid_doctrinal_quote(quote: str) -> bool:
    return bool(clean_doctrinal_quote(quote))


def quote_precision_score(quote: str, source: str = "", role: str = "") -> float:
    q = clean_doctrinal_quote(quote)
    if not q:
        return -1000.0

    q_l = q.lower()
    source_l = (source or "").lower()
    words = q.split()

    score = 0.0

    if 12 <= len(words) <= 35:
        score += 8
    elif 36 <= len(words) <= 45:
        score += 4
    elif len(words) > 50:
        score -= 3

    for marker in [
        "must",
        "requires",
        "standard of review",
        "business judgment",
        "entire fairness",
        "fair dealing",
        "fair price",
        "fully informed",
        "uncoerced",
        "special committee",
        "majority of the minority",
        "controller",
        "duty of loyalty",
        "good faith",
        "best value reasonably available",
        "coercive",
        "preclusive",
        "reasonable doubt",
        "impartially consider",
        "director-by-director",
        "proper purpose",
        "credible basis",
        "compelling justification",
    ]:
        if marker in q_l:
            score += 5

    if role == "foundation":
        score += 6
    elif role in {"supreme_refinement", "refinement"}:
        score += 5
    elif role == "modern_application":
        score += 3

    source_boosts = {
        "caremark": ["utter failure to attempt to assure", "reporting system", "information system"],
        "stone": ["failure to act in good faith", "duty of loyalty"],
        "marchand": ["good faith effort", "oversight system", "mission critical"],
        "weinberger": ["entire fairness", "fair dealing", "fair price"],
        "kahn": ["entire fairness", "controller", "controlling stockholder"],
        "mfw": ["special committee", "majority of the minority", "business judgment"],
        "corwin": ["fully informed", "uncoerced", "business judgment"],
        "unocal": ["threat to corporate policy", "reasonable grounds"],
        "unitrin": ["coercive", "preclusive", "range of reasonableness"],
        "revlon": ["best value reasonably available"],
        "qvc": ["change of control", "best value reasonably available"],
        "aronson": ["reasonable doubt"],
        "rales": ["impartially consider"],
        "zuckerberg": ["director-by-director"],
        "malone": ["truthfully", "materially misleading"],
        "blasius": ["compelling justification", "stockholder franchise"],
        "schnell": ["inequitable"],
    }

    for case_key, anchors in source_boosts.items():
        if case_key in source_l:
            for anchor in anchors:
                if anchor in q_l:
                    score += 12

    if any(x in q_l for x in ["the court held", "the court explained", "the court stated"]):
        score -= 8

    return score


def pick_best_quote(quotes: List[str], source: str = "", role: str = "") -> str:
    cleaned = []

    for quote in quotes or []:
        q = clean_doctrinal_quote(quote)
        if q:
            cleaned.append(q)

    if not cleaned:
        return ""

    ranked = sorted(
        cleaned,
        key=lambda q: quote_precision_score(q, source=source, role=role),
        reverse=True,
    )

    return ranked[0]


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_quote_fragment(role: str, quote: str) -> str:
    quote_l = _normalize_quote_text(quote).lower()

    patterns_by_role = {
        "foundation": [
            "utter failure to attempt to assure",
            "sustained or systematic failure",
            "reporting or information system exists",
            "entire fairness",
            "fair dealing",
            "fair price",
            "fully informed and uncoerced",
            "best value reasonably available",
            "reasonable grounds for believing that a threat",
            "reasonable doubt",
            "truthfully and completely",
            "proper purpose",
            "credible basis",
            "compelling justification",
            "inequitable action",
        ],
        "supreme_refinement": [
            "failure to act in good faith",
            "subsidiary element of the duty of loyalty",
            "neither coercive nor preclusive",
            "change of control",
            "impartially consider a demand",
            "materially misleading",
            "majority of the minority",
            "special committee",
        ],
        "modern_application": [
            "good faith effort to implement an oversight system",
            "conscious failure to monitor",
            "mission critical",
            "within a range of reasonableness",
            "business judgment deference",
            "uncoerced",
            "director-by-director",
            "knowingly disseminate false information",
        ],
    }

    for pattern in patterns_by_role.get(role, []):
        if pattern in quote_l:
            return pattern

    words = re.findall(r"\b[a-z]{4,}\b", quote_l)
    return " ".join(words[:8]).strip()

def gatekeep_case_quotes(
    case_quotes: Dict[str, List[str]],
    min_score: float = 8.0,
) -> Dict[str, List[str]]:
    """
    Final quote-quality gate before role_quote_map construction.
    Removes OCR fragments, weak doctrinal sentences, duplicate fragments,
    and quotes that fail precision scoring.
    """
    gated: Dict[str, List[str]] = {}

    for source, quotes in (case_quotes or {}).items():
        accepted: List[str] = []
        seen: Set[str] = set()

        for quote in quotes or []:
            cleaned = clean_doctrinal_quote(quote)
            if not cleaned:
                continue

            score = quote_precision_score(cleaned, source=source)

            if score < min_score:
                continue

            key = re.sub(r"\W+", "", cleaned.lower())
            if key in seen:
                continue

            seen.add(key)
            accepted.append(cleaned)

        if accepted:
            gated[source] = accepted

    return gated


# ============================================================
# ROLE MAP
# ============================================================

def build_role_based_quote_map(
    cases: List[Dict[str, Any]],
    case_quotes: Dict[str, List[str]],
    get_case_role,
    get_case_display_name,
) -> Dict[str, Dict[str, str]]:
    selected: Dict[str, Dict[str, str]] = {}
    seen_quotes: Set[str] = set()

    for role in ["foundation", "supreme_refinement", "refinement", "modern_application"]:
        for case in cases:
            source = case.get("source", "")
            case_role = case.get("role", get_case_role(source))

            if case_role != role:
                continue

            quotes = case_quotes.get(source, [])
            filtered_quotes = [quote for quote in quotes if is_valid_doctrinal_quote(quote)]

            best_quote = pick_best_quote(filtered_quotes, source=source, role=role) if filtered_quotes else ""

            if not best_quote:
                continue

            quote_key = re.sub(r"\s+", " ", best_quote.lower()).strip()

            if quote_key in seen_quotes and role != "modern_application":
                continue

            seen_quotes.add(quote_key)

            selected[role] = {
                "case": get_case_display_name({"source": source}).strip(),
                "quote": best_quote if best_quote[-1] in ".!?" else best_quote + ".",
                "source": source,
            }
            break

    return selected