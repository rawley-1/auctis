import streamlit as st
from index_loader import ensure_index_exists

ensure_index_exists()

from ask import run_query


st.set_page_config(page_title="Auctis", layout="wide")


if "show_demo" not in st.session_state:
    st.session_state["show_demo"] = False

if "question" not in st.session_state:
    st.session_state["question"] = ""

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None


def score_color(score):
    score = int(score or 0)
    if score >= 85:
        return "#22C55E"
    if score >= 70:
        return "#FACC15"
    return "#EF4444"


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
        ("Doctrine classification", "Routes questions into Delaware fiduciary law frameworks."),
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

    question = st.text_area(
        "Ask a Delaware law question",
        value=st.session_state.get("question", ""),
        height=140,
        placeholder="Compare Caremark and Marchand",
    )

    run_clicked = st.button("Run Analysis", type="primary")

    if run_clicked:
        if not question or not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Reasoning through doctrine..."):
                result = run_query(question)
                st.session_state["last_result"] = result
                st.session_state["question"] = question

    result = st.session_state.get("last_result")

    if result:
        st.markdown("---")

        # REJECTION: bad/nonsense queries stop here only
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

        st.subheader("Answer")
        st.markdown(result.get("answer", "No answer returned."))

        corrected_question = result.get("corrected_question", "")
        legal_corrections = result.get("legal_corrections", [])

        if (
            legal_corrections
            and corrected_question
            and corrected_question != st.session_state.get("question", "")
        ):
            correction_text = ", ".join(
                [f"{old} → {new}" for old, new in legal_corrections]
            )

            st.info(f"Did you mean: {corrected_question}")
            st.caption(f"Legal term correction: {correction_text}")

            if st.button("Use corrected query"):
                st.session_state["question"] = corrected_question
                st.session_state["last_result"] = None
                st.rerun()

        cases = result.get("cases", [])

        if cases:
            st.markdown("### Supporting Cases")

            case_html = ""

            for case in cases[:8]:
                if isinstance(case, dict):
                    raw_name = case.get("source", "Unknown case")
                else:
                    raw_name = str(case)

                name = raw_name.replace(".txt", "").replace("_", " ").title()

                case_html += f'<span class="case-chip">{name}</span>'

            st.markdown(case_html, unsafe_allow_html=True)

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