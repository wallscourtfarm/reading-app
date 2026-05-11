"""
content_generator.py
Calls the Claude API to generate Being a Reader lesson content.
Outputs a structured JSON object with three lessons (Vocabulary, Retrieval, Inference).
Each question now carries:
  - type        : cognitive demand category
  - format      : rendering format (controls how pdf_builder/pptx_builder draws the question)
  - marks       : mark value (int)
  - text_reference : scoping instruction directing the reader to the relevant passage
  - question    : question text
  - answer      : full mark-scheme answer
  - format_data : format-specific payload (options, statements, items, etc.)
"""

import anthropic
import json
import re

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# FORMAT REFERENCE (kept here for documentation; duplicated in the prompt)
# ---------------------------------------------------------------------------
# open_line          : ruled line(s) for a written answer
#   format_data: { lines: int }   (1 = short answer, 2 = longer answer)
#
# find_and_copy      : short blank for a single word or phrase
#   format_data: { target_word: str }   (the correct word/phrase)
#
# numbered_list      : numbered blank lines (1. ___ 2. ___)
#   format_data: { num_points: int }
#
# tick_one           : four options, one correct, "Tick one." instruction
#   format_data: { options: [str, str, str, str], correct_index: int (0-based) }
#
# tick_two           : five options, two correct, "Tick two." instruction
#   format_data: { options: [str, str, str, str, str], correct_indices: [int, int] }
#
# true_false_table   : table of statements, reader ticks True or False per row
#   format_data: { statements: [ { text: str, correct: bool } ] }
#   (minimum 4 rows, maximum 5 rows; mix of True and False answers; marks = 1-2)
#
# sequencing         : list of events/steps; reader writes 1-N to show correct order
#   format_data: { items: [str] }   (items listed in CORRECT order; builder shuffles them)
#
# reason_evidence_table : two-column table (Reason | Evidence); one example row pre-filled
#   format_data: { example: { reason: str, evidence: str }, rows: int }
#   (rows = number of blank rows to complete, always 2; marks = 3)
#
# two_part_ab        : single stem, two sub-questions (a) and (b), each 1 mark
#   format_data: { parts: [ { label: str, question: str, answer: str } ] }
# ---------------------------------------------------------------------------

# Recommended format per question slot in each lesson type.
# The generator may deviate for good reason but should default to these.
LESSON_FORMAT_GUIDANCE = {
    "vocabulary": [
        # slot 1: retrieval
        "open_line (1 mark, lines=2)",
        # slot 2: list
        "numbered_list (2 marks, num_points=2)",
        # slot 3: vocabulary
        "tick_one (1 mark) — quote the word/phrase from text; 4 options; one correct",
        # slot 4: explain
        "open_line (1 mark, lines=2)",
        # slot 5: multiple_choice
        "tick_one (1 mark) — test understanding of a key idea or phrase from the text",
        # slot 6: compare
        "open_line (1 mark, lines=2) OR numbered_list (2 marks, num_points=2)",
        # slot 7: inference
        "open_line (1 mark, lines=2) OR tick_one (1 mark)",
    ],
    "retrieval": [
        # slot 1: retrieval
        "open_line (1 mark, lines=2)",
        # slot 2: list
        "numbered_list (2 marks, num_points=2)",
        # slot 3: ordering
        "sequencing (1 mark) — 4 events in correct order; builder will shuffle",
        # slot 4: compare
        "open_line (1 mark, lines=2)",
        # slot 5: explain
        "open_line (1 mark, lines=2)",
        # slot 6: multiple_choice
        "tick_one (1 mark)",
        # slot 7: inference
        "true_false_table (2 marks) — 4-5 statements, mix of true and false",
    ],
    "inference": [
        # slot 1: retrieval
        "find_and_copy (1 mark) — one word or short phrase",
        # slot 2: vocabulary
        "tick_one (1 mark) — meaning of a word/phrase in context",
        # slot 3: multiple_choice
        "tick_one (1 mark)",
        # slot 4: explain
        "open_line (1 mark, lines=2) OR two_part_ab (2 marks)",
        # slot 5: inference
        "open_line (1 mark, lines=2)",
        # slot 6: inference
        "numbered_list (2 marks, num_points=2) OR tick_two (1 mark)",
        # slot 7: inference
        "reason_evidence_table (3 marks) — 1 example row + 2 blank rows",
    ],
}


