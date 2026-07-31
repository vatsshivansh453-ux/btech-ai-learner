"""
Shared Groq client + prompt functions for every AI feature:
notes generation, PDF Q&A, quiz generation, and mock interviews.

Every call site catches rate-limit/API errors gracefully and returns a
readable message instead of crashing — this was a real issue in
PDF-LEARNER's first version, fixed here from the start.
"""

import os
import json
import random
from groq import Groq, RateLimitError, APIError
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL_NAME = "llama-3.3-70b-versatile"

RATE_LIMIT_MESSAGE = (
    "I've hit the AI provider's rate limit for the moment (the free tier "
    "has a daily usage cap). Please try again in a little while."
)
GENERIC_ERROR_MESSAGE = "Something went wrong talking to the AI provider just now. Please try again."


def _friendly_error(exc) -> str:
    return RATE_LIMIT_MESSAGE if isinstance(exc, RateLimitError) else GENERIC_ERROR_MESSAGE


def _chat(messages, temperature=0.2, max_tokens=3000, stream=False):
    """Thin wrapper around the Groq call, used by every feature below."""
    return client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )


##############################################################
# DEEP NOTES GENERATION
##############################################################

NOTES_SYSTEM_PROMPT = """
You are an expert B.Tech professor writing extremely deep, exam-and-interview
-grade study notes for a serious student — the kind of notes that could
replace an entire textbook chapter plus a paid interview-prep course on this
exact topic. Write ENTIRELY IN YOUR OWN WORDS — do not reproduce text from
any specific website or textbook; this must be original writing.

Structure the notes with these Markdown sections, in this order. Every
section that asks for examples needs AT LEAST 10 distinct, concrete
examples — not 2 or 3 padded out, genuinely 10+ varied ones. Do not skip
depth to save space; go long.

## 1. Quick Definition
One crisp, precise definition a student can memorize in 10 seconds.

## 2. Intuition (Plain-English)
Explain the underlying idea the way you'd explain it to a smart friend with
no jargon first, using 2-3 real-life analogies.

## 3. Deep Dive — How It Works
Full technical depth, step by step, covering every important sub-concept,
internal mechanism, or variant. This is the core section — be thorough.

## 4. Worked Examples (minimum 10)
Provide AT LEAST 10 distinct worked examples that build understanding —
mix trivial, medium, and tricky/edge cases. For CS/programming topics,
include real, correct, runnable code (C/C++/Java/Python as fits the
subject) for several of them, with actual sample input/output. For
theory/math topics, show actual numbers/steps worked out fully, not just
described.

## 5. Real-World Applications (minimum 10)
List AT LEAST 10 concrete real-world scenarios, industries, products, or
systems where this concept is actually used, each with one sentence on
*how* it's used there — not just a bare list of nouns.

## 6. Comparison Table
If the topic naturally involves comparing approaches, algorithms, data
structures, protocols, or paradigms, include a Markdown table comparing
them across relevant dimensions (time/space complexity, pros/cons,
use-cases). If truly not applicable, briefly say so and skip.

## 7. Complexity / Performance Analysis
If relevant (DSA, algorithms, systems topics): best/average/worst case
time and space complexity, with a one-line justification for each.

## 8. Common Mistakes & Misconceptions (minimum 10)
AT LEAST 10 specific mistakes students actually make on this topic —
conceptual confusions, common bugs, wrong assumptions — each with the
correction.

## 9. Interview & Exam Questions (minimum 10)
AT LEAST 10 questions actually asked on this exact topic in interviews or
exams, each followed immediately by a concise, correct, model answer.
Vary difficulty from fundamental to advanced/tricky.

## 10. Key Takeaways
A tight bullet summary — the 8-10 things a student MUST remember before
walking into an exam or interview on this topic.

Use Markdown headings exactly as numbered above. Do not pad with fluff —
every sentence should teach something concrete. Prefer being long and
genuinely deep over being short.
"""


