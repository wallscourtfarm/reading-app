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

YG_TEXT_GUIDANCE = {
    "Y1": (
        "Age 5–6. Very simple sentences of 5–8 words. Common Reception/Y1 vocabulary only. "
        "Fiction: familiar, everyday settings (home, school, garden, park) with simple characters "
        "and a clear event. Non-fiction: one concrete topic, very short sentences, bold subheadings "
        "to break text into 3–4 sections. Poetry: short rhyming verse, 8–16 lines. "
        "Embed 3–4 slightly ambitious but inferable words — these become question targets. "
        "Total text: 280–380 words. Paragraphs 2–3 sentences maximum."
    ),
    "Y2": (
        "Age 6–7. Simple but varied sentences of 8–12 words. Year 1/2 CEW vocabulary with "
        "4–5 slightly challenging words deliberately seeded as question targets. "
        "Fiction: clear narrative with recognisable characters, a problem and resolution. "
        "Non-fiction: clear topic sentences, 3–4 subheaded sections, one bullet-point or facts section. "
        "Poetry: rhyming or free verse, 12–20 lines, accessible imagery. "
        "Total text: 350–500 words."
    ),
    "Y4": (
        "Age 8–9. Accessible prose with Tier 2 vocabulary embedded naturally. "
        "Sentences varied but clear. Y3/4 CEW list. Inference requires reading between "
        "the lines; author viewpoint accessible. Non-fiction may use subheadings for "
        "long texts."
    ),
    "Y5": (
        "Age 9–10. More ambitious prose with Tier 2 and some Tier 3 vocabulary. "
        "Complex sentence structures and figurative language used where appropriate. "
        "Y5/6 CEW list begins. Multiple layers of meaning in fiction. Non-fiction may "
        "use cross-references, index-style organisation or embedded data."
    ),
    "Y6": (
        "Age 10–11. Challenging prose with full Y5/6 CEW vocabulary. May include irony, "
        "ambiguity, unreliable narrators or complex structural choices. Texts can have "
        "multiple layers of meaning. Fiction may use shifts in perspective or time. "
        "Non-fiction may include persuasion, bias or evaluative stance."
    ),
}

YG_QUESTION_GUIDANCE = {
    "Y1": (
        "KS1 content domains: 1a (vocabulary), 1b (key facts/events), 1c (sequence), "
        "1d (inference), 1e (prediction). ALL questions 1 mark — no exceptions. "
        "Heavy use of tick_one (4 options in a 2×2 grid) and short open_line. "
        "Inference: simple deduction — 'This tells you... Tick one.' style. "
        "Do not use draw_lines_matching, true_false_table, or numbered_list. "
        "8–10 questions per passage."
    ),
    "Y2": (
        "KS1 content domains: 1a (vocabulary), 1b (key facts/events), 1c (sequence), "
        "1d (inference), 1e (prediction). Mix of 1-mark and 2-mark questions. "
        "Core types: tick_one, find_and_copy, open_line (short written answer). "
        "2-mark types: true_false_table (4 statements), numbered_list (write two reasons, 1 mark each). "
        "1-mark list: numbered_list (write two things, 1 mark total for any correct answer). "
        "draw_lines_matching: 1 mark, ALL pairs must be correct — use once per passage maximum. "
        "No question over 2 marks. Target 8–9 questions per passage, ~10 marks total."
    ),
    "Y4": (
        "Full 2a–2h content domain at Y4 level. Balance retrieval, vocabulary and "
        "inference. Inference: unstated meaning, author viewpoint. Vocabulary: "
        "connotation, word families, Tier 2 in context."
    ),
    "Y5": (
        "Full 2a–2h at Y5 level. Increase weighting of inference and author craft. "
        "Inference: figurative language, between-the-lines meaning, author intent. "
        "Author craft (2f): analyse specific language and structure choices for effect. "
        "Retrieval: multiple steps, using glossary or cross-reference."
    ),
    "Y6": (
        "Full 2a–2h at Y6 level with sustained analytical depth. Strong weighting to "
        "inference, language effect and comparison. Questions may target irony, "
        "ambiguity, unreliable narrators. Use SATs-style question stems for analysis "
        "questions. reason_evidence_table and multi-mark open_line questions more "
        "frequent. Summary (2c): condense extended passages."
    ),
}

