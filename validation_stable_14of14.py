from __future__ import annotations

from ast import pattern
import re
from typing import Any, Dict, List, Optional, Tuple
from xml.parsers.expat import errors

from ask_stable_10of10_debug import extract_sections
from doctrine_config import DOCTRINE_LABELS
from quotes import normalize_quote_fragment


def get_multi_doctrine_labels(query_plan: Dict[str, Any]) -> List[str]:
    lines = [line for line in query_plan.get("target_lines", []) if line != "unknown"]
    return [DOCTRINE_LABELS.get(line) or line.replace("_", " ").title() for line in lines[:2]]


# ============================================================
# HELPERS
# ============================================================

import re

def extract_sections(ai_answer: str, query_plan: Dict[str, Any]) -> Dict[str, str]:
    text = (ai_answer or "").strip()

    def section_body(name: str) -> str:
        pattern = rf"(?ms)^\s*{re.escape(name)}\s*:\s*(.*?)\s*(?=^\s*[A-Z][A-Za-z\s]+:\s*|\Z)"
        m = re.search(pattern, text)
        return m.group(1).strip() if m else ""

    sections: Dict[str, str] = {
        "text": text,
        "short_answer": section_body("Short Answer"),
        "key_distinction": section_body("Key Distinction"),
        "rule_comparison": section_body("Rule Comparison"),
        "rule": section_body("Rule"),
        "analysis": section_body("Analysis"),
        "confidence": section_body("Confidence"),
    }

    if query_plan.get("multi_doctrine"):
        labels = get_multi_doctrine_labels(query_plan)
        if len(labels) >= 1:
            sections[labels[0].lower()] = section_body(labels[0])
        if len(labels) >= 2:
            sections[labels[1].lower()] = section_body(labels[1])

    return sections


def fragment_present(fragment: str, text: str) -> bool:
    fragment_l = (fragment or "").lower()
    text_l = (text or "").lower()

    if not fragment_l or not text_l:
        return False

    if fragment_l in text_l:
        return True

    frag_words = [w for w in re.findall(r"[a-z]+", fragment_l) if len(w) >= 4]
    text_words = set(re.findall(r"[a-z]+", text_l))
    hits = sum(1 for w in frag_words if w in text_words)
    return hits >= 2


