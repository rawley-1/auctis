from __future__ import annotations

import re
from typing import Any, Dict, List, Set


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_sentence(text: str) -> str:
    if not text:
        return ""

    # remove metadata junk
    junk_patterns = [
        r"SECTION:.*",
        r"CASE:.*",
        r"COURT:.*",
        r"YEAR:.*",
        r"DOCTRINE:.*",
        r"AUTHORITY:.*",
        r"KEY TOPIC:.*",
    ]

    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # keep only clean sentences
    if len(text.split()) < 8:
        return ""

    return text

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


def extract_case_quotes(chunks, fallback_quotes=None, max_quotes_per_case=5):
    fallback_quotes = fallback_quotes or {}
    case_quotes = {}

    def clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(r"SECTION:\s*", "", text, flags=re.I)
        return text

    def split_candidates(text: str):
        text = clean_text(text)

        # Split by sentence, but preserve useful long doctrinal sentences.
        sentences = re.split(r"(?<=[.!?])\s+", text)

        candidates = []

        for s in sentences:
            s = clean_text(s)

            if not s:
                continue

            # Remove metadata-only junk
            if re.fullmatch(r"(CASE|COURT|YEAR|DOCTRINE|AUTHORITY|KEY TOPIC):.*", s, flags=re.I):
                continue

            if len(s.split()) >= 8:
                candidates.append(s)

        return candidates

    def source_from_chunk(chunk):
        return chunk.get("source") or chunk.get("case") or chunk.get("file") or "unknown"

    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue

        source = source_from_chunk(chunk)
        text = chunk.get("text", "") or ""

        candidates = split_candidates(text)

        if not candidates:
            continue

        existing = case_quotes.setdefault(source, [])

        for cand in candidates:
            if cand not in existing:
                existing.append(cand)

    # Add fallback doctrinal quotes when extraction found nothing.
    for source, quotes in fallback_quotes.items():
        if source not in case_quotes or not case_quotes[source]:
            if isinstance(quotes, list):
                case_quotes[source] = quotes[:max_quotes_per_case]
            elif isinstance(quotes, str):
                case_quotes[source] = [quotes]

    # Pick top quotes per case using improved picker.
    cleaned = {}

    for source, quotes in case_quotes.items():
        selected = []

        for _ in range(max_quotes_per_case):
            best = pick_best_quote(
                quotes,
                source=source,
                doctrine_line="",
            )

            if not best or best in selected:
                break

            selected.append(best)

            # Remove selected from candidate pool
            quotes = [q for q in quotes if str(q) != best]

        if selected:
            cleaned[source] = selected

    return cleaned


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

def pick_best_quote(
    quotes,
    source: str = "",
    role: str = "",
    doctrine_line: str = "",
):
    if not quotes:
        return ""

    source_l = (source or "").lower()
    role_l = (role or "").lower()
    doctrine_l = (doctrine_line or "").lower()

    def clean_quote(q: str) -> str:
        q = re.sub(r"\s+", " ", q or "").strip()
        q = q.replace("“", '"').replace("”", '"').replace("’", "'")
        q = re.sub(
            r"^(SECTION|CASE|COURT|YEAR|DOCTRINE|AUTHORITY|KEY TOPIC):\s*",
            "",
            q,
            flags=re.I,
        )
        return q.strip()

    def is_garbage(q: str) -> bool:
        q = clean_quote(q)
        q_l = q.lower()

        if not q:
            return True

        if len(q.split()) < 8:
            return True

        if len(q) > 360:
            return True

        if len(re.findall(r"\b\d+\b", q)) >= 3:
            return True

        if q.count(",") > 6:
            return True

        tiny_words = [w for w in q.split() if len(w) <= 2]
        if len(tiny_words) / max(1, len(q.split())) > 0.30:
            return True

        garbage_markers = [
            "supra",
            "infra",
            "ibid",
            "footnote",
            "appendix",
            "see also",
            "plaintiffs argue",
            "defendants argue",
            "j.corp.law",
            "j. corp. law",
            "fordham",
            "law review",
            "article",
            "professor",
            "available at",
            "created supreme delaware court",
            "the po in that",
            "more satisfy the court",
            "there is a vast difference be",
            "declined iconic",
            "intermediate standard the that",
        ]

        if any(g in q_l for g in garbage_markers):
            return True

        return False

    def looks_like_rule(q: str) -> bool:
        q_l = q.lower()

        rule_signals = [
            "must",
            "requires",
            "required",
            "duty",
            "obligation",
            "is triggered",
            "are triggered",
            "applies when",
            "applies where",
            "standard",
            "review",
            "turns on",
            "the question is",
            "directors",
            "board",
            "fiduciary",
            "stockholders",
        ]

        return any(signal in q_l for signal in rule_signals)

    def anchor_bonus(q: str) -> int:
        q_l = q.lower()

        anchors = {
            "revlon": [
                "best value reasonably available",
                "auctioneers",
                "stockholders' benefit",
                "for sale",
            ],
            "qvc": [
                "change of control",
                "results in a change of control",
                "sale of control",
                "control of the corporation",
                "best value reasonably available",
            ],
            "paramount": [
                "change of control",
                "sale of control",
                "control of the corporation",
                "best value reasonably available",
            ],
            "lyondell": [
                "no single blueprint",
                "reasonable decision",
                "not perfection",
                "utterly failed",
                "bad faith",
                "revlon duties",
            ],
            "barkan": [
                "no single blueprint",
                "reasonable course",
                "active and direct role",
                "market check",
                "best value",
            ],
            "metro": [
                "financial advisors",
                "informed and reasonable",
                "board reliance",
                "sale process",
            ],
            "rural metro": [
                "financial advisors",
                "sale process",
                "informed and reasonable",
            ],
            "unocal": [
                "threat to corporate policy",
                "enhanced scrutiny",
                "reasonable grounds",
            ],
            "unitrin": [
                "coercive",
                "preclusive",
                "range of reasonableness",
            ],
            "airgas": [
                "coercive",
                "preclusive",
                "range of reasonableness",
                "reasonable grounds",
            ],
            "caremark": [
                "utter failure",
                "reporting system",
                "information and reporting system",
            ],
            "stone": [
                "bad faith",
                "duty of loyalty",
                "failure to act in good faith",
            ],
            "marchand": [
                "good faith effort",
                "mission critical",
                "red flags",
            ],
            "mfw": [
                "majority of the minority",
                "special committee",
                "from the outset",
                "business judgment",
            ],
            "corwin": [
                "fully informed",
                "uncoerced",
                "business judgment",
            ],
            "weinberger": [
                "entire fairness",
                "fair dealing",
                "fair price",
            ],
            "aronson": [
                "reasonable doubt",
                "demand futility",
            ],
            "rales": [
                "impartially consider",
                "demand futility",
            ],
            "zuckerberg": [
                "director-by-director",
                "demand futility",
            ],
            "malone": [
                "truthfully",
                "materially misleading",
            ],
            "blasius": [
                "compelling justification",
                "stockholder franchise",
            ],
            "schnell": [
                "inequitable",
            ],
            "section 220": [
                "proper purpose",
                "credible basis",
            ],
        }

        bonus = 0

        for case_key, phrases in anchors.items():
            if case_key in source_l:
                for phrase in phrases:
                    if phrase in q_l:
                        bonus += 20

        return bonus

    def marker_score(q: str) -> int:
        q_l = q.lower()
        score = 0

        universal = {
            "must": 6,
            "requires": 6,
            "required": 5,
            "duty": 6,
            "obligation": 5,
            "standard": 5,
            "review": 5,
            "board": 4,
            "directors": 5,
            "fiduciary": 5,
            "stockholders": 5,
            "reasonable": 4,
            "reasonably": 4,
        }

        sale = {
            "best value reasonably available": 22,
            "highest value reasonably attainable": 20,
            "change of control": 18,
            "for sale": 12,
            "sale of control": 12,
            "auction": 10,
            "auctioneers": 14,
            "maximize": 10,
            "maximization": 10,
            "stockholders' benefit": 12,
            "revlon duties": 10,
            "sale process": 8,
        }

        takeover = {
            "enhanced scrutiny": 18,
            "coercive": 14,
            "preclusive": 14,
            "range of reasonableness": 18,
            "threat to corporate policy": 18,
            "reasonable grounds": 12,
            "defensive measure": 10,
        }

        fairness = {
            "entire fairness": 18,
            "fair dealing": 14,
            "fair price": 14,
            "burden": 8,
        }

        controller = {
            "majority of the minority": 18,
            "special committee": 14,
            "business judgment": 12,
            "controller": 10,
            "from the outset": 10,
        }

        oversight = {
            "utter failure": 18,
            "good faith effort": 18,
            "bad faith": 14,
            "reporting system": 12,
            "red flags": 12,
            "mission critical": 12,
            "duty of loyalty": 10,
        }

        demand = {
            "demand futility": 16,
            "particularized facts": 14,
            "independent and disinterested": 14,
            "reasonable doubt": 10,
            "impartially consider": 10,
            "director-by-director": 10,
        }

        books_records = {
            "proper purpose": 16,
            "credible basis": 16,
            "necessary and essential": 12,
        }

        franchise = {
            "compelling justification": 18,
            "stockholder franchise": 16,
            "inequitable": 12,
        }

        disclosure = {
            "truthfully": 14,
            "materially misleading": 16,
            "material information": 12,
        }

        groups = [universal]

        if "sale_of_control" in doctrine_l or any(
            x in source_l for x in ["revlon", "qvc", "barkan", "lyondell", "paramount", "metro"]
        ):
            groups.append(sale)

        if "takeover_defense" in doctrine_l or any(
            x in source_l for x in ["unocal", "unitrin", "airgas"]
        ):
            groups.append(takeover)

        if "entire_fairness" in doctrine_l or any(
            x in source_l for x in ["weinberger", "entire fairness"]
        ):
            groups.append(fairness)

        if "controller" in doctrine_l or any(
            x in source_l for x in ["mfw", "tesla", "kahn"]
        ):
            groups.append(controller)

        if "oversight" in doctrine_l or any(
            x in source_l for x in ["caremark", "stone", "marchand"]
        ):
            groups.append(oversight)

        if "demand_futility" in doctrine_l or any(
            x in source_l for x in ["aronson", "rales", "zuckerberg"]
        ):
            groups.append(demand)

        if "books" in doctrine_l or "220" in doctrine_l or "section 220" in source_l:
            groups.append(books_records)

        if any(x in doctrine_l for x in ["blasius", "schnell", "franchise", "equitable_intervention"]):
            groups.append(franchise)

        if "disclosure" in doctrine_l or "malone" in source_l:
            groups.append(disclosure)

        for group in groups:
            for marker, weight in group.items():
                if marker in q_l:
                    score += weight

        score += anchor_bonus(q)

        if looks_like_rule(q):
            score += 10
        else:
            score -= 16

        length = len(q.split())

        if 10 <= length <= 28:
            score += 10
        elif 29 <= length <= 45:
            score += 4
        elif length > 60:
            score -= 14

        if q.strip().endswith("."):
            score += 2

        if role_l == "foundation" and any(
            x in q_l for x in ["must", "duty", "requires", "standard", "best value"]
        ):
            score += 8

        if role_l in {"supreme_refinement", "refinement"} and any(
            x in q_l for x in ["clarifies", "triggered", "change of control", "standard", "applies"]
        ):
            score += 8

        if role_l == "modern_application" and any(
            x in q_l for x in ["applies", "reasonable", "reliance", "process", "informed"]
        ):
            score += 6

        weak_markers = [
            "helps define",
            "generally speaking",
            "in this case",
            "the court considered",
            "the court noted",
            "the court stated",
            "the court explained",
        ]

        if any(w in q_l for w in weak_markers):
            score -= 10

        if is_garbage(q):
            score -= 100

        return score

    scored = []

    for q in quotes:
        raw = q.get("quote", q.get("text", "")) if isinstance(q, dict) else str(q)
        cleaned = clean_quote(raw)

        if not cleaned:
            continue

        score = marker_score(cleaned)

        if score > 0:
            scored.append((score, cleaned))

    if not scored:
        return ""

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


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
            filtered_quotes = quotes

            best_quote = pick_best_quote(
                filtered_quotes,
                source=source,
                role=role,
                doctrine_line="",   # or pass real doctrine_line later if you want
            ) if filtered_quotes else ""

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