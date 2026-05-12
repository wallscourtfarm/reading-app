"""
pdf_builder.py
Consumes content dict from content_generator.py.
Produces 3 merged PDFs:
  - Standard Pupil  (Voc + Ret + Inf, 7 questions each)
  - Supported Pupil (Voc + Ret + Inf, 5 questions each, with scaffolds)
  - All Answers     (6 pages: Std + Sup for each lesson)

Renders all 9 question formats:
  open_line, find_and_copy, numbered_list,
  tick_one, tick_two, true_false_table,
  sequencing, reason_evidence_table, two_part_ab
"""

import os
import hashlib
import random
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import mm
from pypdf import PdfReader, PdfWriter

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------
W, H = A4
MARGIN = 8 * mm
CW = W - 2 * MARGIN        # usable content width
MIN_Y = 14 * mm             # bottom margin — nothing drawn below this

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BOX_BORDER = (0.173, 0.173, 0.424)   # #2c2c6c — borders, question labels
BOX_BG     = (0.941, 0.941, 0.973)   # #f0f0f8 — reading text box
GREEN      = (0.102, 0.478, 0.102)   # #1a7a1a — answer text and highlights
DARK       = (0.133, 0.133, 0.133)   # body text
GREY_LINE  = (0.6,   0.6,   0.6  )  # ruled lines, cell borders
LIGHT_GREY = (0.94,  0.94,  0.94 )  # table cell backgrounds
TICK_CELL  = (0.85,  0.95,  0.85 )  # answer highlight cell


# ===========================================================================
# Low-level drawing utilities
# ===========================================================================

def wrap_text(c, text, font, size, max_w):
    """Return list of lines that fit within max_w."""
    words = str(text).split()
    lines, line = [], ''
    for w in words:
        test = (line + ' ' + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines or ['']


def text_height(c, text, font, size, max_w, line_leading=1.35):
    """Return height of wrapped text block in points."""
    lines = wrap_text(c, text, font, size, max_w)
    return len(lines) * size * line_leading


def draw_wrapped(c, text, font, size, x, y, max_w, line_leading=1.35):
    """Draw wrapped text starting at (x, y). Returns y after last line."""
    c.setFont(font, size)
    lines = wrap_text(c, text, font, size, max_w)
    for line in lines:
        c.drawString(x, y, line)
        y -= size * line_leading
    return y


def draw_checkbox(c, x, y, size=4 * mm, filled=False, fill_colour=None):
    """Draw a small square checkbox. Returns (right_edge, centre_y)."""
    if filled and fill_colour:
        c.setFillColorRGB(*fill_colour)
        c.rect(x, y - size, size, size, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1) if not filled else None
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    c.rect(x, y - size, size, size, fill=0, stroke=1)
    return x + size, y - size / 2


def marks_label(c, marks, y):
    """Print 'N mark(s)' right-aligned at current y."""
    label = f"{marks} mark" if marks == 1 else f"{marks} marks"
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawRightString(MARGIN + CW, y, label)


def draw_tick_instruction(c, instruction, y):
    """Print 'Tick one.' or 'Tick two.' right-aligned."""
    c.setFont("Helvetica-BoldOblique", 8)
    c.setFillColorRGB(*BOX_BORDER)
    c.drawRightString(MARGIN + CW, y, instruction)
    return y - 4 * mm


def draw_ruled_line(c, y, gap=6.5 * mm):
    """Draw one answer line at y. Returns y below line."""
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    c.line(MARGIN, y - gap, MARGIN + CW, y - gap)
    return y - gap


def deterministic_shuffle(items):
    """Shuffle a list reproducibly based on its own content."""
    seed = int(hashlib.md5('|'.join(items).encode()).hexdigest()[:8], 16)
    r = random.Random(seed)
    result = list(items)
    r.shuffle(result)
    return result


# ===========================================================================
# Header
# ===========================================================================

def draw_header(c, lesson_type, day, date, key_q, i_can_statements, icon_path):
    """Draw the learning label. Returns y immediately below the final rule."""
    y = H - MARGIN

    # Row 1: "Key Question"  [icon]  "Day Date"
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(*DARK)
    c.drawString(MARGIN, y - 5 * mm, "Key Question")

    icon_x = MARGIN + 27 * mm
    try:
        c.drawImage(icon_path, icon_x, y - 7 * mm,
                    width=7 * mm, height=7 * mm,
                    mask='auto', preserveAspectRatio=True)
    except Exception:
        pass

    c.setFont("Helvetica", 8)
    c.drawString(icon_x + 8 * mm, y - 5 * mm, f"{day}  {date}")
    y -= 8 * mm

    # Key question — bold, underlined, dark blue
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(*BOX_BORDER)
    c.drawString(MARGIN, y - 4 * mm, key_q)
    kq_w = c.stringWidth(key_q, "Helvetica-Bold", 10)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(*BOX_BORDER)
    c.line(MARGIN, y - 5 * mm, MARGIN + kq_w, y - 5 * mm)
    y -= 7 * mm

    # I can statements
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(*DARK)
    for ican in i_can_statements:
        c.drawString(MARGIN, y - 3.5 * mm, ican)
        y -= 4.5 * mm

    # Rule
    y -= 1 * mm
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, MARGIN + CW, y)
    y -= 2.5 * mm

    return y


# ===========================================================================
# Reading text box
# ===========================================================================

def draw_text_box(c, text, y_top, font_size=10):
    """Draw the reading extract box. Returns y below box."""
    lines = wrap_text(c, text, "Helvetica", font_size, CW - 6 * mm)
    lh = font_size * 1.4
    box_h = len(lines) * lh + 6 * mm

    c.setFillColorRGB(*BOX_BG)
    c.setStrokeColorRGB(*BOX_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, y_top - box_h, CW, box_h, 2 * mm, fill=1, stroke=1)

    c.setFillColorRGB(*DARK)
    c.setFont("Helvetica", font_size)
    ty = y_top - 3.5 * mm - font_size * 0.72
    for line in lines:
        c.drawString(MARGIN + 3 * mm, ty, line)
        ty -= lh

    return y_top - box_h - 3 * mm


# ===========================================================================
# Question preamble (text_reference + question label)
# ===========================================================================

def draw_preamble(c, q, y):
    """
    Draw text_reference (small grey italic) and question number + text.
    Returns y after question text, and the indent width used for the number.
    """
    # text_reference
    ref = q.get('text_reference', '').strip()
    if ref:
        c.setFont("Helvetica-Oblique", 7.5)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(MARGIN, y, ref)
        y -= 7.5 * 1.3

    # Question number + text
    c.setFillColorRGB(*DARK)
    c.setFont("Helvetica-Bold", 9)
    label = f"{q['number']}. "
    lw = c.stringWidth(label, "Helvetica-Bold", 9)
    c.drawString(MARGIN, y, label)

    qtext = q.get('question', '')
    # If question contains a quoted line (separated by \n\n), draw quote first
    parts = qtext.split('\n\n', 1)
    if len(parts) == 2:
        quote, question_body = parts
        c.setFont("Helvetica-BoldOblique", 9)
        c.drawString(MARGIN + lw, y, quote)
        y -= 9 * 1.35
        c.setFont("Helvetica-Bold", 9)
        q_lines = wrap_text(c, question_body, "Helvetica-Bold", 9, CW - lw)
        for i, line in enumerate(q_lines):
            c.drawString(MARGIN + (lw if i == 0 else 0), y, line)
            y -= 9 * 1.35
    else:
        q_lines = wrap_text(c, qtext, "Helvetica-Bold", 9, CW - lw)
        for i, line in enumerate(q_lines):
            c.drawString(MARGIN + (lw if i == 0 else 0), y, line)
            y -= 9 * 1.35

    y -= 1 * mm
    return y, lw


def draw_scaffold(c, scaffold, y):
    """Draw the supported scaffold hint in italic below the question."""
    if not scaffold:
        return y
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.4, 0.4, 0.6)
    c.drawString(MARGIN + 3 * mm, y, scaffold)
    y -= 8 * 1.35
    return y


# ===========================================================================
# Format renderers — pupil versions
# ===========================================================================

def render_open_line_pupil(c, q, y, is_supported):
    lines_n = q['format_data'].get('lines', 2)
    if is_supported:
        y = draw_scaffold(c, q.get('supported_scaffold'), y)
    gap = 6.5 * mm
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for i in range(lines_n):
        ly = y - (i + 1) * gap
        c.line(MARGIN, ly, MARGIN + CW, ly)
    return y - lines_n * gap - 2 * mm


def render_find_and_copy_pupil(c, q, y, is_supported):
    # Short blank line for one word/phrase
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(*DARK)
    c.drawString(MARGIN, y - 3 * mm, "_______________________________________________")
    return y - 8 * mm


def render_numbered_list_pupil(c, q, y, is_supported):
    n = q['format_data'].get('num_points', 2)
    if is_supported:
        y = draw_scaffold(c, q.get('supported_scaffold'), y)
    gap = 6.5 * mm
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(*DARK)
    for i in range(n):
        c.drawString(MARGIN, y - (i * (gap * 2)) - 3 * mm, f"{i + 1}.")
        # Two ruled lines per point
        c.line(MARGIN + 5 * mm, y - (i * (gap * 2)) - gap, MARGIN + CW, y - (i * (gap * 2)) - gap)
        c.line(MARGIN + 5 * mm, y - (i * (gap * 2)) - gap * 2, MARGIN + CW, y - (i * (gap * 2)) - gap * 2)
    return y - n * gap * 2 - 2 * mm


def render_tick_one_pupil(c, q, y):
    fd = q['format_data']
    options = fd.get('options', [])
    y = draw_tick_instruction(c, "Tick one.", y)
    row_h = 6.5 * mm
    col_w = CW / 2
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for row in range(2):
        for col in range(2):
            idx = row * 2 + col
            if idx >= len(options):
                break
            x = MARGIN + col * col_w
            ry = y - row * row_h
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, ry - row_h, col_w, row_h, fill=1, stroke=1)
            c.setFillColorRGB(*DARK)
            c.setFont("Helvetica", 8.5)
            c.drawString(x + 2 * mm, ry - row_h + 2 * mm, options[idx])
    return y - 2 * row_h - 2 * mm


def render_tick_two_pupil(c, q, y):
    fd = q['format_data']
    options = fd.get('options', [])
    y = draw_tick_instruction(c, "Tick two.", y)
    row_h = 6 * mm
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for i, opt in enumerate(options):
        ry = y - i * row_h
        c.setFillColorRGB(1, 1, 1)
        c.rect(MARGIN, ry - row_h, CW, row_h, fill=1, stroke=1)
        draw_checkbox(c, MARGIN + 2 * mm, ry - row_h * 0.2)
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 8.5)
        c.drawString(MARGIN + 8 * mm, ry - row_h + 2 * mm, opt)
    return y - len(options) * row_h - 2 * mm


def render_true_false_table_pupil(c, q, y):
    fd = q['format_data']
    statements = fd.get('statements', [])
    col_stmt = CW * 0.72
    col_tf = CW * 0.14
    row_h = 7 * mm

    # Header row
    c.setFillColorRGB(*BOX_BORDER)
    c.rect(MARGIN, y - row_h, CW, row_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MARGIN + 2 * mm, y - row_h + 2 * mm, "Statement")
    c.drawCentredString(MARGIN + col_stmt + col_tf / 2, y - row_h + 2 * mm, "True")
    c.drawCentredString(MARGIN + col_stmt + col_tf + col_tf / 2, y - row_h + 2 * mm, "False")
    y -= row_h

    # Statement rows
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for i, stmt in enumerate(statements):
        fill = LIGHT_GREY if i % 2 == 0 else (1, 1, 1)
        c.setFillColorRGB(*fill)
        c.rect(MARGIN, y - row_h, CW, row_h, fill=1, stroke=1)
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN + 2 * mm, y - row_h + 2 * mm, stmt.get('text', ''))
        # Dividers between T/F columns
        c.setLineWidth(0.3)
        c.line(MARGIN + col_stmt, y, MARGIN + col_stmt, y - row_h)
        c.line(MARGIN + col_stmt + col_tf, y, MARGIN + col_stmt + col_tf, y - row_h)
        y -= row_h

    return y - 2 * mm


