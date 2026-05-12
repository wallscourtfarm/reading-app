"""
content_generator.py
Two generation modes:
  generate_content()        — Lesson Mode (3 lessons, Vocabulary/Retrieval/Inference)
  generate_reading_paper()  — Reading Paper Mode (flat question set, no lesson structure)
"""

import anthropic
import json
import re

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

WORD_COUNTS = {
    "standard": "200–250",
    "extended": "400–500",
    "long":     "700–800",
}

# Cognitive question types
QUESTION_TYPES = {
    "Retrieval":               "retrieval",
    "Vocabulary in context":   "vocabulary",
    "Inference":               "inference",
    "Explanation":             "explain",
    "Find and copy":           "find_and_copy",
    "Author intent / effect":  "author_effect",
    "Comparison":              "compare",
    "Summary":                 "summary",
}

# Presentation layouts
QUESTION_LAYOUTS = {
    "Open written answer":             "open_line",
    "Multiple choice (tick one)":      "tick_one",
    "Tick two":                        "tick_two",
    "True / false table":              "true_false_table",
    "Sequencing / ordering":           "sequencing",
    "Numbered list (write 2–3 things)":"numbered_list",
    "Reason & evidence (3 marks)":     "reason_evidence_table",
    "Two-part question (a/b)":         "two_part_ab",
    "Find and copy blank":             "find_and_copy",
}

FORMAT_REFERENCE = """
QUESTION LAYOUTS — every question must have one of these as its "format" value:

open_line          Written answer on ruled lines.
                   format_data: { "lines": 1 or 2 }

find_and_copy      Short blank for one word or short phrase verbatim from text.
                   format_data: { "target_word": "exact word or phrase" }
                   Question must say "Find and copy one word/phrase which..."

numbered_list      Numbered blanks for multiple distinct points.
                   format_data: { "num_points": 2 or 3 }
                   Question must say "Write two things..." or "Give three reasons..."

tick_one           Four options in 2×2 grid. "Tick one." instruction.
                   format_data: { "options": ["A","B","C","D"], "correct_index": 0 }
                   Exactly 4 options. One unambiguously correct. Three plausible distractors.

tick_two           Five options stacked. "Tick two." instruction.
                   format_data: { "options": ["A","B","C","D","E"], "correct_indices": [1,3] }
                   Exactly 5 options. Exactly 2 correct.

true_false_table   Table of statements, True/False columns.
                   format_data: { "statements": [{"text":"...","correct":true},...] }
                   4–5 statements. Mix of true and false. Some require inference.

sequencing         Small numbered boxes beside shuffled events/steps.
                   format_data: { "items": ["first","second","third","fourth"] }
                   Exactly 4 items listed in CORRECT order (builder shuffles for display).

reason_evidence_table  Two-column table (Reason | Evidence). One example row pre-filled.
                   format_data: { "example":{"reason":"...","evidence":"..."}, "rows": 2 }
                   Always 2 blank rows. 3 marks total.
                   ANSWER FIELD FORMAT (mandatory): provide mark scheme for both blank rows as:
                   "reason1 | evidence1\nreason2 | evidence2"
                   Each row should give the primary acceptable answer. If multiple phrasings
                   are acceptable, separate them with " / " within the cell:
                   "He was brave / He showed courage | He fought the street cats / He stood his ground"
                   The answer field must always contain exactly 2 rows separated by \n.

two_part_ab        Two sub-questions (a) and (b), each worth 1 mark.
                   format_data: { "parts":[{"label":"a","question":"...","answer":"..."},
                                           {"label":"b","question":"...","answer":"..."}] }

QUESTION WRITING RULES:
- Every question must include "text_reference" scoping the reader to the relevant passage:
    "Read the paragraph beginning: [first 5-6 words]..."
    "Read the section: [subheading]"   (if text has subheadings)
    "Look at the whole text."          (synthesis questions only)
- For vocabulary/inference questions, reproduce the quoted phrase in the question field,
  separated from the actual question by \\n\\n:
    "She felt a cool focus flood her veins.\\n\\nWhat does this suggest about how Merry was feeling?"
- find_and_copy: the target_word must appear verbatim in the standard_text.
- tick_one distractors: make them genuinely tempting — not obviously wrong.
- true_false_table: avoid statements answerable from common knowledge alone.
- sequencing items: paraphrase text events slightly — do not copy verbatim.
- Do not use "pupils" anywhere. Use "explain", "give reasons", "how can you tell" — not "evaluate" or "analyse".
- Inference questions must push beyond surface retrieval.

SUPPORTED SCAFFOLD:
Every question needs a "supported_scaffold" string — a sentence starter or hint
for the Supported Pupil version. Keep it brief.
  open_line:    "The text says that..."
  numbered_list:"1. One thing is... 2. Another thing is..."
  inference:    "We can tell this because..."
  tick_one:     null  (format is already simplified)
  find_and_copy:null
"""

