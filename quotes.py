from __future__ import annotations

import re
from typing import Any, Dict, List, Set


def _normalize_quote_text(text: str) -> str:
    text = (text or "").replace("\n", " ").replace("\xad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(' "\'')


def extract_case_quotes_from_text(text: str) -> List[str]:
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    clean: List[str] = []

    doctrinal_markers = [
        "must",
        "requires",
        "good faith",
        "duty of loyalty",
        "business judgment",
        "entire fairness",
        "fully informed",
        "uncoerced",
        "special committee",
        "majority of the minority",
        "reporting system",
        "oversight system",
        "reasonable doubt",
        "best value reasonably available",
        "coercive",
        "preclusive",
        "change of control",
    ]

    bad_markers = [
        "court:",
        "year:",
        "doctrine:",
        "authority:",
        "key topic:",
        "section:",
    ]

    for sentence in sentences:
        sentence = _normalize_quote_text(sentence)
        sentence_l = sentence.lower()

        if len(sentence.split()) < 8:
            continue
        if any(bad in sentence_l for bad in bad_markers):
            continue
        if any(marker in sentence_l for marker in doctrinal_markers):
            clean.append(sentence)

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
            quote_norm = re.sub(r"\s+", " ", quote.strip().lower())
            if not quote_norm or quote_norm in seen:
                continue
            seen.add(quote_norm)
            deduped.append(quote.strip())
            if len(deduped) >= max_quotes_per_case:
                break

        if deduped:
            result[source] = deduped
        elif source in fallback_quotes:
            result[source] = [fallback_quotes[source]]

    return result


def is_valid_doctrinal_quote(quote: str) -> bool:
    if not quote:
        return False

    quote_l = quote.lower()
    doctrinal_markers = [
        "must",
        "requires",
        "duty",
        "standard",
        "review",
        "fully informed",
        "uncoerced",
        "business judgment",
        "entire fairness",
        "controller",
        "good faith",
        "oversight system",
        "reporting system",
        "reasonable doubt",
        "change of control",
        "coercive",
        "preclusive",
    ]
    return any(marker in quote_l for marker in doctrinal_markers)


