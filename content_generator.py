"""
content_generator.py  –  Calls Claude API to generate Being a Reader lesson content.
Returns structured JSON for all 3 lessons (Vocabulary / Retrieval / Inference).
"""

import json
import anthropic

SYSTEM_PROMPT = """You generate Being a Reader reading comprehension lesson content for a Year 4 class (ages 8–9) in a UK primary school.

You will receive: topic, key question, week reference, and day+date for each of 3 lessons.

Return ONLY valid JSON — no preamble, no markdown fences.

JSON structure:
{
  "lessons": [
    {
      "number": 1,
      "type": "Vocabulary",
      "day": "Tuesday",
      "date": "12/05/2026",
      "vocab": [
        {"word": "...", "definition": "..."},
        ... (5 items)
      ],
      "focus_word": "...",
      "extract_standard": "...",
      "extract_supported": "...",
      "questions_standard": [
        {"number": 1, "question": "...", "answer": "..."},
        ... (7 items)
      ],
      "questions_supported": [
        {"number": 1, "question": "...", "answer": "..."},
        ... (5 items, genuinely simpler not just fewer)
      ],
      "we_do_questions": [
        {"question": "...", "answer": "..."},
        {"question": "...", "answer": "..."}
      ]
    },
    {
      "number": 2,
      "type": "Retrieval",
      ...same structure...
    },
    {
      "number": 3,
      "type": "Inference",
      ...same structure...
    }
  ]
}

CONTENT RULES:

EXTRACTS:
- Write ONE extract per lesson — a different aspect of the topic each time
- Standard extract: 200–250 words, a single flowing paragraph in plain prose
- Supported extract: 130–150 words, simpler vocabulary and shorter sentences, same topic angle as standard
- Both extracts MUST be entirely original — not copied from any real source
- Embed the lesson's 5 vocabulary words naturally in the standard extract
- Lesson 1 (Vocabulary): focus on defining and explaining key concepts
- Lesson 2 (Retrieval): focus on facts, examples, and sequences that can be found in the text
- Lesson 3 (Inference): focus on cause, effect, author viewpoint, and implication

VOCABULARY (Lesson 1 only — same 5 words appear in all 3 lessons' vocab table):
- 5 Tier 2 words embedded in the Lesson 1 extract
- Definitions: one clear, child-friendly sentence. No jargon.
- Focus word: the most commonly encountered of the 5 words — this is the one pupils practise writing
- Lessons 2 and 3 also need vocab fields — choose 5 NEW Tier 2 words relevant to those extracts

QUESTIONS:
- Standard: 7 questions, Q1 easiest → Q7 hardest
- Supported: 5 questions, genuinely simpler (not Q1–Q5 of standard — rephrase/simplify them)
- Use at least 3 different question types across the 7: multiple-choice, fill-in-the-blank, short answer, true/false, ordering, inference, vocabulary-in-context
- Answers: complete sentences, appropriate for Y4
- We-do questions: 2 questions for class modelling (similar style to Q1/Q2 but worded differently, with full model answers)

LANGUAGE AND STYLE:
- British English throughout
- No em dashes. No Oxford comma. Active voice.
- No "moreover", "pivotal", "nuanced", "delves", "fosters", "underscores", "tapestry", "embark", "elevate"
- Extracts read as natural, well-written informational prose — not AI-generated lists
- Y4-appropriate: answerable by an 8–9 year old in 1–3 sentences
- Never use "pupils" — questions address pupils directly (e.g. "What does the word X mean...")
"""


def generate_lesson_content(
    topic: str,
    key_question: str,
    week_ref: str,
    lesson_days: list[dict]   # [{'day': 'Tuesday', 'date': '12/05'}, ...]
) -> dict:
    """
    Call Claude API and return parsed lesson content JSON.
    lesson_days: list of 3 dicts, one per lesson (Vocabulary, Retrieval, Inference).
    """
    client = anthropic.Anthropic()

    user_prompt = f"""Generate Being a Reader lesson content for the following week.

Week reference: {week_ref}
Topic / text: {topic}
Key question: {key_question}

Lesson days:
- Lesson 1 (Vocabulary):  {lesson_days[0]['day']}, {lesson_days[0]['date']}
- Lesson 2 (Retrieval):   {lesson_days[1]['day']}, {lesson_days[1]['date']}
- Lesson 3 (Inference):   {lesson_days[2]['day']}, {lesson_days[2]['date']}

Return the complete JSON now."""

    message = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_prompt}]
    )

    raw = message.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = raw.removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    return json.loads(raw)
