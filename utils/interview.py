from utils.llm import interview_reply, interview_feedback
from utils.memory import (
    get_interview_session, update_interview_transcript, save_interview_feedback
)


def start_interview(session_id, subject):
    reply = interview_reply(subject, [])
    transcript = [{"role": "interviewer", "content": reply}]
    update_interview_transcript(session_id, transcript)
    return reply


def continue_interview(session_id, student_message):
    session = get_interview_session(session_id)
    if not session:
        return None

    transcript = session["transcript"]
    transcript.append({"role": "student", "content": student_message})

    reply = interview_reply(session["subject"], transcript)
    transcript.append({"role": "interviewer", "content": reply})

    update_interview_transcript(session_id, transcript)
    return reply


def end_interview(session_id):
    session = get_interview_session(session_id)
    if not session:
        return None

    feedback = interview_feedback(session["subject"], session["transcript"])
    save_interview_feedback(session_id, feedback)
    return feedback
