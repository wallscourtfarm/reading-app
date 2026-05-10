"""
pptx_builder.py  –  Being a Reader PPTX builder
Clones template.pptx and replaces all lesson content for a new week.

Template (T5W4) slide → XML file mapping (slide1.xml is hidden):
  Lesson 1  title=slide2, vocab_table=slide4, focus=slide5, read=slide6,  pq=slide8
  Lesson 2  title=slide9, vocab_table=slide11, focus=slide12, read=slide13, pq=slide15
  Lesson 3  title=slide16, vocab_table=slide18, focus=slide19, read=slide20, pq=slide22

Template vocab words per lesson (used as keys for table replacement):
  L1: insulate, absorb, muffle, dense, transmit
  L2: echolocation, frequency, detect, evolved, locate
  L3: ultrasound, sonar, navigate, technology, diagnose

Template focus words:  L1=absorb  L2=detect  L3=technology
Template day names:    L1=Tuesday L2=Thursday L3=Friday
"""

import zipfile, shutil, os, re, html, tempfile
from pathlib import Path

# ── helpers ──────────────────────────────────────────────────────────────────

def xe(text: str) -> str:
    """Escape text for insertion into XML <a:t> element content."""
    return html.escape(str(text), quote=False)


def find_shape(slide_xml: str, spid: int) -> str | None:
    """Return the full <p:sp>...</p:sp> XML for a shape with the given id."""
    m = re.search(
        rf'<p:sp>(?:(?!<p:sp>).)*?<p:cNvPr[^>]*\bid="{spid}".*?</p:sp>',
        slide_xml, re.DOTALL
    )
    return m.group(0) if m else None


def get_para_rpr(para_xml: str) -> str:
    """Extract the first <a:rPr .../> from a paragraph, or a safe default."""
    m = re.search(r'<a:rPr[^/]*/>', para_xml)
    if m:
        return m.group(0)
    m = re.search(r'<a:rPr[^>]*>.*?</a:rPr>', para_xml, re.DOTALL)
    return m.group(0) if m else '<a:rPr lang="en-GB" dirty="0"/>'


def get_para_ppr(para_xml: str) -> str:
    """Extract <a:pPr .../> from a paragraph if present."""
    m = re.search(r'<a:pPr[^/]*/>', para_xml)
    return m.group(0) if m else ''


def get_paras(sp_xml: str) -> list[str]:
    """Return list of <a:p>…</a:p> strings from a shape's txBody."""
    return re.findall(r'<a:p>.*?</a:p>', sp_xml, re.DOTALL)


def build_para(text: str, rpr: str, ppr: str = '') -> str:
    """Build a single-run paragraph."""
    return f'<a:p>{ppr}<a:r>{rpr}<a:t>{xe(text)}</a:t></a:r></a:p>'


def build_empty_para(rpr: str) -> str:
    """Build an empty paragraph (blank line between Q+A pairs)."""
    return f'<a:p><a:endParaRPr {rpr[8:] if rpr.startswith("<a:rPr") else "lang=\"en-GB\""}></a:p>'


# ── single-shape text replacements ───────────────────────────────────────────

def replace_shape_single_text(slide_xml: str, spid: int, new_text: str) -> str:
    """Replace all text in a shape, preserving bodyPr/lstStyle intact."""
    sp = find_shape(slide_xml, spid)
    if not sp:
        return slide_xml
    paras = get_paras(sp)
    if not paras:
        return slide_xml
    rpr = get_para_rpr(paras[0])
    ppr = get_para_ppr(paras[0])
    new_para = build_para(new_text, rpr, ppr)
    # Replace ALL paragraphs (from first <a:p> to last </a:p>) in one pass.
    # This leaves bodyPr and lstStyle completely untouched.
    new_sp = re.sub(
        r'<a:p>.*</a:p>',
        new_para,
        sp,
        flags=re.DOTALL,
        count=1
    )
    return slide_xml.replace(sp, new_sp)