def generate_notes(subject: str, topic: str) -> str:
    try:
        response = _chat(
            messages=[
                {"role": "system", "content": NOTES_SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Subject: {subject}\nTopic: {topic}\n\n"
                    "Write the deep notes now, following every numbered section "
                    "and every 'minimum 10' requirement exactly. Do not shorten "
                    "or summarize sections to save space."
                )},
            ],
            temperature=0.3,
            max_tokens=7500,
        )
    except (RateLimitError, APIError) as e:
        return _friendly_error(e)

    return response.choices[0].message.content


##############################################################
# PDF Q&A (same behavior as PDF-LEARNER)
##############################################################

PDF_SYSTEM_PROMPT = """
You are an intelligent study assistant helping a student work through an
uploaded PDF, across a real ongoing conversation — you have full memory of
everything said earlier in this chat (see Conversation History below).

How to answer:
- Ground your answer in the PDF Context first — it's your primary source
  of truth for this document.
- Use the Conversation History to understand follow-up questions: resolve
  pronouns ("it", "its", "that", "this one"), and understand when the
  student is asking you to go deeper on something you or they already
  mentioned (e.g. "explain its types", "give an example", "what about the
  disadvantages").
- IMPORTANT: if a follow-up question is a natural extension of something
  the PDF covers (e.g. the PDF defines "AI" and the student then asks "what
  are its types") but that specific detail isn't literally written in the
  PDF text, DO NOT just say "that's not in the PDF" and stop. Instead,
  answer it properly using your own general subject knowledge, and briefly
  flag that you're extending beyond the PDF, e.g. "The PDF doesn't spell
  this out directly, but building on what it says about AI, here's how
  it's generally classified: ...". Always leave the student with a real,
  usable answer.
- Only say something is fully outside scope if it's genuinely unrelated to
  the PDF's subject matter and the conversation so far — and even then,
  offer to answer it as general knowledge instead of just refusing.

Write like a normal chat reply: plain paragraphs by default. Only use
headings/lists if the answer genuinely needs structure. Use **bold**
sparingly for 1-2 key terms, not everywhere.
"""


