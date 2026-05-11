"""
app.py — Being a Reader resource generator
Wallscourt Farm Academy

Two modes:
  Lesson Mode        — 3 lessons (Vocabulary / Retrieval / Inference), full resource set
  Reading Paper Mode — standalone text + question paper + mark scheme
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

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
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


def _b64_img(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _next_weekday(weekday):
    today = date.today()
    days_ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
if LOGO_PATH.exists():
    st.markdown(
        f'<img src="data:image/webp;base64,{_b64_img(LOGO_PATH)}" '
        f'style="height:52px;margin-bottom:6px;">',
        unsafe_allow_html=True,
    )

st.title("Being a Reader")
st.divider()

# ---------------------------------------------------------------------------
# Mode selector
# ---------------------------------------------------------------------------
mode = st.radio(
    "Mode",
    ["Lesson Mode", "Reading Paper Mode"],
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()

# ---------------------------------------------------------------------------
# Shared inputs
# ---------------------------------------------------------------------------
topic = st.text_input(
    "Topic / text focus",
    placeholder="e.g. Anglo-Saxons, Sound waves, Charlotte's Web chapter 3",
)
key_question = st.text_input(
    "Key question",
    placeholder="e.g. What can objects tell us about how Anglo-Saxons lived?",
)

# ---------------------------------------------------------------------------
# Mode-specific inputs
# ---------------------------------------------------------------------------
if mode == "Lesson Mode":
    st.markdown("**Lesson dates**")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.caption("Vocabulary")
        voc_date = st.date_input("Vocabulary", value=_next_weekday(1),
                                  format="DD/MM/YYYY", label_visibility="collapsed")
    with d2:
        st.caption("Retrieval")
        ret_date = st.date_input("Retrieval", value=_next_weekday(3),
                                  format="DD/MM/YYYY", label_visibility="collapsed")
    with d3:
        st.caption("Inference")
        inf_date = st.date_input("Inference", value=_next_weekday(4),
                                  format="DD/MM/YYYY", label_visibility="collapsed")

else:  # Reading Paper Mode
    rp_col1, rp_col2 = st.columns(2)
    with rp_col1:
        text_length_label = st.radio(
            "Text length",
            ["Standard (~250 words)", "Extended (~500 words)", "Long (~750 words)"],
        )
        text_length = (
            "long"     if "Long"     in text_length_label else
            "extended" if "Extended" in text_length_label else
            "standard"
        )
    with rp_col2:
        num_questions = st.slider("Number of questions", min_value=5, max_value=20, value=10)

# ---------------------------------------------------------------------------
# Options (both modes)
# ---------------------------------------------------------------------------
with st.expander("Options", expanded=False):

    # ── Question types (cognitive) ────────────────────────────────────────
    st.markdown("**Question types**")
    st.caption("Leave blank for a balanced mix. Select specific types to restrict what is generated.")
    qt_labels = list(QUESTION_TYPES.keys())
    selected_type_labels = st.multiselect(
        "Question types", qt_labels, default=[],
        label_visibility="collapsed",
    )
    question_types = [QUESTION_TYPES[l] for l in selected_type_labels] or None

    # ── Question layouts (presentation) ──────────────────────────────────
    st.markdown("**Question layouts**")
    st.caption("Leave blank for a balanced mix. Select specific layouts to restrict the format.")
    ql_labels = list(QUESTION_LAYOUTS.keys())
    selected_layout_labels = st.multiselect(
        "Question layouts", ql_labels, default=[],
        label_visibility="collapsed",
    )
    question_layouts = [QUESTION_LAYOUTS[l] for l in selected_layout_labels] or None

    st.divider()

    # ── Text length (Lesson Mode only — Reading Paper has its own control) ─
    if mode == "Lesson Mode":
        st.markdown("**Text length**")
        tl_label = st.radio(
            "Text length",
            ["Standard (~250 words)", "Extended (~500 words)", "Long (~750 words)"],
            horizontal=True,
            label_visibility="collapsed",
        )
        text_length = (
            "long"     if "Long"     in tl_label else
            "extended" if "Extended" in tl_label else
            "standard"
        )

        st.divider()

        # ── Layout (Lesson Mode only) ────────────────────────────────────
        st.markdown("**Layout**")
        layout_label = st.radio(
            "Layout",
            ["Combined text and questions", "Separate text and questions"],
            label_visibility="collapsed",
        )
        layout = "sats" if "Separate" in layout_label else "integrated"

        st.divider()

        # ── Output selection (Lesson Mode only) ───────────────────────────
        st.markdown("**Outputs**")
        oc1, oc2, oc3 = st.columns(3)
        out_standard  = oc1.checkbox("Standard Pupil PDF",  value=True)
        out_supported = oc2.checkbox("Supported Pupil PDF", value=True)
        out_answers   = oc3.checkbox("All Answers PDF",     value=True)
        oc4, oc5, _   = st.columns(3)
        out_pptx      = oc4.checkbox("Teaching PPTX", value=True)
        out_xlsx      = oc5.checkbox("Content XLSX",  value=True)

        st.divider()

    # ── Learning label (both modes) ───────────────────────────────────────
    st.markdown("**Learning label**")
    st.caption(
        "When on, a learning label appears in the top-left of the first questions page. "
        "In Lesson Mode the label content is set automatically per lesson type."
    )
    include_label = st.checkbox("Include learning label", value=True)

    custom_label = ""
    if include_label and mode == "Reading Paper Mode":
        custom_label = st.text_input(
            "Label text",
            placeholder="e.g. T5W3 Reading Practice — Anglo-Saxons",
            help="This appears as the learning label on the questions page.",
        )

    # ── Curriculum context ────────────────────────────────────────────────
    st.divider()
    st.markdown("**Curriculum context** *(optional)*")
    context = st.text_area(
        "context",
        placeholder=(
            "Give Claude context about your current unit so the text fits. "
            "e.g. Y4 history — children have studied Anglo-Saxon settlements and trade."
        ),
        height=70,
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
st.divider()
ready = bool(topic.strip()) and bool(key_question.strip())
if not ready:
    st.info("Enter a topic and key question to generate resources.")

if st.button("Generate resources", type="primary",
             disabled=not ready, use_container_width=True):

    # ── Call the appropriate generator ────────────────────────────────────
    if mode == "Lesson Mode":
        with st.spinner("Generating reading extract and lessons… (20–40 seconds)"):
            try:
                content = generate_content(
                    topic=topic,
                    key_question=key_question,
                    vocab_day=voc_date.strftime("%A"),
                    vocab_date=voc_date.strftime("%-d %B %Y"),
                    vocab_i_can=I_CAN["vocabulary"],
                    retrieval_day=ret_date.strftime("%A"),
                    retrieval_date=ret_date.strftime("%-d %B %Y"),
                    retrieval_i_can=I_CAN["retrieval"],
                    inference_day=inf_date.strftime("%A"),
                    inference_date=inf_date.strftime("%-d %B %Y"),
                    inference_i_can=I_CAN["inference"],
                    context=context,
                    question_types=question_types,
                    question_layouts=question_layouts,
                    text_length=text_length,
                )
            except (ValueError, Exception) as e:
                st.error(f"Generation failed: {e}")
                st.stop()

    else:  # Reading Paper Mode
        with st.spinner(f"Generating reading paper ({num_questions} questions)… (20–50 seconds)"):
            try:
                content = generate_reading_paper(
                    topic=topic,
                    key_question=key_question,
                    num_questions=num_questions,
                    text_length=text_length,
                    question_types=question_types,
                    question_layouts=question_layouts,
                    context=context,
                )
            except (ValueError, Exception) as e:
                st.error(f"Generation failed: {e}")
                st.stop()

    generated_text = content.get("standard_text", "")

    # Inject text into lesson dicts (Lesson Mode only)
    for lesson in content.get("lessons", []):
        lesson["text"] = generated_text

    tmp = tempfile.mkdtemp()
    try:
        week_ref = date.today().strftime("%d%b").upper()

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

        else:  # Reading Paper Mode
            with st.spinner("Building reading paper PDFs…"):
                pdf_paths = build_reading_paper_pdfs(
                    content=content,
                    icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                    output_dir=tmp,
                    include_label=include_label,
                    custom_label=custom_label,
                )
            pptx_path = None
            xlsx_path = None

        # ── Preview generated text ────────────────────────────────────────
        if generated_text:
            with st.expander("Preview reading extract"):
                st.write(generated_text)

        st.success("Done!")
        st.divider()

        # ── Download buttons ──────────────────────────────────────────────
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

        else:  # Reading Paper Mode
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
