"""
app.py — WFA Reading Resource Generator
Three tabs:
  📖 Being a Reader  — Y4–Y6 lesson mode + KS2 reading papers
  📝 Reading Papers  — Y1/Y2 KS1 assessment papers
  🔤 Decodable Reader — Reception–Y1 phonics-constrained texts
"""

import os
import tempfile
import shutil
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from wfa_shared import YEAR_COLOURS, WFA_BLUE, year_colour
from wfa_shared.logo import logo_html
from wfa_shared.streamlit_css import inject_wfa_css

from content_generator import (
    generate_content,
    generate_reading_paper,
    generate_ks1_paper,
    generate_decodable_text,
    PHASE_DATA,
    QUESTION_TYPES,
    QUESTION_LAYOUTS,
)
from pdf_builder import (
    build_pdfs,
    build_reading_paper_pdfs,
    build_ks1_paper2_pdfs,
    build_ks1_paper1_pdfs,
    build_decodable_pdf,
    build_decodable_pptx,
)
from excel_builder import build_excel

try:
    from pptx_builder import build_pptx
    PPTX_AVAILABLE = True
except Exception:
    PPTX_AVAILABLE = False

st.set_page_config(
    page_title="WFA Reading Resources",
    page_icon="📖",
    layout="centered",
)

ICON_PATH     = Path("assets/reader.png")
TEMPLATE_PATH = Path("template.pptx")

KS2_YGS = ["Y4", "Y5", "Y6"]
KS1_YGS = ["Y1", "Y2"]
PHASES  = list(PHASE_DATA.keys())

PDF_MIME  = "application/pdf"
PPTX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".presentationml.presentation")
XLSX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".spreadsheetml.sheet")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_weekday(weekday):
    today = date.today()
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _checkbox_grid(labels, key_prefix):
    cols = st.columns(4)
    checked = []
    for i, label in enumerate(labels):
        if cols[i % 4].checkbox(label, key=f"{key_prefix}_{i}"):
            checked.append(label)
    return checked


def _show_downloads(key, session_key):
    items = st.session_state.get(session_key, [])
    if not items:
        return
    st.success("Resources ready.")
    cols = st.columns(min(len(items), 4))
    for i, (label, data, mime, fname) in enumerate(items):
        cols[i % len(cols)].download_button(
            label=label, data=data, file_name=fname, mime=mime,
            use_container_width=True, key=f"{key}_{i}_{fname}",
        )


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

I_CAN = {
    "vocabulary": [
        "I can explain the meaning of new words using context clues",
        "I can discuss vocabulary choices made by the author",
    ],
    "retrieval": [
        "I can find and record information from a text",
        "I can use evidence from the text to support my answers",
    ],
    "inference": [
        "I can make inferences about characters and events",
        "I can explain my inferences using evidence from the text",
    ],
}

LF_DEFAULTS = {
    "vocabulary": "To explore and explain the meaning of new vocabulary in context",
    "retrieval":  "To retrieve and record key information from a text",
    "inference":  "To make and explain inferences using evidence from the text",
}

TEXT_LENGTHS = {
    "Standard (200–250 words)": "standard",
    "Extended (400–500 words)": "extended",
    "Long (700–800 words)":     "long",
}

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

for _k in ("bar_dl", "kp_dl", "dec_dl", "bar_preview", "kp_preview", "dec_preview"):
    if _k not in st.session_state:
        st.session_state[_k] = [] if _k.endswith("_dl") else ""

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

inject_wfa_css(download=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(logo_html("WFA Reading Resources"), unsafe_allow_html=True)
st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_bar, tab_kp, tab_dec = st.tabs([
    "📖 Being a Reader",
    "📝 Reading Papers",
    "🔤 Decodable Reader",
])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — Being a Reader  (Y4 / Y5 / Y6)
# ═══════════════════════════════════════════════════════════════════════════
with tab_bar:

    st.markdown("#### Year group")
    bar_yg = st.radio("bar_yg", KS2_YGS, horizontal=True,
                      label_visibility="collapsed", key="bar_yg_r")
    st.divider()

    st.markdown("#### Mode")
    bar_mode = st.radio("bar_mode", ["Lesson Mode", "Reading Paper Mode"],
                        horizontal=True, label_visibility="collapsed")
    st.divider()

    bar_topic = st.text_input(
        "Topic / text focus",
        placeholder="e.g. Anglo-Saxons, Sound waves, Charlotte's Web chapter 3",
        key="bar_topic",
    )
    if bar_mode == "Lesson Mode":
        bar_kq = st.text_input(
            "Key question",
            placeholder="e.g. What can objects tell us about how Anglo-Saxons lived?",
            key="bar_kq",
        )
    else:
        bar_kq = ""
    st.divider()

    if bar_mode == "Lesson Mode":
        st.markdown("#### Lesson dates")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.caption("Vocabulary")
            voc_date = st.date_input("voc", value=_next_weekday(1),
                                     format="DD/MM/YYYY", label_visibility="collapsed")
        with d2:
            st.caption("Retrieval")
            ret_date = st.date_input("ret", value=_next_weekday(3),
                                     format="DD/MM/YYYY", label_visibility="collapsed")
        with d3:
            st.caption("Inference")
            inf_date = st.date_input("inf", value=_next_weekday(4),
                                     format="DD/MM/YYYY", label_visibility="collapsed")

        st.markdown("#### Lesson objectives")
        st.caption("Pre-filled with defaults — edit if needed.")
        obj_tabs = st.tabs(["📖 Vocabulary", "🔍 Retrieval", "💡 Inference"])
        with obj_tabs[0]:
            voc_lf  = st.text_input("Learning Focus", value=LF_DEFAULTS["vocabulary"], key="voc_lf")
            voc_ic1 = st.text_input("I can 1", value=I_CAN["vocabulary"][0], key="voc_ic1")
            voc_ic2 = st.text_input("I can 2", value=I_CAN["vocabulary"][1], key="voc_ic2")
        with obj_tabs[1]:
            ret_lf  = st.text_input("Learning Focus", value=LF_DEFAULTS["retrieval"], key="ret_lf")
            ret_ic1 = st.text_input("I can 1", value=I_CAN["retrieval"][0], key="ret_ic1")
            ret_ic2 = st.text_input("I can 2", value=I_CAN["retrieval"][1], key="ret_ic2")
        with obj_tabs[2]:
            inf_lf  = st.text_input("Learning Focus", value=LF_DEFAULTS["inference"], key="inf_lf")
            inf_ic1 = st.text_input("I can 1", value=I_CAN["inference"][0], key="inf_ic1")
            inf_ic2 = st.text_input("I can 2", value=I_CAN["inference"][1], key="inf_ic2")
        st.divider()

    st.markdown("#### Text length")
    bar_tl = st.radio("bar_tl", list(TEXT_LENGTHS.keys()), horizontal=True,
                      label_visibility="collapsed")
    bar_text_length = TEXT_LENGTHS[bar_tl]
    st.divider()

    if bar_mode == "Reading Paper Mode":
        st.markdown("#### Number of questions")
        bar_nq = st.slider("bar_nq", min_value=5, max_value=20, value=10,
                           label_visibility="collapsed")
        st.divider()

    st.markdown("#### Question types")
    bar_qt = st.radio("bar_qt", ["Variety (recommended)", "Select specific types"],
                      horizontal=True, label_visibility="collapsed", key="bar_qt_r")
    bar_question_types = None
    if bar_qt == "Select specific types":
        ck = _checkbox_grid(list(QUESTION_TYPES.keys()), "bar_qt")
        bar_question_types = [QUESTION_TYPES[l] for l in ck] or None
    st.divider()

    st.markdown("#### Question layouts")
    bar_ql = st.radio("bar_ql", ["Variety (recommended)", "Select specific layouts"],
                      horizontal=True, label_visibility="collapsed", key="bar_ql_r")
    bar_question_layouts = None
    if bar_ql == "Select specific layouts":
        ck = _checkbox_grid(list(QUESTION_LAYOUTS.keys()), "bar_ql")
        bar_question_layouts = [QUESTION_LAYOUTS[l] for l in ck] or None
    st.divider()

    if bar_mode == "Lesson Mode":
        st.markdown("#### Outputs")
        oc1, oc2, oc3 = st.columns(3)
        bar_std  = oc1.checkbox("Standard Pupil PDF",  value=True, key="bar_std")
        bar_sup  = oc2.checkbox("Supported Pupil PDF", value=True, key="bar_sup")
        bar_ans  = oc3.checkbox("All Answers PDF",     value=True, key="bar_ans")
        oc4, oc5, _ = st.columns(3)
        bar_pptx = oc4.checkbox("Teaching PPTX", value=True, key="bar_pptx")
        bar_xlsx = oc5.checkbox("Content XLSX",  value=True, key="bar_xlsx")
        st.markdown("#### Layout")
        bar_layout_lbl = st.radio(
            "bar_layout",
            ["Combined text and questions", "Separate text and questions"],
            label_visibility="collapsed",
        )
        bar_layout = "sats" if "Separate" in bar_layout_lbl else "integrated"
        st.divider()

    bar_ready = bool(bar_topic.strip()) and (
        bool(bar_kq.strip()) if bar_mode == "Lesson Mode" else True
    )
    if not bar_ready:
        st.info("Enter a topic to continue.")

    if st.button("Generate", type="primary", disabled=not bar_ready,
                 use_container_width=True, key="bar_gen"):
        st.session_state.bar_dl      = []
        st.session_state.bar_preview = ""

        if bar_mode == "Lesson Mode":
            with st.spinner("Generating reading extract and lessons… (20–40 s)"):
                try:
                    content = generate_content(
                        topic=bar_topic, key_question=bar_kq,
                        vocab_day=voc_date.strftime("%A"),
                        vocab_date=voc_date.strftime("%-d %B %Y"),
                        vocab_i_can=[voc_ic1, voc_ic2], vocab_lf=voc_lf,
                        retrieval_day=ret_date.strftime("%A"),
                        retrieval_date=ret_date.strftime("%-d %B %Y"),
                        retrieval_i_can=[ret_ic1, ret_ic2], retrieval_lf=ret_lf,
                        inference_day=inf_date.strftime("%A"),
                        inference_date=inf_date.strftime("%-d %B %Y"),
                        inference_i_can=[inf_ic1, inf_ic2], inference_lf=inf_lf,
                        question_types=bar_question_types,
                        question_layouts=bar_question_layouts,
                        text_length=bar_text_length,
                        year_group=bar_yg,
                    )
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.stop()
        else:
            with st.spinner(f"Generating reading paper ({bar_nq} questions)… (20–50 s)"):
                try:
                    content = generate_reading_paper(
                        topic=bar_topic, key_question=bar_kq,
                        num_questions=bar_nq,
                        text_length=bar_text_length,
                        question_types=bar_question_types,
                        question_layouts=bar_question_layouts,
                        year_group=bar_yg,
                    )
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.stop()

        generated_text = content.get("standard_text", "")
        content["topic"] = bar_topic
        for lesson in content.get("lessons", []):
            lesson["text"] = generated_text
        st.session_state.bar_preview = generated_text

        tmp = tempfile.mkdtemp()
        try:
            week_ref = (
                voc_date.strftime("%d%b").upper()
                if bar_mode == "Lesson Mode"
                else date.today().strftime("%d%b").upper()
            )
            if bar_mode == "Lesson Mode":
                with st.spinner("Building PDFs…"):
                    pdf_paths = build_pdfs(
                        content=content,
                        icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                        output_dir=tmp, layout=bar_layout, year_group=bar_yg,
                    )
                if bar_std and "standard" in pdf_paths:
                    st.session_state.bar_dl.append((
                        "📄 Standard Pupil PDF", _read_bytes(pdf_paths["standard"]),
                        PDF_MIME, f"BaR_{week_ref}_Standard.pdf",
                    ))
                if bar_sup and "supported" in pdf_paths:
                    st.session_state.bar_dl.append((
                        "📄 Supported Pupil PDF", _read_bytes(pdf_paths["supported"]),
                        PDF_MIME, f"BaR_{week_ref}_Supported.pdf",
                    ))
                if bar_ans and "answers" in pdf_paths:
                    st.session_state.bar_dl.append((
                        "📄 All Answers PDF", _read_bytes(pdf_paths["answers"]),
                        PDF_MIME, f"BaR_{week_ref}_Answers.pdf",
                    ))
                if bar_layout == "sats" and "text_booklet" in pdf_paths:
                    st.session_state.bar_dl.append((
                        "📄 Text Booklet", _read_bytes(pdf_paths["text_booklet"]),
                        PDF_MIME, f"BaR_{week_ref}_TextBooklet.pdf",
                    ))
                if bar_pptx and PPTX_AVAILABLE and TEMPLATE_PATH.exists():
                    with st.spinner("Building PPTX…"):
                        pptx_path = os.path.join(tmp, "Teaching.pptx")
                        try:
                            build_pptx(content=content,
                                       template_path=str(TEMPLATE_PATH),
                                       output_path=pptx_path)
                            st.session_state.bar_dl.append((
                                "📊 Teaching PPTX", _read_bytes(pptx_path),
                                PPTX_MIME, f"BaR_{week_ref}_Teaching.pptx",
                            ))
                        except Exception as e:
                            st.warning(f"PPTX skipped: {e}")
                if bar_xlsx:
                    with st.spinner("Building Excel…"):
                        xlsx_path = os.path.join(tmp, "Content.xlsx")
                        build_excel(content=content, output_path=xlsx_path)
                        st.session_state.bar_dl.append((
                            "📊 Content XLSX", _read_bytes(xlsx_path),
                            XLSX_MIME, f"BaR_{week_ref}_Content.xlsx",
                        ))
            else:
                with st.spinner("Building reading paper PDFs…"):
                    pdf_paths = build_reading_paper_pdfs(
                        content=content,
                        icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                        output_dir=tmp, include_label=False,
                        custom_label="", year_group=bar_yg,
                    )
                for lbl, key, fn in [
                    ("📄 Text",        "text",        f"Paper_{week_ref}_Text.pdf"),
                    ("📄 Questions",   "questions",   f"Paper_{week_ref}_Questions.pdf"),
                    ("📄 Mark Scheme", "mark_scheme", f"Paper_{week_ref}_MarkScheme.pdf"),
                ]:
                    if key in pdf_paths:
                        st.session_state.bar_dl.append((
                            lbl, _read_bytes(pdf_paths[key]), PDF_MIME, fn,
                        ))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if st.session_state.bar_preview:
        st.divider()
        with st.expander("Preview reading extract"):
            st.write(st.session_state.bar_preview)
    _show_downloads("bar", "bar_dl")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — Reading Papers  (Y1 / Y2)
# ═══════════════════════════════════════════════════════════════════════════
with tab_kp:

    st.markdown("#### Year group")
    kp_yg = st.radio("kp_yg", KS1_YGS, horizontal=True,
                     label_visibility="collapsed", key="kp_yg_r")
    st.divider()

    st.markdown("#### Paper type")
    kp_type_lbl = st.radio(
        "kp_paper_type",
        ["Combined text and questions (Paper 1)",
         "Separate text + questions (Paper 2)"],
        horizontal=True, label_visibility="collapsed",
    )
    kp_paper_type = "combined" if "Combined" in kp_type_lbl else "separate"
    st.divider()

    st.markdown("#### Passage 1")
    kp_c1a, kp_c1b = st.columns(2)
    with kp_c1a:
        kp_topic1 = st.text_input("Topic / title",
                                   placeholder="e.g. The Life of Honeybees",
                                   key="kp_topic1")
    with kp_c1b:
        kp_type1 = st.selectbox(
            "Text type", ["non_fiction", "fiction", "poetry"], key="kp_type1",
            format_func=lambda x: x.replace("_", "-").title(),
        )
    st.markdown("#### Passage 2")
    kp_c2a, kp_c2b = st.columns(2)
    with kp_c2a:
        kp_topic2 = st.text_input("Topic / title",
                                   placeholder="e.g. The Lost Kite",
                                   key="kp_topic2")
    with kp_c2b:
        kp_type2 = st.selectbox(
            "Text type", ["fiction", "non_fiction", "poetry"], key="kp_type2",
            format_func=lambda x: x.replace("_", "-").title(),
        )
    st.divider()

    kp_ready = bool(kp_topic1.strip()) and bool(kp_topic2.strip())
    if not kp_ready:
        st.info("Enter topics for both passages to continue.")

    if st.button("Generate", type="primary", disabled=not kp_ready,
                 use_container_width=True, key="kp_gen"):
        st.session_state.kp_dl      = []
        st.session_state.kp_preview = ""

        ptype_lbl = ("Paper 1 (combined)"
                     if kp_paper_type == "combined"
                     else "Paper 2 (separate)")
        with st.spinner(f"Generating KS1 {ptype_lbl} — two passages… (40–80 s)"):
            try:
                content = generate_ks1_paper(
                    topic1=kp_topic1, text_type1=kp_type1,
                    topic2=kp_topic2, text_type2=kp_type2,
                    paper_type=kp_paper_type, year_group=kp_yg,
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        p1 = content.get("passage1", {})
        preview = (" ".join(s.get("text_chunk", "")
                             for s in p1.get("sections", []))
                   if kp_paper_type == "combined"
                   else p1.get("standard_text", ""))
        st.session_state.kp_preview = preview

        tmp = tempfile.mkdtemp()
        try:
            week_ref = date.today().strftime("%d%b").upper()
            with st.spinner("Building PDFs…"):
                if kp_paper_type == "combined":
                    pdf_paths = build_ks1_paper1_pdfs(
                        content=content, output_dir=tmp, year_group=kp_yg,
                    )
                    st.session_state.kp_dl.append((
                        "📄 Combined Pupil Booklet",
                        _read_bytes(pdf_paths["combined"]),
                        PDF_MIME, f"KS1_{kp_yg}_{week_ref}_Combined.pdf",
                    ))
                else:
                    pdf_paths = build_ks1_paper2_pdfs(
                        content=content, output_dir=tmp, year_group=kp_yg,
                    )
                    for lbl, key, fn in [
                        ("📄 Reading Text Booklet", "text",
                         f"KS1_{kp_yg}_{week_ref}_Text.pdf"),
                        ("📄 Answer Booklet", "questions",
                         f"KS1_{kp_yg}_{week_ref}_Questions.pdf"),
                        ("📄 Supported Answer Booklet", "supported",
                         f"KS1_{kp_yg}_{week_ref}_Supported.pdf"),
                    ]:
                        if key in pdf_paths:
                            st.session_state.kp_dl.append((
                                lbl, _read_bytes(pdf_paths[key]), PDF_MIME, fn,
                            ))
                st.session_state.kp_dl.append((
                    "📄 Mark Scheme",
                    _read_bytes(pdf_paths["mark_scheme"]),
                    PDF_MIME, f"KS1_{kp_yg}_{week_ref}_MarkScheme.pdf",
                ))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if st.session_state.kp_preview:
        st.divider()
        with st.expander("Preview passage 1"):
            st.write(st.session_state.kp_preview)
    _show_downloads("kp", "kp_dl")


# ═══════════════════════════════════════════════════════════════════════════
# TAB 3 — Decodable Reader  (Reception – Y1)
# ═══════════════════════════════════════════════════════════════════════════
with tab_dec:

    st.markdown("#### Phonics phase")
    dec_phase = st.radio("dec_phase", PHASES, horizontal=True,
                         label_visibility="collapsed")
    phase_info = PHASE_DATA[dec_phase]
    st.caption(
        f"**{phase_info['stage_label']}**  ·  "
        f"Target: {phase_info['word_count']} words  ·  "
        f"{len(phase_info['gpcs'])} GPCs  ·  "
        f"{len(phase_info['cew'])} CEW"
    )
    st.divider()

    dec_topic = st.text_input(
        "Topic / text content",
        placeholder="e.g. a dog at the park, bugs in the garden, Sam at school",
        key="dec_topic",
    )
    dec_context = st.text_input(
        "Additional context (optional)",
        placeholder="e.g. link to class topic on minibeasts",
        key="dec_context",
    )
    st.divider()

    if not dec_topic.strip():
        st.info("Enter a topic to continue.")

    if st.button("Generate", type="primary", disabled=not dec_topic.strip(),
                 use_container_width=True, key="dec_gen"):
        st.session_state.dec_dl      = []
        st.session_state.dec_preview = ""

        with st.spinner(f"Generating {dec_phase} decodable text… (15–30 s)"):
            try:
                result = generate_decodable_text(
                    topic=dec_topic,
                    phase_key=dec_phase,
                    context=dec_context,
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

        st.session_state.dec_preview = result.get("text", "")

        val  = result.get("validation", {})
        hard = val.get("flag_hard", [])
        vce  = val.get("flag_vce",  [])

        if hard:
            st.warning(
                f"**Words to check** (may be outside {dec_phase} GPCs): "
                + ", ".join(f"`{w}`" for w in hard)
            )
        if vce:
            st.info(
                f"**Possible split digraphs** — check if intended at {dec_phase}: "
                + ", ".join(f"`{w}`" for w in vce)
            )
        if result.get("qa_applied"):
            st.caption("A QA correction pass was applied to this text.")

        tmp = tempfile.mkdtemp()
        try:
            week_ref  = date.today().strftime("%d%b").upper()
            phase_tag = dec_phase.replace(" ", "")
            pdf_path  = build_decodable_pdf(result, tmp)
            st.session_state.dec_dl.append((
                "📄 Text PDF", _read_bytes(pdf_path),
                PDF_MIME, f"Decodable_{phase_tag}_{week_ref}.pdf",
            ))
            try:
                pptx_path = build_decodable_pptx(result, tmp)
                st.session_state.dec_dl.append((
                    "📊 Display Slide", _read_bytes(pptx_path),
                    PPTX_MIME, f"Decodable_{phase_tag}_{week_ref}.pptx",
                ))
            except Exception:
                st.warning("PPTX output unavailable — python-pptx not installed.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if st.session_state.dec_preview:
        st.divider()
        st.markdown("**Generated text:**")
        st.write(st.session_state.dec_preview)

    _show_downloads("dec", "dec_dl")

    if st.session_state.dec_dl:
        with st.expander(f"GPC reference — {dec_phase}"):
            gpcs    = sorted(phase_info["gpcs"], key=len, reverse=True)
            cew     = sorted(phase_info["cew"])
            single  = sorted(g for g in gpcs if len(g) == 1)
            digraph = sorted(g for g in gpcs if len(g) == 2)
            longer  = sorted(g for g in gpcs if len(g) >= 3)
            st.markdown(
                f"**Single letters:** {' · '.join(single)}  \n"
                f"**Digraphs:** {' · '.join(digraph)}"
                + (f"  \n**Trigraphs / split digraphs:** {' · '.join(longer)}"
                   if longer else "")
                + f"  \n**CEW:** {' · '.join(cew)}"
            )