YG_SUPPORTED_GUIDANCE = {
    "Y1": (
        "Supported version: identical to standard — the combined Paper 1 layout already "
        "reduces cognitive load by placing text alongside questions. No additional changes."
    ),
    "Y2": (
        "Supported version pitched at Year 1 reading level: very short sentences, common "
        "everyday words only. For open_line questions provide a sentence starter scaffold. "
        "Keep format identical to standard version."
    ),
    "Y4": (
        "Supported version pitched at Year 1/2 reading level: shorter sentences, "
        "simpler synonyms substituted for harder words, generous scaffolding and "
        "sentence starters throughout."
    ),
    "Y5": (
        "Supported version pitched at Year 3 reading level: simplified but not "
        "babyish; sentence frames provided; key vocabulary glossed inline; "
        "scaffolding supports structure without over-simplifying the thinking."
    ),
    "Y6": (
        "Supported version pitched at Year 4 reading level: still cognitively "
        "demanding; vocabulary support and structured sentence frames provided; "
        "inference scaffolded with evidence prompts."
    ),
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
    "Draw lines to match":             "draw_lines_matching",
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

draw_lines_matching  Left column of sentence stems, right column of completions (already shuffled).
                   Pupil draws lines to match each stem to its correct completion.
                   format_data: {
                     "left_items":  ["stem 1…", "stem 2…", "stem 3…"],
                     "right_items": ["completion B", "completion C", "completion A"],
                     "correct_pairs": [[0,2],[1,0],[2,1]]
                   }
                   correct_pairs: list of [left_index, right_index] pairs (right index into
                   right_items as displayed — i.e. already shuffled order).
                   right_items MUST be in shuffled order (not aligned to left_items).
                   Question: "Draw N lines to match each [X] with the correct [Y]."
                   Always 1 mark, awarded only if ALL pairs correct.
                   KS1 only — do not use in KS2 Lesson Mode or KS2 Reading Paper Mode.

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
      "learning_focus": "To explore and explain the meaning of new vocabulary in context",
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
    vocab_day, vocab_date, vocab_i_can, vocab_lf,
    retrieval_day, retrieval_date, retrieval_i_can, retrieval_lf,
    inference_day, inference_date, inference_i_can, inference_lf,
    context, question_types, question_layouts, text_length,
    year_group="Y4",
):
    word_count = WORD_COUNTS.get(text_length, "200–250")
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""

    yg_text = YG_TEXT_GUIDANCE.get(year_group, YG_TEXT_GUIDANCE["Y4"])
    yg_q    = YG_QUESTION_GUIDANCE.get(year_group, YG_QUESTION_GUIDANCE["Y4"])
    yg_sup  = YG_SUPPORTED_GUIDANCE.get(year_group, YG_SUPPORTED_GUIDANCE["Y4"])

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

    return f"""YEAR GROUP: {year_group}
TOPIC: {topic}{context_line}
TEXT_LENGTH: {word_count} words
TEXT GUIDANCE: {yg_text}
QUESTION GUIDANCE: {yg_q}
SUPPORTED VERSION: {yg_sup}{type_r}{layout_r}

KEY QUESTION: {key_question}

LESSON SCHEDULE:
  Lesson 1 (Vocabulary):  {vocab_day}, {vocab_date}
  Learning Focus: {vocab_lf or "To explore and explain the meaning of new vocabulary in context"}
  I can: {'; '.join(vocab_i_can)}

  Lesson 2 (Retrieval):   {retrieval_day}, {retrieval_date}
  Learning Focus: {retrieval_lf or "To retrieve and record key information from a text"}
  I can: {'; '.join(retrieval_i_can)}

  Lesson 3 (Inference):   {inference_day}, {inference_date}
  Learning Focus: {inference_lf or "To make and explain inferences using evidence from the text"}
  I can: {'; '.join(inference_i_can)}

Return each lesson's learning_focus exactly as given above in the LESSON SCHEDULE.

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
    question_types, question_layouts, context, year_group="Y4",
):
    word_count = WORD_COUNTS.get(text_length, "200–250")
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""
    type_r = _type_restriction(question_types)
    layout_r = _layout_restriction(question_layouts)
    yg_text = YG_TEXT_GUIDANCE.get(year_group, YG_TEXT_GUIDANCE["Y4"])
    yg_q    = YG_QUESTION_GUIDANCE.get(year_group, YG_QUESTION_GUIDANCE["Y4"])
    yg_sup  = YG_SUPPORTED_GUIDANCE.get(year_group, YG_SUPPORTED_GUIDANCE["Y4"])

    title_line = f"\nKEY QUESTION: {key_question}" if key_question.strip() else ""
    return f"""YEAR GROUP: {year_group}
TOPIC: {topic}{context_line}
TEXT_LENGTH: {word_count} words
TEXT GUIDANCE: {yg_text}
QUESTION GUIDANCE: {yg_q}
SUPPORTED VERSION: {yg_sup}
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
    "draw_lines_matching",
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
    "draw_lines_matching":   {"left_items", "right_items", "correct_pairs"},
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
    vocab_lf: str = "",
    retrieval_day: str = "",
    retrieval_date: str = "",
    retrieval_i_can: list = None,
    retrieval_lf: str = "",
    inference_day: str = "",
    inference_date: str = "",
    inference_i_can: list = None,
    inference_lf: str = "",
    context: str = "",
    question_types: list = None,
    question_layouts: list = None,
    text_length: str = "standard",
    year_group: str = "Y4",
) -> dict:
    """
    Lesson Mode: generate 3 lessons × 7 questions.
    Returns dict with 'standard_text' and 'lessons'.
    """
    prompt = _build_lesson_prompt(
        topic=topic, key_question=key_question,
        vocab_day=vocab_day, vocab_date=vocab_date,
        vocab_i_can=vocab_i_can, vocab_lf=vocab_lf,
        retrieval_day=retrieval_day, retrieval_date=retrieval_date,
        retrieval_i_can=retrieval_i_can or [], retrieval_lf=retrieval_lf,
        inference_day=inference_day, inference_date=inference_date,
        inference_i_can=inference_i_can or [], inference_lf=inference_lf,
        context=context, question_types=question_types,
        question_layouts=question_layouts, text_length=text_length,
        year_group=year_group,
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
    year_group: str = "Y4",
) -> dict:
    """
    Reading Paper Mode: generate a text + flat question set.
    Returns dict with 'standard_text' and 'questions'.
    """
    prompt = _build_reading_paper_prompt(
        topic=topic, key_question=key_question,
        num_questions=num_questions, text_length=text_length,
        question_types=question_types, question_layouts=question_layouts,
        context=context, year_group=year_group,
    )
    # More tokens for larger question sets
    max_tok = max(6000, num_questions * 600)
    data = _call_api(READING_PAPER_SYSTEM_PROMPT, prompt, max_tokens=min(max_tok, 12000))
    _validate_reading_paper(data, num_questions)
    return data


# ---------------------------------------------------------------------------
# KS1 READING PAPER MODE
# ---------------------------------------------------------------------------

KS1_WORD_COUNTS = {
    "Y1": "280–380",
    "Y2": "350–500",
}

# KS1 Paper 2 (separate text + answer booklet) — uses existing flat question schema
# but with KS1-specific guidance injected via year group constants.

KS1_PAPER2_SYSTEM_PROMPT = f"""You are an expert KS1 reading comprehension question writer for Year 1/2 pupils (age 5–7) in England, working to national KS1 assessment conventions.

You will generate ONE reading passage and a set of comprehension questions for a KS1 Paper 2 (separate reading booklet and answer booklet).

TEXT:
- Write the text yourself. Do not ask for it.
- Fiction: clear narrative, short paragraphs, dialogue optional.
- Non-fiction: 3–4 subheaded sections (format: **Heading** on own line) plus optional bullet/fact section.
- Poetry: short verse, 12–20 lines, 2–4 stanzas.
- The text goes in the top-level "standard_text" field.
- Total length determined by TEXT_LENGTH in the user message.

{FORMAT_REFERENCE}

KS1 MARK SCHEME CONVENTIONS:
- open_line answers: provide 2–4 acceptable phrasings separated by " / ".
  Also include "do_not_accept" field (string) for common wrong answers where relevant.
- tick_one: one correct answer, three plausible distractors.
- find_and_copy: exact word(s) from the text verbatim.
- true_false_table: 4 statements, mix of true and false; 2 marks (all 4 correct) or 1 mark (3 correct).
- numbered_list (write two things, 1 mark total): answer field gives both acceptable items as "item1 / item2".
- numbered_list (write two reasons, 2 marks): answer field gives items separated by " / ", 1 mark each.
- draw_lines_matching: answer field summarises the correct pairs as "left→right" entries separated by "; ".

QUESTION WRITING RULES:
- text_reference: reference section headings for non-fiction ("Look at the section: X"),
  or paragraph beginnings for fiction ("Look at the paragraph beginning: X...").
  Use "(pages X–Y)" style only for whole-text questions.
- For vocabulary questions (tick_one or find_and_copy), quote the target word/phrase in the question.
- Tick one questions: instruction is "Tick one." at end of question. Four options.
- Keep question language at KS1 level — short, direct sentences.
- Do not use "pupils". Do not say "evaluate" or "analyse".
- supported_scaffold: for open_line questions provide a brief sentence starter; null for all other formats.

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
      "do_not_accept": "",
      "supported_scaffold": "The text says...",
      "format_data": {{"lines": 1}}
    }}
  ]
}}
"""


# KS1 Paper 1 (combined text + questions) — requires chunked text schema
KS1_PAPER1_SYSTEM_PROMPT = f"""You are an expert KS1 reading comprehension question writer for Year 1/2 pupils (age 5–7) in England, working to national KS1 assessment conventions.

You will generate ONE reading passage for a KS1 Paper 1 (combined booklet where text and questions appear on the same pages).

The passage is divided into SECTIONS. Each section has:
1. A short text chunk (50–100 words) — a natural paragraph or section break
2. 1–2 questions (never more than 2 per chunk)

ALL questions are worth exactly 1 mark. No 2-mark questions in Paper 1.

ALLOWED FORMATS in Paper 1:
- open_line (lines: 1 only)
- tick_one (4 options)
- find_and_copy

Do NOT use: true_false_table, numbered_list, draw_lines_matching, tick_two, sequencing, reason_evidence_table, two_part_ab.

TEXT RULES:
- Fiction: 4–6 sections of 50–100 words each (~350–450 words total).
- Non-fiction: 3–5 sections with bold subheadings (**Heading**) (~300–420 words total).
- Poetry: 3–5 stanzas of 4–6 lines each, one or two questions per stanza.
- Maintain narrative/thematic flow across all sections.

QUESTION RULES (Paper 1):
- No text_reference field — text is printed directly above the question.
- answer field: 2–4 acceptable phrasings separated by " / ".
- supported_scaffold: null for all questions (Paper 1 layout already reduces cognitive load).
- tick_one: "Tick one." instruction, four options, one correct.
- find_and_copy: exact word from the text chunk above.

OUTPUT: Valid JSON only — no preamble, no markdown fences.

{{
  "title": "...",
  "text_type": "fiction|non_fiction|poetry",
  "sections": [
    {{
      "text_chunk": "...",
      "questions": [
        {{
          "number": 1,
          "format": "open_line",
          "marks": 1,
          "question": "...",
          "answer": "...",
          "supported_scaffold": null,
          "format_data": {{"lines": 1}}
        }}
      ]
    }}
  ]
}}
"""


def _build_ks1_paper2_prompt(topic, text_type, year_group, context=""):
    word_count = KS1_WORD_COUNTS.get(year_group, "350–500")
    yg_text = YG_TEXT_GUIDANCE.get(year_group, YG_TEXT_GUIDANCE["Y2"])
    yg_q    = YG_QUESTION_GUIDANCE.get(year_group, YG_QUESTION_GUIDANCE["Y2"])
    yg_sup  = YG_SUPPORTED_GUIDANCE.get(year_group, YG_SUPPORTED_GUIDANCE["Y2"])
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""
    q_count = "8–9" if year_group == "Y2" else "8–10"
    return f"""YEAR GROUP: {year_group}
TOPIC: {topic}
TEXT TYPE: {text_type}{context_line}
TEXT_LENGTH: {word_count} words
TEXT GUIDANCE: {yg_text}
QUESTION GUIDANCE: {yg_q}
SUPPORTED VERSION: {yg_sup}
NUMBER OF QUESTIONS: {q_count} (targeting ~10 marks total)

Generate {q_count} questions now. ONLY valid JSON — no markdown fences."""


def _validate_ks1_paper2_passage(data, passage_label=""):
    if not data.get("standard_text", "").strip():
        raise ValueError(f"{passage_label}: missing standard_text")
    qs = data.get("questions", [])
    if not (6 <= len(qs) <= 12):
        raise ValueError(f"{passage_label}: expected 6–12 questions, got {len(qs)}")
    for q in qs:
        _validate_question(q, lesson_label=passage_label)
        # KS1 mark cap
        if q.get("marks", 1) > 2:
            raise ValueError(f"{passage_label} Q{q.get('number','?')}: KS1 max 2 marks")


def _validate_ks1_paper1_passage(data, passage_label=""):
    if not data.get("title", "").strip():
        raise ValueError(f"{passage_label}: missing title")
    sections = data.get("sections", [])
    if not (3 <= len(sections) <= 7):
        raise ValueError(f"{passage_label}: expected 3–7 sections, got {len(sections)}")
    q_num = 0
    for i, section in enumerate(sections):
        if not section.get("text_chunk", "").strip():
            raise ValueError(f"{passage_label} section {i+1}: missing text_chunk")
        qs = section.get("questions", [])
        if not (1 <= len(qs) <= 2):
            raise ValueError(f"{passage_label} section {i+1}: expected 1–2 questions")
        for q in qs:
            q_num += 1
            fmt = q.get("format", "")
            if fmt not in ("open_line", "tick_one", "find_and_copy"):
                raise ValueError(
                    f"{passage_label} section {i+1}: Paper 1 format '{fmt}' not allowed"
                )
            if q.get("marks", 1) != 1:
                raise ValueError(
                    f"{passage_label} section {i+1}: Paper 1 questions must be 1 mark"
                )


def _build_ks1_paper1_prompt(topic, text_type, year_group, context=""):
    word_count = KS1_WORD_COUNTS.get(year_group, "350–450")
    yg_text = YG_TEXT_GUIDANCE.get(year_group, YG_TEXT_GUIDANCE["Y2"])
    context_line = f"\nCURRICULUM CONTEXT: {context}" if context.strip() else ""
    return f"""YEAR GROUP: {year_group}
TOPIC: {topic}
TEXT TYPE: {text_type}{context_line}
TEXT_LENGTH per passage: {word_count} words total, divided into 4–6 chunks of 50–100 words each
TEXT GUIDANCE: {yg_text}

Generate the passage now. ONLY valid JSON — no markdown fences."""


def generate_ks1_paper(
    topic1: str,
    text_type1: str,
    topic2: str,
    text_type2: str,
    paper_type: str = "separate",
    year_group: str = "Y2",
    context: str = "",
) -> dict:
    """
    KS1 Reading Paper generator.
    paper_type: "separate"  → Paper 2 (text booklet + answer booklet)
                "combined"  → Paper 1 (text and questions on same pages)
    Returns:
      {
        "paper_type": "separate"|"combined",
        "passage1": {...},   # standard_text+questions for separate; title+sections for combined
        "passage2": {...},
      }
    """
    if paper_type == "combined":
        system = KS1_PAPER1_SYSTEM_PROMPT
        p1 = _call_api(system,
                       _build_ks1_paper1_prompt(topic1, text_type1, year_group, context),
                       max_tokens=8000)
        _validate_ks1_paper1_passage(p1, "Passage 1")

        p2 = _call_api(system,
                       _build_ks1_paper1_prompt(topic2, text_type2, year_group, context),
                       max_tokens=8000)
        _validate_ks1_paper1_passage(p2, "Passage 2")

        # Renumber questions across passages (P2 continues from P1)
        offset = sum(len(s.get("questions", [])) for s in p1.get("sections", []))
        for section in p2.get("sections", []):
            for q in section.get("questions", []):
                q["number"] = q.get("number", 0) + offset

    else:  # separate (Paper 2)
        system = KS1_PAPER2_SYSTEM_PROMPT
        p1 = _call_api(system,
                       _build_ks1_paper2_prompt(topic1, text_type1, year_group, context),
                       max_tokens=8000)
        _validate_ks1_paper2_passage(p1, "Passage 1")

        p2 = _call_api(system,
                       _build_ks1_paper2_prompt(topic2, text_type2, year_group, context),
                       max_tokens=8000)
        _validate_ks1_paper2_passage(p2, "Passage 2")

        # Renumber questions across passages
        offset = len(p1.get("questions", []))
        for q in p2.get("questions", []):
            q["number"] = q.get("number", 0) + offset

    return {
        "paper_type": paper_type,
        "passage1": p1,
        "passage2": p2,
        "year_group": year_group,
    }