def replace_shape_qa_text(
    slide_xml: str, spid: int,
    q1: str, a1: str, q2: str, a2: str
) -> str:
    """
    Replace a practice-question shape (Q1 / A1 / blank / Q2 / A2).
    Preserves bodyPr/lstStyle from template; only the paragraph block is replaced.
    """
    sp = find_shape(slide_xml, spid)
    if not sp:
        return slide_xml
    paras = get_paras(sp)

    def rpr_for(idx: int) -> str:
        return get_para_rpr(paras[idx]) if idx < len(paras) else '<a:rPr lang="en-GB" sz="1900"/>'

    rpr_q1 = rpr_for(0)
    rpr_a1 = rpr_for(1)
    rpr_q2 = rpr_for(3) if len(paras) > 3 else rpr_for(0)
    rpr_a2 = rpr_for(4) if len(paras) > 4 else rpr_for(1)

    # Build sz value for empty paragraph from first rPr
    sz_m = re.search(r'sz="(\d+)"', rpr_q1)
    sz = sz_m.group(1) if sz_m else '1900'

    new_paras = (
        build_para(q1, rpr_q1) +
        build_para(a1, rpr_a1) +
        f'<a:p><a:endParaRPr lang="en-GB" sz="{sz}"/></a:p>' +
        build_para(q2, rpr_q2) +
        build_para(a2, rpr_a2)
    )
    # Replace all paragraphs in the shape, preserving bodyPr/lstStyle
    new_sp = re.sub(
        r'<a:p>.*</a:p>',
        new_paras,
        sp,
        flags=re.DOTALL,
        count=1
    )
    return slide_xml.replace(sp, new_sp)


# ── day name replacement ──────────────────────────────────────────────────────

_DAYS = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
         'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')

def replace_day_name(slide_xml: str, new_day: str) -> str:
    """Replace whatever day name is present in a title slide."""
    for day in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'):
        if f'<a:t>{day}</a:t>' in slide_xml:
            return slide_xml.replace(f'<a:t>{day}</a:t>', f'<a:t>{xe(new_day)}</a:t>', 1)
    return slide_xml


# ── vocab table replacement ───────────────────────────────────────────────────

def replace_vocab_table(
    slide_xml: str,
    template_vocab: list[tuple[str, str]],
    new_vocab: list[dict]          # [{'word': ..., 'definition': ...}, ...]
) -> str:
    """
    Replace vocab words and definitions in the table graphicFrame.
    template_vocab is the list of (word, definition) tuples from the template.
    new_vocab is the list of dicts from the generated content.
    """
    result = slide_xml
    for (old_word, old_def), entry in zip(template_vocab, new_vocab):
        new_word = entry['word']
        new_def  = entry['definition']
        # Replace in table cell text
        result = result.replace(
            f'<a:t>{xe(old_word)}</a:t>',
            f'<a:t>{xe(new_word)}</a:t>',
            1
        )
        result = result.replace(
            f'<a:t>{xe(old_def)}</a:t>',
            f'<a:t>{xe(new_def)}</a:t>',
            1
        )
    return result


# ── focus word replacement ────────────────────────────────────────────────────

def replace_focus_word(slide_xml: str, old_word: str, new_word: str) -> str:
    """Replace both occurrences of the focus word (write-5-times + word-web)."""
    return slide_xml.replace(
        f'<a:t>{xe(old_word)}</a:t>',
        f'<a:t>{xe(new_word)}</a:t>'
    )


# ── template constants ────────────────────────────────────────────────────────

# These must match the T5W4 template exactly.
TEMPLATE_VOCAB = [
    # L1 (slide4)
    [
        ('insulate', 'to stop sound or heat from passing through a material'),
        ('absorb',   'to take something in so that it cannot pass through'),
        ('muffle',   'to make a sound quieter by surrounding or blocking it'),
        ('dense',    'closely and heavily packed together'),
        ('transmit', 'to pass something through or from one place to another'),
    ],
    # L2 (slide11)
    [
        ('echolocation', 'finding objects by sending out sounds and listening for the echoes that bounce back'),
        ('frequency',    'how many vibrations happen per second; this determines how high or low a sound is'),
        ('detect',       'to notice or discover something, often using the senses'),
        ('evolved',      'changed slowly over a very long time to become better suited to surviving'),
        ('locate',       'to find where something is'),
    ],
    # L3 (slide18)
    [
        ('ultrasound',  'sound at a frequency too high for humans to hear, used in medicine and technology'),
        ('sonar',       'a system that uses sound echoes to detect objects underwater'),
        ('navigate',    'to find your way from one place to another'),
        ('technology',  'the use of scientific knowledge to create tools and systems that solve problems'),
        ('diagnose',    'to identify what is wrong with someone or something by examining it carefully'),
    ],
]