TEXT_INSTRUCTIONS = """
READING TEXT:
Write the reading extract yourself. Do not ask for it.

Structure:
- For non-fiction topics with Standard or Extended length: plain continuous prose is fine.
- For non-fiction topics with Long length (700-800 words): use bold subheadings to break
  the text into 3–5 sections. Format subheadings as **Heading text** on their own line.
- For fiction/narrative topics at any length: plain paragraphs only, no subheadings.
  Separate paragraphs with a blank line.
- Claude should judge fiction vs non-fiction from the topic and apply these rules automatically.

Quality:
- Clear, engaging prose at Y4 level (age 8–9)
- Must be original — not copied from any published source
- Must contain enough specific detail to support the required number of questions
- Embed at least 4 Tier 2 vocabulary words naturally
- The text goes in the top-level "standard_text" field

Length: determined by TEXT_LENGTH in the user message.
"""

# ---------------------------------------------------------------------------
# LESSON MODE
# ---------------------------------------------------------------------------

LESSON_FORMAT_GUIDANCE = {
    "vocabulary": [
        "open_line (1 mark, lines=2)",
        "numbered_list (2 marks, num_points=2)",
        "tick_one (1 mark) — quote the word/phrase; 4 options",
        "open_line (1 mark, lines=2)",
        "tick_one (1 mark) — key idea or phrase from text",
        "open_line OR numbered_list",
        "open_line OR tick_one (1 mark)",
    ],
    "retrieval": [
        "open_line (1 mark, lines=2)",
        "numbered_list (2 marks, num_points=2)",
        "sequencing (1 mark) — 4 events; builder shuffles",
        "open_line (1 mark, lines=2)",
        "open_line (1 mark, lines=2)",
        "tick_one (1 mark)",
        "true_false_table (2 marks) — 4–5 statements",
    ],
    "inference": [
        "find_and_copy (1 mark)",
        "tick_one (1 mark) — vocabulary in context",
        "tick_one (1 mark)",
        "open_line (1 mark, lines=2) OR two_part_ab (2 marks)",
        "open_line (1 mark, lines=2)",
        "numbered_list (2 marks, num_points=2) OR tick_two (1 mark)",
        "reason_evidence_table (3 marks)",
    ],
}