def render_sequencing_pupil(c, q, y):
    fd = q['format_data']
    items = deterministic_shuffle(fd.get('items', []))
    row_h = 6 * mm
    box_sz = 4.5 * mm

    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(*DARK)
    for i, item in enumerate(items):
        ry = y - i * row_h
        # Small square box for number
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(*BOX_BORDER)
        c.setLineWidth(0.5)
        c.rect(MARGIN, ry - box_sz, box_sz, box_sz, fill=1, stroke=1)
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 8.5)
        c.drawString(MARGIN + box_sz + 2 * mm, ry - row_h + 2 * mm, item)
    return y - len(items) * row_h - 2 * mm


def render_reason_evidence_pupil(c, q, y):
    fd = q['format_data']
    example = fd.get('example', {})
    blank_rows = fd.get('rows', 2)
    col_r = CW * 0.42
    col_e = CW - col_r
    header_h = 6 * mm
    row_h = 11 * mm

    # Header
    c.setFillColorRGB(*BOX_BORDER)
    c.rect(MARGIN, y - header_h, col_r, header_h, fill=1, stroke=0)
    c.rect(MARGIN + col_r, y - header_h, col_e, header_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(MARGIN + col_r / 2, y - header_h + 2 * mm, "Reason")
    c.drawCentredString(MARGIN + col_r + col_e / 2, y - header_h + 2 * mm, "Evidence")
    y -= header_h

    # Example row (shaded)
    c.setFillColorRGB(*LIGHT_GREY)
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    c.rect(MARGIN, y - row_h, col_r, row_h, fill=1, stroke=1)
    c.rect(MARGIN + col_r, y - row_h, col_e, row_h, fill=1, stroke=1)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont("Helvetica-Oblique", 8)
    reason_lines = wrap_text(c, example.get('reason', ''), "Helvetica-Oblique", 8, col_r - 4 * mm)
    ry = y - 3 * mm
    for line in reason_lines:
        c.drawString(MARGIN + 2 * mm, ry, line)
        ry -= 8 * 1.3
    ev_lines = wrap_text(c, example.get('evidence', ''), "Helvetica-Oblique", 8, col_e - 4 * mm)
    ry = y - 3 * mm
    for line in ev_lines:
        c.drawString(MARGIN + col_r + 2 * mm, ry, line)
        ry -= 8 * 1.3
    y -= row_h

    # Blank rows
    for _ in range(blank_rows):
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(*GREY_LINE)
        c.setLineWidth(0.4)
        c.rect(MARGIN, y - row_h, col_r, row_h, fill=1, stroke=1)
        c.rect(MARGIN + col_r, y - row_h, col_e, row_h, fill=1, stroke=1)
        y -= row_h

    return y - 2 * mm


def render_two_part_ab_pupil(c, q, y, is_supported):
    fd = q['format_data']
    parts = fd.get('parts', [])
    for part in parts:
        label = part.get('label', '?')
        pq = part.get('question', '')
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColorRGB(*DARK)
        pl = f"({label})  "
        plw = c.stringWidth(pl, "Helvetica-Bold", 8.5)
        c.drawString(MARGIN + 3 * mm, y, pl)
        pq_lines = wrap_text(c, pq, "Helvetica-Bold", 8.5, CW - plw - 3 * mm)
        for i, line in enumerate(pq_lines):
            c.drawString(MARGIN + 3 * mm + plw, y - i * (8.5 * 1.35), line)
        y -= len(pq_lines) * (8.5 * 1.35) + 1 * mm
        # One answer line per part
        c.setStrokeColorRGB(*GREY_LINE)
        c.setLineWidth(0.4)
        c.line(MARGIN + 3 * mm, y - 6 * mm, MARGIN + CW, y - 6 * mm)
        c.line(MARGIN + 3 * mm, y - 12 * mm, MARGIN + CW, y - 12 * mm)
        y -= 13 * mm
    return y - 2 * mm


# ===========================================================================
# Format renderers — answer versions
# ===========================================================================

def render_open_line_answer(c, q, y):
    answer = q.get('answer', '')
    c.setFillColorRGB(*GREEN)
    c.setFont("Helvetica-Oblique", 8.5)
    ans_lines = wrap_text(c, answer, "Helvetica-Oblique", 8.5, CW)
    for line in ans_lines:
        c.drawString(MARGIN, y - 5 * mm, line)
        y -= 5 * mm
    return y - 3 * mm


def render_find_and_copy_answer(c, q, y):
    target = q['format_data'].get('target_word', q.get('answer', ''))
    c.setFont("Helvetica-BoldOblique", 9)
    c.setFillColorRGB(*GREEN)
    c.drawString(MARGIN, y - 4 * mm, f"\u2714  {target}")
    return y - 9 * mm


def render_numbered_list_answer(c, q, y):
    answer = q.get('answer', '')
    n = q['format_data'].get('num_points', 2)
    # Try to split on "1." / "2." etc.
    parts = []
    import re
    matches = re.split(r'\d+\.\s+', answer)
    parts = [p.strip() for p in matches if p.strip()]
    if len(parts) < n:
        parts = [answer] + [''] * (n - 1)
    c.setFont("Helvetica-Oblique", 8.5)
    c.setFillColorRGB(*GREEN)
    for i in range(n):
        c.setFont("Helvetica-Bold", 9)
        c.setFillColorRGB(*DARK)
        c.drawString(MARGIN, y - 3 * mm, f"{i + 1}.")
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColorRGB(*GREEN)
        c.drawString(MARGIN + 5 * mm, y - 3 * mm, parts[i] if i < len(parts) else '')
        y -= 9 * mm
    return y - 2 * mm


def render_tick_one_answer(c, q, y):
    fd = q['format_data']
    options = fd.get('options', [])
    correct_i = fd.get('correct_index', 0)
    y = draw_tick_instruction(c, "Tick one.", y)
    row_h = 6.5 * mm
    col_w = CW / 2
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for row in range(2):
        for col in range(2):
            idx = row * 2 + col
            if idx >= len(options):
                break
            x = MARGIN + col * col_w
            ry = y - row * row_h
            is_correct = (idx == correct_i)
            if is_correct:
                c.setFillColorRGB(*TICK_CELL)
            else:
                c.setFillColorRGB(1, 1, 1)
            c.rect(x, ry - row_h, col_w, row_h, fill=1, stroke=1)
            if is_correct:
                c.setFillColorRGB(*GREEN)
                c.setFont("Helvetica-Bold", 8.5)
                c.drawString(x + 2 * mm, ry - row_h + 2 * mm, options[idx] + "  \u2714")
            else:
                c.setFillColorRGB(*DARK)
                c.setFont("Helvetica", 8.5)
                c.drawString(x + 2 * mm, ry - row_h + 2 * mm, options[idx])
    return y - 2 * row_h - 2 * mm


def render_tick_two_answer(c, q, y):
    fd = q['format_data']
    options = fd.get('options', [])
    correct_is = set(fd.get('correct_indices', []))
    y = draw_tick_instruction(c, "Tick two.", y)
    row_h = 6 * mm
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for i, opt in enumerate(options):
        ry = y - i * row_h
        is_correct = (i in correct_is)
        fill = TICK_CELL if is_correct else (1, 1, 1)
        c.setFillColorRGB(*fill)
        c.rect(MARGIN, ry - row_h, CW, row_h, fill=1, stroke=1)
        if is_correct:
            c.setFillColorRGB(*GREEN)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(MARGIN + 8 * mm, ry - row_h + 2 * mm, opt + "  \u2714")
        else:
            c.setFillColorRGB(*DARK)
            c.setFont("Helvetica", 8.5)
            c.drawString(MARGIN + 8 * mm, ry - row_h + 2 * mm, opt)
    return y - len(options) * row_h - 2 * mm


def render_true_false_table_answer(c, q, y):
    fd = q['format_data']
    statements = fd.get('statements', [])
    col_stmt = CW * 0.72
    col_tf = CW * 0.14
    row_h = 7 * mm

    # Header
    c.setFillColorRGB(*BOX_BORDER)
    c.rect(MARGIN, y - row_h, CW, row_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MARGIN + 2 * mm, y - row_h + 2 * mm, "Statement")
    c.drawCentredString(MARGIN + col_stmt + col_tf / 2, y - row_h + 2 * mm, "True")
    c.drawCentredString(MARGIN + col_stmt + col_tf + col_tf / 2, y - row_h + 2 * mm, "False")
    y -= row_h

    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    for i, stmt in enumerate(statements):
        fill = LIGHT_GREY if i % 2 == 0 else (1, 1, 1)
        c.setFillColorRGB(*fill)
        c.rect(MARGIN, y - row_h, CW, row_h, fill=1, stroke=1)
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN + 2 * mm, y - row_h + 2 * mm, stmt.get('text', ''))
        c.line(MARGIN + col_stmt, y, MARGIN + col_stmt, y - row_h)
        c.line(MARGIN + col_stmt + col_tf, y, MARGIN + col_stmt + col_tf, y - row_h)

        # Tick the correct column
        is_true = stmt.get('correct', False)
        tick_x_centre = (MARGIN + col_stmt + col_tf / 2) if is_true else (MARGIN + col_stmt + col_tf + col_tf / 2)
        c.setFillColorRGB(*GREEN)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(tick_x_centre, y - row_h + 2 * mm, "\u2714")
        y -= row_h

    return y - 2 * mm


def render_sequencing_answer(c, q, y):
    fd = q['format_data']
    correct_order = fd.get('items', [])
    shuffled = deterministic_shuffle(correct_order)
    # Build a map: item text → correct position (1-based)
    position = {item: str(i + 1) for i, item in enumerate(correct_order)}
    row_h = 6 * mm
    box_sz = 4.5 * mm

    for i, item in enumerate(shuffled):
        ry = y - i * row_h
        # Green filled box with correct number
        c.setFillColorRGB(*TICK_CELL)
        c.setStrokeColorRGB(*BOX_BORDER)
        c.setLineWidth(0.5)
        c.rect(MARGIN, ry - box_sz, box_sz, box_sz, fill=1, stroke=1)
        c.setFillColorRGB(*GREEN)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(MARGIN + box_sz / 2, ry - box_sz + 1 * mm, position[item])
        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 8.5)
        c.drawString(MARGIN + box_sz + 2 * mm, ry - row_h + 2 * mm, item)
    return y - len(shuffled) * row_h - 2 * mm


def render_reason_evidence_answer(c, q, y):
    fd = q['format_data']
    example = fd.get('example', {})
    blank_rows = fd.get('rows', 2)
    answer = q.get('answer', '')
    col_r = CW * 0.42
    col_e = CW - col_r
    header_h = 6 * mm
    row_h = 11 * mm

    # Header
    c.setFillColorRGB(*BOX_BORDER)
    c.rect(MARGIN, y - header_h, col_r, header_h, fill=1, stroke=0)
    c.rect(MARGIN + col_r, y - header_h, col_e, header_h, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(MARGIN + col_r / 2, y - header_h + 2 * mm, "Reason")
    c.drawCentredString(MARGIN + col_r + col_e / 2, y - header_h + 2 * mm, "Evidence")
    y -= header_h

    # Example row
    c.setFillColorRGB(*LIGHT_GREY)
    c.setStrokeColorRGB(*GREY_LINE)
    c.setLineWidth(0.4)
    c.rect(MARGIN, y - row_h, col_r, row_h, fill=1, stroke=1)
    c.rect(MARGIN + col_r, y - row_h, col_e, row_h, fill=1, stroke=1)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont("Helvetica-Oblique", 8)
    ry = y - 3 * mm
    for line in wrap_text(c, example.get('reason', ''), "Helvetica-Oblique", 8, col_r - 4 * mm):
        c.drawString(MARGIN + 2 * mm, ry, line)
        ry -= 8 * 1.3
    ry = y - 3 * mm
    for line in wrap_text(c, example.get('evidence', ''), "Helvetica-Oblique", 8, col_e - 4 * mm):
        c.drawString(MARGIN + col_r + 2 * mm, ry, line)
        ry -= 8 * 1.3
    y -= row_h

    # Answer rows in green
    import re as _re
    # Try to split answer into reason/evidence pairs
    ans_pairs = []
    raw_parts = _re.split(r'\n', answer.strip())
    for rp in raw_parts:
        if '|' in rp:
            r, e = rp.split('|', 1)
            ans_pairs.append((r.strip(), e.strip()))
    while len(ans_pairs) < blank_rows:
        ans_pairs.append(('', ''))

    for i in range(blank_rows):
        c.setFillColorRGB(*TICK_CELL)
        c.setStrokeColorRGB(*GREY_LINE)
        c.setLineWidth(0.4)
        c.rect(MARGIN, y - row_h, col_r, row_h, fill=1, stroke=1)
        c.rect(MARGIN + col_r, y - row_h, col_e, row_h, fill=1, stroke=1)
        if i < len(ans_pairs) and ans_pairs[i][0]:
            c.setFillColorRGB(*GREEN)
            c.setFont("Helvetica-Oblique", 8)
            ry = y - 3 * mm
            for line in wrap_text(c, ans_pairs[i][0], "Helvetica-Oblique", 8, col_r - 4 * mm):
                c.drawString(MARGIN + 2 * mm, ry, line)
                ry -= 8 * 1.3
            ry = y - 3 * mm
            for line in wrap_text(c, ans_pairs[i][1], "Helvetica-Oblique", 8, col_e - 4 * mm):
                c.drawString(MARGIN + col_r + 2 * mm, ry, line)
                ry -= 8 * 1.3
        y -= row_h

    return y - 2 * mm


def render_two_part_ab_answer(c, q, y):
    fd = q['format_data']
    parts = fd.get('parts', [])
    for part in parts:
        label = part.get('label', '?')
        pq = part.get('question', '')
        ans = part.get('answer', '')
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColorRGB(*DARK)
        pl = f"({label})  "
        plw = c.stringWidth(pl, "Helvetica-Bold", 8.5)
        c.drawString(MARGIN + 3 * mm, y, pl)
        pq_lines = wrap_text(c, pq, "Helvetica-Bold", 8.5, CW - plw - 3 * mm)
        for i, line in enumerate(pq_lines):
            c.drawString(MARGIN + 3 * mm + plw, y - i * (8.5 * 1.35), line)
        y -= len(pq_lines) * (8.5 * 1.35) + 1 * mm
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColorRGB(*GREEN)
        c.drawString(MARGIN + 5 * mm, y - 3 * mm, f"\u2714  {ans}")
        y -= 9 * mm
    return y - 2 * mm


# ===========================================================================
# Height estimation (for overflow checking)
# ===========================================================================

def estimate_height(c, q):
    """
    Estimate the height (in points) that a question will occupy.
    Used to decide whether Q7 (or Q5) fits before drawing.
    """
    ref_h = 7.5 * 1.3 if q.get('text_reference', '').strip() else 0
    qtext = q.get('question', '')
    # Estimate label width (e.g. "7. ")
    lw = c.stringWidth(f"{q['number']}. ", "Helvetica-Bold", 9)
    q_lines = wrap_text(c, qtext.split('\n\n')[-1], "Helvetica-Bold", 9, CW - lw)
    q_text_h = len(q_lines) * 9 * 1.35 + 1 * mm

    fmt = q.get('format', 'open_line')
    fd = q.get('format_data', {})

    if fmt == 'open_line':
        body_h = fd.get('lines', 2) * 6.5 * mm + 2 * mm
    elif fmt == 'find_and_copy':
        body_h = 8 * mm
    elif fmt == 'numbered_list':
        body_h = fd.get('num_points', 2) * 13 * mm + 2 * mm
    elif fmt in ('tick_one',):
        body_h = 4 * mm + 2 * 6.5 * mm + 2 * mm
    elif fmt == 'tick_two':
        body_h = 4 * mm + len(fd.get('options', [])) * 6 * mm + 2 * mm
    elif fmt == 'true_false_table':
        body_h = (len(fd.get('statements', [])) + 1) * 7 * mm + 2 * mm
    elif fmt == 'sequencing':
        body_h = len(fd.get('items', [])) * 6 * mm + 2 * mm
    elif fmt == 'reason_evidence_table':
        body_h = 6 * mm + (fd.get('rows', 2) + 1) * 11 * mm + 2 * mm
    elif fmt == 'two_part_ab':
        body_h = len(fd.get('parts', [])) * (8.5 * 1.35 + 10 * mm) + 2 * mm
    else:
        body_h = 13 * mm

    return ref_h + q_text_h + body_h + 3 * mm


# ===========================================================================
# Single question renderer (dispatches by format)
# ===========================================================================

def render_question(c, q, y, is_answer, is_supported):
    """
    Render one question at position y.
    Returns new y below question, or None if estimated height exceeds remaining space.
    """
    if y - estimate_height(c, q) < MIN_Y:
        return None

    y, _ = draw_preamble(c, q, y)
    marks_label(c, q.get('marks', 1), y + 9 * 1.35)  # align to question text top

    fmt = q.get('format', 'open_line')

    if is_answer:
        dispatch = {
            'open_line':              lambda: render_open_line_answer(c, q, y),
            'find_and_copy':          lambda: render_find_and_copy_answer(c, q, y),
            'numbered_list':          lambda: render_numbered_list_answer(c, q, y),
            'tick_one':               lambda: render_tick_one_answer(c, q, y),
            'tick_two':               lambda: render_tick_two_answer(c, q, y),
            'true_false_table':       lambda: render_true_false_table_answer(c, q, y),
            'sequencing':             lambda: render_sequencing_answer(c, q, y),
            'reason_evidence_table':  lambda: render_reason_evidence_answer(c, q, y),
            'two_part_ab':            lambda: render_two_part_ab_answer(c, q, y),
        }
    else:
        dispatch = {
            'open_line':              lambda: render_open_line_pupil(c, q, y, is_supported),
            'find_and_copy':          lambda: render_find_and_copy_pupil(c, q, y, is_supported),
            'numbered_list':          lambda: render_numbered_list_pupil(c, q, y, is_supported),
            'tick_one':               lambda: render_tick_one_pupil(c, q, y),
            'tick_two':               lambda: render_tick_two_pupil(c, q, y),
            'true_false_table':       lambda: render_true_false_table_pupil(c, q, y),
            'sequencing':             lambda: render_sequencing_pupil(c, q, y),
            'reason_evidence_table':  lambda: render_reason_evidence_pupil(c, q, y),
            'two_part_ab':            lambda: render_two_part_ab_pupil(c, q, y, is_supported),
        }

    renderer = dispatch.get(fmt)
    if renderer is None:
        # Unknown format — fall back to open lines
        return render_open_line_pupil(c, q, y, is_supported) - 3 * mm

    return renderer() - 3 * mm


# ===========================================================================
# Page builder
# ===========================================================================

def build_page(path, lesson, text, questions, is_answer, is_supported, icon_path):
    """Build a single A4 PDF page for one lesson version."""
    c = rl_canvas.Canvas(path, pagesize=A4)

    lesson_type = lesson['lesson_type'].capitalize()
    day = lesson['day']
    date = lesson['date']
    key_q = lesson.get('key_question', '')
    i_cans = lesson.get('i_can_statements', [])

    y = draw_header(c, lesson_type, day, date, key_q, i_cans, icon_path)
    y = draw_text_box(c, text, y, font_size=10 if not is_supported else 9.5)

    for q in questions:
        result = render_question(c, q, y, is_answer=is_answer, is_supported=is_supported)
        if result is None:
            # No room — silently drop remaining questions (Q7 / Q5)
            break
        y = result

    c.save()


def check_pages(path):
    return len(PdfReader(path).pages)


def merge_pdfs(paths, out_path):
    writer = PdfWriter()
    for p in paths:
        for page in PdfReader(p).pages:
            writer.add_page(page)
    with open(out_path, 'wb') as f:
        writer.write(f)


# ===========================================================================
# Main entry point
# ===========================================================================

# ===========================================================================
# Text booklet page (SATs layout)
# ===========================================================================

def build_text_booklet_page(path, lesson, icon_path):
    """
    Build a text-only page for SATs-style output.
    Full-width reading extract at large font, no questions.
    """
    c = rl_canvas.Canvas(path, pagesize=A4)

    lesson_type = lesson["lesson_type"].capitalize()
    day = lesson["day"]
    date_str = lesson["date"]
    key_q = lesson.get("key_question", "")
    i_cans = lesson.get("i_can_statements", [])

    y = draw_header(c, lesson_type, day, date_str, key_q, i_cans, icon_path)

    text = lesson.get("text", "")
    if text:
        # Larger font for text booklet — easier reading
        lines = wrap_text(c, text, "Helvetica", 11, CW - 6 * mm)
        lh = 11 * 1.5
        box_h = len(lines) * lh + 8 * mm

        c.setFillColorRGB(*BOX_BG)
        c.setStrokeColorRGB(*BOX_BORDER)
        c.setLineWidth(0.8)
        c.roundRect(MARGIN, y - box_h, CW, box_h, 2 * mm, fill=1, stroke=1)

        c.setFillColorRGB(*DARK)
        c.setFont("Helvetica", 11)
        ty = y - 4 * mm - 11 * 0.72
        for line in lines:
            c.drawString(MARGIN + 3 * mm, ty, line)
            ty -= lh

    c.save()


def build_pdfs(content: dict, icon_path: str, output_dir: str,
               layout: str = "integrated") -> dict:
    """
    Build PDFs from content_generator output.

    content    : dict returned by content_generator.generate_content()
    icon_path  : path to the reader icon PNG/WebP
    output_dir : directory to write final PDFs
    layout     : "integrated" (text + questions on same page, default)
                 "sats" (separate text booklet PDF, questions-only PDFs)

    Returns dict with keys:
      standard, supported, answers          — always present
      text_booklet                          — only when layout="sats"
    """
    import tempfile, shutil

    tmp = tempfile.mkdtemp()
    key_q = content.get('key_question', '')

    for lesson in content['lessons']:
        lesson['key_question'] = key_q

    std_pages, sup_pages, ans_pages, txt_pages = [], [], [], []

    for lesson in content['lessons']:
        lt = lesson['lesson_type']
        std_qs = lesson['questions']
        sup_qs = lesson['questions'][:5]
        text = lesson.get('text', '')

        if layout == 'sats':
            # Text booklet page — text only, no questions
            tp = os.path.join(tmp, f"{lt}_text.pdf")
            build_text_booklet_page(tp, lesson, icon_path)
            txt_pages.append(tp)

            # Question pages — no text box
            p = os.path.join(tmp, f"{lt}_std.pdf")
            build_page(p, lesson, '', std_qs, is_answer=False,
                       is_supported=False, icon_path=icon_path)
            if check_pages(p) > 1:
                build_page(p, lesson, '', std_qs[:-1], is_answer=False,
                           is_supported=False, icon_path=icon_path)
            std_pages.append(p)

            p = os.path.join(tmp, f"{lt}_sup.pdf")
            build_page(p, lesson, '', sup_qs, is_answer=False,
                       is_supported=True, icon_path=icon_path)
            if check_pages(p) > 1:
                build_page(p, lesson, '', sup_qs[:-1], is_answer=False,
                           is_supported=True, icon_path=icon_path)
            sup_pages.append(p)

            p = os.path.join(tmp, f"{lt}_std_ans.pdf")
            build_page(p, lesson, '', std_qs, is_answer=True,
                       is_supported=False, icon_path=icon_path)
            p2 = os.path.join(tmp, f"{lt}_sup_ans.pdf")
            build_page(p2, lesson, '', sup_qs, is_answer=True,
                       is_supported=True, icon_path=icon_path)
            ans_pages.extend([p, p2])

        else:
            # Integrated layout — existing behaviour
            p = os.path.join(tmp, f"{lt}_std.pdf")
            build_page(p, lesson, text, std_qs, is_answer=False,
                       is_supported=False, icon_path=icon_path)
            if check_pages(p) > 1:
                build_page(p, lesson, text, std_qs[:-1], is_answer=False,
                           is_supported=False, icon_path=icon_path)
            std_pages.append(p)

            p = os.path.join(tmp, f"{lt}_sup.pdf")
            build_page(p, lesson, text, sup_qs, is_answer=False,
                       is_supported=True, icon_path=icon_path)
            if check_pages(p) > 1:
                build_page(p, lesson, text, sup_qs[:-1], is_answer=False,
                           is_supported=True, icon_path=icon_path)
            sup_pages.append(p)

            p = os.path.join(tmp, f"{lt}_std_ans.pdf")
            build_page(p, lesson, text, std_qs, is_answer=True,
                       is_supported=False, icon_path=icon_path)
            p2 = os.path.join(tmp, f"{lt}_sup_ans.pdf")
            build_page(p2, lesson, text, sup_qs, is_answer=True,
                       is_supported=True, icon_path=icon_path)
            ans_pages.extend([p, p2])

    os.makedirs(output_dir, exist_ok=True)
    out_std = os.path.join(output_dir, 'Standard_Pupil.pdf')
    out_sup = os.path.join(output_dir, 'Supported_Pupil.pdf')
    out_ans = os.path.join(output_dir, 'All_Answers.pdf')

    merge_pdfs(std_pages, out_std)
    merge_pdfs(sup_pages, out_sup)
    merge_pdfs(ans_pages, out_ans)

    result = {
        'standard': out_std,
        'supported': out_sup,
        'answers': out_ans,
    }

    if layout == 'sats' and txt_pages:
        out_txt = os.path.join(output_dir, 'Text_Booklet.pdf')
        merge_pdfs(txt_pages, out_txt)
        result['text_booklet'] = out_txt

    shutil.rmtree(tmp)
    return result


# ===========================================================================
# Structured text rendering (supports **heading** markers for non-fiction)
# ===========================================================================

def _parse_structured_text(text):
    """
    Parse text into list of (is_heading, content) tuples.
    Headings are lines wrapped in **...**. Paragraphs separated by blank lines.
    """
    segments = []
    for block in text.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        if block.startswith('**') and block.endswith('**') and block.count('**') == 2:
            segments.append((True, block[2:-2].strip()))
        else:
            clean = block.replace('**', '')
            segments.append((False, clean))
    return segments or [(False, text)]


def draw_structured_text_box(c, text, y_top, font_size=10):
    """
    Draw reading text box with optional bold subheadings.
    Handles **heading** markers. Returns y below box.
    """
    segments = _parse_structured_text(text)

    # Calculate total height
    lh_body = font_size * 1.42
    lh_head = font_size * 1.35
    gap = 2.5 * mm
    total_h = 5 * mm  # top + bottom padding
    for is_heading, content in segments:
        font = "Helvetica-Bold" if is_heading else "Helvetica"
        lh = lh_head if is_heading else lh_body
        lines = wrap_text(c, content, font, font_size, CW - 6 * mm)
        total_h += len(lines) * lh + gap

    # Box
    c.setFillColorRGB(*BOX_BG)
    c.setStrokeColorRGB(*BOX_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN, y_top - total_h, CW, total_h, 2 * mm, fill=1, stroke=1)

    # Text
    ty = y_top - 3.5 * mm
    c.setFillColorRGB(*DARK)
    for is_heading, content in segments:
        font = "Helvetica-Bold" if is_heading else "Helvetica"
        lh = lh_head if is_heading else lh_body
        c.setFont(font, font_size)
        lines = wrap_text(c, content, font, font_size, CW - 6 * mm)
        for line in lines:
            ty -= lh
            c.drawString(MARGIN + 3 * mm, ty, line)
        ty -= gap

    return y_top - total_h - 3 * mm


# ===========================================================================
# Multi-page question rendering
# ===========================================================================

def _start_question_page(tmp_dir, prefix, page_num, header_kwargs, include_label):
    """Create a new canvas for a question page. Returns (canvas, y, path)."""
    path = os.path.join(tmp_dir, f"{prefix}_p{page_num}.pdf")
    c = rl_canvas.Canvas(path, pagesize=A4)
    if include_label and page_num == 1:
        y = draw_header(c, **header_kwargs)
    else:
        y = H - MARGIN - 4 * mm
        if page_num > 1:
            c.setFont("Helvetica-Oblique", 7.5)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawRightString(MARGIN + CW, y + 1 * mm, "continued…")
            y -= 5 * mm
    return c, y, path


def build_question_pages(
    tmp_dir, prefix, questions,
    is_answer, is_supported,
    icon_path, header_kwargs, include_label,
):
    """
    Render questions across one or more pages. Returns list of page paths.
    header_kwargs: dict of keyword args for draw_header (lesson_type, day, date, key_q,
                   i_can_statements, icon_path). Ignored when include_label=False.
    """
    pages = []
    page_num = 1
    c, y, path = _start_question_page(
        tmp_dir, prefix, page_num, header_kwargs, include_label
    )

    for q in questions:
        result = render_question(c, q, y, is_answer=is_answer, is_supported=is_supported)
        if result is None:
            # Doesn't fit — save page, start new
            c.save()
            pages.append(path)
            page_num += 1
            c, y, path = _start_question_page(
                tmp_dir, prefix, page_num, header_kwargs, include_label=False
            )
            result = render_question(c, q, y, is_answer=is_answer, is_supported=is_supported)
            if result is None:
                result = y - 25 * mm  # force past it if question is pathologically tall
        y = result

    c.save()
    pages.append(path)
    return pages


# ===========================================================================
# Reading Paper PDF builder
# ===========================================================================

def _build_reading_paper_text_pages(tmp_dir, text, title, font_size=11):
    """
    Build text-only page(s) for a reading paper.
    Flows segments across as many pages as needed. Returns list of page paths.
    """
    lh_body = font_size * 1.42
    lh_head = font_size * 1.35
    seg_gap  = 2.5 * mm
    padding  = 3.5 * mm

    segments = _parse_structured_text(text)
    pages    = []
    seg_idx  = 0
    page_num = 0

    while seg_idx < len(segments):
        page_num += 1
        p = os.path.join(tmp_dir, f"rp_text_p{page_num}.pdf")
        c = rl_canvas.Canvas(p, pagesize=A4)

        # ── Title block (first page only) ─────────────────────────────
        if page_num == 1 and title:
            y = H - MARGIN - 2 * mm
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(*BOX_BORDER)
            for line in wrap_text(c, title, "Helvetica-Bold", 12, CW):
                c.drawString(MARGIN, y, line)
                y -= 12 * 1.4
            y -= 3 * mm
            c.setStrokeColorRGB(*GREY_LINE)
            c.setLineWidth(0.5)
            c.line(MARGIN, y, MARGIN + CW, y)
            y -= 5 * mm
            box_top = y
        else:
            box_top = H - MARGIN - 2 * mm

        box_bottom = MARGIN

        # ── Draw box background for this page ─────────────────────────
        c.setFillColorRGB(*BOX_BG)
        c.setStrokeColorRGB(*BOX_BORDER)
        c.setLineWidth(0.8)
        c.roundRect(MARGIN, box_bottom, CW, box_top - box_bottom,
                    2 * mm, fill=1, stroke=1)

        # ── Render segments that fit on this page ──────────────────────
        ty = box_top - padding
        c.setFillColorRGB(*DARK)

        while seg_idx < len(segments):
            is_heading, content = segments[seg_idx]
            font = "Helvetica-Bold" if is_heading else "Helvetica"
            lh   = lh_head if is_heading else lh_body
            lines = wrap_text(c, content, font, font_size, CW - 6 * mm)
            seg_h = len(lines) * lh + seg_gap

            if ty - seg_h < box_bottom + padding:
                break  # this segment goes on the next page

            c.setFont(font, font_size)
            for line in lines:
                ty -= lh
                c.drawString(MARGIN + 3 * mm, ty, line)
            ty -= seg_gap
            seg_idx += 1

        c.save()
        pages.append(p)

    return pages


def build_reading_paper_pdfs(
    content: dict,
    icon_path: str,
    output_dir: str,
    include_label: bool = False,
    custom_label: str = "",
) -> dict:
    """
    Build PDFs for Reading Paper Mode.
    content must have 'standard_text' and 'questions'.
    Returns dict: { 'text': path, 'questions': path, 'mark_scheme': path }
    """
    import tempfile, shutil

    tmp = tempfile.mkdtemp()
    key_q = content.get("key_question", "") or content.get("topic", "")
    text = content.get("standard_text", "")
    questions = content.get("questions", [])

    # ── Text page(s) ──────────────────────────────────────────────────────
    txt_pages = _build_reading_paper_text_pages(tmp, text, key_q)

    # ── Learning label header for questions page ───────────────────────────
    # For reading paper mode the label is the custom_label (user-set)
    # We build a minimal header: just the label text and key question
    if include_label and custom_label.strip():
        def _draw_rp_label(c):
            y = H - MARGIN
            c.setFont("Helvetica-Bold", 8)
            c.setFillColorRGB(*DARK)
            c.drawString(MARGIN, y - 5 * mm, custom_label.strip())
            y -= 7 * mm
            c.setFont("Helvetica-Bold", 10)
            c.setFillColorRGB(*BOX_BORDER)
            c.drawString(MARGIN, y - 4 * mm, key_q)
            kq_w = c.stringWidth(key_q, "Helvetica-Bold", 10)
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(*BOX_BORDER)
            c.line(MARGIN, y - 5 * mm, MARGIN + kq_w, y - 5 * mm)
            y -= 8 * mm
            c.setStrokeColorRGB(*GREY_LINE)
            c.setLineWidth(0.5)
            c.line(MARGIN, y, MARGIN + CW, y)
            y -= 3 * mm
            return y
    else:
        _draw_rp_label = None

    # ── Question pages ─────────────────────────────────────────────────────
    q_pages = []
    page_num = 0

    def new_q_page(is_first):
        nonlocal page_num
        page_num += 1
        p = os.path.join(tmp, f"rp_q_p{page_num}.pdf")
        c = rl_canvas.Canvas(p, pagesize=A4)
        if is_first:
            # Name space — top right
            name_y = H - MARGIN - 3 * mm
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(*DARK)
            name_line = "Name:  ___________________________________"
            c.drawRightString(MARGIN + CW, name_y, name_line)

            if _draw_rp_label:
                y = _draw_rp_label(c)
            else:
                y = H - MARGIN - 14 * mm  # clear of name line
        else:
            y = H - MARGIN - 4 * mm
            c.setFont("Helvetica-Oblique", 7.5)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawRightString(MARGIN + CW, y + 1 * mm, "continued…")
            y -= 5 * mm
        return c, y, p

    c, y, path = new_q_page(is_first=True)

    for q in questions:
        result = render_question(c, q, y, is_answer=False, is_supported=False)
        if result is None:
            c.save()
            q_pages.append(path)
            c, y, path = new_q_page(is_first=False)
            result = render_question(c, q, y, is_answer=False, is_supported=False)
            if result is None:
                result = y - 25 * mm
        y = result

    c.save()
    q_pages.append(path)

    # ── Mark scheme pages ──────────────────────────────────────────────────
    ms_pages = []
    page_num_ms = 0

    def new_ms_page(is_first):
        nonlocal page_num_ms
        page_num_ms += 1
        p = os.path.join(tmp, f"rp_ms_p{page_num_ms}.pdf")
        c = rl_canvas.Canvas(p, pagesize=A4)
        y = H - MARGIN - 2 * mm
        if is_first:
            c.setFont("Helvetica-Bold", 11)
            c.setFillColorRGB(*BOX_BORDER)
            c.drawString(MARGIN, y, "Mark Scheme")
            y -= 11 * 1.4 + 3 * mm
            c.setStrokeColorRGB(*GREY_LINE)
            c.setLineWidth(0.5)
            c.line(MARGIN, y, MARGIN + CW, y)
            y -= 4 * mm
        else:
            c.setFont("Helvetica-Oblique", 7.5)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.drawRightString(MARGIN + CW, y + 1 * mm, "Mark Scheme continued…")
            y -= 5 * mm
        return c, y, p

    c, y, path = new_ms_page(is_first=True)

    for q in questions:
        result = render_question(c, q, y, is_answer=True, is_supported=False)
        if result is None:
            c.save()
            ms_pages.append(path)
            c, y, path = new_ms_page(is_first=False)
            result = render_question(c, q, y, is_answer=True, is_supported=False)
            if result is None:
                result = y - 25 * mm
        y = result

    c.save()
    ms_pages.append(path)

    # ── Merge and write outputs ────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    out_text = os.path.join(output_dir, "ReadingPaper_Text.pdf")
    out_q    = os.path.join(output_dir, "ReadingPaper_Questions.pdf")
    out_ms   = os.path.join(output_dir, "ReadingPaper_MarkScheme.pdf")

    merge_pdfs(txt_pages, out_text)
    merge_pdfs(q_pages,   out_q)
    merge_pdfs(ms_pages,  out_ms)

    shutil.rmtree(tmp)

    return {
        "text":        out_text,
        "questions":   out_q,
        "mark_scheme": out_ms,
    }
