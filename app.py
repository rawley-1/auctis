import streamlit as st
from index_loader import ensure_index_exists
import re

ensure_index_exists()
import os
import streamlit as st

try:
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

from ask import run_query
from ask import run_query

st.set_page_config(page_title="Auctis", layout="wide")


if "show_demo" not in st.session_state:
    st.session_state["show_demo"] = False

if "question" not in st.session_state:
    st.session_state["question"] = ""

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None


def link_cited_cases(answer: str, case_cards: list) -> str:
    html = answer or ""

    for card in case_cards or []:
        name = card.get("name", "")
        anchor = card.get("anchor", name.lower().replace(" ", "-"))

        if not name:
            continue

        html = html.replace(
            name,
            f'<a href="#{anchor}" style="color:#22C55E; font-weight:700; text-decoration:none;">{name}</a>',
        )

    return html


import re


def highlight_quote_in_context(context: str, quote: str) -> str:
    if not context or not quote:
        return context or ""

    # Clean both
    clean_quote = " ".join(quote.split())
    clean_context = context

    # Try exact match first (best case)
    if clean_quote in clean_context:
        return clean_context.replace(
            clean_quote,
            f'<mark style="background:rgba(34,197,94,0.25); padding:2px 4px; border-radius:4px;">{clean_quote}</mark>',
        )

    # Otherwise: find strongest doctrinal fragment (not the beginning)
    words = clean_quote.split()

    # prioritize middle of quote (skip headers / metadata)
    mid = len(words) // 2
    window = words[mid : mid + 8]

    if len(window) < 4:
        window = words[:8]

    fragment = " ".join(window)

    pattern = re.escape(fragment)

    return re.sub(
        pattern,
        f'<mark style="background:rgba(34,197,94,0.25); padding:2px 4px; border-radius:4px;">{fragment}</mark>',
        clean_context,
        flags=re.IGNORECASE,
    )


def case_preview_map(case_cards: list) -> dict:
    previews = {}

    for card in case_cards or []:
        name = card.get("name", "")
        why = card.get("why_matters", "")
        quote = card.get("quote", "")
        role = card.get("role", "")

        if not name:
            continue

        preview = f"{role}. {why}"
        if quote:
            preview += f" Key quote: {quote[:180]}..."

        previews[name] = preview

    return previews


def cited_cases_from_answer(answer: str) -> set[str]:
    known = {
        "Revlon",
        "QVC",
        "Unocal",
        "Unitrin",
        "Weinberger",
        "MFW",
        "Corwin",
        "Caremark",
        "Stone",
        "Marchand",
        "Aronson",
        "Rales",
        "Zuckerberg",
        "Malone",
        "Blasius",
        "Schnell",
        "Section 220",
    }
    return {case for case in known if case in (answer or "")}


def score_color(score):
    score = int(score or 0)
    if score >= 85:
        return "#22C55E"
    if score >= 70:
        return "#FACC15"
    return "#EF4444"


def highlight_quote_in_answer(answer: str, role_quote_map: dict) -> str:
    html = answer or ""

    for role, item in (role_quote_map or {}).items():
        quote = item.get("quote", "")
        case = item.get("case", "")

        if not quote or not case:
            continue

        short = " ".join(quote.split()[:6])

        if short in html:
            html = html.replace(
                short,
                f'<mark title="{case}" style="background:rgba(59,130,246,0.25); padding:2px 4px; border-radius:4px;">{short}</mark>',
            )

    return html


