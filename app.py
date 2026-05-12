"""
app.py — Being a Reader resource generator
Wallscourt Farm Academy
"""

import base64
import os
import tempfile
import shutil
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from content_generator import (
    generate_content,
    generate_reading_paper,
    QUESTION_TYPES,
    QUESTION_LAYOUTS,
)
from pdf_builder import build_pdfs, build_reading_paper_pdfs
from excel_builder import build_excel

try:
    from pptx_builder import build_pptx
    PPTX_AVAILABLE = True
except Exception:
    PPTX_AVAILABLE = False

st.set_page_config(
    page_title="Being a Reader — WFA",
    page_icon="📖",
    layout="centered",
)

LOGO_PATH     = Path("assets/wfa_logo.jpg")
ICON_PATH     = Path("assets/reader.png")
TEMPLATE_PATH = Path("template.pptx")

YEAR_GROUPS = ["Y4", "Y5", "Y6"]

YG_COLOURS = {
    "Y4": "#1798d3",
    "Y5": "#e57d24",
    "Y6": "#2bae62",
}

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
        "I can explain what a text implies using evidence",
        "I can make inferences based on what I have read",
    ],
}

LF_DEFAULTS = {
    "vocabulary": "To explore and explain the meaning of new vocabulary in context",
    "retrieval":  "To retrieve and record key information from a text",
    "inference":  "To make and explain inferences using evidence from the text",
}

TEXT_LENGTHS = {
    "Standard (~250 words)": "standard",
    "Extended (~500 words)": "extended",
    "Long (~750 words)":     "long",
}


def _b64_img(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _next_weekday(weekday):
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)


def _checkbox_grid(labels, key_prefix):
    cols = st.columns(3)
    checked = []
    for i, label in enumerate(labels):
        if cols[i % 3].checkbox(label, key=f"{key_prefix}_{i}"):
            checked.append(label)
    return checked


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "downloads" not in st.session_state:
    st.session_state.downloads = []   # list of (label, bytes, mime, filename)
if "preview_text" not in st.session_state:
    st.session_state.preview_text = ""

# ---------------------------------------------------------------------------
# CSS — school colour overrides
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Dividers */
hr { border-color: #1798d3 !important; opacity: 0.3; }

/* Section headings */
h4 { color: #1798d3 !important; }

/* Download buttons — secondary style */
div[data-testid="stDownloadButton"] > button {
    border: 1.5px solid #1798d3 !important;
    color: #1798d3 !important;
    background: #ffffff !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: #e8f5fc !important;
}

/* Info / success banners */
div[data-testid="stAlert"] {
    border-left-color: #1798d3 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header — logo and title on same line
# ---------------------------------------------------------------------------
if LOGO_PATH.exists():
    logo_b64 = _b64_img(LOGO_PATH)
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:18px;margin-bottom:6px;">
          <img src="data:image/jpeg;base64,{logo_b64}"
               style="height:64px;width:auto;flex-shrink:0;">
          <span style="font-size:2rem;font-weight:700;
                       color:#1798d3;line-height:1.15;">Being a Reader</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<span style="font-size:2rem;font-weight:700;color:#1798d3;">Being a Reader</span>',
        unsafe_allow_html=True,
    )
st.divider()

# ---------------------------------------------------------------------------
# a) Mode
# ---------------------------------------------------------------------------
st.markdown("#### Mode")
mode = st.radio(
    "mode", ["Lesson Mode", "Reading Paper Mode"],
    horizontal=True, label_visibility="collapsed",
)
st.divider()

# ---------------------------------------------------------------------------
# Year group
# ---------------------------------------------------------------------------
st.markdown("#### Year group")
year_group = st.radio(
    "yg", YEAR_GROUPS,
    horizontal=True, label_visibility="collapsed",
    key="year_group_radio",
)
yg_colour = YG_COLOURS[year_group]

# Inject year-group accent colour into CSS custom property
st.markdown(
    f"<style>:root {{--yg-accent: {yg_colour};}}</style>",
    unsafe_allow_html=True,
)
st.divider()

# ---------------------------------------------------------------------------
# Topic + key question
# ---------------------------------------------------------------------------
topic = st.text_input(
    "Topic / text focus",
    placeholder="e.g. Anglo-Saxons, Sound waves, Charlotte's Web chapter 3",
)
if mode == "Lesson Mode":
    key_question = st.text_input(
        "Key question",
        placeholder="e.g. What can objects tell us about how Anglo-Saxons lived?",
    )
else:
    key_question = ""
st.divider()

# ---------------------------------------------------------------------------
# Lesson Mode — dates
# ---------------------------------------------------------------------------
if mode == "Lesson Mode":
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

# ---------------------------------------------------------------------------
# b) Text length
# ---------------------------------------------------------------------------
st.markdown("#### Text length")
tl_label = st.radio(
    "tl", list(TEXT_LENGTHS.keys()),
    horizontal=True, label_visibility="collapsed",
)
text_length = TEXT_LENGTHS[tl_label]
st.divider()

# ---------------------------------------------------------------------------
# c) Number of questions (Reading Paper Mode only)
# ---------------------------------------------------------------------------
if mode == "Reading Paper Mode":
    st.markdown("#### Number of questions")
    num_questions = st.slider(
        "nq", min_value=5, max_value=20, value=10,
        label_visibility="collapsed",
    )
    st.divider()

# ---------------------------------------------------------------------------
# d) Question types
# ---------------------------------------------------------------------------
st.markdown("#### Question types")
qt_choice = st.radio(
    "qt_choice",
    ["Variety (recommended)", "Select specific types"],
    horizontal=True, label_visibility="collapsed",
    key="qt_choice_radio",
)
question_types = None
if qt_choice == "Select specific types":
    checked_types = _checkbox_grid(list(QUESTION_TYPES.keys()), "qt")
    question_types = [QUESTION_TYPES[l] for l in checked_types] or None
st.divider()

# ---------------------------------------------------------------------------
# e) Question layouts
# ---------------------------------------------------------------------------
st.markdown("#### Question layouts")
ql_choice = st.radio(
    "ql_choice",
    ["Variety (recommended)", "Select specific layouts"],
    horizontal=True, label_visibility="collapsed",
    key="ql_choice_radio",
)
question_layouts = None
if ql_choice == "Select specific layouts":
    checked_layouts = _checkbox_grid(list(QUESTION_LAYOUTS.keys()), "ql")
    question_layouts = [QUESTION_LAYOUTS[l] for l in checked_layouts] or None
st.divider()

# ---------------------------------------------------------------------------
# Lesson Mode extras
# ---------------------------------------------------------------------------
if mode == "Lesson Mode":
    st.markdown("#### Learning label")
    include_label = st.checkbox(
        "Include learning label (added automatically per lesson type)",
        value=True,
    )

    st.markdown("#### Outputs")
    oc1, oc2, oc3 = st.columns(3)
    out_standard  = oc1.checkbox("Standard Pupil PDF",  value=True)
    out_supported = oc2.checkbox("Supported Pupil PDF", value=True)
    out_answers   = oc3.checkbox("All Answers PDF",     value=True)
    oc4, oc5, _   = st.columns(3)
    out_pptx = oc4.checkbox("Teaching PPTX", value=True)
    out_xlsx = oc5.checkbox("Content XLSX",  value=True)

    st.markdown("#### Layout")
    layout_label = st.radio(
        "layout",
        ["Combined text and questions", "Separate text and questions"],
        label_visibility="collapsed",
    )
    layout = "sats" if "Separate" in layout_label else "integrated"
    st.divider()

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
ready = bool(topic.strip()) and (
    bool(key_question.strip()) if mode == "Lesson Mode" else True
)
if not ready:
    st.info("Enter a topic and key question to continue.")

if st.button("Generate resources", type="primary",
             disabled=not ready, use_container_width=True):

    # Clear any previous downloads
    st.session_state.downloads = []
    st.session_state.preview_text = ""

    if mode == "Lesson Mode":
        with st.spinner("Generating reading extract and lessons… (20–40 seconds)"):
            try:
                content = generate_content(
                    topic=topic, key_question=key_question,
                    vocab_day=voc_date.strftime("%A"),
                    vocab_date=voc_date.strftime("%-d %B %Y"),
                    vocab_i_can=[voc_ic1, voc_ic2],
                    vocab_lf=voc_lf,
                    retrieval_day=ret_date.strftime("%A"),
                    retrieval_date=ret_date.strftime("%-d %B %Y"),
                    retrieval_i_can=[ret_ic1, ret_ic2],
                    retrieval_lf=ret_lf,
                    inference_day=inf_date.strftime("%A"),
                    inference_date=inf_date.strftime("%-d %B %Y"),
                    inference_i_can=[inf_ic1, inf_ic2],
                    inference_lf=inf_lf,
                    question_types=question_types,
                    question_layouts=question_layouts,
                    text_length=text_length,
                    year_group=year_group,
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()
    else:
        with st.spinner(f"Generating reading paper ({num_questions} questions)… (20–50 seconds)"):
            try:
                content = generate_reading_paper(
                    topic=topic, key_question=key_question,
                    num_questions=num_questions,
                    text_length=text_length,
                    question_types=question_types,
                    question_layouts=question_layouts,
                    year_group=year_group,
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

    generated_text = content.get("standard_text", "")
    content["topic"] = topic
    for lesson in content.get("lessons", []):
        lesson["text"] = generated_text
    st.session_state.preview_text = generated_text

    tmp = tempfile.mkdtemp()
    try:
        PDF_MIME = "application/pdf"
        PPTX_MIME = ("application/vnd.openxmlformats-officedocument"
                     ".presentationml.presentation")
        XLSX_MIME = ("application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet")

        if mode == "Lesson Mode":
            week_ref = voc_date.strftime("%d%b").upper()

            with st.spinner("Building PDFs…"):
                pdf_paths = build_pdfs(
                    content=content,
                    icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                    output_dir=tmp,
                    layout=layout,
                    year_group=year_group,
                )

            if out_standard and "standard" in pdf_paths:
                st.session_state.downloads.append((
                    "📄 Standard Pupil PDF", _read_bytes(pdf_paths["standard"]),
                    PDF_MIME, f"BeingAReader_{week_ref}_Standard.pdf"
                ))
            if out_supported and "supported" in pdf_paths:
                st.session_state.downloads.append((
                    "📄 Supported Pupil PDF", _read_bytes(pdf_paths["supported"]),
                    PDF_MIME, f"BeingAReader_{week_ref}_Supported.pdf"
                ))
            if out_answers and "answers" in pdf_paths:
                st.session_state.downloads.append((
                    "📄 All Answers PDF", _read_bytes(pdf_paths["answers"]),
                    PDF_MIME, f"BeingAReader_{week_ref}_Answers.pdf"
                ))
            if layout == "sats" and "text_booklet" in pdf_paths:
                st.session_state.downloads.append((
                    "📄 Text Booklet", _read_bytes(pdf_paths["text_booklet"]),
                    PDF_MIME, f"BeingAReader_{week_ref}_TextBooklet.pdf"
                ))

            if out_pptx and PPTX_AVAILABLE and TEMPLATE_PATH.exists():
                with st.spinner("Building PPTX…"):
                    pptx_path = os.path.join(tmp, "Teaching_Slides.pptx")
                    try:
                        build_pptx(content=content, template_path=str(TEMPLATE_PATH),
                                    output_path=pptx_path)
                        st.session_state.downloads.append((
                            "📊 Teaching PPTX", _read_bytes(pptx_path),
                            PPTX_MIME, f"BeingAReader_{week_ref}_Teaching.pptx"
                        ))
                    except Exception as e:
                        st.warning(f"PPTX skipped: {e}")

            if out_xlsx:
                with st.spinner("Building Excel…"):
                    xlsx_path = os.path.join(tmp, "Reading_Content.xlsx")
                    build_excel(content=content, output_path=xlsx_path)
                    st.session_state.downloads.append((
                        "📊 Content XLSX", _read_bytes(xlsx_path),
                        XLSX_MIME, f"BeingAReader_{week_ref}_Content.xlsx"
                    ))

        else:
            week_ref = date.today().strftime("%d%b").upper()

            with st.spinner("Building reading paper PDFs…"):
                pdf_paths = build_reading_paper_pdfs(
                    content=content,
                    icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                    output_dir=tmp,
                    include_label=False,
                    custom_label="",
                    year_group=year_group,
                )

            st.session_state.downloads.append((
                "📄 Text", _read_bytes(pdf_paths["text"]),
                PDF_MIME, f"ReadingPaper_{week_ref}_Text.pdf"
            ))
            st.session_state.downloads.append((
                "📄 Questions", _read_bytes(pdf_paths["questions"]),
                PDF_MIME, f"ReadingPaper_{week_ref}_Questions.pdf"
            ))
            st.session_state.downloads.append((
                "📄 Mark Scheme", _read_bytes(pdf_paths["mark_scheme"]),
                PDF_MIME, f"ReadingPaper_{week_ref}_MarkScheme.pdf"
            ))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
# Downloads — rendered from session state, persist across reruns
# ---------------------------------------------------------------------------
if st.session_state.downloads:
    st.divider()
    if st.session_state.preview_text:
        with st.expander("Preview reading extract"):
            st.write(st.session_state.preview_text)

    st.success("Resources ready — download any or all below.")
    cols = st.columns(min(len(st.session_state.downloads), 4))
    for i, (label, data, mime, filename) in enumerate(st.session_state.downloads):
        cols[i % len(cols)].download_button(
            label=label,
            data=data,
            file_name=filename,
            mime=mime,
            use_container_width=True,
            key=f"dl_{i}_{filename}",   # stable key so buttons don't flicker
        )