TEMPLATE_FOCUS_WORDS = ['absorb', 'detect', 'technology']

# Slide XML filenames per lesson role
SLIDE_MAP = [
    # L1
    dict(title='slide2', vocab_table='slide4', focus='slide5',
         read='slide6', read_extract_spid=15,
         pq='slide8',   pq_extract_spid=3, pq_qa_spid=10),
    # L2
    dict(title='slide9', vocab_table='slide11', focus='slide12',
         read='slide13', read_extract_spid=15,
         pq='slide15',  pq_extract_spid=9, pq_qa_spid=2),
    # L3
    dict(title='slide16', vocab_table='slide18', focus='slide19',
         read='slide20', read_extract_spid=15,
         pq='slide22',  pq_extract_spid=7, pq_qa_spid=3),
]


# ── main builder ─────────────────────────────────────────────────────────────

def build_pptx(template_path: str, output_path: str, lesson_data: dict) -> None:
    """
    Clone template.pptx and replace all lesson content.

    lesson_data structure:
    {
      "lessons": [
        {
          "day": "Tuesday",
          "vocab": [{"word": ..., "definition": ...} × 5],
          "focus_word": ...,
          "extract_standard": ...,
          "we_do_questions": [{"question": ..., "answer": ...} × 2]
        },
        ... (× 3 lessons)
      ]
    }
    """
    # Work in a temp directory
    with tempfile.TemporaryDirectory() as tmp:
        slides_dir = os.path.join(tmp, 'ppt', 'slides')

        # Unpack
        with zipfile.ZipFile(template_path, 'r') as z:
            z.extractall(tmp)

        # Process each lesson
        for i, lesson in enumerate(lesson_data['lessons']):
            sm = SLIDE_MAP[i]
            template_vocab = TEMPLATE_VOCAB[i]
            old_focus = TEMPLATE_FOCUS_WORDS[i]

            # Helper: read + modify + write a slide
            def modify(slide_name: str, fn):
                path = os.path.join(slides_dir, f'{slide_name}.xml')
                with open(path, encoding='utf-8') as f:
                    xml = f.read()
                xml = fn(xml)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(xml)

            # 1. Title slide – day name
            modify(sm['title'], lambda xml: replace_day_name(xml, lesson['day']))

            # 2. Vocab table
            modify(sm['vocab_table'], lambda xml, vocab=lesson['vocab'], tv=template_vocab:
                   replace_vocab_table(xml, tv, vocab))

            # 3. Focus word slide
            modify(sm['focus'], lambda xml, ow=old_focus, nw=lesson['focus_word']:
                   replace_focus_word(xml, ow, nw))

            # 4. Read slide – extract text
            extract = lesson['extract_standard']
            modify(sm['read'], lambda xml, sp=sm['read_extract_spid'], ex=extract:
                   replace_shape_single_text(xml, sp, ex))

            # 5. Practice Q slide – extract + Q&A
            we_do = lesson.get('we_do_questions', [])
            q1 = we_do[0]['question'] if len(we_do) > 0 else ''
            a1 = we_do[0]['answer']   if len(we_do) > 0 else ''
            q2 = we_do[1]['question'] if len(we_do) > 1 else ''
            a2 = we_do[1]['answer']   if len(we_do) > 1 else ''

            def update_pq(xml, sp_ex=sm['pq_extract_spid'], sp_qa=sm['pq_qa_spid'],
                          ex=extract, _q1=q1, _a1=a1, _q2=q2, _a2=a2):
                xml = replace_shape_single_text(xml, sp_ex, ex)
                xml = replace_shape_qa_text(xml, sp_qa, _q1, _a1, _q2, _a2)
                return xml

            modify(sm['pq'], update_pq)

        # Repack as zip
        shutil.copy(template_path, output_path)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(tmp):
                # Skip __MACOSX and .DS_Store
                dirs[:] = [d for d in dirs if not d.startswith('__')]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.relpath(fpath, tmp)
                    zout.write(fpath, arcname)
