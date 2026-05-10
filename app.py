"""
app.py  –  Being a Reader Lesson Generator
Streamlit front end for Wallscourt Farm Academy.
"""

import streamlit as st
import os, io, json, zipfile, tempfile
from pathlib import Path

from content_generator import generate_lesson_content
from pptx_builder import build_pptx
from pdf_builder import build_pdfs
from excel_builder import build_excel

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title='Being a Reader – Lesson Generator',
    page_icon='📖',
    layout='centered',
)

st.title('📖 Being a Reader')
st.caption('Wallscourt Farm Academy — Year 4 reading lesson resource generator')
st.divider()

# ── file paths ────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).parent
TEMPLATE    = REPO_ROOT / 'template.pptx'
ICON_PATH   = str(REPO_ROOT / 'assets' / 'reader.png')

# ── session state ─────────────────────────────────────────────────────────────

if 'generated' not in st.session_state:
    st.session_state['generated'] = False
if 'lesson_data' not in st.session_state:
    st.session_state['lesson_data'] = None

# ── input form ────────────────────────────────────────────────────────────────

with st.form('lesson_form'):
    st.subheader('Lesson details')

    col1, col2 = st.columns(2)
    with col1:
        week_ref = st.text_input('Week reference', placeholder='T5W5')
    with col2:
        topic = st.text_input('Topic / text', placeholder='Sound – how animals use it')

    key_question = st.text_input(
        'Key question',
        placeholder='How do scientists investigate sound?'
    )

    st.subheader('Lesson days')

    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

    col_l1, col_d1 = st.columns([2, 2])
    with col_l1:
        day1 = st.selectbox('Lesson 1 – Vocabulary', DAYS, index=1)
    with col_d1:
        date1 = st.text_input('Date (L1)', placeholder='13/05/2026')

    col_l2, col_d2 = st.columns([2, 2])
    with col_l2:
        day2 = st.selectbox('Lesson 2 – Retrieval', DAYS, index=3)
    with col_d2:
        date2 = st.text_input('Date (L2)', placeholder='15/05/2026')

    col_l3, col_d3 = st.columns([2, 2])
    with col_l3:
        day3 = st.selectbox('Lesson 3 – Inference', DAYS, index=4)
    with col_d3:
        date3 = st.text_input('Date (L3)', placeholder='16/05/2026')

    generate_btn = st.form_submit_button('✨ Generate content', use_container_width=True)

# ── generation ────────────────────────────────────────────────────────────────

if generate_btn:
    # Basic validation
    if not week_ref.strip():
        st.error('Enter a week reference (e.g. T5W5).')
        st.stop()
    if not topic.strip():
        st.error('Enter a topic.')
        st.stop()
    if not key_question.strip():
        st.error('Enter the key question.')
        st.stop()

    with st.spinner('Generating lesson content with Claude…'):
        try:
            lesson_days = [
                {'day': day1, 'date': date1},
                {'day': day2, 'date': date2},
                {'day': day3, 'date': date3},
            ]
            data = generate_lesson_content(topic, key_question, week_ref, lesson_days)
            data['week'] = week_ref
            data['topic'] = topic
            data['key_question'] = key_question
            st.session_state['lesson_data'] = data
            st.session_state['generated'] = True
        except Exception as e:
            st.error(f'Content generation failed: {e}')
            st.stop()

    st.success('✅ Content generated.')

# ── content preview ───────────────────────────────────────────────────────────

if st.session_state['generated'] and st.session_state['lesson_data']:
    data = st.session_state['lesson_data']
    week_ref = data.get('week', 'TxWx')

    st.divider()
    st.subheader('Content preview')

    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']
    for i, lesson in enumerate(data.get('lessons', [])):
        ltype = lesson.get('type', lesson_types[i])
        with st.expander(f'Lesson {i+1} – {ltype}  ({lesson.get("day", "")} {lesson.get("date", "")})',
                         expanded=(i == 0)):
            # Vocab
            st.markdown('**Vocabulary (5 words)**')
            for entry in lesson.get('vocab', []):
                st.markdown(f"- **{entry.get('word', '')}** — {entry.get('definition', '')}")

            st.markdown(f"**Focus word:** {lesson.get('focus_word', '')}")

            # Extract
            st.markdown('**Standard extract**')
            st.info(lesson.get('extract_standard', ''))
            st.markdown('**Supported extract**')
            st.info(lesson.get('extract_supported', ''))

            # We-do questions
            st.markdown('**We-do questions (PPTX)**')
            for q in lesson.get('we_do_questions', []):
                st.markdown(f"Q: {q.get('question', '')}")
                st.markdown(f"A: *{q.get('answer', '')}*")

    st.divider()

    # ── build and download ────────────────────────────────────────────────────

    if st.button('📦 Build all files and download', use_container_width=True):
        with st.spinner('Building PPTX, PDFs and Excel…'):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    # 1. PPTX
                    pptx_out = os.path.join(tmp, f'Being_a_Reader_{week_ref}.pptx')
                    build_pptx(str(TEMPLATE), pptx_out, data)

                    # 2. PDFs
                    pdf_paths = build_pdfs(data, data.get('key_question', ''),
                                           ICON_PATH, tmp)

                    # 3. Excel
                    xlsx_out = os.path.join(tmp, f'Reading_Content_{week_ref}.xlsx')
                    build_excel(data, xlsx_out)

                    # 4. Zip everything
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(pptx_out, os.path.basename(pptx_out))
                        zf.write(xlsx_out, os.path.basename(xlsx_out))
                        for name, path in pdf_paths.items():
                            zf.write(path, os.path.basename(path))
                    zip_buf.seek(0)

                st.success('✅ Files built.')
                st.download_button(
                    label=f'⬇️ Download {week_ref} reading pack (.zip)',
                    data=zip_buf.getvalue(),
                    file_name=f'Being_a_Reader_{week_ref}.zip',
                    mime='application/zip',
                    use_container_width=True,
                )
            except Exception as e:
                import traceback
                st.error(f'Build failed: {e}')
                st.code(traceback.format_exc())

    st.divider()
    st.caption('Content not right? Adjust inputs above and regenerate.')
