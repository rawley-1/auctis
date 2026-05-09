from __future__ import annotations

import re

from typing import Any, Dict, List, Set, Optional


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
    quotes: List[str],
    doctrine_line: str = "unknown",
    role: str = "unknown",
    source: str = "",
) -> Optional[str]:
    """
    Select the cleanest, most doctrinally useful quote.

    Design goal:
    - Prefer doctrinal rule / holding language.
    - Reject OCR garbage, captions, reporter metadata, and malformed fragments.
    - Prefer doctrine-specific anchors.
    - Return None rather than a bad quote.
    """

    import re

    if not quotes:
        return None

    doctrine_line = doctrine_line or "unknown"
    role = role or "unknown"
    source_l = (source or "").lower()

    def clean_quote(q: str) -> str:
        q = (q or "").strip()
        q = q.replace("“", '"').replace("”", '"').replace("’", "'")
        q = re.sub(r"\s+", " ", q)
        q = re.sub(r"\s+([,.;:])", r"\1", q)
        return q.strip()

    DOCTRINE_ANCHORS = {
        "oversight": [
            "utter failure",
            "reporting system",
            "information system",
            "good faith",
            "good faith effort",
            "known duty to act",
            "conscious disregard",
            "red flags",
            "mission critical",
            "monitoring",
            "oversight",
        ],
        "sale_of_control": [
            "best value reasonably available",
            "best value",
            "change of control",
            "sale of control",
            "stockholders",
            "shareholders",
            "revlon",
            "auctioneer",
        ],
        "takeover_defense": [
            "coercive",
            "preclusive",
            "range of reasonableness",
            "reasonable grounds",
            "threat",
            "defensive measure",
            "unocal",
            "unitrin",
        ],
        "controller_transactions": [
            "controller",
            "entire fairness",
            "fair dealing",
            "fair price",
            "special committee",
            "majority of the minority",
            "minority stockholders",
        ],
        "stockholder_vote_cleansing": [
            "fully informed",
            "uncoerced",
            "disinterested stockholders",
            "stockholder approval",
            "business judgment",
            "corwin",
        ],
        "demand_futility": [
            "demand futility",
            "particularized facts",
            "reasonable doubt",
            "disinterested",
            "independent",
            "aronson",
            "rales",
            "zuckerberg",
        ],
        "disclosure_loyalty": [
            "disclosure",
            "material",
            "stockholder action",
            "duty of disclosure",
            "candor",
        ],
        "entire_fairness": [
            "entire fairness",
            "fair dealing",
            "fair price",
            "utmost good faith",
            "burden",
        ],
        "section_220": [
            "proper purpose",
            "books and records",
            "credible basis",
            "inspection",
        ],
        "schnell": [
            "inequitable action",
            "legally possible",
            "equitable principles",
        ],
        "blasius": [
            "compelling justification",
            "stockholder franchise",
            "vote",
            "election",
        ],
    }

    GENERAL_RULE_TERMS = [
        "directors",
        "board",
        "fiduciary",
        "duty",
        "duty of loyalty",
        "good faith",
        "bad faith",
        "reasonable",
        "reasonably",
        "requires",
        "must",
        "liability",
        "standard",
        "stockholders",
        "shareholders",
    ]

    BAD_TERMS = [
        "submitted:",
        "decided:",
        "attorneys for",
        "plaintiff",
        "defendant",
        "appellant",
        "appellee",
        "civil action",
        "court of chancery",
        "supreme court of delaware",
        "esq.",
        "transcript",
        "deposition",
        "trial",
        "brief",
        "argued",
        "testified",
        "credible if",
        "our law would be more credible",
        "not based on any",
    ]

    OCR_BAD_TERMS = [
        "olated",
        "refiduciary",
        "lationship",
        "prodirectors",
        "readigood",
        "have rulings",
        "albreached",
        "substan",
        "fiducia flags",
        "nizable",
        "concl uded",
        "moni tor",
    ]

    def is_bad_quote(q: str) -> bool:
        q_l = q.lower()
        words = q.split()

        if len(words) < 8:
            return True

        if len(words) > 85:
            return True

        if q[:1].islower():
            return True

        if not re.search(r"[A-Za-z]", q):
            return True

        if sum(1 for term in BAD_TERMS if term in q_l) >= 2:
            return True

        if any(term in q_l for term in OCR_BAD_TERMS):
            return True

        if len(re.findall(r"\b\d{2,}\b", q)) >= 4:
            return True

        if len(re.findall(r"\b[A-Z]{4,}\b", q)) >= 3:
            return True

        if q.count(",") > 10:
            return True

        if q.count("§") >= 2:
            return True

        alpha_chars = len(re.findall(r"[A-Za-z]", q))
        if alpha_chars / max(len(q), 1) < 0.58:
            return True

        # Reject citation/caption-heavy strings.
        if re.search(r"\b\d+\s+A\.(2d|3d)\s+\d+\b", q):
            return True

        if re.search(r"\bC\.A\.\s+No\.", q, flags=re.IGNORECASE):
            return True

        # Reject obvious broken OCR word runs.
        if re.search(r"\b[a-z]{1,2}\s+[a-z]{1,2}\s+[a-z]{1,2}\b", q_l):
            return True

        if re.search(r"\b[A-Za-z]{22,}\b", q):
            return True

        return False

    def score_quote(q: str) -> float:
        q_l = q.lower()
        words = q.split()
        score = 0.0

        if is_bad_quote(q):
            return -999.0

        # Good length band.
        if 14 <= len(words) <= 45:
            score += 4.0
        elif 46 <= len(words) <= 65:
            score += 2.0
        else:
            score -= 1.0

        # General doctrinal utility.
        for term in GENERAL_RULE_TERMS:
            if term in q_l:
                score += 1.0

        # Doctrine-specific anchors matter most.
        for term in DOCTRINE_ANCHORS.get(doctrine_line, []):
            if term in q_l:
                score += 3.0

        # Role preference.
        if role == "foundation":
            if any(t in q_l for t in ["requires", "standard", "duty", "liability"]):
                score += 2.0
        elif role == "supreme_refinement":
            if any(t in q_l for t in ["held", "requires", "duty", "good faith", "clarifies"]):
                score += 2.0
        elif role == "modern_application":
            if any(t in q_l for t in ["reasonable inference", "particularized facts", "where", "because"]):
                score += 2.0

        # Source-specific boosts.
        if "caremark" in source_l and doctrine_line == "oversight":
            if any(t in q_l for t in ["utter failure", "reporting system", "information system"]):
                score += 5.0

        if "stone" in source_l and doctrine_line == "oversight":
            if any(t in q_l for t in ["known duty to act", "conscious disregard", "good faith"]):
                score += 5.0

        if "marchand" in source_l and doctrine_line == "oversight":
            if any(t in q_l for t in ["good faith effort", "mission critical", "monitoring", "red flags"]):
                score += 5.0

        if "revlon" in source_l and doctrine_line == "sale_of_control":
            if any(t in q_l for t in ["best value", "stockholders", "shareholders"]):
                score += 5.0

        if "qvc" in source_l and doctrine_line == "sale_of_control":
            if any(t in q_l for t in ["change of control", "best value", "stockholders", "shareholders"]):
                score += 5.0

        if "airgas" in source_l and doctrine_line == "takeover_defense":
            if any(t in q_l for t in ["coercive", "preclusive", "range of reasonableness", "reasonable grounds"]):
                score += 5.0

        if "metro" in source_l or "rural" in source_l:
            if any(t in q_l for t in ["board reliance", "advisors", "informed", "reasonable"]):
                score += 4.0

        # Penalize weak / conversational / non-rule language.
        weak_terms = [
            "our law would be more credible",
            "i believe",
            "i think",
            "suppose",
            "perhaps",
            "argued",
            "testified",
            "contends",
            "asserts",
        ]
        for term in weak_terms:
            if term in q_l:
                score -= 5.0

        # Penalize procedural or citation-heavy strings.
        procedural_terms = [
            "summary judgment",
            "motion to dismiss",
            "complaint",
            "brief",
            "oral argument",
            "trial court",
            "remanded",
            "reversed",
        ]
        for term in procedural_terms:
            if term in q_l:
                score -= 1.5

        # Prefer complete sentences.
        if q.endswith((".", "!", "?")):
            score += 1.0
        else:
            score -= 1.0

        return score

    cleaned_quotes = []
    seen = set()

    for q in quotes:
        cq = clean_quote(q)
        if not cq:
            continue

        key = re.sub(r"\s+", " ", cq.lower()).strip()
        if key in seen:
            continue

        seen.add(key)
        cleaned_quotes.append(cq)

    if not cleaned_quotes:
        return None

    scored = [(score_quote(q), q) for q in cleaned_quotes]
    scored.sort(key=lambda item: item[0], reverse=True)

    best_score, best_quote = scored[0]

    # Hard gate: no quote is better than a corrupted quote.
    if best_score < 5.0:
        return None

    return best_quote

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

    role_order = [
        "foundation",
        "supreme_refinement",
        "refinement",
        "modern_application",
        "related_case",
    ]

    def clean_quote_text(text: str) -> str:
        if not text:
            return ""

        text = str(text)
        text = text.replace("“", '"').replace("”", '"').replace("’", "'")
        text = text.replace("\xad", "")
        text = re.sub(r"\s+", " ", text).strip()

        text = re.sub(r"\bSECTION:\s*[^A-Z]*", "", text, flags=re.I)
        text = re.sub(r"\bCASE:\s*[^A-Z]*", "", text, flags=re.I)
        text = re.sub(r"\bCOURT:\s*[^A-Z]*", "", text, flags=re.I)
        text = re.sub(r"\bYEAR:\s*\d{4}", "", text, flags=re.I)
        text = re.sub(r"\bDOCTRINE:\s*[^A-Z]*", "", text, flags=re.I)
        text = re.sub(r"\bAUTHORITY:\s*[^A-Z]*", "", text, flags=re.I)
        text = re.sub(r"\bKEY TOPIC:\s*", "", text, flags=re.I)

        return re.sub(r"\s+", " ", text).strip(" -:;,")

    def is_bad_quote(text: str) -> bool:
        q = clean_quote_text(text)
        q_l = q.lower()

        if not q:
            return True

        if len(q.split()) < 8:
            return True

        if len(q) > 420:
            return True

        bad_markers = [
            "supra",
            "infra",
            "ibid",
            "footnote",
            "appendix",
            "law review",
            "j.corp.law",
            "j. corp. law",
            "fordham",
            "article",
            "plaintiffs argue",
            "defendants argue",
            "created supreme delaware court",
            "the po in that",
            "more satisfy the court",
            "there is a vast difference be",
            "intermediate standard the that",
            "declined iconic",
            "reashowing",
            "dangrounds",
            "seismic and its not this",
            "judge process conduct neither",
        ]

        if any(marker in q_l for marker in bad_markers):
            return True

        tiny_words = [w for w in q.split() if len(w) <= 2]
        if len(tiny_words) / max(1, len(q.split())) > 0.35:
            return True

        return False

    def quote_candidates_from_case_quotes(source: str) -> List[str]:
        candidates = []

        for q in case_quotes.get(source, []) or []:
            raw = q.get("quote", q.get("text", "")) if isinstance(q, dict) else str(q)
            cleaned = clean_quote_text(raw)

            if cleaned and not is_bad_quote(cleaned):
                candidates.append(cleaned)

        return candidates

    def quote_candidates_from_chunks(case: Dict[str, Any]) -> List[str]:
        candidates = []

        markers = [
            "best value reasonably available",
            "highest value reasonably attainable",
            "change of control",
            "sale of control",
            "for sale",
            "auctioneers",
            "enhanced scrutiny",
            "range of reasonableness",
            "entire fairness",
            "fair dealing",
            "fair price",
            "business judgment",
            "special committee",
            "majority of the minority",
            "good faith",
            "bad faith",
            "reporting system",
            "red flags",
            "reasonable",
            "reasonably",
            "duty",
            "requires",
            "must",
        ]

        for chunk in case.get("chunks", []) or []:
            raw_text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
            text = clean_quote_text(raw_text)

            if not text:
                continue

            for sentence in re.split(r"(?<=[.!?])\s+", text):
                s = clean_quote_text(sentence)
                s_l = s.lower()

                if is_bad_quote(s):
                    continue

                if any(marker in s_l for marker in markers):
                    candidates.append(s)

        return candidates

    def normalize_role(role: str) -> str:
        role = (role or "").strip() or "related_case"

        aliases = {
            "supreme refinement": "supreme_refinement",
            "modern application": "modern_application",
            "related": "related_case",
        }

        return aliases.get(role, role)

    for role in role_order:
        for case in cases or []:
            if not isinstance(case, dict):
                continue

            source = case.get("source", "")
            if not source:
                continue

            case_role = normalize_role(case.get("role") or get_case_role(source))

            if case_role != role:
                continue

            candidates = quote_candidates_from_case_quotes(source)

            if not candidates:
                candidates = quote_candidates_from_chunks(case)

            best_quote = (
                pick_best_quote(
                    candidates,
                    source=source,
                    role=role,
                    doctrine_line="",
                )
                if candidates
                else ""
            )

            best_quote = (
                pick_best_quote(
                candidates,
                source=source,
                role=role,
                doctrine_line="",
            )
                if candidates
                else ""
            )

            if best_quote:
                best_quote = clean_quote_text(best_quote)
            else:
                best_quote = ""

            quote_key = re.sub(r"\s+", " ", best_quote.lower()).strip()

            if quote_key in seen_quotes:
                continue

            seen_quotes.add(quote_key)

            best_quote = clean_quote_text(best_quote or "")

            if not best_quote:
                continue

            if best_quote[-1] not in ".!?":
                best_quote += "."

            if role not in selected:
                selected[role] = {
                "case": get_case_display_name({"source": source}).strip(),
                "quote": best_quote,
                "source": source,
            }

            break

    return selected