def stream_pdf_answer(question, context, history=None):
    history = history or []
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history) or "(no earlier messages)"

    prompt = f"""Conversation History:
{history_text}

PDF Context:
{context}

Current Question:
{question}

Answer the Current Question, using the Conversation History to resolve any
pronouns/references in it and to keep continuity with what's already been
discussed.
"""

    try:
        stream = _chat(
            messages=[
                {"role": "system", "content": PDF_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=2000,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except (RateLimitError, APIError) as e:
        yield _friendly_error(e)


def rewrite_question(question, history):
    if not history:
        return question
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    try:
        response = _chat(
            messages=[{
                "role": "user",
                "content": f"Conversation:\n{history_text}\n\nCurrent Question:\n{question}\n\nRewrite this into a complete standalone question. Only return the rewritten question."
            }],
            temperature=0,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except (RateLimitError, APIError):
        return question


def generate_chat_title(question):
    try:
        response = _chat(
            messages=[
                {"role": "system", "content": "Generate a short chat title. Max 5 words. No punctuation, no quotes. Return only the title."},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_tokens=30,
        )
        return response.choices[0].message.content.strip()
    except (RateLimitError, APIError):
        return "New Chat"


##############################################################
# QUIZ GENERATION
##############################################################

QUIZ_SYSTEM_PROMPT = """
You write multiple-choice quiz questions for B.Tech students. Respond with
ONLY valid JSON (no markdown fences, no commentary) in exactly this shape:

{
  "questions": [
    {
      "question": "string",
      "options": ["string", "string", "string", "string"],
      "correct_index": 0,
      "explanation": "one or two sentence explanation of the correct answer"
    }
  ]
}

Rules:
- Exactly 4 options per question, only one correct.
- Questions must test real understanding (concepts, application, reasoning),
  not trivial recall.
- Vary difficulty across the set: some fundamental, some tricky.
- Base questions only on the given subject/topic (and PDF context, if given).
- This is one of MANY quiz attempts a student will take on this same
  topic over time — it is critical that this set feels genuinely fresh
  and different from previous attempts, not a reshuffle of the same
  handful of "obvious" questions every topic tends to produce. Actively
  explore different angles, sub-concepts, and phrasings each time.
"""

# Rotated each generation so repeated requests for the same topic don't
# converge on the same "default" set of questions the model tends to
# produce at low temperature.
_QUIZ_ANGLES = [
    "core definitions and terminology",
    "step-by-step / how-it-works mechanics",
    "worked numerical or code-tracing problems",
    "comparing this topic against closely related concepts",
    "real-world application and use-case scenarios",
    "common bugs, pitfalls, and misconceptions",
    "edge cases and boundary conditions",
    "time/space complexity or performance implications",
    "short code-reading or debugging snippets",
    "cause-and-effect / what-happens-if scenarios",
]


def generate_quiz(subject, topic, num_questions=5, context=None, previous_questions=None):
    previous_questions = previous_questions or []

    angles = random.sample(_QUIZ_ANGLES, k=min(4, len(_QUIZ_ANGLES)))
    user_content = (
        f"Subject: {subject}\nTopic: {topic}\nNumber of questions: {num_questions}\n\n"
        f"For this attempt, lean the question mix toward these angles where they fit "
        f"naturally: {', '.join(angles)}."
    )
    if context:
        user_content += f"\n\nBase the questions on this material:\n{context}"

    if previous_questions:
        prev_list = "\n".join(f"- {q}" for q in previous_questions[:40])
        user_content += (
            "\n\nThe student has already seen these exact questions on this topic in "
            "earlier attempts. Do NOT reuse any of them, and do NOT just lightly "
            "reword them — write genuinely new questions covering different angles "
            f"or sub-concepts instead:\n{prev_list}"
        )

    try:
        response = _chat(
            messages=[
                {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.9,
            max_tokens=2500,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return data.get("questions", [])
    except (RateLimitError, APIError):
        return {"error": RATE_LIMIT_MESSAGE}
    except (json.JSONDecodeError, KeyError):
        return {"error": "Couldn't generate a valid quiz just now — please try again."}


##############################################################
# MOCK INTERVIEW
##############################################################

_INTERVIEW_OPENERS = [
    "a real-world scenario or system-design-flavored question",
    "a sharp conceptual definition question",
    "a 'walk me through how X works internally' question",
    "a short code-reading or debug-this question",
    "a compare-and-contrast question between two related concepts",
    "a practical 'how would you use this on the job' question",
]


def interview_system_prompt(subject):
    opener_style = random.choice(_INTERVIEW_OPENERS)
    return f"""
You are a friendly but rigorous technical interviewer conducting a mock
interview for a B.Tech student on the subject: {subject}.

Rules:
- Ask ONE question at a time, then wait for the student's answer.
- Start with a warm, brief greeting and your first question. For THIS
  session, open with {opener_style} — vary this every session so students
  who retake the interview never get the same predictable opening.
- After each answer, give brief (1-2 sentence) feedback on that specific
  answer, then ask the next question — increase difficulty gradually.
- Ask a mix of conceptual and practical/scenario questions, and actively
  avoid defaulting to the same "textbook standard" question order every
  time — mix up which sub-topics you probe and in what sequence.
- Keep each of your messages short and conversational, like a real
  interviewer talking, not an essay.
- After 6 questions total, say the interview is complete and tell the
  student to end the session for their full feedback report.
"""


def interview_reply(subject, history):
    messages = [{"role": "system", "content": interview_system_prompt(subject)}]
    for m in history:
        role = "assistant" if m["role"] == "interviewer" else "user"
        messages.append({"role": role, "content": m["content"]})

    try:
        response = _chat(messages=messages, temperature=0.75, max_tokens=400)
        return response.choices[0].message.content
    except (RateLimitError, APIError) as e:
        return _friendly_error(e)


def interview_feedback(subject, history):
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    try:
        response = _chat(
            messages=[
                {"role": "system", "content": (
                    f"You just finished mock-interviewing a student on {subject}. "
                    "Based on the transcript, write a short feedback report in Markdown: "
                    "a 'Strengths' section, a 'Areas to Improve' section, and an overall "
                    "readiness rating out of 10 with one sentence justifying it."
                )},
                {"role": "user", "content": transcript_text},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except (RateLimitError, APIError) as e:
        return _friendly_error(e)