# ============================================================
# SECTION VALIDATORS
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

    real_target_lines = [x for x in target_lines if x and x != "unknown"]
    target_set = set(real_target_lines)

    if not key_distinction:
        return ["Key Distinction is empty"], -12

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", key_distinction)
        if s.strip()
    ]

    # Allow polished judicial phrasing to use two short sentences.
    if len(sentences) > 2:
        errors.append("Key Distinction must be no more than two sentences")
        delta -= 6

    # Keep it concise, but not artificially cramped.
    if len(key_distinction.split()) > 55:
        errors.append("Key Distinction is too long")
        delta -= 4

    contrast_terms = [
        "whereas",
        "while",
        "by contrast",
        "in contrast",
        "distinct",
        "different",
        "addresses",
        "focuses on",
        "governs",
        "instead",
    ]

    if not any(term in kd_l for term in contrast_terms):
        errors.append("Key Distinction must use contrast language")
        delta -= 5

    # -------------------------------------------------
    # Single-doctrine comparison mode
    # Caremark/Marchand, Aronson/Rales, etc.
    # -------------------------------------------------
    if len(real_target_lines) <= 1:
        if target_set == {"oversight"}:
            if not any(term in kd_l for term in [
                "caremark",
                "marchand",
                "stone",
                "oversight",
                "monitor",
                "monitoring",
                "good faith",
                "red flags",
                "mission critical",
                "reporting system",
                "oversight system",
            ]):
                errors.append("Key Distinction must include oversight doctrinal language")
                delta -= 5

        elif target_set == {"demand_futility"}:
            if not any(term in kd_l for term in [
                "aronson",
                "rales",
                "zuckerberg",
                "reasonable doubt",
                "demand",
                "demand futility",
                "impartially consider",
                "disinterested",
                "independent",
            ]):
                errors.append("Key Distinction must include demand-futility doctrinal language")
                delta -= 5

        return errors, delta

    # -------------------------------------------------
    # Multi-doctrine mode
    # -------------------------------------------------
    labels = [
        DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()
        for line in real_target_lines[:2]
    ]

    # Accept formal labels OR common doctrinal case names.
    label_aliases = {
        "controller_transactions": [
            "controller transactions",
            "controller",
            "mfw",
            "special committee",
            "majority of the minority",
            "majority-of-the-minority",
        ],
        "stockholder_vote_cleansing": [
            "stockholder vote cleansing",
            "stockholder vote",
            "corwin",
            "fully informed",
            "uncoerced",
        ],
        "oversight": [
            "oversight",
            "caremark",
            "stone",
            "marchand",
            "good faith",
            "monitor",
            "monitoring",
        ],
        "takeover_defense": [
            "takeover defense",
            "defensive measure",
            "defensive measures",
            "unocal",
            "unitrin",
            "coercive",
            "preclusive",
            "range of reasonableness",
        ],
        "sale_of_control": [
            "sale of control",
            "sale",
            "change of control",
            "revlon",
            "qvc",
            "best value",
            "best value reasonably available",
        ],
        "demand_futility": [
            "demand futility",
            "demand",
            "aronson",
            "rales",
            "zuckerberg",
            "impartially consider",
        ],
        "disclosure_loyalty": [
            "disclosure loyalty",
            "disclosure",
            "malone",
            "truthfully",
            "materially misleading",
            "stockholder communication",
        ],
    }

    def mentions_doctrine(line: str) -> bool:
        aliases = label_aliases.get(
            line,
            [
                DOCTRINE_LABELS.get(line, line.replace("_", " ")).lower(),
                line.replace("_", " "),
            ],
        )
        return any(alias in kd_l for alias in aliases)

    for line in real_target_lines[:2]:
        if not mentions_doctrine(line):
            label = DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()
            errors.append(f"Key Distinction must mention {label}")
            delta -= 4

    # -------------------------------------------------
    # Pair-specific substance
    # -------------------------------------------------
    def has_any(terms: List[str]) -> bool:
        return any(term in kd_l for term in terms)

    if target_set == {"controller_transactions", "stockholder_vote_cleansing"}:
        if not has_any([
            "mfw",
            "special committee",
            "majority-of-the-minority",
            "majority of the minority",
            "controller",
        ]):
            errors.append("Key Distinction must include MFW doctrinal language")
            delta -= 5

        if not has_any([
            "corwin",
            "fully informed",
            "uncoerced",
            "stockholder vote",
        ]):
            errors.append("Key Distinction must include Corwin doctrinal language")
            delta -= 5

    elif target_set == {"oversight", "takeover_defense"}:
        if not has_any([
            "caremark",
            "oversight",
            "good faith",
            "monitor",
            "monitoring",
            "oversight system",
            "red flags",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 5

        if not has_any([
            "unocal",
            "unitrin",
            "coercive",
            "preclusive",
            "range of reasonableness",
            "defensive measure",
            "defensive measures",
        ]):
            errors.append("Key Distinction must include takeover-defense doctrinal language")
            delta -= 5

    elif target_set == {"controller_transactions", "sale_of_control"}:
        if not has_any([
            "mfw",
            "special committee",
            "majority-of-the-minority",
            "majority of the minority",
            "controller",
        ]):
            errors.append("Key Distinction must include controller-transactions doctrinal language")
            delta -= 5

        if not has_any([
            "revlon",
            "qvc",
            "best value reasonably available",
            "best value",
            "change of control",
            "sale",
        ]):
            errors.append("Key Distinction must include sale-of-control doctrinal language")
            delta -= 5

    elif target_set == {"oversight", "sale_of_control"}:
        if not has_any([
            "caremark",
            "oversight",
            "good faith",
            "monitor",
            "monitoring",
            "oversight system",
            "red flags",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 5

        if not has_any([
            "revlon",
            "qvc",
            "best value reasonably available",
            "best value",
            "change of control",
            "sale",
        ]):
            errors.append("Key Distinction must include sale-of-control doctrinal language")
            delta -= 5

    elif target_set == {"demand_futility", "oversight"}:
        if not has_any([
            "aronson",
            "rales",
            "zuckerberg",
            "demand",
            "reasonable doubt",
            "impartially consider",
        ]):
            errors.append("Key Distinction must include demand-futility doctrinal language")
            delta -= 5

        if not has_any([
            "caremark",
            "oversight",
            "good faith",
            "monitor",
            "monitoring",
            "oversight system",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 5

    # Key Distinction should never dominate validation.
    delta = max(delta, -12)
    delta = min(delta, 6)

    return errors, delta

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
    real_target_lines = [x for x in (target_lines or []) if x != "unknown"]
    target_set = set(real_target_lines)

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

    if "whereas" not in s3_l:
        errors.append("Rule Comparison sentence 3 must contain 'whereas'")
        delta -= 6

    # Single-doctrine comparison mode: e.g. Caremark vs Marchand, Aronson vs Rales
    if len(real_target_lines) <= 1:
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

            if not any(term in s2_l for term in [
                "good faith effort to implement an oversight system",
                "good faith effort to implement",
                "monitor",
            ]):
                errors.append("Rule Comparison sentence 2 must state Marchand's monitoring requirement")
                delta -= 8

            if not any(term in rc_l for term in [
                "failure to act in good faith",
                "duty of loyalty",
                "good faith",
            ]):
                errors.append("Rule Comparison must reflect Stone's good-faith refinement")
                delta -= 6

            return errors, delta

        if target_set == {"demand_futility"}:
            if not any(term in rc_l for term in ["aronson", "rales"]):
                errors.append("Rule Comparison must expressly include Aronson and Rales")
                delta -= 8
            if not any(term in rc_l for term in [
                "reasonable doubt",
                "demand",
                "impartially consider",
            ]):
                errors.append("Rule Comparison must include demand-futility doctrinal language")
                delta -= 8
            return errors, delta

        return errors, delta

    # Multi-doctrine mode: first require the actual doctrine labels.
    labels = [
        DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()
        for line in real_target_lines[:2]
    ]
    if len(labels) >= 1 and labels[0].lower() not in rc_l:
        errors.append(f"Rule Comparison must expressly include {labels[0]}")
        delta -= 6
    if len(labels) >= 2 and labels[1].lower() not in rc_l:
        errors.append(f"Rule Comparison must expressly include {labels[1]}")
        delta -= 6

    # Exact pair enforcement only.
    if target_set == {"controller_transactions", "stockholder_vote_cleansing"}:
        if not any(term in rc_l for term in [
            "mfw", "special committee", "majority-of-the-minority", "majority of the minority",
            "controller",
        ]):
            errors.append("Rule Comparison must include MFW doctrinal language")
            delta -= 8
        if not any(term in rc_l for term in [
            "corwin", "fully informed", "uncoerced", "stockholder vote",
        ]):
            errors.append("Rule Comparison must include Corwin doctrinal language")
            delta -= 8

    elif target_set == {"oversight", "takeover_defense"}:
        if not any(term in rc_l for term in [
            "caremark", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Rule Comparison must include oversight doctrinal language")
            delta -= 8
        if not any(term in rc_l for term in [
            "unocal", "coercive", "preclusive", "range of reasonableness", "defensive measures",
        ]):
            errors.append("Rule Comparison must include takeover-defense doctrinal language")
            delta -= 8

    elif target_set == {"controller_transactions", "sale_of_control"}:
        if not any(term in rc_l for term in [
            "mfw", "special committee", "majority-of-the-minority", "majority of the minority",
            "controller",
        ]):
            errors.append("Rule Comparison must include controller-transactions doctrinal language")
            delta -= 8
        if not any(term in rc_l for term in [
            "revlon", "qvc", "best value reasonably available", "change of control", "sale",
        ]):
            errors.append("Rule Comparison must include sale-of-control doctrinal language")
            delta -= 8

    elif target_set == {"oversight", "sale_of_control"}:
        if not any(term in rc_l for term in [
            "caremark", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Rule Comparison must include oversight doctrinal language")
            delta -= 8
        if not any(term in rc_l for term in [
            "revlon", "qvc", "best value reasonably available", "change of control", "sale",
        ]):
            errors.append("Rule Comparison must include sale-of-control doctrinal language")
            delta -= 8

    elif target_set == {"demand_futility", "oversight"}:
        if not any(term in rc_l for term in [
            "aronson", "rales", "demand", "reasonable doubt", "impartially consider",
        ]):
            errors.append("Rule Comparison must include demand-futility doctrinal language")
            delta -= 8
        if not any(term in rc_l for term in [
            "caremark", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Rule Comparison must include oversight doctrinal language")
            delta -= 8

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
    
    if len(target_lines) >= 2:
        if not any(term in analysis_l for term in ["good faith", "mfw", "monitor", "duty of loyalty"]):
            errors.append("Analysis must include doctrinal anchor language")
        delta -= 6

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
            if oversight_hits < 2:
                errors.append("Analysis must reflect at least two doctrinal anchor fragments")
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

    real_target_lines = [x for x in target_lines if x and x != "unknown"]
    target_set = set(real_target_lines)

    # Only enforce quote grounding strictly where it is stable enough to help.
    # Other validators already handle multi-doctrine structure and non-oversight doctrines.
    oversight_mode = target_set == {"oversight"}

    if not oversight_mode:
        return errors, delta

    # -------------------------------------------------
    # Canonical trusted anchors
    # -------------------------------------------------
    canonical_anchors_by_doctrine = {
        "oversight": {
            "foundation": [
                "utter failure to attempt to assure",
                "sustained or systematic failure",
                "reporting or information system exists",
            ],
            "supreme_refinement": [
                "failure to act in good faith",
                "subsidiary element of the duty of loyalty",
                "duty of loyalty",
                "conscious disregard",
            ],
            "modern_application": [
                "good faith effort to implement an oversight system",
                "good faith effort to implement",
                "mission critical",
                "red flags",
            ],
        }
    }

    bad_grounding_patterns = [
        "decessor",
        "memhoe",
        "condiregulatory",
        "insmall",
        "prevent grounds deception",
        "vice payments",
        "federal antito",
        "bers consist",
        "caremark decessor",
        "deriv were necessary",
        "caremark means anything",
        "committee insmall",
        "refiduciary",
        "olated",
        "substan",
        "charac 10 view",
    ]

    def clean_fragment(fragment: str) -> str:
        fragment = re.sub(r"\s+", " ", (fragment or "").lower()).strip()
        fragment = fragment.strip(" .,:;\"'")
        return fragment

    def is_bad_fragment(fragment: str) -> bool:
        f = clean_fragment(fragment)

        if not f:
            return True

        if any(p in f for p in bad_grounding_patterns):
            return True

        if len(f.split()) < 3:
            return True

        if len(f.split()) > 14:
            return True

        if re.search(r"\b[a-z]{14,}\b", f):
            return True

        if re.search(r"\b[a-z]{1,2}\s+[a-z]{1,2}\s+[a-z]{1,2}\b", f):
            return True

        alpha_chars = len(re.findall(r"[a-z]", f))
        if alpha_chars / max(len(f), 1) < 0.70:
            return True

        return False

    def trusted_fragments_for_role(role: str, quote: str) -> List[str]:
        quote_l = clean_fragment(quote)
        trusted: List[str] = []

        for anchor in canonical_anchors_by_doctrine["oversight"].get(role, []):
            if anchor in quote_l:
                trusted.append(anchor)

        # If the quote fragment normalizer found one of the canonical anchors, accept it.
        normalized = clean_fragment(normalize_quote_fragment(role, quote))
        for anchors in canonical_anchors_by_doctrine["oversight"].values():
            for anchor in anchors:
                if normalized == anchor or anchor in normalized:
                    trusted.append(anchor)

        return list(dict.fromkeys(trusted))

    fragments: Dict[str, Dict[str, str]] = {}

    for role, item in role_quote_map.items():
        quote = item.get("quote", "") if isinstance(item, dict) else ""

        if not quote:
            continue

        # Never allow OCR-derived garbage fragments to become validator requirements.
        normalized = clean_fragment(normalize_quote_fragment(role, quote))
        if normalized and is_bad_fragment(normalized):
            continue

        trusted = trusted_fragments_for_role(role, quote)

        if not trusted:
            continue

        # Use the strongest trusted anchor for this role.
        fragment = trusted[0]

        if is_bad_fragment(fragment):
            continue

        fragments[role] = {
            "case": item.get("case", role),
            "fragment": fragment,
        }

    # If no trusted fragments exist, do not penalize the answer.
    # Missing quote grounding should not tank otherwise sound legal analysis.
    if not fragments:
        return errors, delta

    # -------------------------------------------------
    # Rule grounding
    # -------------------------------------------------
    rule_hits = 0

    for role, item in fragments.items():
        fragment = item["fragment"]
        case_name = item["case"]

        if fragment_present(fragment, rule_text):
            rule_hits += 1
            delta += 3
        else:
            # Light penalty only. This validator should not dominate the score.
            errors.append(
                f'Rule missing trusted grounded fragment: {case_name} ({role}) -> "{fragment}"'
            )
            delta -= 2

    # -------------------------------------------------
    # Rule Comparison grounding
    # -------------------------------------------------
    if query_type == "comparison":
        rc_hits = 0

        for role, item in fragments.items():
            fragment = item["fragment"]
            case_name = item["case"]

            if fragment_present(fragment, rule_comparison_text):
                rc_hits += 1
                delta += 3
            else:
                errors.append(
                    f'Rule Comparison missing trusted grounded fragment: {case_name} ({role}) -> "{fragment}"'
                )
                delta -= 2

        if rc_hits == 0 and fragments:
            errors.append("Rule Comparison must include at least one trusted doctrinal anchor")
            delta -= 2

    # -------------------------------------------------
    # Analysis grounding
    # -------------------------------------------------
    analysis_hits = 0

    for item in fragments.values():
        if fragment_present(item["fragment"], analysis_text):
            analysis_hits += 1

    if analysis_hits >= 1:
        delta += 3
    else:
        # Light penalty: analysis style validators already handle structure.
        errors.append("Analysis should reflect at least one trusted doctrinal anchor")
        delta -= 2

    # -------------------------------------------------
    # Safety cap: quote grounding should help or lightly adjust, not dominate.
    # -------------------------------------------------
    delta = max(delta, -8)
    delta = min(delta, 12)

    return errors, delta

def validate_style_lock(
    text: str,
    sections: Dict[str, str],
    query_plan: Dict[str, Any],
) -> Tuple[List[str], int]:
    errors: List[str] = []
    delta = 0

    full_text = (text or "").lower()
    target_lines = [x for x in query_plan.get("target_lines", []) if x != "unknown"]

    # Hard ban obvious contaminated quote / OCR / secondary-source leakage
    forbidden_fragments = [
        "j.corp.law",
        "corp.law",
        "fordham",
        "law review",
        "journal",
        "article",
        "citation",
        "laster",
        "blatt",
        "zelett",
        "strip-casting",
        "ha-",
        "in this views",
        "found application",
        "travis",
        "supra",
        "infra",
    ]

    for frag in forbidden_fragments:
        if frag in full_text:
            errors.append(f"Output contains contaminated source fragment: {frag}")
            delta -= 15

    # Ban casual / summarizer language
    forbidden_style = [
        "this case shows",
        "the court held",
        "the court explained",
        "the court stated",
        "in simple terms",
        "basically",
        "it means that",
        "this means that",
    ]

    for phrase in forbidden_style:
        if phrase in full_text:
            errors.append(f"Output contains non-court style phrase: {phrase}")
            delta -= 8

    # Rule must not be bloated
    rule = (sections.get("rule", "") or "").strip()
    if rule:
        rule_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", rule) if s.strip()]
        if len(rule_sentences) > 3:
            errors.append("Rule is too long; must be no more than three sentences")
            delta -= 10

    # Analysis must stay exactly three sentences in Structured mode
    analysis = (sections.get("analysis", "") or "").strip()
    if analysis:
        analysis_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", analysis) if s.strip()]
        if len(analysis_sentences) != 3:
            errors.append("Analysis must remain exactly three sentences")
            delta -= 10

    # Detect near-duplicate sentences across Rule + Analysis
    combined = " ".join([
        sections.get("rule", "") or "",
        sections.get("analysis", "") or "",
        sections.get("rule_comparison", "") or "",
    ])

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", combined) if len(s.split()) >= 7]

    def sig(sentence: str) -> set[str]:
        stop = {
            "the", "a", "an", "and", "or", "of", "to", "for", "in", "on",
            "that", "this", "where", "when", "with", "under", "doctrine",
            "directors", "board", "must", "requires", "require",
        }
        return {
            w for w in re.findall(r"[a-z]+", sentence.lower())
            if len(w) >= 4 and w not in stop
        }

    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            a = sig(sentences[i])
            b = sig(sentences[j])
            if not a or not b:
                continue
            overlap = len(a & b) / max(1, min(len(a), len(b)))
            if overlap >= 0.75:
                errors.append("Output contains repetitive rule/analysis sentence")
                delta -= 8
                return errors, delta

    # Doctrine-specific anchor lock
    target_set = set(target_lines)
    if "sale_of_control" in target_set:
        needed = ["change of control", "best value reasonably available"]
        for phrase in needed:
            if phrase not in full_text:
                errors.append(f"Sale-of-control answer missing required phrase: {phrase}")
                delta -= 8

    if "entire_fairness" in target_set:
        needed = ["entire fairness", "fair dealing", "fair price"]
        for phrase in needed:
            if phrase not in full_text:
                errors.append(f"Entire-fairness answer missing required phrase: {phrase}")
                delta -= 8

    if "takeover_defense" in target_set:
        needed_any = ["coercive", "preclusive", "range of reasonableness"]
        if sum(1 for phrase in needed_any if phrase in full_text) < 2:
            errors.append("Takeover-defense answer missing coercive/preclusive/range-of-reasonableness anchors")
            delta -= 10

    if "stockholder_vote_cleansing" in target_set:
        needed = ["fully informed", "uncoerced"]
        for phrase in needed:
            if phrase not in full_text:
                errors.append(f"Stockholder-vote-cleansing answer missing required phrase: {phrase}")
                delta -= 8

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
    target_lines = query_plan.get("target_lines", []) or []
    target_set = {x for x in target_lines if x and x != "unknown"}
    multi_doctrine = bool(query_plan.get("multi_doctrine", False))

    text_l = text.lower()

    # -------------------------------------------------
    # Normalize Caremark/Marchand as oversight evolution.
    # This prevents single-doctrine oversight evolution from
    # being punished by ordinary comparison validators.
    # -------------------------------------------------
    caremark_marchand_evolution = (
        target_set == {"oversight"}
        and "caremark" in text_l
        and "marchand" in text_l
    )

    if caremark_marchand_evolution:
        query_type = "doctrine_evolution"
        multi_doctrine = False

    sections = extract_sections(ai_answer, query_plan)

    errors: List[str] = []
    score = 100

    def add_error(message: str, penalty: int) -> None:
        nonlocal score
        errors.append(message)
        score -= penalty

    def apply_result(result: Tuple[List[str], int], max_penalty: Optional[int] = None) -> None:
        nonlocal score, errors

        section_errors, delta = result

        if delta < 0 and max_penalty is not None:
            delta = max(delta, -abs(max_penalty))

        score += delta

        if delta < 0 and section_errors:
            errors.extend(section_errors)

    # -------------------------------------------------
    # Basic doctrine recognition
    # -------------------------------------------------
    if not target_set:
        add_error("Query did not map to a recognized doctrine", 40)

    # -------------------------------------------------
    # Required section enforcement
    # -------------------------------------------------
    required_sections = ["short_answer", "analysis", "confidence"]

    if query_type == "comparison" and multi_doctrine:
        labels = get_multi_doctrine_labels(query_plan)
        label_a = labels[0] if len(labels) >= 1 else "Doctrine A"
        label_b = labels[1] if len(labels) >= 2 else "Doctrine B"

        required_sections.extend(
            [
                "key_distinction",
                label_a.lower(),
                label_b.lower(),
                "rule_comparison",
            ]
        )

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
        for label in labels[:2]:
            section_name_map[label.lower()] = label

    for key in required_sections:
        if not sections.get(key, "").strip():
            section_label = section_name_map.get(key, key.replace("_", " ").title())
            add_error(f"Missing section: {section_label}", 20)

    # -------------------------------------------------
    # Confidence format
    # -------------------------------------------------
    confidence = sections.get("confidence", "").strip()

    if confidence:
        confidence_clean = confidence.rstrip(".").strip()
        if confidence_clean not in {"High", "Medium", "Low"}:
            add_error("Confidence must be exactly one word: High, Medium, or Low", 8)

    # -------------------------------------------------
    # Section validators
    # -------------------------------------------------
    apply_result(
        validate_short_answer(
            sections,
            query_type=query_type,
            target_lines=target_lines,
        ),
        max_penalty=18,
    )

    apply_result(
        validate_key_distinction(
            sections,
            query_type=query_type,
            target_lines=target_lines,
        ),
        max_penalty=18,
    )

    if query_type == "comparison" and not caremark_marchand_evolution:
        apply_result(
            validate_rule_comparison_v2(
                sections,
                query_type=query_type,
                tree_result=tree_result,
                target_lines=target_lines,
            ),
            max_penalty=25,
        )
    else:
        apply_result(
            validate_rule_v2(
                sections,
                query_type=query_type,
                target_lines=target_lines,
            ),
            max_penalty=25,
        )

    apply_result(
        validate_analysis(
            sections,
            query_type=query_type,
            target_lines=target_lines,
            tree_result=tree_result,
        ),
        max_penalty=25,
    )

    apply_result(
        validate_quote_grounding(
            sections,
            query_type=query_type,
            role_quote_map=role_quote_map,
            target_lines=target_lines,
        ),
        max_penalty=18,
    )

    apply_result(
        validate_style_lock(
            text,
            sections,
            query_plan,
        ),
        max_penalty=20,
    )

    # -------------------------------------------------
    # Caremark/Marchand bonus stabilization
    # -------------------------------------------------
    if caremark_marchand_evolution:
        required_fragments = [
            "utter failure",
            "good faith",
            "mission-critical",
        ]

        hits = sum(1 for frag in required_fragments if frag in text_l)

        if hits >= 2:
            score += 8

        if "rule comparison" in text_l:
            score += 4

    # -------------------------------------------------
    # Forbidden leaked UI / debug sections
    # -------------------------------------------------
    forbidden_outputs = {
        "quoted authority": 10,
        "supporting cases": 6,
        "citation + quote map": 6,
        "doctrinal thread": 6,
        "validation score": 8,
        "debug": 10,
        "query plan": 8,
        "sources_used": 8,
    }

    for phrase, penalty in forbidden_outputs.items():
        if phrase in text_l:
            add_error(f"Model output included forbidden UI/debug text: {phrase}", penalty)

    # -------------------------------------------------
    # Basic answer hygiene
    # -------------------------------------------------
    if "```" in text:
        add_error("Model output included code fencing", 8)

    if len(text.split()) < 18:
        add_error("Answer is too short to provide legal reasoning", 15)

    if text.count("\n\n\n") >= 1:
        add_error("Answer contains excessive blank spacing", 4)

    # -------------------------------------------------
    # Multi-doctrine sanity checks
    # -------------------------------------------------
    if multi_doctrine and len(target_set) >= 2:
        normalized_text = text_l.replace("-", "_").replace(" ", "_")

        missing_doctrines = []
        for doctrine in target_set:
            doctrine_label = doctrine.replace("_", " ")
            doctrine_token = doctrine.replace("_", " ")

            if (
                doctrine not in normalized_text
                and doctrine_label not in text_l
                and doctrine_token not in text_l
            ):
                missing_doctrines.append(doctrine)

        if missing_doctrines:
            add_error(
                "Multi-doctrine answer failed to address: "
                + ", ".join(sorted(missing_doctrines)),
                12,
            )

    # -------------------------------------------------
    # Deduplicate errors
    # -------------------------------------------------
    deduped_errors: List[str] = []
    seen = set()

    for err in errors:
        if err not in seen:
            deduped_errors.append(err)
            seen.add(err)

    score = max(0, min(100, score))

    is_valid = len(deduped_errors) == 0
    return is_valid, deduped_errors, score