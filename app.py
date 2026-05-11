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

from content_generator import generate_content
from pdf_builder import build_pdfs
from excel_builder import build_excel

try:
    from pptx_builder import build_pptx
    PPTX_AVAILABLE = True
except Exception:
    PPTX_AVAILABLE = False

# ---------------------------------------------------------------------------
# Config
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

# Human-readable labels → internal format keys
QUESTION_TYPE_OPTIONS = {
    "Open written answer":          "open_line",
    "Find and copy":                "find_and_copy",
    "Numbered list (write 2–3 things)": "numbered_list",
    "Multiple choice (tick one)":   "tick_one",
    "Tick two":                     "tick_two",
    "True / false table":           "true_false_table",
    "Sequence events":              "sequencing",
    "Reason & evidence (3 marks)":  "reason_evidence_table",
    "Two-part question (a/b)":      "two_part_ab",
}


def _b64_img(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _next_weekday(weekday: int) -> date:
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
# Core inputs
# ---------------------------------------------------------------------------
key_question = st.text_input(
    "Key question",
    placeholder="e.g. What can objects tell us about how Anglo-Saxons lived?",
)

text_focus = st.text_input(
    "Text focus",
    placeholder="e.g. Anglo-Saxons, Sound waves, Charlotte's Web chapter 3",
    help="Claude will write a reading extract on this topic.",
)

st.markdown("**Lesson dates**")
date_col1, date_col2, date_col3 = st.columns(3)
with date_col1:
    st.caption("Vocabulary")
    voc_date = st.date_input("Vocabulary", value=_next_weekday(1),
                              format="DD/MM/YYYY", label_visibility="collapsed")
with date_col2:
    st.caption("Retrieval")
    ret_date = st.date_input("Retrieval", value=_next_weekday(3),
                              format="DD/MM/YYYY", label_visibility="collapsed")
with date_col3:
    st.caption("Inference")
    inf_date = st.date_input("Inference", value=_next_weekday(4),
                              format="DD/MM/YYYY", label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Options (optional)
# ---------------------------------------------------------------------------
with st.expander("Options", expanded=False):

    # ── Output selection ──────────────────────────────────────────────────
    st.markdown("**Select outputs**")
    o1, o2, o3 = st.columns(3)
    out_standard  = o1.checkbox("Standard Pupil PDF",  value=True)
    out_supported = o2.checkbox("Supported Pupil PDF", value=True)
    out_answers   = o3.checkbox("All Answers PDF",     value=True)
    o4, o5, _     = st.columns(3)
    out_pptx      = o4.checkbox("Teaching PPTX",  value=True)
    out_xlsx      = o5.checkbox("Content XLSX",   value=True)

    st.divider()

    # ── Question type focus ───────────────────────────────────────────────
    st.markdown("**Question type focus**")
    st.caption(
        "Leave all unchecked for a balanced mix (recommended). "
        "Check specific types to restrict what appears in the PDFs."
    )
    qt_cols = st.columns(3)
    selected_labels = []
    for i, label in enumerate(QUESTION_TYPE_OPTIONS):
        col = qt_cols[i % 3]
        if col.checkbox(label, value=False, key=f"qt_{i}"):
            selected_labels.append(label)
    # Convert to internal format keys (None = no restriction)
    allowed_formats = (
        [QUESTION_TYPE_OPTIONS[l] for l in selected_labels]
        if selected_labels else None
    )

    st.divider()

    # ── Text length ───────────────────────────────────────────────────────
    st.markdown("**Text length**")
    text_length_label = st.radio(
        "Text length",
        ["Standard (200–250 words)", "Extended (400–500 words)"],
        label_visibility="collapsed",
        horizontal=True,
    )
    text_length = "extended" if "Extended" in text_length_label else "standard"

    # ── Layout ────────────────────────────────────────────────────────────
    st.markdown("**Layout**")
    layout_label = st.radio(
        "Layout",
        [
            "Integrated — text and questions on the same page",
            "SATs style — separate text booklet and question paper",
        ],
        label_visibility="collapsed",
    )
    layout = "sats" if "SATs" in layout_label else "integrated"

    if layout == "sats":
        st.caption(
            "SATs style produces an additional Text Booklet PDF. "
            "Questions reference the booklet by paragraph rather than repeating the text."
        )

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
st.divider()
ready = bool(key_question.strip()) and bool(text_focus.strip())

if not ready:
    st.info("Enter a key question and text focus to generate resources.")

if st.button("Generate resources", type="primary",
             disabled=not ready, use_container_width=True):

    with st.spinner("Generating reading extract and questions… (20–40 seconds)"):
        try:
            content = generate_content(
                topic=text_focus,
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
                allowed_formats=allowed_formats,
                text_length=text_length,
            )
        except ValueError as e:
            st.error(f"Generation failed: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

    generated_text = content.get("standard_text", "")
    for lesson in content["lessons"]:
        lesson["text"] = generated_text

    tmp = tempfile.mkdtemp()
    try:
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

        if out_xlsx:
            with st.spinner("Building Excel…"):
                xlsx_path = os.path.join(tmp, "Reading_Content.xlsx")
                build_excel(content=content, output_path=xlsx_path)
        else:
            xlsx_path = None

        # ── Preview ───────────────────────────────────────────────────────
        if generated_text:
            with st.expander("Preview reading extract"):
                st.write(generated_text)

        st.success("Done!")
        st.divider()

        week_ref = voc_date.strftime("%d%b").upper()

        # Collect downloads
        downloads = []
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

        if downloads:
            dl_cols = st.columns(min(len(downloads), 4))
            for i, (path, label, mime, filename) in enumerate(downloads):
                col = dl_cols[i % len(dl_cols)]
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
                    mime="application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet",
                )

    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass
