"""
content_generator.py  –  Calls Claude API to generate Being a Reader lesson content.
Returns structured JSON for all 3 lessons (Vocabulary / Retrieval / Inference).
"""

import json
import anthropic

SYSTEM_PROMPT = """You generate Being a Reader reading comprehension lesson content for a Year 4 class (ages 8–9) in a UK primary school.

Return ONLY valid JSON — no preamble, no markdown fences.

JSON structure:
{
  "lessons": [
    {
      "number": 1,
      "type": "Vocabulary",
      "day": "Tuesday",
      "date": "12/05/2026",
      "vocab": [{"word": "...", "definition": "..."}, ... (5 items)],
      "focus_word": "...",
      "extract_standard": "...",
      "extract_supported": "...",
      "questions_standard": [ ... 7 question objects ... ],
      "questions_supported": [ ... 5 question objects ... ],
      "we_do_questions": [{"question": "...", "answer": "..."}, {"question": "...", "answer": "..."}]
    },
    { "number": 2, "type": "Retrieval", ... same structure ... },
    { "number": 3, "type": "Inference", ... same structure ... }
  ]
}

═══════════════════════════════════════════
QUESTION OBJECT FORMAT
═══════════════════════════════════════════

Every question object MUST have a "type" field. Valid types and their required fields:

TYPE: "retrieval"
{"number": 1, "type": "retrieval", "question": "...", "answer": "..."}
Use for: straightforward find-it-in-the-text questions. "According to the text, what..."

TYPE: "list"
{"number": 2, "type": "list", "question": "...", "answer": "..."}
Use for: "Give two examples of...", "Name three...", "List two..."

TYPE: "vocabulary"
{"number": 3, "type": "vocabulary", "question": "...", "answer": "..."}
Use for: "What does the word '...' mean in this text?"

TYPE: "explain"
{"number": 4, "type": "explain", "question": "...", "answer": "..."}
Use for: "Why...? Use evidence from the text.", "How does...? Use the text to support your answer."
MUST include "Use evidence from the text." at the end of the question.

TYPE: "multiple_choice"
{"number": 5, "type": "multiple_choice", "question": "...", "options": ["A", "B", "C", "D"], "answer": "..."}
CRITICAL: options must be a JSON array of exactly 4 short text strings.
DO NOT put a/b/c/d labels inside the option strings — just plain text.
Example: "options": ["Thin glass", "Thick foam panels", "Smooth metal", "Open mesh fabric"]
The answer field is the correct option text.

TYPE: "ordering"
{"number": 3, "type": "ordering", "question": "Put these steps in the correct order...", "items": ["Step A", "Step B", "Step C", "Step D"], "answer": "..."}
CRITICAL: items must be a JSON array of exactly 4 strings — the steps to reorder.
Shuffle them so they are NOT already in the correct order.
The answer explains the correct order.

TYPE: "compare"
{"number": 6, "type": "compare", "question": "...", "answer": "..."}
Use for: "How is X different from Y?", "What do X and Y have in common?"

TYPE: "inference"
{"number": 7, "type": "inference", "question": "...", "answer": "..."}
Use for: deeper questions. "What does this suggest about...?", "The text says '...'. What does this tell us about why...?"
INCLUDE a short quote from the extract (under 10 words) in inverted commas when relevant.

TYPE: "fill_blank"
{"number": 2, "type": "fill_blank", "question": "Complete this sentence: Buddhism was founded over _____ years ago.", "answer": "2,500"}
Use for: supported version only, for simple factual recall.

═══════════════════════════════════════════
REQUIRED QUESTION TYPE SEQUENCE
═══════════════════════════════════════════

You MUST follow this exact sequence of question types for each lesson. Do not substitute or reorder.

LESSON 1 — Vocabulary (7 standard, 5 supported):
Standard: retrieval, list, vocabulary, explain, multiple_choice, compare, inference
Supported: retrieval, fill_blank, vocabulary, multiple_choice, explain
(Supported questions are genuinely simpler — not the same questions with fewer of them)

LESSON 2 — Retrieval (7 standard, 5 supported):
Standard: retrieval, list, ordering, compare, explain, multiple_choice, inference
Supported: retrieval, list, ordering, explain, multiple_choice

LESSON 3 — Inference (7 standard, 5 supported):
Standard: retrieval, vocabulary, multiple_choice, explain, inference, inference, inference
Supported: retrieval, vocabulary, multiple_choice, explain, inference

═══════════════════════════════════════════
CONTENT RULES
═══════════════════════════════════════════

EXTRACTS:
- One extract per lesson — a different angle on the same topic each time
- Standard: 200–250 words, single flowing paragraph, plain informational prose
- Supported: 130–150 words, simpler vocabulary, shorter sentences, same topic angle
- Embed all 5 vocabulary words naturally in the standard extract
- L1 (Vocabulary): explain and define key concepts
- L2 (Retrieval): facts, examples, sequences that can be found in the text
- L3 (Inference): cause, effect, author viewpoint, implication

VOCABULARY (5 words per lesson, 15 different words across the 3 lessons):
- Tier 2 words, accessible for age 8–9
- Definitions: one clear child-friendly sentence, no jargon
- Focus word: the most commonly encountered of the 5 — used for the "write it 5 times" slide
- NEVER use the same word in two different lessons

LANGUAGE:
- British English throughout. No em dashes. No Oxford comma.
- No "moreover", "pivotal", "nuanced", "delves", "fosters", "underscores", "tapestry", "embark", "elevate"
- Extracts must read as natural informational prose — not AI-generated lists
- Y4-appropriate — answerable by 8–9 year olds in 1–3 sentences
- Never address pupils as "pupils" — use second person ("you") in questions

ANSWERS:
- Complete sentences
- Appropriate length for Y4
- For explain/evidence questions: full model answer using text evidence
- For multiple_choice: just the correct option text"""


def generate_lesson_content(
    topic: str,
    key_question: str,
    week_ref: str,
    lesson_days: list[dict]
) -> dict:
    client = anthropic.Anthropic()

    user_prompt = f"""Generate Being a Reader lesson content for the following week.

Week reference: {week_ref}
Topic / text: {topic}
Key question: {key_question}

Lesson days:
- Lesson 1 (Vocabulary):  {lesson_days[0]['day']}, {lesson_days[0]['date']}
- Lesson 2 (Retrieval):   {lesson_days[1]['day']}, {lesson_days[1]['date']}
- Lesson 3 (Inference):   {lesson_days[2]['day']}, {lesson_days[2]['date']}

Follow the REQUIRED QUESTION TYPE SEQUENCE exactly. Return the complete JSON now."""

    message = anthropic.Anthropic().messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_prompt}]
    )

    raw = message.content[0].text.strip()
    raw = raw.removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    return json.loads(raw)