SYSTEM_PROMPT = """You are an expert KS2 reading comprehension question writer for Year 4 pupils (age 8-9) in England.

You will be given:
- A reading text (or passage summary)
- A key question that frames the lesson sequence
- Day and date for each of three lessons
- I can statements for each lesson

Your job is to generate three lessons of Being a Reader comprehension questions:
  Lesson 1: Vocabulary lesson
  Lesson 2: Retrieval lesson
  Lesson 3: Inference lesson

Each lesson has exactly 7 questions following a fixed type sequence:
  Vocabulary:  retrieval → list → vocabulary → explain → multiple_choice → compare → inference
  Retrieval:   retrieval → list → ordering → compare → explain → multiple_choice → inference
  Inference:   retrieval → vocabulary → multiple_choice → explain → inference → inference → inference

CRITICAL: The questions must be closely tied to the actual text content provided. Do not generate generic comprehension questions. Every question must be answerable specifically from the text given.

---
FORMAT SYSTEM

Every question must carry a "format" field. The format controls how the question is rendered on the page. Choose the format that best fits the question type and content, following the guidance below.

Available formats and their required format_data fields:

open_line
  Use for: retrieval, explain, compare, inference questions with a written response
  format_data: { "lines": 1 or 2 }
  Mark range: 1
  Answer: write a complete model answer

find_and_copy
  Use for: questions asking the reader to identify a specific word or phrase
  format_data: { "target_word": "the exact word or phrase" }
  Mark range: 1
  Question must say "Find and copy one word/phrase which..."

numbered_list
  Use for: questions asking for two or more separate points
  format_data: { "num_points": 2 (or 3) }
  Mark range: equal to num_points
  Question must say "Write two things..." or "Give two reasons..." etc.
  Answer: provide each point separately as "1. ... 2. ..."

tick_one
  Use for: vocabulary in context, multiple choice, some inference questions
  format_data: { "options": ["option A", "option B", "option C", "option D"], "correct_index": 0 }
  Mark range: 1
  Requirements:
    - Exactly 4 options
    - One unambiguously correct answer
    - Three plausible distractors (not obviously wrong)
    - Options roughly equal in length
    - correct_index is 0-based

tick_two
  Use for: questions with exactly two correct answers from a list
  format_data: { "options": ["A", "B", "C", "D", "E"], "correct_indices": [1, 3] }
  Mark range: 1
  Requirements: exactly 5 options, exactly 2 correct

true_false_table
  Use for: checking understanding of several statements from the text at once
  format_data: { "statements": [ { "text": "...", "correct": true }, ... ] }
  Mark range: 2
  Requirements:
    - 4 or 5 statements
    - Mix of true and false (roughly half and half)
    - Statements must be clearly answerable from the text — no ambiguity
    - Some statements should require inference, not just word-matching

sequencing
  Use for: ordering events, steps in a process, or stages in a narrative
  format_data: { "items": ["first event", "second event", "third event", "fourth event"] }
  Mark range: 1
  Requirements:
    - Exactly 4 items
    - Items listed in CORRECT chronological/logical order (the builder will shuffle them for display)
    - Items are short phrases, not full sentences
    - Items must all come from the text, not be inferred

reason_evidence_table
  Use for: inference questions requiring the reader to justify a claim with textual evidence
  format_data: { "example": { "reason": "...", "evidence": "..." }, "rows": 2 }
  Mark range: 3
  Requirements:
    - Provide one complete example row as a model
    - rows is always 2 (two blank rows to complete)
    - The example must be genuinely helpful, not just a re-statement

two_part_ab
  Use for: when two related but distinct pieces of information are needed from the same passage
  format_data: { "parts": [ { "label": "a", "question": "...", "answer": "..." }, { "label": "b", "question": "...", "answer": "..." } ] }
  Mark range: 2 total (1 per part)

---
TEXT REFERENCE

Every question must include a "text_reference" field that scopes the reader to the relevant passage.
Use one of these patterns exactly:
  "Read the section: [subheading]"           — when the text has subheadings
  "Read the paragraph beginning: [first 5-6 words of the paragraph]..."
  "Look at page [N]."                        — when the text booklet has page numbers
  "Read the paragraph beginning: [phrase]... to the paragraph ending: ...[phrase]"
  "Look at the whole text."                  — for synthesis questions only

For questions that quote a line from the text, reproduce the quote in the question field before the question itself, e.g.:
  "She felt a cool focus flood her veins.\\n\\nWhat does this suggest about how Merry was feeling?"

---
QUESTION WRITING RULES

- Questions must be answerable from the text alone. Do not require outside knowledge.
- Vocabulary questions: always quote the exact word/phrase from the text, reference the paragraph.
- Find-and-copy questions: the target word/phrase must appear verbatim in the text.
- True/false statements: avoid ones where the answer is obvious from common knowledge.
- Sequencing items: use language close to the text but not identical — paraphrase slightly.
- Distractors in tick_one: make them genuinely tempting. Avoid options that are obviously silly.
- Do not use the word "pupils" anywhere. Do not ask learners to "evaluate" or "analyse" — use "explain", "give reasons", "how can you tell".
- Inference questions should push beyond surface retrieval — ask about character motivation, author intent, or what a phrase implies.

---
SUPPORTED VERSION SCAFFOLDING

For each question, also provide a "supported_scaffold" string. This is additional text (a sentence starter, a hint, or a partially completed answer) that will be shown only on the Supported Pupil version. Keep it brief. Examples:
  open_line: "The text says that..."
  numbered_list: "1. One thing is that... 2. Another thing is..."
  inference: "We can tell this because..."
  tick_one: null (tick_one needs no scaffold — the format is already simplified)
  find_and_copy: null

---
OUTPUT FORMAT

Respond with ONLY valid JSON. No preamble, no explanation, no markdown fences.

The JSON must match this exact structure:

{
  "key_question": "...",
  "lessons": [
    {
      "lesson_type": "vocabulary",
      "day": "...",
      "date": "...",
      "i_can_statements": ["...", "..."],
      "questions": [
        {
          "number": 1,
          "type": "retrieval",
          "format": "open_line",
          "marks": 1,
          "text_reference": "...",
          "question": "...",
          "answer": "...",
          "supported_scaffold": "...",
          "format_data": {
            "lines": 2
          }
        }
      ]
    },
    {
      "lesson_type": "retrieval",
      ...
    },
    {
      "lesson_type": "inference",
      ...
    }
  ]
}
"""


