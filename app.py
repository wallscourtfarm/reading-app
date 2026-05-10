"""
app.py  –  Being a Reader Lesson Generator
Streamlit front end for Wallscourt Farm Academy.
"""

import streamlit as st
import os, io, zipfile, tempfile, datetime, base64, time
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

# Prefer webp; fall back to PNG if present
_LOGO_FILE = next(
    (REPO_ROOT / 'assets' / f for f in ('wfa_logo.webp', 'school_logo.png') if (REPO_ROOT / 'assets' / f).exists()),
    None
)

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

# ── header (base64-embedded logo — crisp, no hover zoom) ─────────────────────

def _logo_img_tag() -> str:
    if _LOGO_FILE and _LOGO_FILE.exists():
        mime = 'image/webp' if _LOGO_FILE.suffix == '.webp' else 'image/png'
        b64  = base64.b64encode(_LOGO_FILE.read_bytes()).decode()
        return f'<img src="data:{mime};base64,{b64}" style="height:64px;width:auto;display:block">'
    return ''

st.markdown(f"""
<div style="display:flex;align-items:center;gap:24px;padding-bottom:16px;
            border-bottom:2px solid #e5e5e5;margin-bottom:8px">
    {_logo_img_tag()}
    <div>
        <p style="margin:0;padding:0;font-size:2rem;line-height:1.15;
                  font-weight:700;color:#1a1a1a">Being a Reader</p>
        <p style="margin:4px 0 0 0;padding:0;color:#666;font-size:0.95rem">
            Reading lesson resource generator
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── session state ─────────────────────────────────────────────────────────────

if 'generated' not in st.session_state:
    st.session_state['generated'] = False
if 'lesson_data' not in st.session_state:
    st.session_state['lesson_data'] = None

# ── helpers ───────────────────────────────────────────────────────────────────

def fmt_date(d: datetime.date) -> str:
    return d.strftime('%d/%m/%Y')

def next_weekday(n: int) -> datetime.date:
    today = datetime.date.today()
    days_ahead = n - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + datetime.timedelta(days=days_ahead)

# ── input form ────────────────────────────────────────────────────────────────

st.markdown('### Lesson details')

with st.form('lesson_form'):
    col1, col2 = st.columns(2)
    with col1:
        week_ref = st.text_input('Week reference', placeholder='T5W5')
    with col2:
        topic = st.text_input('Topic / text', placeholder='Sound – how animals use it')

    key_question = st.text_input('Key question',
                                 placeholder='How do scientists investigate sound?')

    st.markdown('#### Lesson dates')
    st.caption('Pick a date for each lesson — the day name is worked out automatically.')

    col_v, col_r, col_i = st.columns(3)
    with col_v:
        st.markdown('**Lesson 1**  \nVocabulary')
        date1 = st.date_input('', value=next_weekday(1), key='date1',
                               format='DD/MM/YYYY', label_visibility='collapsed')
    with col_r:
        st.markdown('**Lesson 2**  \nRetrieval')
        date2 = st.date_input('', value=next_weekday(3), key='date2',
                               format='DD/MM/YYYY', label_visibility='collapsed')
    with col_i:
        st.markdown('**Lesson 3**  \nInference')
        date3 = st.date_input('', value=next_weekday(4), key='date3',
                               format='DD/MM/YYYY', label_visibility='collapsed')

    generate_btn = st.form_submit_button('✨ Generate content', use_container_width=True)

# ── generation ────────────────────────────────────────────────────────────────

if generate_btn:
    if not week_ref.strip():
        st.error('Enter a week reference.')
        st.stop()
    if not topic.strip():
        st.error('Enter a topic.')
        st.stop()
    if not key_question.strip():
        st.error('Enter the key question.')
        st.stop()

    # ── waiting UI ────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:#f0f4ff;border-left:4px solid #4a6fa5;
                padding:16px 20px;border-radius:4px;margin:12px 0">
        <p style="margin:0;font-weight:600;color:#1a1a1a;font-size:1rem">
            ⏳ Generating lesson content…
        </p>
        <p style="margin:6px 0 0 0;color:#444;font-size:0.9rem">
            Claude is writing three extracts, 45 questions, vocabulary lists and 
            we-do questions. This usually takes <strong>20–35 seconds</strong>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    progress = st.progress(0, text='Sending request to Claude…')

    try:
        lesson_days = [
            {'day': date1.strftime('%A'), 'date': fmt_date(date1)},
            {'day': date2.strftime('%A'), 'date': fmt_date(date2)},
            {'day': date3.strftime('%A'), 'date': fmt_date(date3)},
        ]

        # Animate progress while waiting
        import threading

        result_holder = {'data': None, 'error': None}

        def _generate():
            try:
                result_holder['data'] = generate_lesson_content(
                    topic, key_question, week_ref, lesson_days
                )
            except Exception as exc:
                result_holder['error'] = exc

        thread = threading.Thread(target=_generate)
        thread.start()

        # Update progress bar while the API call runs
        steps = [
            (5,  'Sending request to Claude…'),
            (15, 'Writing vocabulary and extracts…'),
            (35, 'Drafting retrieval questions…'),
            (55, 'Drafting inference questions…'),
            (75, 'Assembling final content…'),
            (90, 'Almost there…'),
        ]
        step_idx = 0
        elapsed = 0
        while thread.is_alive():
            if step_idx < len(steps) and elapsed >= step_idx * 5:
                pct, msg = steps[step_idx]
                progress.progress(pct, text=msg)
                step_idx += 1
            time.sleep(0.5)
            elapsed += 0.5

        thread.join()
        progress.progress(100, text='Done!')
        time.sleep(0.4)
        progress.empty()

        if result_holder['error']:
            raise result_holder['error']

        data = result_holder['data']
        data['week']         = week_ref
        data['topic']        = topic
        data['key_question'] = key_question
        st.session_state['lesson_data'] = data
        st.session_state['generated']   = True

    except Exception as e:
        st.error(f'Content generation failed: {e}')
        st.stop()

    st.success('✅ Content generated — review below, then build your files.')

# ── content preview ───────────────────────────────────────────────────────────

if st.session_state['generated'] and st.session_state['lesson_data']:
    data     = st.session_state['lesson_data']
    week_ref = data.get('week', 'TxWx')

    st.divider()
    st.markdown('### Content preview')

    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']
    for i, lesson in enumerate(data.get('lessons', [])):
        ltype = lesson.get('type', lesson_types[i])
        day   = lesson.get('day', '')
        date  = lesson.get('date', '')
        with st.expander(f'Lesson {i+1} — {ltype}  ({day} {date})', expanded=(i == 0)):
            st.markdown('**Vocabulary (5 words)**')
            for entry in lesson.get('vocab', []):
                st.markdown(f"- **{entry.get('word','')}** — {entry.get('definition','')}")
            st.markdown(f"**Focus word:** `{lesson.get('focus_word','')}`")
            st.markdown('**Standard extract**')
            st.info(lesson.get('extract_standard', ''))
            st.markdown('**Supported extract**')
            st.info(lesson.get('extract_supported', ''))
            st.markdown('**We-do questions (slide deck)**')
            for q in lesson.get('we_do_questions', []):
                st.markdown(f"**Q:** {q.get('question','')}")
                st.markdown(f"*A: {q.get('answer','')}*")

    st.divider()

    if st.button('📦 Build all files and download', use_container_width=True):

        build_progress = st.progress(0, text='Building PPTX…')

        try:
            with tempfile.TemporaryDirectory() as tmp:
                logo = str(_LOGO_FILE) if _LOGO_FILE and _LOGO_FILE.exists() else None

                pptx_out = os.path.join(tmp, f'Being_a_Reader_{week_ref}.pptx')
                build_pptx(str(TEMPLATE), pptx_out, data)
                build_progress.progress(40, text='Building PDFs…')

                pdf_paths = build_pdfs(data, data.get('key_question', ''),
                                       ICON_PATH, tmp, logo_path=logo)
                build_progress.progress(75, text='Building Excel…')

                xlsx_out = os.path.join(tmp, f'Reading_Content_{week_ref}.xlsx')
                build_excel(data, xlsx_out)
                build_progress.progress(95, text='Zipping…')

                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(pptx_out, os.path.basename(pptx_out))
                    zf.write(xlsx_out, os.path.basename(xlsx_out))
                    for name, path in pdf_paths.items():
                        zf.write(path, os.path.basename(path))
                zip_buf.seek(0)

            build_progress.progress(100, text='Done!')
            time.sleep(0.3)
            build_progress.empty()

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
            build_progress.empty()
            st.error(f'Build failed: {e}')
            st.code(traceback.format_exc())

    st.divider()
    st.caption('Content not right? Adjust inputs above and regenerate.')
