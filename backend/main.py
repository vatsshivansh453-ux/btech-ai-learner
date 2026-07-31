"""
BTech-AI-Learner — main FastAPI app.

Features:
  /auth/*        — register / login (email+password, JWT bearer token)
  /notes/*       — AI-generated deep notes per subject/topic (cached)
  /pdf/*         — upload a PDF, chat with it (RAG, same engine as PDF-LEARNER)
  /quiz/*        — AI-generated quizzes, scored and saved per user
  /interview/*   — AI mock interview (multi-turn), with a final feedback report
  /dashboard     — strengths/weaknesses across subjects, from quiz history
"""

import os
import shutil
import uuid

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from utils.auth import hash_password, verify_password, create_access_token, get_current_user
from utils.memory import (
    create_user, get_user_by_email,
    create_session, get_sessions, get_session_owner, delete_session, get_chat_history,
)
from utils.subjects import list_subjects, list_topics
from utils.notes import get_notes
from utils.rag import stream_answer
from utils.vector_store import load_vector_store, save_vector_store, create_faiss_index, add_embeddings
from utils.embedding import create_embeddings
from utils.pdf_reader import extract_text_from_pdf
from utils.text_splitter import split_text_into_chunks
from utils.quiz import create_quiz, score_quiz
from utils.interview import start_interview, continue_interview, end_interview
from utils.memory import create_interview_session, get_interview_session
from utils.dashboard import get_dashboard

load_dotenv()

app = FastAPI(title="BTech-AI-Learner API")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://btech-ai-learner.vercel.app",
        "http://localhost:5173",
        "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory PDF store, backed by disk (same architecture as PDF-LEARNER)
faiss_index, pdf_chunks = load_vector_store()
os.makedirs("uploads", exist_ok=True)


@app.get("/")
def home():
    return {"project": "BTech-AI-Learner API", "status": "running"}


##############################################################
# AUTH
##############################################################

class RegisterBody(BaseModel):
    email: str
    password: str
    name: str


class LoginBody(BaseModel):
    email: str
    password: str
    
class GoogleLoginBody(BaseModel):
    token: str


@app.post("/auth/register")
def register(body: RegisterBody):
    if get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user_id = create_user(body.email, hash_password(body.password), body.name)
    token = create_access_token(user_id)
    return {"token": token, "user": {"id": user_id, "email": body.email, "name": body.name}}


@app.post("/auth/login")
def login(body: LoginBody):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


##############################################################
# NOTES
##############################################################

@app.get("/notes/subjects")
def get_subjects():
    return {"subjects": list_subjects()}


@app.get("/notes/{subject}/topics")
def get_topics(subject: str):
    topics = list_topics(subject)
    if not topics:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return {"subject": subject, "topics": topics}


@app.get("/notes/{subject}/{topic}")
def notes_for_topic(subject: str, topic: str, user=Depends(get_current_user)):
    content = get_notes(subject, topic)
    return {"subject": subject, "topic": topic, "content": content}


##############################################################
# PDF UPLOAD + CHAT
##############################################################

@app.post("/pdf/upload")
async def upload_pdf(file: UploadFile = File(...), user=Depends(get_current_user)):
    global faiss_index, pdf_chunks

    existing_names = {c["file_name"] for c in pdf_chunks if c.get("user_id") == user["id"]}
    if file.filename in existing_names:
        return {"message": f'"{file.filename}" is already uploaded.'}

    file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    pages = extract_text_from_pdf(file_path)
    new_chunks = split_text_into_chunks(pages)

    if not new_chunks:
        raise HTTPException(status_code=400, detail="Couldn't extract any text from that PDF.")

    texts = [c["text"] for c in new_chunks]
    embeddings = create_embeddings(texts)

    start_index = len(pdf_chunks)
    for i, chunk in enumerate(new_chunks):
        pdf_chunks.append({
            "file_name": file.filename,
            "page_number": chunk["page_number"],
            "chunk_number": start_index + i,
            "text": chunk["text"],
            "user_id": user["id"],
        })

    if faiss_index is None:
        faiss_index = create_faiss_index(embeddings)
    else:
        add_embeddings(faiss_index, embeddings)

    save_vector_store(faiss_index, pdf_chunks)

    return {"message": f'"{file.filename}" uploaded — {len(new_chunks)} chunks indexed.'}


