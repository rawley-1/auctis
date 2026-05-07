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
    source_l = (source or "").lower()
    role_l = (role or "").lower()
    doctrine_l = (doctrine_line or "").lower()

    WEAK_OCR_SOURCES = {
        "metro.txt",
        "rural metro.txt",
        "rural_metro.txt",
        "barkan.txt",
    }

    CANONICAL_QUOTES = {
        "caremark.txt": [
            "Utter failure to attempt to assure a reasonable information and reporting system exists.",
        ],
        "in re caremark.txt": [
            "Utter failure to attempt to assure a reasonable information and reporting system exists.",
        ],
        "stone.txt": [
            "Failure to act in good faith is a breach of the duty of loyalty.",
            "Where directors fail to act in the face of a known duty to act, thereby demonstrating a conscious disregard for their responsibilities, they breach their duty of loyalty by failing to discharge that fiduciary obligation in good faith.",
        ],
        "marchand.txt": [
            "Directors must make a good faith effort to implement an oversight system.",
            "Caremark requires that a board make a good faith effort to put in place a reasonable system of monitoring and reporting about the corporation's central compliance risks.",
        ],
        "revlon.txt": [
            "Directors become auctioneers charged with getting the best price reasonably available for the stockholders' benefit.",
        ],
        "qvc.txt": [
            "The directors' obligation is to seek the best value reasonably available for the stockholders where there is a pending sale of control.",
        ],
        "paramount v qvc.txt": [
            "The directors' obligation is to seek the best value reasonably available for the stockholders where there is a pending sale of control.",
        ],
        "lyondell.txt": [
            "There are no legally prescribed steps that directors must follow to satisfy their Revlon duties.",
        ],
        "barkan.txt": [
            "There is no single blueprint that a board must follow to fulfill its duties.",
        ],
        "metro.txt": [
            "Board reliance on advisors must be informed and reasonable.",
        ],
        "rural metro.txt": [
            "Board reliance on advisors must be informed and reasonable.",
        ],
        "rural_metro.txt": [
            "Board reliance on advisors must be informed and reasonable.",
        ],
        "unocal.txt": [
            "Directors must show that they had reasonable grounds for believing that a danger to corporate policy and effectiveness existed.",
        ],
        "unitrin.txt": [
            "A defensive measure cannot be coercive or preclusive and must fall within a range of reasonableness.",
        ],
        "airgas.txt": [
            "The defensive measures must not be coercive or preclusive and must fall within a range of reasonableness.",
        ],
        "mfw.txt": [
            "Business judgment review applies if and only if the controller conditions the transaction from the outset on approval by both an independent special committee and a majority of the minority stockholders.",
        ],
        "corwin.txt": [
            "When a transaction not subject to the entire fairness standard is approved by a fully informed, uncoerced vote of disinterested stockholders, the business judgment rule applies.",
        ],
        "weinberger.txt": [
            "The concept of fairness has two basic aspects: fair dealing and fair price.",
        ],
        "aronson.txt": [
            "Demand is excused where particularized facts create a reasonable doubt that the directors are disinterested and independent or that the challenged transaction was otherwise the product of a valid exercise of business judgment.",
        ],
        "rales.txt": [
            "The inquiry is whether the board could have properly exercised its independent and disinterested business judgment in responding to a demand.",
        ],
        "zuckerberg.txt": [
            "Demand futility turns on a director-by-director inquiry.",
        ],
    }

    def clean_quote(q: str) -> str:
        if not q:
            return ""

        q = str(q)
        q = q.replace("“", '"').replace("”", '"').replace("’", "'")
        q = q.replace("\xad", "")
        q = q.replace("—", "-")
        q = re.sub(r"\s+", " ", q).strip()

        metadata_patterns = [
            r"\bSECTION:\s*",
            r"\bCASE:\s*",
            r"\bCOURT:\s*",
            r"\bYEAR:\s*\d{4}",
            r"\bDOCTRINE:\s*",
            r"\bAUTHORITY:\s*",
            r"\bKEY TOPIC:\s*",
            r"\bIMPORTANT HOLDING:\s*",
            r"\bRELATION TO OTHER [A-Z\- ]+:\s*",
        ]

        for pattern in metadata_patterns:
            q = re.sub(pattern, "", q, flags=re.I)

        q = re.sub(r"([A-Za-z])- ([A-Za-z])", r"\1\2", q)
        q = re.sub(r"\s+", " ", q).strip(" -:;,\n\t")

        return q

    def source_matches(key: str) -> bool:
        key_l = key.lower().replace("_", " ").strip()
        normalized_source = source_l.replace("_", " ").strip()

        return (
            key_l == normalized_source
            or key_l.replace(".txt", "") == normalized_source.replace(".txt", "")
            or key_l.replace(".txt", "") in normalized_source.replace(".txt", "")
        )

    def is_weak_ocr_source() -> bool:
        normalized_source = source_l.replace("_", " ").strip()
        return any(source_matches(src) for src in WEAK_OCR_SOURCES) or any(
            weak.replace(".txt", "") in normalized_source.replace(".txt", "")
            for weak in WEAK_OCR_SOURCES
        )

    def sentence_integrity_penalty(q: str) -> int:
        q = clean_quote(q)
        q_l = q.lower()
        penalty = 0
        words = q.split()

        if not q:
            return 100

        if re.match(r"^[\]\)\.,;:\-–—'\"]", q):
            penalty += 30

        if re.match(r"^\d+[\.\)]?\s+", q):
            penalty += 22

        if q and q[0].islower():
            penalty += 14

        ugly_fragments = [
            "posed.",
            "reashowing",
            "dangrounds",
            "selectresponse",
            "the po in that",
            "there is a vast difference be",
            "intermediate standard the that",
            "declined iconic",
            "not seismic and its not this",
            "judge process conduct neither",
            "substantial basis, ...",
            "more satisfy the court",
            "they selectresponse",
            "that sonable",
            "our of corp",
            "corpothe",
            "thestockhold",
            "revlon as to fairness tive effect",
            "insubstantial basis",
            "retroacthe revlon",
            "judicial expansive corporate policy",
            "comfortably permit also do not but",
            "threat and that proper and not selfish",
            "their actions one v. objective",
            "the selectresponse",
            "that their motiva to show persuasion",
            "corporation the sale of a for cash",
            "enhanced 506",
            "rbc never- least",
            "must respond theless",
            "serve as the ad hoe",
            "valua- fairness committee",
            "at pany for valuation purposes",
            "tion football field",
        ]

        if any(x in q_l for x in ugly_fragments):
            penalty += 90

        if "[]" in q:
            penalty += 45

        if re.search(r"\b[a-zA-Z]+\[\]\b", q):
            penalty += 45

        numeric_citations = len(re.findall(r"\b\d+\b", q))

        if numeric_citations >= 4:
            penalty += 22

        if numeric_citations >= 7:
            penalty += 18

        if re.search(r"\bA\.?2d\b|\bA\.?3d\b|\bDel\.?\b|\bWL\b", q, flags=re.I):
            penalty += 8

        if q.count('"') >= 4:
            penalty += 18

        if q.count(",") > 7:
            penalty += 12

        if q.count(";") >= 3:
            penalty += 14

        if q and q[-1] not in ".!?":
            penalty += 8

        if q.count(".") == 0 and len(words) > 22:
            penalty += 18

        caps_words = [w for w in words if len(w) > 4 and w.isupper()]
        if len(caps_words) >= 4:
            penalty += 25

        if words:
            tiny_words = [
                w for w in words
                if len(w.strip(".,;:()[]{}\"'")) <= 2
            ]

            if len(tiny_words) / max(1, len(words)) > 0.30:
                penalty += 35

            weird_words = [
                w for w in words
                if len(w) > 16 and not re.search(r"[aeiouAEIOU]", w)
            ]

            penalty += min(30, len(weird_words) * 10)

        metadata_markers = [
            "important holding",
            "relation to other",
            "doctrine:",
            "authority:",
            "key topic:",
            "binding precedent",
            "section:",
            "court:",
            "year:",
        ]

        metadata_hits = sum(1 for marker in metadata_markers if marker in q_l)
        penalty += metadata_hits * 12

        doctrinal_terms = [
            "duty",
            "board",
            "director",
            "fiduciary",
            "stockholder",
            "shareholder",
            "good faith",
            "bad faith",
            "oversight",
            "control",
            "sale",
            "transaction",
            "process",
            "reasonable",
            "reasonably",
            "standard",
            "review",
        ]

        doctrinal_hits = sum(1 for term in doctrinal_terms if term in q_l)

        if doctrinal_hits == 0:
            penalty += 15

        if (
            doctrinal_hits >= 2
            and q[-1] in ".!?"
            and numeric_citations < 4
            and 10 <= len(words) <= 60
        ):
            penalty -= 10

        return max(0, penalty)

    def is_garbage(q: str) -> bool:
        q = clean_quote(q)
        q_l = q.lower()

        if not q:
            return True

        words = q.split()

        if len(words) < 8:
            return True

        if len(q) > 460:
            return True

        if sentence_integrity_penalty(q) >= 70:
            return True

        if "[]" in q:
            return True

        if re.search(r"\b[a-zA-Z]+\[\]\b", q):
            return True

        if q.count(".") == 0 and len(words) > 22:
            return True

        if q[0].islower():
            return True

        if re.match(r"^[\]\)\.,;:\-–—'\"]", q):
            return True

        if len(re.findall(r"\b\d+\b", q)) >= 4:
            return True

        tiny_words = [
            w for w in words
            if len(w.strip(".,;:()[]{}\"'")) <= 2
        ]

        if len(tiny_words) / max(1, len(words)) > 0.32:
            return True

        weird_words = [
            w for w in words
            if len(w) > 16 and not re.search(r"[aeiouAEIOU]", w)
        ]

        if len(weird_words) >= 2:
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
            "intermediate standard the that",
            "declined iconic",
            "reashowing",
            "dangrounds",
            "selectresponse",
            "that sonable",
            "corpothe",
            "thestockhold",
            "insubstantial basis",
            "judge process conduct neither",
            "not seismic and its not this",
            "posed.",
            "rbc never- least",
            "must respond theless",
            "serve as the ad hoe",
            "valua- fairness committee",
            "at pany for valuation purposes",
            "tion football field",
        ]

        if any(g in q_l for g in garbage_markers):
            return True

        if q.count('"') >= 4:
            return True

        if q.count(",") > 8:
            return True

        return False

    def hard_eligible(q: str) -> bool:
        q = clean_quote(q)

        if not q:
            return False

        if is_garbage(q):
            return False

        penalty_limit = 32 if is_weak_ocr_source() else 45

        if sentence_integrity_penalty(q) >= penalty_limit:
            return False

        if len(q.split()) < 10:
            return False

        tiny_word_count = len(
            [
                w for w in q.split()
                if len(w.strip(".,;:()[]{}\"'")) <= 2
            ]
        )

        if tiny_word_count >= 5 and q.count(",") > 4:
            return False

        return True

    def looks_like_rule(q: str) -> bool:
        q_l = q.lower()

        rule_signals = [
            "must",
            "requires",
            "required",
            "duty",
            "duties",
            "obligation",
            "obligated",
            "is triggered",
            "are triggered",
            "applies when",
            "applies where",
            "standard",
            "review",
            "turns on",
            "directors",
            "board",
            "fiduciary",
            "stockholders",
            "shareholders",
            "plaintiff must",
            "court will",
        ]

        return any(signal in q_l for signal in rule_signals)

    def has_doctrinal_subject(q: str) -> bool:
        q_l = q.lower()

        subjects = [
            "directors",
            "director",
            "board",
            "fiduciary",
            "stockholders",
            "stockholder",
            "shareholders",
            "shareholder",
            "corporation",
            "controller",
            "committee",
            "plaintiff",
            "demand",
            "court",
        ]

        return any(s in q_l for s in subjects)

    def anchor_bonus(q: str) -> int:
        q_l = q.lower()

        anchors = {
            "revlon": [
                "best value reasonably available",
                "auctioneers",
                "stockholders' benefit",
                "shareholders' benefit",
                "for sale",
                "maximization",
            ],
            "qvc": [
                "change of control",
                "results in a change of control",
                "sale of control",
                "control of the corporation",
                "best value reasonably available",
                "highest value reasonably attainable",
            ],
            "paramount": [
                "change of control",
                "sale of control",
                "control of the corporation",
                "best value reasonably available",
                "highest value reasonably attainable",
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
                "aiding and abetting",
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
                "known duty to act",
                "conscious disregard",
            ],
            "marchand": [
                "good faith effort",
                "mission critical",
                "red flags",
                "central compliance risks",
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
        }

        bonus = 0

        for case_key, phrases in anchors.items():
            if case_key in source_l:
                for phrase in phrases:
                    if phrase in q_l:
                        bonus += 24

        return bonus

    def doctrine_marker_groups():
        universal = {
            "must": 8,
            "requires": 8,
            "required": 6,
            "duty": 8,
            "duties": 8,
            "obligation": 7,
            "obligated": 7,
            "standard": 6,
            "review": 5,
            "board": 5,
            "directors": 7,
            "director": 6,
            "fiduciary": 6,
            "stockholders": 6,
            "stockholder": 5,
            "shareholders": 6,
            "shareholder": 5,
            "reasonable": 5,
            "reasonably": 5,
        }

        sale = {
            "best value reasonably available": 30,
            "highest value reasonably attainable": 28,
            "change of control": 24,
            "for sale": 15,
            "sale of control": 18,
            "auction": 12,
            "auctioneers": 20,
            "maximize": 12,
            "maximization": 12,
            "stockholders' benefit": 16,
            "shareholders' benefit": 16,
            "revlon duties": 16,
            "sale process": 12,
        }

        oversight = {
            "utter failure": 28,
            "good faith effort": 28,
            "bad faith": 22,
            "reporting system": 20,
            "information and reporting system": 22,
            "red flags": 18,
            "mission critical": 18,
            "central compliance risks": 18,
            "duty of loyalty": 18,
            "conscious failure": 18,
            "conscious disregard": 18,
            "known duty to act": 18,
            "monitor": 12,
            "oversight": 12,
        }

        takeover = {
            "enhanced scrutiny": 24,
            "coercive": 18,
            "preclusive": 18,
            "range of reasonableness": 24,
            "threat to corporate policy": 24,
            "reasonable grounds": 16,
            "defensive measure": 14,
        }

        fairness = {
            "entire fairness": 24,
            "fair dealing": 18,
            "fair price": 18,
            "burden": 8,
        }

        controller = {
            "majority of the minority": 24,
            "special committee": 18,
            "business judgment": 16,
            "controller": 14,
            "from the outset": 14,
        }

        demand = {
            "demand futility": 22,
            "particularized facts": 18,
            "independent and disinterested": 18,
            "reasonable doubt": 14,
            "impartially consider": 14,
            "director-by-director": 14,
        }

        groups = [universal]

        if "sale_of_control" in doctrine_l or any(
            x in source_l
            for x in ["revlon", "qvc", "barkan", "lyondell", "paramount", "metro"]
        ):
            groups.append(sale)

        if "oversight" in doctrine_l or any(
            x in source_l for x in ["caremark", "stone", "marchand"]
        ):
            groups.append(oversight)

        if "takeover_defense" in doctrine_l or any(
            x in source_l for x in ["unocal", "unitrin", "airgas"]
        ):
            groups.append(takeover)

        if "entire_fairness" in doctrine_l or "weinberger" in source_l:
            groups.append(fairness)

        if "controller" in doctrine_l or any(
            x in source_l for x in ["mfw", "tesla", "kahn"]
        ):
            groups.append(controller)

        if "demand_futility" in doctrine_l or any(
            x in source_l for x in ["aronson", "rales", "zuckerberg"]
        ):
            groups.append(demand)

        return groups

    def marker_score(q: str) -> int:
        q = clean_quote(q)
        q_l = q.lower()

        score = 0

        for group in doctrine_marker_groups():
            for marker, weight in group.items():
                if marker in q_l:
                    score += weight

        score += anchor_bonus(q)

        if looks_like_rule(q):
            score += 14
        else:
            score -= 25

        if has_doctrinal_subject(q):
            score += 8
        else:
            score -= 12

        length = len(q.split())

        if 10 <= length <= 32:
            score += 12
        elif 33 <= length <= 52:
            score += 4
        elif length > 60:
            score -= 22

        if q.strip().endswith("."):
            score += 3

        if role_l == "foundation":
            if any(
                x in q_l
                for x in [
                    "must",
                    "duty",
                    "requires",
                    "standard",
                    "best value",
                    "obligation",
                    "utter failure",
                ]
            ):
                score += 12

        if role_l in {"supreme_refinement", "refinement"}:
            if any(
                x in q_l
                for x in [
                    "good faith",
                    "duty of loyalty",
                    "failure to act in good faith",
                    "known duty to act",
                    "conscious disregard",
                    "change of control",
                    "range of reasonableness",
                    "obligation",
                ]
            ):
                score += 18

        if role_l == "modern_application":
            if any(
                x in q_l
                for x in [
                    "mission critical",
                    "central compliance risks",
                    "red flags",
                    "good faith effort",
                    "financial advisors",
                    "sale process",
                    "informed",
                    "reasonable",
                ]
            ):
                score += 14

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
            score -= 12

        score -= sentence_integrity_penalty(q)

        if is_garbage(q):
            score -= 200

        if is_weak_ocr_source():
            score -= 25

            # Only very strong quotes survive from weak OCR sources.
            if anchor_bonus(q) >= 24 or (
                looks_like_rule(q)
                and has_doctrinal_subject(q)
                and sentence_integrity_penalty(q) < 25
            ):
                score += 30

        return score

    # Step 1: canonical anchors first for cornerstone cases and weak OCR sources.
    for source_key, canonical_quotes in CANONICAL_QUOTES.items():
        if source_matches(source_key):
            canonical_scored = []

            for cq in canonical_quotes:
                cq_clean = clean_quote(cq)
                if not cq_clean:
                    continue

                score = marker_score(cq_clean) + 85
                canonical_scored.append((score, cq_clean))

            if canonical_scored:
                canonical_scored.sort(key=lambda item: item[0], reverse=True)
                return canonical_scored[0][1]

    # Step 2: clean all quote candidates.
    cleaned_quotes = []

    for q in quotes or []:
        raw = q.get("quote", q.get("text", "")) if isinstance(q, dict) else str(q)
        cleaned = clean_quote(raw)

        if cleaned:
            cleaned_quotes.append(cleaned)

    # Step 3: hard eligibility filter.
    eligible_quotes = [q for q in cleaned_quotes if hard_eligible(q)]

    # Step 4: score eligible quotes only.
    scored = []

    for q in eligible_quotes:
        score = marker_score(q)

        if score > 10:
            scored.append((score, q))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    return ""
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

            best_quote = clean_quote_text(best_quote)

            if not best_quote or is_bad_quote(best_quote):
                continue

            quote_key = re.sub(r"\s+", " ", best_quote.lower()).strip()

            if quote_key in seen_quotes:
                continue

            seen_quotes.add(quote_key)

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