LESSON_SYSTEM_PROMPT = f"""You are an expert KS2 reading comprehension question writer for Year 4 pupils (age 8–9) in England, working in the CLF Being a Reader framework.

You will generate THREE comprehension lessons (Vocabulary, Retrieval, Inference) from a single reading text.

{TEXT_INSTRUCTIONS}

{FORMAT_REFERENCE}

LESSON SEQUENCES (fixed — do not change the cognitive type for each slot):
  Vocabulary:  retrieval → list → vocabulary → explain → multiple_choice → compare → inference
  Retrieval:   retrieval → list → ordering → compare → explain → multiple_choice → inference
  Inference:   retrieval → vocabulary → multiple_choice → explain → inference → inference → inference

Each lesson has exactly 7 questions. Follow the slot sequences above for cognitive type.
Use the format guidance in the user message for layout, but you may deviate for good reason.

Questions must be answerable from the generated text alone.

OUTPUT: Valid JSON only — no preamble, no markdown fences.

{{
  "key_question": "...",
  "standard_text": "...",
  "lessons": [
    {{
      "lesson_type": "vocabulary",
      "day": "...",
      "date": "...",
      "i_can_statements": ["...", "..."],
      "questions": [
        {{
          "number": 1,
          "type": "retrieval",
          "format": "open_line",
          "marks": 1,
          "text_reference": "...",
          "question": "...",
          "answer": "...",
          "supported_scaffold": "...",
          "format_data": {{"lines": 2}}
        }}
      ]
    }},
    {{"lesson_type": "retrieval", "...": "..."}},
    {{"lesson_type": "inference", "...": "..."}}
  ]
}}
"""


def _type_restriction(question_types):
    if not question_types:
        return ""
    type_labels = {v: k for k, v in QUESTION_TYPES.items()}
    readable = [type_labels.get(t, t) for t in question_types]
    return (
        "\n\nCOGNITIVE TYPE RESTRICTION: Only generate questions that test these skills: "
        + ", ".join(readable)
        + ". Do not use any other cognitive type."
    )


def _layout_restriction(question_layouts):
    if not question_layouts:
        return ""
    layout_labels = {v: k for k, v in QUESTION_LAYOUTS.items()}
    readable = [layout_labels.get(l, l) for l in question_layouts]
    return (
        "\n\nLAYOUT RESTRICTION: Only use these question layouts: "
        + ", ".join(readable)
        + ". Do not use any other layout format, even if more appropriate."
    )


def _build_lesson_prompt(
    topic, key_question,
    vocab_day, vocab_date, vocab_i_can,
    retrieval_day, retrieval_date, retrieval_i_can,
    inference_day, inference_date, inference_i_can,
    context, question_types, question_layouts, text_length,
):
    word_count = WORD_COUNTS.get(text_length, "200–250")
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""

    type_r = _type_restriction(question_types)
    layout_r = _layout_restriction(question_layouts)

    slot_types = {
        "vocabulary": ["retrieval", "list", "vocabulary", "explain",
                       "multiple_choice", "compare", "inference"],
        "retrieval":  ["retrieval", "list", "ordering", "compare",
                       "explain", "multiple_choice", "inference"],
        "inference":  ["retrieval", "vocabulary", "multiple_choice", "explain",
                       "inference", "inference", "inference"],
    }

    def fmt_guidance(lt):
        return "\n".join(
            f"  Slot {i+1} ({t}): {g}"
            for i, (t, g) in enumerate(zip(slot_types[lt], LESSON_FORMAT_GUIDANCE[lt]))
        )

    return f"""TOPIC: {topic}{context_line}
TEXT_LENGTH: {word_count} words{type_r}{layout_r}

KEY QUESTION: {key_question}

LESSON SCHEDULE:
  Lesson 1 (Vocabulary):  {vocab_day}, {vocab_date}
  I can: {'; '.join(vocab_i_can)}

  Lesson 2 (Retrieval):   {retrieval_day}, {retrieval_date}
  I can: {'; '.join(retrieval_i_can)}

  Lesson 3 (Inference):   {inference_day}, {inference_date}
  I can: {'; '.join(inference_i_can)}

FORMAT GUIDANCE:
Vocabulary:
{fmt_guidance("vocabulary")}

Retrieval:
{fmt_guidance("retrieval")}

Inference:
{fmt_guidance("inference")}

Generate all three lessons now. ONLY valid JSON — no markdown fences."""


# ---------------------------------------------------------------------------
# READING PAPER MODE
# ---------------------------------------------------------------------------