@app.get("/pdf/documents")
def list_documents(user=Depends(get_current_user)):
    names = sorted({c["file_name"] for c in pdf_chunks if c.get("user_id") == user["id"]})
    return {"documents": names}


@app.post("/pdf/sessions")
def new_session(user=Depends(get_current_user)):
    return {"session_id": create_session(user["id"])}


@app.get("/pdf/sessions")
def sessions(user=Depends(get_current_user)):
    return {"sessions": get_sessions(user["id"])}


@app.get("/pdf/sessions/{session_id}/history")
def session_history(session_id: str, user=Depends(get_current_user)):
    if get_session_owner(session_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session.")
    return {"history": get_chat_history(session_id)}


@app.delete("/pdf/sessions/{session_id}")
def remove_session(session_id: str, user=Depends(get_current_user)):
    if get_session_owner(session_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session.")
    delete_session(session_id)
    return {"message": "deleted"}


class AskBody(BaseModel):
    question: str
    session_id: str


@app.post("/pdf/ask-stream")
def ask_stream(body: AskBody, user=Depends(get_current_user)):
    if get_session_owner(body.session_id) != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session.")

    history = get_chat_history(body.session_id)

    return StreamingResponse(
        stream_answer(body.question, faiss_index, pdf_chunks, body.session_id, history, user["id"]),
        media_type="application/x-ndjson",
    )


##############################################################
# QUIZ
##############################################################

class QuizRequestBody(BaseModel):
    subject: str
    topic: str
    num_questions: int = 5


@app.post("/quiz/generate")
def quiz_generate(body: QuizRequestBody, user=Depends(get_current_user)):
    questions = create_quiz(user["id"], body.subject, body.topic, body.num_questions)
    if isinstance(questions, dict) and "error" in questions:
        raise HTTPException(status_code=503, detail=questions["error"])
    return {"questions": questions}


class QuizSubmitBody(BaseModel):
    subject: str
    topic: str
    questions: list
    answers: list[int | None]


@app.post("/quiz/submit")
def quiz_submit(body: QuizSubmitBody, user=Depends(get_current_user)):
    return score_quiz(user["id"], body.subject, body.topic, body.questions, body.answers)


##############################################################
# MOCK INTERVIEW
##############################################################

class InterviewStartBody(BaseModel):
    subject: str


@app.post("/interview/start")
def interview_start(body: InterviewStartBody, user=Depends(get_current_user)):
    session_id = create_interview_session(user["id"], body.subject)
    first_message = start_interview(session_id, body.subject)
    return {"session_id": session_id, "message": first_message}


class InterviewMessageBody(BaseModel):
    session_id: str
    message: str


@app.post("/interview/message")
def interview_message(body: InterviewMessageBody, user=Depends(get_current_user)):
    session = get_interview_session(body.session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your interview session.")

    reply = continue_interview(body.session_id, body.message)
    return {"message": reply}


class InterviewEndBody(BaseModel):
    session_id: str


@app.post("/interview/end")
def interview_end(body: InterviewEndBody, user=Depends(get_current_user)):
    session = get_interview_session(body.session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your interview session.")

    feedback = end_interview(body.session_id)
    return {"feedback": feedback}


##############################################################
# DASHBOARD
##############################################################

@app.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    return get_dashboard(user["id"])

@app.post("/auth/google")
def google_login(body: GoogleLoginBody):
    try:
        google_user = id_token.verify_oauth2_token(
            body.token,
            google_requests.Request(),
            "932026077017-7fa91hsl5oki13i416gou883ujv4tgas.apps.googleusercontent.com"
        )

        email = google_user["email"]
        name = google_user.get("name", "Google User")

        user = get_user_by_email(email)

        if not user:
            user_id = create_user(
                email,
                "GOOGLE_AUTH",
                name
            )

            user = {
                "id": user_id,
                "email": email,
                "name": name
            }

        token = create_access_token(user["id"])

        return {
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"]
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Google login failed: {str(e)}"
        )