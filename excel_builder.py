"""
excel_builder.py  –  Generates the Being a Reader content XLSX.
Column structure is locked (matches the skill definition).
"""

import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


# ── colours ───────────────────────────────────────────────────────────────────

HDR_FILL  = PatternFill('solid', fgColor='2C2C6C')   # dark blue
HDR_FONT  = Font(color='FFFFFF', bold=True, name='Calibri', size=10)
BODY_FONT = Font(name='Calibri', size=10)
WRAP_ALIGN = Alignment(wrap_text=True, vertical='top')
THIN = Side(border_style='thin', color='CCCCCC')
THIN_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

LESSON_FILLS = [
    PatternFill('solid', fgColor='E8F4FD'),   # light blue  – Vocabulary
    PatternFill('solid', fgColor='EDF7ED'),   # light green – Retrieval
    PatternFill('solid', fgColor='FDF3E8'),   # light amber – Inference
]


def build_excel(lesson_data: dict, output_path: str) -> str:
    """
    Build the XLSX content file. Returns the output_path on success.

    Column structure:
      A  Lesson Number
      B  Lesson (Vocabulary / Retrieval / Inference)
      C  Version (Standard / Standard (MC) / Supported)
      D  Section (Text / Vocabulary / Question / Answer)
      E  Word / Q number
      F  Content
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Reading Content'

    # Header row
    headers = ['Lesson Number', 'Lesson', 'Version', 'Section', 'Word / Q', 'Content']
    for col, hdr in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=hdr)
        cell.font = HDR_FONT
        cell.fill = HDR_FILL
        cell.alignment = WRAP_ALIGN
        cell.border = THIN_BORDER

    # Column widths
    col_widths = [12, 14, 18, 12, 12, 80]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    lessons = lesson_data['lessons']
    lesson_types = ['Vocabulary', 'Retrieval', 'Inference']
    versions = ['Standard', 'Standard (MC)', 'Supported']

    row = 2
    for i, lesson in enumerate(lessons):
        lnum = i + 1
        ltype = lesson.get('type', lesson_types[i])
        fill = LESSON_FILLS[i]

        for version in versions:
            # Text row
            row = _add_row(ws, row, lnum, ltype, version, 'Text', '',
                           lesson.get('extract_standard' if 'Standard' in version
                                      else 'extract_supported', ''),
                           fill)

            # Vocabulary rows (Standard only)
            if version == 'Standard':
                for entry in lesson.get('vocab', []):
                    row = _add_row(ws, row, lnum, ltype, version, 'Vocabulary',
                                   entry.get('word', ''),
                                   entry.get('definition', ''), fill)

            # Questions
            qs = lesson.get(
                'questions_supported' if version == 'Supported'
                else 'questions_standard',
                []
            )
            for q in qs:
                qnum = q.get('number', '')
                row = _add_row(ws, row, lnum, ltype, version, 'Question',
                               f'Q{qnum}', q.get('question', ''), fill)
                row = _add_row(ws, row, lnum, ltype, version, 'Answer',
                               f'Q{qnum}', q.get('answer', ''), fill)

    # Freeze header
    ws.freeze_panes = 'A2'

    wb.save(output_path)
    return output_path


def _add_row(ws, row, lnum, ltype, version, section, word, content, fill):
    vals = [lnum, ltype, version, section, word, content]
    for col, val in enumerate(vals, 1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.font = BODY_FONT
        cell.alignment = WRAP_ALIGN
        cell.border = THIN_BORDER
        if col < 6:
            cell.fill = fill
    ws.row_dimensions[row].height = None   # auto
    return row + 1
