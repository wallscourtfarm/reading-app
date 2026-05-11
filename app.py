"""
app.py — Being a Reader resource generator
Streamlit front-end for Wallscourt Farm Academy.
Calls content_generator → pdf_builder → pptx_builder → excel_builder.
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

# pptx_builder is optional — gracefully skip if not present or not updated
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
    layout="wide",
)

# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------
LOGO_PATH = Path("assets/wfa_logo.webp")
ICON_PATH = Path("assets/reader.png")
TEMPLATE_PATH = Path("template.pptx")


def _b64_img(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


if LOGO_PATH.exists():
    st.markdown(
        f'<img src="data:image/webp;base64,{_b64_img(LOGO_PATH)}" '
        f'style="height:56px;margin-bottom:8px;">',
        unsafe_allow_html=True,
    )

st.title("Being a Reader")
st.caption("Generate Standard Pupil, Supported Pupil, All Answers PDFs · Teaching PPTX · Content XLSX")

st.divider()

# ---------------------------------------------------------------------------
# Helper — default Monday for the week based on today
# ---------------------------------------------------------------------------
def _next_tuesday() -> date:
    today = date.today()
    days_ahead = (1 - today.weekday()) % 7  # Tuesday = 1
    return today + timedelta(days=days_ahead or 7)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
col_text, col_meta = st.columns([3, 2], gap="large")

with col_text:
    st.subheader("Reading text")
    text = st.text_area(
        "Paste the reading extract here",
        height=280,
        help="This text is used for all three lessons. "
             "Aim for 200–250 words for the standard version.",
        label_visibility="collapsed",
    )

with col_meta:
    st.subheader("Key question")
    key_question = st.text_input(
        "Key question",
        placeholder="e.g. How do writers create tension?",
        label_visibility="collapsed",
    )

    st.subheader("Lesson schedule")

    # Vocabulary
    with st.expander("Lesson 1 — Vocabulary", expanded=True):
        voc_date = st.date_input("Date", value=_next_tuesday(), key="voc_date")
        voc_ican1 = st.text_input(
            "I can statement 1",
            value="I can find and explain the meaning of new words in a text",
            key="voc_ican1",
        )
        voc_ican2 = st.text_input(
            "I can statement 2",
            value="I can use context clues to work out the meaning of unfamiliar words",
            key="voc_ican2",
        )

    # Retrieval
    with st.expander("Lesson 2 — Retrieval", expanded=True):
        ret_date = st.date_input(
            "Date",
            value=_next_tuesday() + timedelta(days=2),
            key="ret_date",
        )
        ret_ican1 = st.text_input(
            "I can statement 1",
            value="I can find and use information from the text",
            key="ret_ican1",
        )
        ret_ican2 = st.text_input(
            "I can statement 2",
            value="I can identify key details from different parts of a text",
            key="ret_ican2",
        )

    # Inference
    with st.expander("Lesson 3 — Inference", expanded=True):
        inf_date = st.date_input(
            "Date",
            value=_next_tuesday() + timedelta(days=3),
            key="inf_date",
        )
        inf_ican1 = st.text_input(
            "I can statement 1",
            value="I can explain what a text suggests using evidence",
            key="inf_ican1",
        )
        inf_ican2 = st.text_input(
            "I can statement 2",
            value="I can make inferences about what I have read",
            key="inf_ican2",
        )

st.divider()

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
ready = bool(text.strip()) and bool(key_question.strip())

if not ready:
    st.info("Paste the reading text and enter a key question to get started.")

generate = st.button(
    "Generate resources",
    type="primary",
    disabled=not ready,
    use_container_width=True,
)

if generate:
    with st.spinner("Generating questions… (this takes about 30 seconds)"):
        try:
            content = generate_content(
                text=text,
                key_question=key_question,
                vocab_day=voc_date.strftime("%A"),
                vocab_date=voc_date.strftime("%-d %B %Y"),
                vocab_i_can=[voc_ican1, voc_ican2],
                retrieval_day=ret_date.strftime("%A"),
                retrieval_date=ret_date.strftime("%-d %B %Y"),
                retrieval_i_can=[ret_ican1, ret_ican2],
                inference_day=inf_date.strftime("%A"),
                inference_date=inf_date.strftime("%-d %B %Y"),
                inference_i_can=[inf_ican1, inf_ican2],
            )
        except ValueError as e:
            st.error(f"Content generation failed: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error during generation: {e}")
            st.stop()

    # Inject the reading text into every lesson so pdf_builder can access it
    for lesson in content["lessons"]:
        lesson["text"] = text

    tmp = tempfile.mkdtemp()

    try:
        # ── PDFs ──────────────────────────────────────────────────────────
        with st.spinner("Building PDFs…"):
            pdf_paths = build_pdfs(
                content=content,
                icon_path=str(ICON_PATH) if ICON_PATH.exists() else "",
                output_dir=tmp,
            )

        # ── PPTX ──────────────────────────────────────────────────────────
        pptx_path = None
        if PPTX_AVAILABLE and TEMPLATE_PATH.exists():
            with st.spinner("Building PPTX…"):
                pptx_path = os.path.join(tmp, "Teaching_Slides.pptx")
                try:
                    build_pptx(
                        content=content,
                        template_path=str(TEMPLATE_PATH),
                        output_path=pptx_path,
                    )
                except Exception as e:
                    st.warning(f"PPTX build skipped: {e}")
                    pptx_path = None

        # ── XLSX ──────────────────────────────────────────────────────────
        with st.spinner("Building Excel…"):
            xlsx_path = os.path.join(tmp, "Reading_Content.xlsx")
            build_excel(content=content, output_path=xlsx_path)

        # ── Downloads ────────────────────────────────────────────────────
        st.success("Done! Download your files below.")
        st.divider()

        dl_cols = st.columns(4 if (pptx_path and os.path.exists(pptx_path)) else 3)

        def _dl_button(col, path, label, mime, file_name):
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    col.download_button(
                        label=label,
                        data=f.read(),
                        file_name=file_name,
                        mime=mime,
                        use_container_width=True,
                    )

        week_ref = voc_date.strftime("%d%b").upper()

        _dl_button(
            dl_cols[0],
            pdf_paths["standard"],
            "📄 Standard Pupil PDF",
            "application/pdf",
            f"BeingAReader_{week_ref}_Standard.pdf",
        )
        _dl_button(
            dl_cols[1],
            pdf_paths["supported"],
            "📄 Supported Pupil PDF",
            "application/pdf",
            f"BeingAReader_{week_ref}_Supported.pdf",
        )
        _dl_button(
            dl_cols[2],
            pdf_paths["answers"],
            "📄 All Answers PDF",
            "application/pdf",
            f"BeingAReader_{week_ref}_Answers.pdf",
        )

        if pptx_path and os.path.exists(pptx_path):
            _dl_button(
                dl_cols[3],
                pptx_path,
                "📊 Teaching PPTX",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                f"BeingAReader_{week_ref}_Teaching.pptx",
            )

        with open(xlsx_path, "rb") as f:
            st.download_button(
                label="📊 Content XLSX",
                data=f.read(),
                file_name=f"BeingAReader_{week_ref}_Content.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=False,
            )

    finally:
        # Clean up temp files after downloads are offered
        # (Streamlit holds file data in session state, so temp dir can go)
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass
