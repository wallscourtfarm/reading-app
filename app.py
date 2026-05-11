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

LOGO_PATH     = Path("assets/wfa_logo.webp")
ICON_PATH     = Path("assets/reader.png")
TEMPLATE_PATH = Path("template.pptx")

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

TEXT_LENGTHS = {
    "Standard (~250 words)":  "standard",
    "Extended (~500 words)":  "extended",
    "Long (~750 words)":      "long",
}


def _b64_img(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _next_weekday(weekday):
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)


def _checkbox_grid(labels, key_prefix):
    """Render a 3-column checkbox grid. Returns list of checked labels."""
    cols = st.columns(3)
    checked = []
    for i, label in enumerate(labels):
        if cols[i % 3].checkbox(label, key=f"{key_prefix}_{i}"):
            checked.append(label)
    return checked


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
if LOGO_PATH.exists():
    st.markdown(
        f'<img src="data:image/webp;base64,{_b64_img(LOGO_PATH)}" '
        f'style="height:52px;margin-bottom:4px;">',
        unsafe_allow_html=True,
    )
st.title("Being a Reader")
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
# Topic and key question (both modes)
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
    st.divider()

# ---------------------------------------------------------------------------
# b) Text length (both modes)
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
# Lesson Mode extras — learning label + output selection
# ---------------------------------------------------------------------------
include_label = False
if mode == "Lesson Mode":
    st.markdown("#### Learning label")
    include_label = st.checkbox(
        "Include learning label on each lesson (added automatically per lesson type)",
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
ready = bool(topic.strip()) and (bool(key_question.strip()) if mode == 'Lesson Mode' else True)
if not ready:
    st.info("Enter a topic and key question to continue.")

if st.button("Generate resources", type="primary",
             disabled=not ready, use_container_width=True):

    if mode == "Lesson Mode":
        with st.spinner("Generating reading extract and lessons… (20–40 seconds)"):
            try:
                content = generate_content(
                    topic=topic, key_question=key_question,
                    vocab_day=voc_date.strftime("%A"),
                    vocab_date=voc_date.strftime("%-d %B %Y"),
                    vocab_i_can=I_CAN["vocabulary"],
                    retrieval_day=ret_date.strftime("%A"),
                    retrieval_date=ret_date.strftime("%-d %B %Y"),
                    retrieval_i_can=I_CAN["retrieval"],
                    inference_day=inf_date.strftime("%A"),
                    inference_date=inf_date.strftime("%-d %B %Y"),
                    inference_i_can=I_CAN["inference"],
                    question_types=question_types,
                    question_layouts=question_layouts,
                    text_length=text_length,
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
                )
            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.stop()

    generated_text = content.get("standard_text", "")
    content["topic"] = topic  # used as fallback title in reading paper PDF
    for lesson in content.get("lessons", []):
        lesson["text"] = generated_text

    tmp = tempfile.mkdtemp()
    try:
        if mode == "Lesson Mode":
            week_ref = voc_date.strftime("%d%b").upper()

            with st.spinner("Building PDFs…"):
                pdf_paths = build_pdfs(
                    content=content,
                    icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                    output_dir=tmp,
                    layout=layout,
                )

            pptx_path = None
            if out_pptx and PPTX_AVAILABLE and TEMPLATE_PATH.exists():
                with st.spinner("Building PPTX…"):
                    pptx_path = os.path.join(tmp, "Teaching_Slides.pptx")
                    try:
                        build_pptx(content=content, template_path=str(TEMPLATE_PATH),
                                    output_path=pptx_path)
                    except Exception as e:
                        st.warning(f"PPTX skipped: {e}")
                        pptx_path = None

            xlsx_path = None
            if out_xlsx:
                with st.spinner("Building Excel…"):
                    xlsx_path = os.path.join(tmp, "Reading_Content.xlsx")
                    build_excel(content=content, output_path=xlsx_path)

        else:
            week_ref = date.today().strftime("%d%b").upper()

            with st.spinner("Building reading paper PDFs…"):
                pdf_paths = build_reading_paper_pdfs(
                    content=content,
                    icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                    output_dir=tmp,
                    include_label=False,
                    custom_label="",
                )
            pptx_path = None
            xlsx_path = None

        if generated_text:
            with st.expander("Preview reading extract"):
                st.write(generated_text)

        st.success("Done!")
        st.divider()

        downloads = []

        if mode == "Lesson Mode":
            if out_standard and "standard" in pdf_paths:
                downloads.append((pdf_paths["standard"], "📄 Standard Pupil",
                                   "application/pdf",
                                   f"BeingAReader_{week_ref}_Standard.pdf"))
            if out_supported and "supported" in pdf_paths:
                downloads.append((pdf_paths["supported"], "📄 Supported Pupil",
                                   "application/pdf",
                                   f"BeingAReader_{week_ref}_Supported.pdf"))
            if out_answers and "answers" in pdf_paths:
                downloads.append((pdf_paths["answers"], "📄 All Answers",
                                   "application/pdf",
                                   f"BeingAReader_{week_ref}_Answers.pdf"))
            if layout == "sats" and "text_booklet" in pdf_paths:
                downloads.append((pdf_paths["text_booklet"], "📄 Text Booklet",
                                   "application/pdf",
                                   f"BeingAReader_{week_ref}_TextBooklet.pdf"))
            if pptx_path and os.path.exists(pptx_path):
                downloads.append((pptx_path, "📊 Teaching PPTX",
                                   "application/vnd.openxmlformats-officedocument"
                                   ".presentationml.presentation",
                                   f"BeingAReader_{week_ref}_Teaching.pptx"))
        else:
            downloads.append((pdf_paths["text"],        "📄 Text",
                               "application/pdf", f"ReadingPaper_{week_ref}_Text.pdf"))
            downloads.append((pdf_paths["questions"],   "📄 Questions",
                               "application/pdf", f"ReadingPaper_{week_ref}_Questions.pdf"))
            downloads.append((pdf_paths["mark_scheme"], "📄 Mark Scheme",
                               "application/pdf", f"ReadingPaper_{week_ref}_MarkScheme.pdf"))

        if downloads:
            cols = st.columns(min(len(downloads), 4))
            for i, (path, label, mime, filename) in enumerate(downloads):
                col = cols[i % len(cols)]
                if path and os.path.exists(path):
                    with open(path, "rb") as f:
                        col.download_button(label=label, data=f.read(),
                                            file_name=filename, mime=mime,
                                            use_container_width=True)

        if xlsx_path and os.path.exists(xlsx_path):
            with open(xlsx_path, "rb") as f:
                st.download_button(
                    label="📊 Content XLSX", data=f.read(),
                    file_name=f"BeingAReader_{week_ref}_Content.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass
