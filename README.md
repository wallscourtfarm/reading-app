# Being a Reader – Lesson Generator

Streamlit app for Wallscourt Farm Academy Year 4.

Generates a full week of Being a Reader resources from a single form:
- **PPTX** — 22-slide teaching deck (animations intact)
- **Standard Pupil PDF** — 3-page worksheet (7 questions per lesson)
- **Supported Pupil PDF** — 3-page worksheet (5 simpler questions per lesson)
- **All Answers PDF** — 6 pages (standard + supported answers for each lesson)
- **Excel** — full content data file

## Setup (Streamlit Cloud)

1. Fork or clone this repo to `wallscourtfarm/reading-app`
2. Add `ANTHROPIC_API_KEY` as a secret in the Streamlit Cloud dashboard
3. Deploy with:
   - **Repository:** `wallscourtfarm/reading-app`
   - **Branch:** `main`
   - **Main file path:** `app.py`

## Local run

```bash
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-... streamlit run app.py
```

## File structure

```
app.py                  Streamlit UI
content_generator.py    Claude API → lesson JSON
pptx_builder.py         Template XML manipulation
pdf_builder.py          ReportLab PDF generation
excel_builder.py        openpyxl Excel generation
requirements.txt
template.pptx           Base PPTX (T5W4 sound – do not delete)
assets/reader.png       School icon
```

## Updating the template

If the school PPTX template changes significantly, replace `template.pptx` and update
the shape ID constants in `pptx_builder.py` (TEMPLATE_VOCAB, TEMPLATE_FOCUS_WORDS, SLIDE_MAP).
