"""
app.py  –  Being a Reader Lesson Generator
Streamlit front end for Wallscourt Farm Academy.
"""

import streamlit as st
import os, io, zipfile, tempfile, datetime
from pathlib import Path
from PIL import Image

from content_generator import generate_lesson_content
from pptx_builder import build_pptx
from pdf_builder import build_pdfs
from excel_builder import build_excel

# ── file paths ────────────────────────────────────────────────────────────────

REPO_ROOT  = Path(__file__).parent
TEMPLATE   = REPO_ROOT / 'template.pptx'
ICON_PATH  = str(REPO_ROOT / 'assets' / 'reader.png')
LOGO_PATH  = str(REPO_ROOT / 'assets' / 'school_logo.png')

# ── page config ───────────────────────────────────────────────────────────────

try:
    _page_icon = Image.open(ICON_PATH)
except Exception:
    _page_icon = '📖'

st.set_page_config(
    page_title='Being a Reader – Lesson Generator',
    page_icon=_page_icon,
    layout='centered',
)

# ── header ────────────────────────────────────────────────────────────────────

col_logo, col_title = st.columns([2, 5])
with col_logo:
    if Path(LOGO_PATH).exists():
        st.image(LOGO_PATH, width=160)
with col_title:
    st.title('Being a Reader')
    st.caption('Reading lesson resource generator')

st.divider()

# ── session state ─────────────────────────────────────────────────────────────

if 'generated' not in st.session_state:
    st.session_state['generated'] = False
if 'lesson_data' not in st.session_state:
    st.session_state['lesson_data'] = None

# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_date(d: datetime.date) -> str:
    return d.strftime('%d/%m/%Y')

def next_weekday(n: int) -> datetime.date:
    """Return the next occurrence of weekday n (0=Mon … 4=Fri)."""
    today = datetime.date.today()
    days_ahead = n - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + datetime.timedelta(days=days_ahead)

# ── input form ────────────────────────────────────────────────────────────────

with st.form('lesson_form'):
    st.subheader('Lesson details')

    col1, col2 = st.columns(2)
    with col1:
        week_ref = st.text_input('Week reference', placeholder='T5W5')
    with col2:
        topic = st.text_input('Topic / text', placeholder='Sound – how animals use it')

    key_question = st.text_input('Key question',
                                 placeholder='How do scientists investigate sound?')

    st.subheader('Lesson dates')
    st.caption('Pick the date for each lesson — the day is worked out automatically.')

    col_v, col_r, col_i = st.columns(3)
    with col_v:
        st.markdown('**Lesson 1**  \nVocabulary')
        date1 = st.date_input('', value=next_weekday(1), key='date1', format='DD/MM/YYYY',
                              label_visibility='collapsed')
    with col_r:
        st.markdown('**Lesson 2**  \nRetrieval')
        date2 = st.date_input('', value=next_weekday(3), key='date2', format='DD/MM/YYYY',
                              label_visibility='collapsed')
    with col_i:
        st.markdown('**Lesson 3**  \nInference')
        date3 = st.date_input('', value=next_weekday(4), key='date3', format='DD/MM/YYYY',
                              label_visibility='collapsed')

    generate_btn = st.form_submit_button('✨ Generate content', use_container_width=True)

# ── generation ────────────────────────────────────────────────────────────────

if generate_btn:
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
                {'day': date1.strftime('%A'), 'date': fmt_date(date1)},
                {'day': date2.strftime('%A'), 'date': fmt_date(date2)},
                {'day': date3.strftime('%A'), 'date': fmt_date(date3)},
            ]
            data = generate_lesson_content(topic, key_question, week_ref, lesson_days)
            data['week']         = week_ref
            data['topic']        = topic
            data['key_question'] = key_question
            st.session_state['lesson_data'] = data
            st.session_state['generated']   = True
        except Exception as e:
            st.error(f'Content generation failed: {e}')
            st.stop()

    st.success('✅ Content generated.')

# ── content preview ───────────────────────────────────────────────────────────

if st.session_state['generated'] and st.session_state['lesson_data']:
    data     = st.session_state['lesson_data']
    week_ref = data.get('week', 'TxWx')

    st.divider()
    st.subheader('Content preview')

    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']
    for i, lesson in enumerate(data.get('lessons', [])):
        ltype = lesson.get('type', lesson_types[i])
        day   = lesson.get('day', '')
        date  = lesson.get('date', '')
        with st.expander(f'Lesson {i+1} — {ltype}  ({day} {date})', expanded=(i == 0)):
            st.markdown('**Vocabulary (5 words)**')
            for entry in lesson.get('vocab', []):
                st.markdown(f"- **{entry.get('word','')}** — {entry.get('definition','')}")
            st.markdown(f"**Focus word:** {lesson.get('focus_word','')}")
            st.markdown('**Standard extract**')
            st.info(lesson.get('extract_standard', ''))
            st.markdown('**Supported extract**')
            st.info(lesson.get('extract_supported', ''))
            st.markdown('**We-do questions (PPTX)**')
            for q in lesson.get('we_do_questions', []):
                st.markdown(f"Q: {q.get('question','')}")
                st.markdown(f"A: *{q.get('answer','')}*")

    st.divider()

    if st.button('📦 Build all files and download', use_container_width=True):
        with st.spinner('Building PPTX, PDFs and Excel…'):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    pptx_out = os.path.join(tmp, f'Being_a_Reader_{week_ref}.pptx')
                    build_pptx(str(TEMPLATE), pptx_out, data)

                    logo = LOGO_PATH if Path(LOGO_PATH).exists() else None
                    pdf_paths = build_pdfs(data, data.get('key_question', ''),
                                           ICON_PATH, tmp, logo_path=logo)

                    xlsx_out = os.path.join(tmp, f'Reading_Content_{week_ref}.xlsx')
                    build_excel(data, xlsx_out)

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
