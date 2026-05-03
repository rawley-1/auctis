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
    real_target_lines = [x for x in target_lines if x != "unknown"]
    target_set = set(real_target_lines)

    if not key_distinction:
        return ["Key Distinction is empty"], -12

    sentences = [s.strip() for s in re.split(r"[.!?]+", key_distinction) if s.strip()]
    if len(sentences) != 1:
        errors.append("Key Distinction must be exactly one sentence")
        delta -= 8

    if len(key_distinction.split()) > 38:
        errors.append("Key Distinction is too long")
        delta -= 4

    if "whereas" not in kd_l:
        errors.append("Key Distinction must use 'whereas'")
        delta -= 6

    # Single-doctrine comparison mode: Caremark vs Marchand, Aronson vs Rales, etc.
    # Only enforce doctrine-specific substance for the doctrine actually in play.
    if len(real_target_lines) <= 1:
        if target_set == {"oversight"}:
            if not any(term in kd_l for term in [
                "caremark", "marchand", "oversight", "monitor", "good faith",
                "implementation", "monitoring",
            ]):
                errors.append("Key Distinction must include oversight doctrinal language")
                delta -= 6
        elif target_set == {"demand_futility"}:
            if not any(term in kd_l for term in [
                "aronson", "rales", "reasonable doubt", "demand", "impartially consider",
            ]):
                errors.append("Key Distinction must include demand-futility doctrinal language")
                delta -= 6
        return errors, delta

    # Multi-doctrine mode: first require the actual doctrine labels.
    labels = [
        DOCTRINE_LABELS.get(line) or line.replace("_", " ").title()
        for line in real_target_lines[:2]
    ]
    if len(labels) >= 1 and labels[0].lower() not in kd_l:
        errors.append(f"Key Distinction must mention {labels[0]}")
        delta -= 5
    if len(labels) >= 2 and labels[1].lower() not in kd_l:
        errors.append(f"Key Distinction must mention {labels[1]}")
        delta -= 5

    # Pair-specific enforcement: ONLY for the exact pair being compared.
    if target_set == {"controller_transactions", "stockholder_vote_cleansing"}:
        if not any(term in kd_l for term in [
            "mfw", "special committee", "majority-of-the-minority", "majority of the minority",
            "controller",
        ]):
            errors.append("Key Distinction must include MFW doctrinal language")
            delta -= 6
        if not any(term in kd_l for term in [
            "corwin", "fully informed", "uncoerced", "stockholder vote",
        ]):
            errors.append("Key Distinction must include Corwin doctrinal language")
            delta -= 6

    elif target_set == {"oversight", "takeover_defense"}:
        if not any(term in kd_l for term in [
            "caremark", "oversight", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 6
        if not any(term in kd_l for term in [
            "unocal", "coercive", "preclusive", "range of reasonableness", "defensive measures",
        ]):
            errors.append("Key Distinction must include takeover-defense doctrinal language")
            delta -= 6

    elif target_set == {"controller_transactions", "sale_of_control"}:
        if not any(term in kd_l for term in [
            "mfw", "special committee", "majority-of-the-minority", "majority of the minority",
            "controller",
        ]):
            errors.append("Key Distinction must include controller-transactions doctrinal language")
            delta -= 6
        if not any(term in kd_l for term in [
            "revlon", "qvc", "best value reasonably available", "change of control", "sale",
        ]):
            errors.append("Key Distinction must include sale-of-control doctrinal language")
            delta -= 6

    elif target_set == {"oversight", "sale_of_control"}:
        if not any(term in kd_l for term in [
            "caremark", "oversight", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 6
        if not any(term in kd_l for term in [
            "revlon", "qvc", "best value reasonably available", "change of control", "sale",
        ]):
            errors.append("Key Distinction must include sale-of-control doctrinal language")
            delta -= 6

    elif target_set == {"demand_futility", "oversight"}:
        if not any(term in kd_l for term in [
            "aronson", "rales", "demand", "reasonable doubt", "impartially consider",
        ]):
            errors.append("Key Distinction must include demand-futility doctrinal language")
            delta -= 6
        if not any(term in kd_l for term in [
            "caremark", "oversight", "good faith", "monitor", "oversight system",
        ]):
            errors.append("Key Distinction must include oversight doctrinal language")
            delta -= 6

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

    # Only enforce trusted doctrinal anchors.
    allowed_fragments = {
        "utter failure to attempt to assure",
        "sustained or systematic failure",
        "reporting or information system exists",
        "failure to act in good faith",
        "subsidiary element of the duty of loyalty",
        "duty of loyalty",
        "good faith effort to implement an oversight system",
        "good faith effort to implement",
        "conscious failure to monitor",
        "consciously fail to monitor",
        "mission critical",
        "fully informed",
        "uncoerced",
        "majority of the minority",
        "special committee",
        "business judgment review applies",
        "best value reasonably available",
        "coercive",
        "preclusive",
        "range of reasonableness",
        "reasonable doubt",
        "impartially consider",
    }

    fragments: Dict[str, Dict[str, str]] = {}
    for role, item in role_quote_map.items():
        fragment = normalize_quote_fragment(role, item.get("quote", ""))
        if fragment and fragment in allowed_fragments:
            fragments[role] = {
                "case": item.get("case", role),
                "fragment": fragment,
            }

    if not fragments:
        return errors, delta

    real_target_lines = [x for x in target_lines if x != "unknown"]
    oversight_mode = "oversight" in real_target_lines and len(real_target_lines) <= 1

    # Only do strict quote-grounding enforcement for single-doctrine oversight mode.
    # Multi-doctrine comparisons are better handled by the other section validators.
    if not oversight_mode:
        return errors, delta

    # Rule grounding: reward real doctrinal anchors, lightly penalize only if we had a trusted fragment.
    for role, item in fragments.items():
        fragment = item["fragment"]
        case_name = item["case"]

        if fragment_present(fragment, rule_text):
            delta += 4
        else:
            errors.append(f'Rule missing grounded fragment: {case_name} ({role}) -> "{fragment}"')
            delta -= 4

    # In oversight comparison mode, also ground Rule Comparison.
    if query_type == "comparison":
        for role, item in fragments.items():
            fragment = item["fragment"]
            case_name = item["case"]

            if fragment_present(fragment, rule_comparison_text):
                delta += 4
            else:
                errors.append(f'Rule Comparison missing grounded fragment: {case_name} ({role}) -> "{fragment}"')
                delta -= 4

    # Analysis only needs at least one real doctrinal anchor, not every fragment.
    analysis_hits = 0
    for item in fragments.values():
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
    target_lines = query_plan.get("target_lines", [])

    sections = extract_sections(ai_answer, query_plan)
    print("\n🔥 DEBUG RULE SECTION:")
    print(sections.get("rule"))
    print("🔥 END RULE SECTION\n")

    errors: List[str] = []
    score = 100

    if not target_lines or "unknown" in target_lines:
        errors.append("Query did not map to a recognized doctrine")
        score -= 40

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
    apply_result(
        validate_style_lock(
            text,
            sections,
            query_plan,
        )
    )

    if not target_lines or "unknown" in target_lines:
        errors.append("Query did not map to a recognized doctrine")
        score -= 40

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

    is_valid = len(deduped_errors) == 0
    return is_valid, deduped_errors, score