def pick_best_quote(quotes: List[str], source: str = "") -> str:
    if not quotes:
        return ""

    source_l = (source or "").lower()

    def is_garbage(quote: str) -> bool:
        quote = (quote or "").strip()
        quote_l = quote.lower()

        if not quote:
            return True
        if len(quote.split()) < 8:
            return True
        if any(marker in quote_l for marker in [
            "court:",
            "year:",
            "doctrine:",
            "authority:",
            "key topic:",
            "section:",
            "case:",
            "the court held",
            "the court explained",
            "the court stated",
            "plaintiff",
            "complaint",
            "motion to dismiss",
            "rescissory damages",
        ]):
            return True
        return False

    def is_doctrinal(quote: str) -> bool:
        quote_l = quote.lower()
        doctrinal_markers = [
            "must",
            "requires",
            "business judgment",
            "entire fairness",
            "fully informed",
            "uncoerced",
            "special committee",
            "majority of the minority",
            "controller",
            "duty of loyalty",
            "good faith",
            "monitor",
            "oversight system",
            "reporting system",
            "reasonable doubt",
            "best value reasonably available",
            "range of reasonableness",
            "coercive",
            "preclusive",
            "change of control",
        ]
        return any(marker in quote_l for marker in doctrinal_markers)

    def score(quote: str) -> float:
        quote_l = quote.lower()
        num_words = len(quote.split())
        score_value = 0.0

        if 10 <= num_words <= 40:
            score_value += 3.0
        elif 8 <= num_words <= 55:
            score_value += 1.5

        for marker in [
            "must",
            "requires",
            "business judgment",
            "entire fairness",
            "fully informed",
            "uncoerced",
            "special committee",
            "majority of the minority",
            "controller",
            "duty of loyalty",
            "good faith",
            "monitor",
            "oversight system",
            "reporting system",
            "reasonable doubt",
            "best value reasonably available",
            "range of reasonableness",
            "coercive",
            "preclusive",
            "change of control",
        ]:
            if marker in quote_l:
                score_value += 2.0

        if "caremark" in source_l and "utter failure to attempt to assure" in quote_l:
            score_value += 10
        if "stone" in source_l and "failure to act in good faith" in quote_l:
            score_value += 10
        if "marchand" in source_l:
            if "good faith effort" in quote_l:
                score_value += 10
            if "implement an oversight system" in quote_l:
                score_value += 8
        if "mfw" in source_l:
            if "special committee" in quote_l:
                score_value += 4
            if "majority of the minority" in quote_l:
                score_value += 4
            if "business judgment" in quote_l:
                score_value += 3
        if "corwin" in source_l:
            if "fully informed" in quote_l:
                score_value += 4
            if "uncoerced" in quote_l:
                score_value += 4
            if "business judgment" in quote_l:
                score_value += 4
        if "unocal" in source_l and "threat to corporate policy and effectiveness" in quote_l:
            score_value += 6
        if "unitrin" in source_l:
            if "coercive" in quote_l:
                score_value += 4
            if "preclusive" in quote_l:
                score_value += 4
        if "qvc" in source_l and "change of control" in quote_l:
            score_value += 6
        if "revlon" in source_l and "best value reasonably available" in quote_l:
            score_value += 6
        if "aronson" in source_l and "reasonable doubt" in quote_l:
            score_value += 6
        if "rales" in source_l and "impartially consider" in quote_l:
            score_value += 6
        if "zuckerberg" in source_l and "director-by-director" in quote_l:
            score_value += 6
        if "malone" in source_l:
            if "truthfully" in quote_l:
                score_value += 5
            if "materially misleading" in quote_l:
                score_value += 5

        return score_value

    clean_quotes = [quote.strip() for quote in quotes if not is_garbage(quote)]
    if not clean_quotes:
        return ""

    doctrinal_quotes = [quote for quote in clean_quotes if is_doctrinal(quote)]
    candidates = doctrinal_quotes if doctrinal_quotes else clean_quotes

    ranked = sorted(candidates, key=score, reverse=True)
    best_quote = ranked[0].strip()

    if best_quote and best_quote[-1] not in ".!?":
        best_quote += "."

    return best_quote


def normalize_quote_fragment(role: str, quote: str) -> str:
    quote_l = _normalize_quote_text(quote).lower()

    patterns_by_role = {
        "foundation": [
            "utter failure to attempt to assure",
            "sustained or systematic failure",
            "reporting or information system exists",
            "entire fairness is the standard of review",
            "fully informed and uncoerced vote of disinterested stockholders invokes business judgment review",
            "once the corporation is for sale",
            "reasonable grounds for believing that a threat to corporate policy and effectiveness existed",
            "demand is excused where particularized facts create a reasonable doubt",
            "directors who communicate with stockholders owe a duty to speak truthfully and completely",
        ],
        "supreme_refinement": [
            "failure to act in good faith",
            "subsidiary element of the duty of loyalty",
            "duty of loyalty",
            "neither coercive nor preclusive",
            "the duty applies when a transaction will result in a change of control",
            "a majority of the board could impartially consider a demand",
            "disclosure that is materially misleading may constitute a breach of the duty of loyalty",
        ],
        "modern_application": [
            "good faith effort to implement an oversight system",
            "conscious failure to monitor",
            "breach of the duty of loyalty",
            "mission critical",
            "within a range of reasonableness",
            "business judgment deference is unavailable if the mfw conditions are not satisfied",
            "the vote must be uncoerced",
            "directors satisfy their duties if they act reasonably to secure the best value reasonably available",
            "director-by-director",
            "directors may not knowingly disseminate false information to stockholders",
        ],
    }

    for pattern in patterns_by_role.get(role, []):
        if pattern in quote_l:
            return pattern

    words = re.findall(r"\b[a-z]{4,}\b", quote_l)
    return " ".join(words[:8]).strip()


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
            best_quote = pick_best_quote(filtered_quotes, source) if filtered_quotes else ""

            if not best_quote:
                continue

            quote_key = best_quote.lower().strip()
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