st.markdown(
    """
<style>
.big-title {
    font-size: 4rem;
    font-weight: 800;
    color: #F4F7FB;
    line-height: 1.05;
}
.subtitle {
    font-size: 1.2rem;
    color: rgba(255,255,255,0.7);
    max-width: 820px;
    margin-top: 1rem;
}
.section-card {
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    padding: 1.4rem;
    border: 1px solid rgba(255,255,255,0.08);
}
.label {
    color: #22C55E;
    font-weight: 700;
    margin-bottom: 0.5rem;
}
.value {
    color: rgba(255,255,255,0.75);
}
.case-chip {
    display:inline-block;
    background: rgba(34,197,94,0.1);
    color: #22C55E;
    padding: 7px 12px;
    margin: 5px;
    border-radius: 9px;
    font-size: 0.88rem;
    font-weight: 700;
}
mark {
    transition: all 0.15s ease-in-out;
}

mark:hover {
    background: rgba(34,197,94,0.45);
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# LANDING PAGE
# =========================
if not st.session_state["show_demo"]:
    st.markdown(
        '<div class="big-title">Legal AI that reasons through doctrine, not vibes.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="subtitle">Auctis retrieves Delaware authority, classifies doctrine, maps cases by role, and validates answers before lawyers rely on them.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("Try the demo", type="primary", use_container_width=True):
            st.session_state["show_demo"] = True
            st.rerun()

    with col2:
        st.caption("Private alpha · Delaware corporate law only")

    st.markdown("---")

    cols = st.columns(3)
    cards = [
        (
            "Doctrine classification",
            "Routes questions into Delaware fiduciary law frameworks.",
        ),
        ("Role mapping", "Separates foundation, refinement, and application cases."),
        ("Validation scoring", "Flags weak answers before they reach the user."),
    ]

    for col, (title, body) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="section-card">
                    <div class="label">{title}</div>
                    <div class="value">{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =========================
# DEMO PAGE
# =========================
if st.session_state["show_demo"]:
    if st.button("← Back"):
        st.session_state["show_demo"] = False
        st.session_state["last_result"] = None
        st.rerun()

    st.markdown("## Auctis")
    st.markdown(
        "Court-ready Delaware law reasoning. Turn case law into governing rules, analysis, and comparisons in seconds."
    )

    user_input = st.chat_input("Ask a Delaware law question...")

    if user_input:
        with st.spinner("Reasoning through doctrine..."):
            result = run_query(user_input)
            st.session_state["last_result"] = result
            st.session_state["last_question"] = user_input

    result = st.session_state.get("last_result")

    if result:
        st.markdown("---")

        if result.get("rejected"):
            st.warning(
                result.get(
                    "rejection_message",
                    "Auctis could not identify a Delaware corporate law doctrine in that question.",
                )
            )
            st.markdown("### Try one of these:")
            st.markdown("- Compare Caremark and Marchand")
            st.markdown("- What is the Unocal standard?")
            st.markdown("- What triggers Revlon duties?")
            st.stop()

        output_mode = st.radio(
            "Output Mode",
            ["Structured", "Memo Mode", "Opinion Mode"],
            horizontal=True,
        )

        role_quote_map = result.get("role_quote_map", {}) or {}
        case_cards = result.get("case_cards", []) or []

        if not case_cards:
            raw_cases = (
                result.get("cases", []) or result.get("doctrine_leaders", []) or []
            )
            case_cards = []

            for case in raw_cases[:8]:
                if isinstance(case, dict):
                    source = case.get("source", "Unknown case")
                    role = case.get("role", "related_case")
                else:
                    source = str(case)
                    role = "related_case"

                name = source.replace(".txt", "").replace("_", " ").title()
                anchor = name.lower().replace(" ", "-")

                case_cards.append(
                    {
                        "name": name,
                        "source": source,
                        "role": role,
                        "quote": "",
                        "why_matters": "This case matters here because it helps define the governing doctrinal framework.",
                        "anchor": anchor,
                    }
                )

        st.subheader("Answer")

        if output_mode == "Memo Mode":
            st.markdown(
                result.get("memo_answer") or result.get("answer", "No answer returned.")
            )

        elif output_mode == "Opinion Mode":
            opinion = (
                result.get("opinion_answer")
                or result.get("memo_answer")
                or result.get("answer", "No answer returned.")
            )

            highlighted = highlight_quote_in_answer(opinion, role_quote_map)
            linked = link_cited_cases(highlighted, case_cards)
            st.markdown(linked, unsafe_allow_html=True)

            cited_cases = cited_cases_from_answer(opinion)

            inline_cards = [
                card for card in case_cards if card.get("name") in cited_cases
            ]

            if inline_cards:
                st.markdown("#### Cited Case Quick View")

                for card in inline_cards:
                    with st.expander(f"{card.get('name', 'Unknown Case')} quick view"):
                        st.markdown(f"**Role:** `{card.get('role', 'related_case')}`")

                        if card.get("why_matters"):
                            st.markdown("**Why it matters here**")
                            st.write(card.get("why_matters"))

                        if card.get("quote"):
                            st.markdown("**Key quote**")
                            st.markdown(f"> {card.get('quote')}")

                        st.caption(f"Source: {card.get('source', '')}")

            with st.expander("Citation + quote map"):
                shown_any = False

                for role, item in role_quote_map.items():
                    if not isinstance(item, dict):
                        continue

                    case_name = item.get("case", "Unknown")

                    if cited_cases and case_name not in cited_cases:
                        continue

                    shown_any = True
                    st.markdown(f"**{case_name}** — `{role}`")
                    st.markdown(f"> {item.get('quote', '')}")
                    st.caption(f"Source: {item.get('source', '')}")

                if not shown_any:
                    st.caption(
                        "No selected quote available for the cited cases. "
                        "See Supporting Cases below for retrieved excerpts."
                    )

        else:
            st.markdown(result.get("answer", "No answer returned."))

        corrected_question = result.get("corrected_question", "")
        legal_corrections = result.get("legal_corrections", [])

        if (
            legal_corrections
            and corrected_question
            and corrected_question != st.session_state.get("last_question", "")
        ):
            correction_text = ", ".join(
                [f"{old} → {new}" for old, new in legal_corrections]
            )

            st.info(f"Did you mean: {corrected_question}")
            st.caption(f"Legal term correction: {correction_text}")

            if st.button("Use corrected query"):
                with st.spinner("Reasoning through corrected doctrine..."):
                    corrected_result = run_query(corrected_question)
                    st.session_state["last_result"] = corrected_result
                    st.session_state["last_question"] = corrected_question
                    st.rerun()

        if case_cards:
            st.markdown("### Supporting Cases")
            st.markdown("#### Click a case to explore reasoning")

            for card in case_cards[:8]:
                name = card.get("name", "Unknown Case")
                role = card.get("role", "related_case")
                source = card.get("source", "")
                quote = card.get("quote", "")
                why = card.get("why_matters", "")
                anchor = card.get("anchor", name.lower().replace(" ", "-"))
                context = card.get("context", "")
                excerpts = card.get("excerpts", [])

                # Skip weak/empty cards (defensive safety)
                if not quote and not context and not excerpts:
                    continue

                st.markdown(f'<div id="{anchor}"></div>', unsafe_allow_html=True)

                with st.expander(f"{name} · {role}"):
                    st.markdown(f"**Role in doctrine:** `{role}`")

                if why:
                    st.markdown("**Why this case matters here**")
                    st.write(why)

                # 🔑 Key Quote (primary signal)
                if quote:
                    st.markdown("**Key Quote**")
                    st.markdown(f"> {quote}")
                else:
                    st.caption("No selected quote available.")

                # 🧠 Context (second layer)
                if context:
                    with st.expander("Context — quote highlighted"):
                        highlighted_context = highlight_quote_in_context(context, quote)
                        st.markdown(highlighted_context, unsafe_allow_html=True)

                # 📚 Supporting passages (deep layer)
                if excerpts:
                    with st.expander("Additional supporting passages"):
                        for i, excerpt in enumerate(excerpts, start=1):
                            st.markdown(f"**Passage {i}**")
                            st.write(excerpt)

                # 📍 Source (lightweight footer)
                if source:
                    st.caption(f"Source: {source}")

        else:
            st.warning("No supporting cases were returned.")

        doctrinal_thread = result.get("doctrinal_thread", {})
        thread = doctrinal_thread.get("thread", [])

        if thread:
            st.markdown("### Doctrinal Thread")
            st.caption("How the doctrine develops across leading cases.")

        cols = st.columns(len(thread))

        for col, node in zip(cols, thread):
            with col:
                st.markdown(
                    f"""
                <div class="section-card">
                    <div class="label">{node.get("case", "Unknown")}</div>
                    <div class="value"><b>{node.get("role", "")}</b></div>
                    <div class="value" style="margin-top:8px;">
                        {node.get("point", "")}
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        if result.get("validation_score") is not None:
            score = int(result.get("validation_score") or 0)
            color = score_color(score)

            st.markdown(
                f"""
                    <div style="
                        margin-top:18px;
                        font-size:1.35rem;
                        font-weight:800;
                        color:{color};
                    ">
                        Validation Score: {score}/100
                    </div>
                    """,
                unsafe_allow_html=True,
            )
