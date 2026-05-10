"""
pdf_builder.py  –  Generates Being a Reader PDFs using ReportLab.
Produces 3 merged PDFs: Standard Pupil, Supported Pupil, All Answers.
Each merged PDF has 3 pages (one per lesson).
"""

import os, io
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import Color, white, black, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter

# ── dimensions ────────────────────────────────────────────────────────────────

W, H = A4          # 595.28 × 841.89 pt
MARGIN = 8 * mm
CW = W - 2 * MARGIN

# ── colours ───────────────────────────────────────────────────────────────────

BOX_BORDER = HexColor('#2c2c6c')
BOX_BG     = HexColor('#f0f0f8')
GREEN      = HexColor('#1a7a1a')
DARK       = HexColor('#222222')
LABEL_BG   = HexColor('#2c2c6c')
LABEL_FG   = white

# ── learning label data ───────────────────────────────────────────────────────

# Fixed per lesson type — not AI-generated
LESSON_LABEL_DATA = {
    'Vocabulary': {
        'lf':    'understand and explain the meaning of new words',
        'ican1': 'find and explain the meaning of new vocabulary',
        'ican2': 'use a new word accurately in a sentence',
    },
    'Retrieval': {
        'lf':    'retrieve and record information from a text',
        'ican1': 'locate specific information within a text',
        'ican2': 'record what I have found using evidence from the text',
    },
    'Inference': {
        'lf':    'make inferences using evidence from a text',
        'ican1': 'read between the lines to work out meaning',
        'ican2': 'explain my thinking using evidence from the text',
    },
}

# ── learning label header ─────────────────────────────────────────────────────

ICON_W   = 14 * mm
LOGO_W   = 11 * mm
LABEL_H  = 14 * mm   # taller to fit logo
LABEL_GAP = 1.5 * mm

def _wrap_text(text: str, font: str, size: float, max_w: float, canvas: Canvas) -> list[str]:
    """Word-wrap text to fit max_w. Returns list of lines."""
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = ' '.join(cur + [word])
        if canvas.stringWidth(test, font, size) <= max_w:
            cur.append(word)
        else:
            if cur:
                lines.append(' '.join(cur))
            cur = [word]
    if cur:
        lines.append(' '.join(cur))
    return lines or [text]


def draw_header(c: Canvas, lesson_type: str, day: str, date: str,
                key_question: str, icon_path: str, y_top: float,
                logo_path: str | None = None) -> float:
    """
    Draw the school learning-label header.
    Returns y position BELOW the header (ready for first content element).

    Layout:
      [school logo] [blue bar: Being a Reader | TYPE | DAY DATE] [reader icon]
      Key question: QUESTION TEXT  (bold, underlined, dark blue)
      LF: ...  (italic)
      I can ...  (italic)
      I can ...  (italic)
      ─────── thin rule ──────────
    """
    bar_y  = y_top - LABEL_H

    # ── school logo (left of bar) ─────────────────────────────────────────────
    logo_x = MARGIN
    logo_w = 0
    if logo_path and os.path.exists(logo_path):
        try:
            from PIL import Image as PILImage
            import tempfile as _tf
            _img = PILImage.open(logo_path)
            # Flatten RGBA/P to RGB so ReportLab can embed it
            if _img.mode in ('RGBA', 'P'):
                _bg = PILImage.new('RGB', _img.size, (255, 255, 255))
                _bg.paste(_img, mask=(_img.split()[3] if _img.mode == 'RGBA' else None))
                _img = _bg
            elif _img.mode != 'RGB':
                _img = _img.convert('RGB')
            _ar    = _img.width / _img.height
            logo_h = LABEL_H - 2 * mm
            logo_w = logo_h * _ar
            with _tf.NamedTemporaryFile(suffix='.png', delete=False) as _t:
                _tmp = _t.name
            _img.save(_tmp, 'PNG')
            c.drawImage(_tmp, logo_x, bar_y + 1 * mm,
                        width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask='auto')
            os.unlink(_tmp)
        except Exception:
            logo_w = 0
    bar_x_start = MARGIN + logo_w + 1.5 * mm

    # ── reader icon (right of bar) ────────────────────────────────────────────
    icon_x = W - MARGIN - ICON_W
    try:
        c.drawImage(icon_path, icon_x, bar_y + 1 * mm,
                    width=ICON_W, height=LABEL_H - 2 * mm,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    bar_x_end = icon_x - 1.5 * mm

    # ── coloured bar ──────────────────────────────────────────────────────────
    bar_w = bar_x_end - bar_x_start
    c.setFillColor(LABEL_BG)
    c.rect(bar_x_start, bar_y, bar_w, LABEL_H, fill=1, stroke=0)

    c.setFillColor(LABEL_FG)
    c.setFont('Helvetica-Bold', 9)
    bar_label = f'Being a Reader  |  {lesson_type}  |  {day}  {date}'
    c.drawString(bar_x_start + 3 * mm, bar_y + (LABEL_H / 2) - 2.5 * mm, bar_label)

    y = bar_y - LABEL_GAP

    # ── key question (bold, underlined, dark blue) ────────────────────────────
    kq_font, kq_size = 'Helvetica-Bold', 10
    kq_full = f'Key question: {key_question}'
    max_kq_w = CW
    lines = _wrap_text(kq_full, kq_font, kq_size, max_kq_w, c)
    line_h = kq_size * 1.3 / 72 * 25.4 * mm   # pt → mm (approx)

    c.setFont(kq_font, kq_size)
    c.setFillColor(BOX_BORDER)
    for line in lines:
        c.drawString(MARGIN, y, line)
        lw = c.stringWidth(line, kq_font, kq_size)
        c.setLineWidth(0.5)
        c.setStrokeColor(BOX_BORDER)
        c.line(MARGIN, y - 0.8 * mm, MARGIN + lw, y - 0.8 * mm)
        y -= line_h + 0.5 * mm
    y -= 1.5 * mm

    # ── LF + I can statements (italic) ───────────────────────────────────────
    lc = LESSON_LABEL_DATA.get(lesson_type, {})
    lf    = lc.get('lf', '')
    ican1 = lc.get('ican1', '')
    ican2 = lc.get('ican2', '')

    c.setFont('Helvetica-Oblique', 9)
    c.setFillColor(DARK)
    lc_line_h = 9 * 1.3 / 72 * 25.4 * mm

    for text in (f'LF: {lf}', f'I can {ican1}.', f'I can {ican2}.'):
        c.drawString(MARGIN, y, text)
        y -= lc_line_h + 0.3 * mm
    y -= 1.5 * mm

    # ── thin rule ─────────────────────────────────────────────────────────────
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(0.4)
    c.line(MARGIN, y, W - MARGIN, y)
    y -= 3 * mm

    return y


# ── text box ──────────────────────────────────────────────────────────────────

def draw_textbox(c: Canvas, text: str, x: float, y: float,
                 width: float, font_size: int = 10) -> float:
    """
    Draw a word-wrapped text block. Returns y below the block.
    """
    from reportlab.platypus import Paragraph, Frame
    from reportlab.lib.styles import ParagraphStyle

    style = ParagraphStyle(
        'body',
        fontName='Helvetica',
        fontSize=font_size,
        leading=font_size * 1.3,
        textColor=DARK,
    )
    p = Paragraph(text.replace('\n', '<br/>'), style)
    w_used, h_used = p.wrap(width, 9999)
    p.drawOn(c, x, y - h_used)
    return y - h_used - 2 * mm


# ── extract box ───────────────────────────────────────────────────────────────

def draw_extract(c: Canvas, extract: str, y: float) -> float:
    """Draw extract in a coloured box. Returns y below."""
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle

    style = ParagraphStyle(
        'extract',
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=DARK,
        leftIndent=3 * mm,
        rightIndent=3 * mm,
    )
    p = Paragraph(extract, style)
    w_used, h_used = p.wrap(CW - 6 * mm, 9999)
    box_h = h_used + 4 * mm
    # Draw box
    c.setFillColor(BOX_BG)
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(0.75)
    c.rect(MARGIN, y - box_h, CW, box_h, fill=1, stroke=1)
    # Draw text
    p.drawOn(c, MARGIN + 3 * mm, y - box_h + 2 * mm)
    return y - box_h - 3 * mm


# ── question rendering ────────────────────────────────────────────────────────

LINE_H  = 7 * mm    # answer line spacing
LABEL_W = 8 * mm    # width of the Q-number badge
Q_GAP   = 2 * mm    # gap between questions

def _draw_q_badge(c: Canvas, qnum: int, y: float):
    """Draw the dark blue rounded number badge. Returns nothing — caller manages y."""
    c.setFillColor(BOX_BORDER)
    c.roundRect(MARGIN, y - 5 * mm, LABEL_W, 5.5 * mm, 1.5 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN + LABEL_W / 2, y - 4 * mm, str(qnum))


def _draw_q_text(c: Canvas, question: str, y: float) -> float:
    """Draw bold question text. Returns y below it."""
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    q_w = CW - LABEL_W - 2 * mm
    style = ParagraphStyle('q', fontName='Helvetica-Bold', fontSize=10,
                           leading=12.5, textColor=DARK)
    p = Paragraph(question.replace('&', '&amp;'), style)
    _, q_h = p.wrap(q_w, 9999)
    p.drawOn(c, MARGIN + LABEL_W + 2 * mm, y - q_h)
    return y - max(q_h, 5 * mm) - 1 * mm


def _draw_answer_lines(c: Canvas, y: float, n: int) -> float:
    c.setStrokeColor(HexColor('#aaaaaa'))
    c.setLineWidth(0.4)
    for _ in range(n):
        y -= LINE_H
        c.line(MARGIN + LABEL_W + 2 * mm, y, W - MARGIN, y)
    return y - Q_GAP


def _draw_answer_text(c: Canvas, answer: str, y: float) -> float:
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    style = ParagraphStyle('a', fontName='Helvetica', fontSize=9.5,
                           leading=12, textColor=GREEN,
                           leftIndent=LABEL_W + 2 * mm)
    p = Paragraph(answer.replace('&', '&amp;'), style)
    _, ah = p.wrap(CW - LABEL_W - 2 * mm, 9999)
    p.drawOn(c, MARGIN, y - ah)
    return y - ah - Q_GAP


def _draw_mc_grid(c: Canvas, options: list, answer: str | None, y: float) -> float:
    """
    Draw a 2×2 multiple-choice grid matching T5W4 format.
    No letters — just plain text in bordered cells.
    If answer is set (answer sheet), correct option is shown in green.
    """
    opts = (options + ['', '', '', ''])[:4]   # pad to 4
    col_w = CW / 2
    row_h = 8 * mm
    y_top = y

    c.setLineWidth(0.5)
    c.setFont('Helvetica', 9.5)

    for row in range(2):
        for col in range(2):
            idx = row * 2 + col
            opt = opts[idx]
            x  = MARGIN + col * col_w
            ry = y_top - row * row_h - row_h
            # Cell border (grey, no fill)
            c.setStrokeColor(HexColor('#888888'))
            c.setFillColor(white)
            c.rect(x, ry, col_w, row_h, fill=1, stroke=1)
            # Option text
            is_correct = answer and opt and opt.strip() == answer.strip()
            c.setFillColor(GREEN if is_correct else DARK)
            c.setFont('Helvetica-Bold' if is_correct else 'Helvetica', 9.5)
            c.drawString(x + 2 * mm, ry + 2.5 * mm, opt)

    return y_top - 2 * row_h - Q_GAP


def _draw_ordering_boxes(c: Canvas, items: list, answer: str | None, y: float) -> float:
    """
    Draw ordering question: small square box to the left of each item.
    On answer sheets, show the correct number in the box in green.
    """
    box_sz  = 5 * mm
    item_h  = 6.5 * mm
    box_x   = MARGIN + LABEL_W + 2 * mm

    # Parse answer string like "2, 4, 1, 3" into a mapping item_idx → position
    pos_map = {}
    if answer:
        nums = [s.strip() for s in answer.replace(';', ',').split(',') if s.strip().isdigit()]
        if len(nums) == len(items):
            pos_map = {i: nums[i] for i in range(len(items))}

    c.setFont('Helvetica', 9.5)
    for i, item in enumerate(items):
        item_y = y - i * item_h - item_h
        # Box
        c.setStrokeColor(HexColor('#888888'))
        c.setLineWidth(0.5)
        c.setFillColor(white)
        c.rect(box_x, item_y, box_sz, box_sz, fill=1, stroke=1)
        # Answer number inside box (answer sheet only)
        if pos_map.get(i):
            c.setFillColor(GREEN)
            c.setFont('Helvetica-Bold', 9)
            c.drawCentredString(box_x + box_sz / 2, item_y + 1.2 * mm, pos_map[i])
        # Item text
        c.setFillColor(DARK)
        c.setFont('Helvetica', 9.5)
        c.drawString(box_x + box_sz + 2 * mm, item_y + 1.2 * mm, item)

    return y - len(items) * item_h - Q_GAP


def draw_question(c: Canvas, q: dict, y: float, show_answers: bool = False) -> float:
    """
    Render one question. Dispatches on q['type']:
      retrieval, list, vocabulary, explain, compare, inference, fill_blank
        → question text + answer lines / green answer
      multiple_choice
        → question text + 2×2 grid
      ordering
        → question text + boxed items
    Returns y below.
    """
    qnum    = q.get('number', 0)
    qtype   = q.get('type', 'retrieval')
    qtext   = q.get('question', '')
    answer  = q.get('answer', '') if show_answers else None

    _draw_q_badge(c, qnum, y)
    y = _draw_q_text(c, qtext, y)

    if qtype == 'multiple_choice':
        opts = q.get('options', [])
        ans_label = q.get('answer', '') if show_answers else None
        y = _draw_mc_grid(c, opts, ans_label, y)

    elif qtype == 'ordering':
        items = q.get('items', [])
        ans_label = q.get('answer', '') if show_answers else None
        y = _draw_ordering_boxes(c, items, ans_label, y)

    else:
        # All other types: answer lines or green answer text
        if show_answers and answer:
            y = _draw_answer_text(c, answer, y)
        else:
            # Scale lines by question number (harder = more space)
            lines = 4 if qnum >= 6 else 3 if qnum >= 4 else 2
            y = _draw_answer_lines(c, y, lines)

    return y


# ── page builder ──────────────────────────────────────────────────────────────

def build_page(
    lesson: dict,
    lesson_type: str,
    version: str,       # 'standard', 'supported', 'answers_std', 'answers_sup'
    key_question: str,
    icon_path: str,
    logo_path: str | None = None,
) -> bytes:
    """Build a single A4 page as PDF bytes."""

    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)

    day  = lesson.get('day', '')
    date = lesson.get('date', '')
    extract = lesson.get(
        'extract_supported' if version == 'supported' else 'extract_standard', ''
    )
    questions = lesson.get(
        'questions_supported' if version in ('supported', 'answers_sup')
        else 'questions_standard',
        []
    )
    show_answers = version in ('answers_std', 'answers_sup')

    y = H - MARGIN

    # Header (includes LF + I can statements internally)
    y = draw_header(c, lesson_type, day, date, key_question, icon_path, y,
                    logo_path=logo_path)

    # Extract box
    y = draw_extract(c, extract, y)
    y -= 2 * mm

    # Questions
    for q in questions:
        y = draw_question(c, q, y, show_answers=show_answers)
        if y < MARGIN + 20 * mm:
            break

    c.save()
    return buf.getvalue()


# ── main function ─────────────────────────────────────────────────────────────

def build_pdfs(lesson_data: dict, key_question: str,
               icon_path: str, output_dir: str,
               logo_path: str | None = None) -> dict[str, str]:
    """
    Build all PDFs and return a dict mapping name → filepath.
    """
    lessons = lesson_data['lessons']
    week_ref = lesson_data.get('week', 'TxWx')
    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']

    pages = {}
    for i, lesson in enumerate(lessons):
        ltype = lesson.get('type', lesson_types[i])
        for ver in ('standard', 'supported', 'answers_std', 'answers_sup'):
            pages[(i, ver)] = build_page(lesson, ltype, ver, key_question,
                                         icon_path, logo_path=logo_path)

    def merge(page_keys: list) -> bytes:
        writer = PdfWriter()
        for key in page_keys:
            reader = PdfReader(io.BytesIO(pages[key]))
            writer.add_page(reader.pages[0])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    os.makedirs(output_dir, exist_ok=True)

    paths = {}

    # Standard pupil: L1_std, L2_std, L3_std
    data = merge([(i, 'standard') for i in range(3)])
    p = os.path.join(output_dir, f'Standard_Pupil_{week_ref}.pdf')
    with open(p, 'wb') as f: f.write(data)
    paths['standard_pupil'] = p

    # Supported pupil
    data = merge([(i, 'supported') for i in range(3)])
    p = os.path.join(output_dir, f'Supported_Pupil_{week_ref}.pdf')
    with open(p, 'wb') as f: f.write(data)
    paths['supported_pupil'] = p

    # All answers: std_ans, sup_ans for each lesson interleaved
    ans_keys = []
    for i in range(3):
        ans_keys += [(i, 'answers_std'), (i, 'answers_sup')]
    data = merge(ans_keys)
    p = os.path.join(output_dir, f'All_Answers_{week_ref}.pdf')
    with open(p, 'wb') as f: f.write(data)
    paths['all_answers'] = p

    return paths