def build_user_prompt(
    text: str,
    key_question: str,
    vocab_day: str,
    vocab_date: str,
    vocab_i_can: list[str],
    retrieval_day: str,
    retrieval_date: str,
    retrieval_i_can: list[str],
    inference_day: str,
    inference_date: str,
    inference_i_can: list[str],
) -> str:
    return f"""TEXT:
{text}

KEY QUESTION: {key_question}

LESSON SCHEDULE:
  Lesson 1 (Vocabulary):  {vocab_day}, {vocab_date}
  I can statements: {'; '.join(vocab_i_can)}

  Lesson 2 (Retrieval):   {retrieval_day}, {retrieval_date}
  I can statements: {'; '.join(retrieval_i_can)}

  Lesson 3 (Inference):   {inference_day}, {inference_date}
  I can statements: {'; '.join(inference_i_can)}

FORMAT GUIDANCE PER SLOT:

Vocabulary lesson (7 questions):
{chr(10).join(f'  Slot {i+1} ({t}): {g}' for i, (t, g) in enumerate(zip(
    ['retrieval','list','vocabulary','explain','multiple_choice','compare','inference'],
    LESSON_FORMAT_GUIDANCE['vocabulary']
)))}

Retrieval lesson (7 questions):
{chr(10).join(f'  Slot {i+1} ({t}): {g}' for i, (t, g) in enumerate(zip(
    ['retrieval','list','ordering','compare','explain','multiple_choice','inference'],
    LESSON_FORMAT_GUIDANCE['retrieval']
)))}

Inference lesson (7 questions):
{chr(10).join(f'  Slot {i+1} ({t}): {g}' for i, (t, g) in enumerate(zip(
    ['retrieval','vocabulary','multiple_choice','explain','inference','inference','inference'],
    LESSON_FORMAT_GUIDANCE['inference']
)))}

Generate all three lessons now. Remember: ONLY valid JSON, no markdown fences."""


def generate_content(
    text: str,
    key_question: str,
    vocab_day: str,
    vocab_date: str,
    vocab_i_can: list[str],
    retrieval_day: str,
    retrieval_date: str,
    retrieval_i_can: list[str],
    inference_day: str,
    inference_date: str,
    inference_i_can: list[str],
) -> dict:
    """
    Call the Claude API and return parsed lesson content as a dict.
    Raises ValueError if the response cannot be parsed as valid JSON.
    """
    user_prompt = build_user_prompt(
        text=text,
        key_question=key_question,
        vocab_day=vocab_day,
        vocab_date=vocab_date,
        vocab_i_can=vocab_i_can,
        retrieval_day=retrieval_day,
        retrieval_date=retrieval_date,
        retrieval_i_can=retrieval_i_can,
        inference_day=inference_day,
        inference_date=inference_date,
        inference_i_can=inference_i_can,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip any accidental markdown fences
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw response:\n{raw[:500]}")

    _validate(data)
    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALID_TYPES = {
    "retrieval", "list", "vocabulary", "explain", "multiple_choice",
    "compare", "ordering", "inference", "find_and_copy", "author_effect",
}

VALID_FORMATS = {
    "open_line", "find_and_copy", "numbered_list", "tick_one", "tick_two",
    "true_false_table", "sequencing", "reason_evidence_table", "two_part_ab",
}

REQUIRED_FORMAT_DATA_KEYS = {
    "open_line": {"lines"},
    "find_and_copy": {"target_word"},
    "numbered_list": {"num_points"},
    "tick_one": {"options", "correct_index"},
    "tick_two": {"options", "correct_indices"},
    "true_false_table": {"statements"},
    "sequencing": {"items"},
    "reason_evidence_table": {"example", "rows"},
    "two_part_ab": {"parts"},
}

LESSON_TYPE_SEQUENCES = {
    "vocabulary": ["retrieval", "list", "vocabulary", "explain", "multiple_choice", "compare", "inference"],
    "retrieval": ["retrieval", "list", "ordering", "compare", "explain", "multiple_choice", "inference"],
    "inference": ["retrieval", "vocabulary", "multiple_choice", "explain", "inference", "inference", "inference"],
}


def _validate(data: dict) -> None:
    """Light validation — raises ValueError on structural problems."""
    if "lessons" not in data:
        raise ValueError("Missing 'lessons' key in response")
    if len(data["lessons"]) != 3:
        raise ValueError(f"Expected 3 lessons, got {len(data['lessons'])}")

    for lesson in data["lessons"]:
        lt = lesson.get("lesson_type")
        if lt not in LESSON_TYPE_SEQUENCES:
            raise ValueError(f"Unknown lesson_type: {lt}")

        questions = lesson.get("questions", [])
        if len(questions) != 7:
            raise ValueError(f"Lesson '{lt}' has {len(questions)} questions, expected 7")

        expected_types = LESSON_TYPE_SEQUENCES[lt]
        for i, q in enumerate(questions):
            # Type check (allow inference slots to be inference)
            expected = expected_types[i]
            actual = q.get("type", "")
            if actual not in VALID_TYPES:
                raise ValueError(f"Lesson '{lt}' Q{i+1}: unknown type '{actual}'")

            # Format check
            fmt = q.get("format", "")
            if fmt not in VALID_FORMATS:
                raise ValueError(f"Lesson '{lt}' Q{i+1}: unknown format '{fmt}'")

            # format_data presence
            if "format_data" not in q:
                raise ValueError(f"Lesson '{lt}' Q{i+1}: missing format_data")

            required_keys = REQUIRED_FORMAT_DATA_KEYS.get(fmt, set())
            missing = required_keys - set(q["format_data"].keys())
            if missing:
                raise ValueError(
                    f"Lesson '{lt}' Q{i+1} (format={fmt}): "
                    f"missing format_data keys: {missing}"
                )

            # tick_one: must have exactly 4 options
            if fmt == "tick_one":
                opts = q["format_data"].get("options", [])
                if len(opts) != 4:
                    raise ValueError(
                        f"Lesson '{lt}' Q{i+1}: tick_one must have 4 options, got {len(opts)}"
                    )
                ci = q["format_data"].get("correct_index", -1)
                if not (0 <= ci <= 3):
                    raise ValueError(
                        f"Lesson '{lt}' Q{i+1}: correct_index {ci} out of range"
                    )

            # tick_two: must have exactly 5 options, 2 correct
            if fmt == "tick_two":
                opts = q["format_data"].get("options", [])
                cis = q["format_data"].get("correct_indices", [])
                if len(opts) != 5:
                    raise ValueError(f"Lesson '{lt}' Q{i+1}: tick_two needs 5 options")
                if len(cis) != 2:
                    raise ValueError(f"Lesson '{lt}' Q{i+1}: tick_two needs 2 correct_indices")

            # true_false_table: 4-5 statements
            if fmt == "true_false_table":
                stmts = q["format_data"].get("statements", [])
                if not (4 <= len(stmts) <= 5):
                    raise ValueError(
                        f"Lesson '{lt}' Q{i+1}: true_false_table needs 4-5 statements, got {len(stmts)}"
                    )

            # sequencing: exactly 4 items
            if fmt == "sequencing":
                items = q["format_data"].get("items", [])
                if len(items) != 4:
                    raise ValueError(
                        f"Lesson '{lt}' Q{i+1}: sequencing needs exactly 4 items, got {len(items)}"
                    )

            # marks present and positive
            marks = q.get("marks", 0)
            if not isinstance(marks, int) or marks < 1:
                raise ValueError(f"Lesson '{lt}' Q{i+1}: invalid marks value '{marks}'")

            # Required string fields
            for field in ("text_reference", "question", "answer"):
                if not q.get(field, "").strip():
                    raise ValueError(f"Lesson '{lt}' Q{i+1}: missing or empty '{field}'")