READING_PAPER_SYSTEM_PROMPT = f"""You are an expert KS2 reading comprehension question writer for Year 4 pupils (age 8–9) in England.

You will generate a standalone reading paper: a text followed by a set of comprehension questions. This is used for practice, reading tasks or assessment — not as part of a lesson sequence.

{TEXT_INSTRUCTIONS}

{FORMAT_REFERENCE}

Generate exactly the number of questions requested. There is no fixed lesson structure —
distribute cognitive types and layouts as directed (or use a balanced mix if unrestricted).

Aim for variety: do not use the same layout for more than 3 consecutive questions.
Higher-mark questions (reason_evidence_table, numbered_list 2-mark) should be spread across
the set, not clustered at the start or end.

OUTPUT: Valid JSON only — no preamble, no markdown fences.

{{
  "key_question": "...",
  "standard_text": "...",
  "questions": [
    {{
      "number": 1,
      "type": "retrieval",
      "format": "open_line",
      "marks": 1,
      "text_reference": "...",
      "question": "...",
      "answer": "...",
      "supported_scaffold": null,
      "format_data": {{"lines": 2}}
    }}
  ]
}}
"""


def _build_reading_paper_prompt(
    topic, key_question, num_questions, text_length,
    question_types, question_layouts, context,
):
    word_count = WORD_COUNTS.get(text_length, "200–250")
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""
    type_r = _type_restriction(question_types)
    layout_r = _layout_restriction(question_layouts)

    title_line = f"\nKEY QUESTION: {key_question}" if key_question.strip() else ""
    return f"""TOPIC: {topic}{context_line}
TEXT_LENGTH: {word_count} words
NUMBER OF QUESTIONS: {num_questions}{type_r}{layout_r}{title_line}

Generate exactly {num_questions} questions now. ONLY valid JSON — no markdown fences."""


# ---------------------------------------------------------------------------
# API call + parse + validate
# ---------------------------------------------------------------------------

def _call_api(system_prompt, user_prompt, max_tokens=8000):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw:\n{raw[:600]}")


VALID_FORMATS = {
    "open_line", "find_and_copy", "numbered_list", "tick_one", "tick_two",
    "true_false_table", "sequencing", "reason_evidence_table", "two_part_ab",
}

REQUIRED_FORMAT_DATA = {
    "open_line":             {"lines"},
    "find_and_copy":         {"target_word"},
    "numbered_list":         {"num_points"},
    "tick_one":              {"options", "correct_index"},
    "tick_two":              {"options", "correct_indices"},
    "true_false_table":      {"statements"},
    "sequencing":            {"items"},
    "reason_evidence_table": {"example", "rows"},
    "two_part_ab":           {"parts"},
}


def _coerce_str(val):
    """Coerce a field value to string — handles list returns from Claude."""
    if isinstance(val, list):
        return " / ".join(str(v) for v in val)
    return str(val) if val is not None else ""


def _validate_question(q, lesson_label=""):
    prefix = f"{lesson_label} Q{q.get('number','?')}"
    fmt = q.get("format", "") or ""  # guard against None
    if not fmt:
        raise ValueError(f"{prefix}: format field is missing or empty")
    if fmt not in VALID_FORMATS:
        raise ValueError(f"{prefix}: unknown format '{fmt}'")
    fd = q.get("format_data", {}) or {}
    missing = REQUIRED_FORMAT_DATA.get(fmt, set()) - set(fd.keys())
    if missing:
        raise ValueError(f"{prefix} format_data missing keys: {missing}")
    if fmt == "tick_one" and len(fd.get("options", [])) != 4:
        raise ValueError(f"{prefix}: tick_one needs 4 options")
    if fmt == "tick_two":
        if len(fd.get("options", [])) != 5:
            raise ValueError(f"{prefix}: tick_two needs 5 options")
        if len(fd.get("correct_indices", [])) != 2:
            raise ValueError(f"{prefix}: tick_two needs 2 correct_indices")
    if fmt == "sequencing" and len(fd.get("items", [])) != 4:
        raise ValueError(f"{prefix}: sequencing needs 4 items")
    if fmt == "true_false_table":
        n = len(fd.get("statements", []))
        if not (4 <= n <= 5):
            raise ValueError(f"{prefix}: true_false_table needs 4–5 statements, got {n}")
    if not q.get("marks", 0):
        raise ValueError(f"{prefix}: missing marks")
    # Required text fields — use _coerce_str to handle list returns from Claude
    for field in ("text_reference", "question"):
        if not _coerce_str(q.get(field, "")).strip():
            raise ValueError(f"{prefix}: missing '{field}'")
    # two_part_ab stores answers inside format_data.parts — skip top-level answer check
    if fmt != "two_part_ab":
        if not _coerce_str(q.get("answer", "")).strip():
            raise ValueError(f"{prefix}: missing 'answer'")


