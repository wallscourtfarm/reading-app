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

# ── fonts ─────────────────────────────────────────────────────────────────────

def register_fonts(assets_dir: str):
    """Register any custom fonts if available; otherwise use Helvetica."""
    pass   # Helvetica is built-in; extend here if needed


# ── learning label header ─────────────────────────────────────────────────────

ICON_W = 14 * mm
LABEL_H = 12 * mm
LABEL_GAP = 2 * mm   # gap between label bottom and first content

def draw_header(c: Canvas, lesson_type: str, day: str, date: str,
                key_question: str, icon_path: str, y_top: float) -> float:
    """
    Draw the school learning-label header.
    Returns y position BELOW the header (ready for first content element).
    """
    # Icon
    icon_x = MARGIN
    icon_y = y_top - ICON_W
    try:
        c.drawImage(icon_path, icon_x, icon_y, width=ICON_W, height=ICON_W,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    # Coloured label bar
    bar_x = MARGIN + ICON_W + 2 * mm
    bar_w = CW - ICON_W - 2 * mm
    bar_y = y_top - LABEL_H
    c.setFillColor(LABEL_BG)
    c.rect(bar_x, bar_y, bar_w, LABEL_H, fill=1, stroke=0)

    # Label text on bar: "Being a Reader  |  Lesson N - TYPE  |  DAY  DATE"
    c.setFillColor(LABEL_FG)
    c.setFont('Helvetica-Bold', 9)
    label_text = f'Being a Reader  |  {lesson_type}  |  {day}  {date}'
    c.drawString(bar_x + 3 * mm, bar_y + 4 * mm, label_text)

    y_after_icon = y_top - max(ICON_W, LABEL_H) - LABEL_GAP

    # Key question line
    c.setFont('Helvetica-Bold', 10)
    c.setFillColor(BOX_BORDER)
    kq = f'Key question: {key_question}'
    # Word-wrap if needed
    max_chars = int(CW / (10 * 0.55))   # rough char width
    if len(kq) <= max_chars:
        c.drawString(MARGIN, y_after_icon, kq)
        y_after_icon -= 5 * mm
    else:
        # Simple two-line wrap
        words = kq.split()
        line1, line2 = [], []
        for w in words:
            if len(' '.join(line1 + [w])) <= max_chars:
                line1.append(w)
            else:
                line2.append(w)
        c.drawString(MARGIN, y_after_icon, ' '.join(line1))
        y_after_icon -= 4.5 * mm
        c.drawString(MARGIN, y_after_icon, ' '.join(line2))
        y_after_icon -= 4.5 * mm

    # Thin rule
    c.setStrokeColor(BOX_BORDER)
    c.setLineWidth(0.5)
    c.line(MARGIN, y_after_icon, W - MARGIN, y_after_icon)
    y_after_icon -= 3 * mm

    return y_after_icon


# ── I can statements ──────────────────────────────────────────────────────────

LC_MAP = {
    'Vocabulary': 'I can find and understand new words.',
    'Retrieval':  'I can find information in a text.',
    'Inference':  'I can read between the lines.',
}

def draw_lc(c: Canvas, lesson_type: str, y: float) -> float:
    """Draw I-can statement. Returns y below it."""
    text = LC_MAP.get(lesson_type, '')
    c.setFont('Helvetica-Oblique', 9)
    c.setFillColor(DARK)
    c.drawString(MARGIN, y, text)
    y -= 5 * mm
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


# ── question lines ────────────────────────────────────────────────────────────

LINE_H      = 7 * mm     # height of each answer line
LABEL_W     = 8 * mm     # width of the Q-number label

def draw_question(c: Canvas, qnum: int, question: str, y: float,
                  lines: int = 3, answer: str = None) -> float:
    """
    Draw one question with answer lines (or answer text for answer sheets).
    Returns y below.
    """
    # Question number badge
    c.setFillColor(BOX_BORDER)
    c.roundRect(MARGIN, y - 5 * mm, LABEL_W, 5.5 * mm, 1.5 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(MARGIN + LABEL_W / 2, y - 4 * mm, str(qnum))

    # Question text
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    q_style = ParagraphStyle('q', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=DARK)
    q_text = question.replace('&', '&amp;')
    p = Paragraph(q_text, q_style)
    q_w = CW - LABEL_W - 2 * mm
    _, q_h = p.wrap(q_w, 9999)
    p.drawOn(c, MARGIN + LABEL_W + 2 * mm, y - q_h)
    y -= max(q_h, 5 * mm) + 1 * mm

    if answer:
        # Answer sheet: draw green answer text
        a_style = ParagraphStyle('a', fontName='Helvetica', fontSize=9.5,
                                 leading=12, textColor=GREEN,
                                 leftIndent=LABEL_W + 2 * mm)
        a_text = answer.replace('&', '&amp;')
        ap = Paragraph(a_text, a_style)
        _, ah = ap.wrap(CW - LABEL_W - 2 * mm, 9999)
        ap.drawOn(c, MARGIN, y - ah)
        y -= ah + 3 * mm
    else:
        # Pupil sheet: answer lines
        c.setStrokeColor(HexColor('#aaaaaa'))
        c.setLineWidth(0.4)
        for _ in range(lines):
            y -= LINE_H
            c.line(MARGIN + LABEL_W + 2 * mm, y, W - MARGIN, y)
        y -= 2 * mm

    return y


# ── page builder ──────────────────────────────────────────────────────────────

def build_page(
    lesson: dict,
    lesson_type: str,
    version: str,       # 'standard', 'supported', 'answers_std', 'answers_sup'
    key_question: str,
    icon_path: str,
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

    # Header
    y = draw_header(c, lesson_type, day, date, key_question, icon_path, y)

    # I-can statement
    y = draw_lc(c, lesson_type, y)

    # Extract box
    y = draw_extract(c, extract, y)
    y -= 2 * mm

    # Questions
    for q in questions:
        qnum = q.get('number', 0)
        qtext = q.get('question', '')
        atext = q.get('answer', '') if show_answers else None
        # Estimate lines needed for pupil version (more lines for harder questions)
        lines = 4 if qnum >= 5 else 3
        y = draw_question(c, qnum, qtext, y, lines=lines, answer=atext)
        if y < MARGIN + 20 * mm:
            break    # clip if page is full

    c.save()
    return buf.getvalue()


# ── main function ─────────────────────────────────────────────────────────────

def build_pdfs(lesson_data: dict, key_question: str,
               icon_path: str, output_dir: str) -> dict[str, str]:
    """
    Build all PDFs and return a dict mapping name → filepath.
    {
      'standard_pupil': '/tmp/.../Standard_Pupil_TxWx.pdf',
      'supported_pupil': ...,
      'all_answers': ...,
    }
    """
    lessons = lesson_data['lessons']
    week_ref = lesson_data.get('week', 'TxWx')
    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']

    # Build 12 individual pages
    pages = {}   # (lesson_idx, version) → bytes
    for i, lesson in enumerate(lessons):
        ltype = lesson.get('type', lesson_types[i])
        for ver in ('standard', 'supported', 'answers_std', 'answers_sup'):
            pages[(i, ver)] = build_page(lesson, ltype, ver, key_question, icon_path)

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