def _validate_lesson(data):
    if not data.get("standard_text", "").strip():
        raise ValueError("Missing standard_text")
    lessons = data.get("lessons", [])
    if len(lessons) != 3:
        raise ValueError(f"Expected 3 lessons, got {len(lessons)}")
    expected_types = ["vocabulary", "retrieval", "inference"]
    for lesson, expected in zip(lessons, expected_types):
        lt = lesson.get("lesson_type", "")
        if lt != expected:
            raise ValueError(f"Expected lesson_type '{expected}', got '{lt}'")
        qs = lesson.get("questions", [])
        if len(qs) != 7:
            raise ValueError(f"Lesson '{lt}' has {len(qs)} questions, expected 7")
        for q in qs:
            _validate_question(q, lesson_label=lt)


def _validate_reading_paper(data, expected_count):
    if not data.get("standard_text", "").strip():
        raise ValueError("Missing standard_text")
    qs = data.get("questions", [])
    if len(qs) != expected_count:
        raise ValueError(f"Expected {expected_count} questions, got {len(qs)}")
    for q in qs:
        _validate_question(q, lesson_label="Paper")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_content(
    topic: str,
    key_question: str,
    vocab_day: str,
    vocab_date: str,
    vocab_i_can: list,
    retrieval_day: str,
    retrieval_date: str,
    retrieval_i_can: list,
    inference_day: str,
    inference_date: str,
    inference_i_can: list,
    context: str = "",
    question_types: list = None,
    question_layouts: list = None,
    text_length: str = "standard",
) -> dict:
    """
    Lesson Mode: generate 3 lessons × 7 questions.
    Returns dict with 'standard_text' and 'lessons'.
    """
    prompt = _build_lesson_prompt(
        topic=topic, key_question=key_question,
        vocab_day=vocab_day, vocab_date=vocab_date, vocab_i_can=vocab_i_can,
        retrieval_day=retrieval_day, retrieval_date=retrieval_date,
        retrieval_i_can=retrieval_i_can,
        inference_day=inference_day, inference_date=inference_date,
        inference_i_can=inference_i_can,
        context=context, question_types=question_types,
        question_layouts=question_layouts, text_length=text_length,
    )
    data = _call_api(LESSON_SYSTEM_PROMPT, prompt)
    _validate_lesson(data)
    return data


def generate_reading_paper(
    topic: str,
    key_question: str,
    num_questions: int,
    text_length: str = "standard",
    question_types: list = None,
    question_layouts: list = None,
    context: str = "",
) -> dict:
    """
    Reading Paper Mode: generate a text + flat question set.
    Returns dict with 'standard_text' and 'questions'.
    """
    prompt = _build_reading_paper_prompt(
        topic=topic, key_question=key_question,
        num_questions=num_questions, text_length=text_length,
        question_types=question_types, question_layouts=question_layouts,
        context=context,
    )
    # More tokens for larger question sets
    max_tok = max(6000, num_questions * 600)
    data = _call_api(READING_PAPER_SYSTEM_PROMPT, prompt, max_tokens=min(max_tok, 12000))
    _validate_reading_paper(data, num_questions)
    return data
