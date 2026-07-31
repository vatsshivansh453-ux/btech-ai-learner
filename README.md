# BTech AI Learner

An AI study companion for B.Tech students:

- **Deep Notes** — pick any subject/topic, AI writes original, exam-and-interview-grade notes (cached so repeats don't cost extra API calls)
- **PDF Chat** — upload your own notes/textbook PDF and ask it questions (same retrieval engine as PDF-LEARNER)
- **Quiz** — AI-generated multiple-choice quizzes, auto-scored, saved to your history
- **Mock Interview** — a short, multi-turn AI interview on a subject, ending in a feedback report
- **Dashboard** — strong/weak subjects, based on your quiz history

## Folder structure

```
btech-ai-learner/
  backend/
    main.py              — FastAPI app, all routes
    requirements.txt
    .env.example          — copy to .env and fill in
    utils/
      auth.py             — email/password + JWT (Bearer token, no OAuth)
      memory.py           — SQLite (users, chat, quiz, interview, notes cache)
      embedding.py        — fastembed (lightweight, no PyTorch)
      vector_store.py     — FAISS, scoped per-user search
      hybrid_search.py    — BM25 keyword search
      pdf_reader.py, text_splitter.py, rag.py  — PDF chat pipeline
      llm.py              — all Groq prompt calls, with graceful rate-limit handling
      subjects.py         — B.Tech subject/topic catalog (edit this for your syllabus)
      notes.py, quiz.py, interview.py, dashboard.py — feature logic
  frontend/
    index.html            — the entire frontend (vanilla JS, no build step)
```

## Running locally

**Backend:**
```powershell
cd backend
python -m venv venv
venv\Scripts\activate          # (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # (Mac/Linux: cp .env.example .env)
```
Edit `.env` and add your `GROQ_API_KEY` (get one free at console.groq.com) and a random `JWT_SECRET_KEY`.

```powershell
uvicorn main:app --reload --port 8000
```

**Frontend:**
Just open `frontend/index.html` directly in a browser, or serve it with any static server. The `API_BASE` constant at the top of the `<script>` tag is already set to `http://localhost:8000` for local use.

## Deploying

Same playbook as PDF-LEARNER:
- **Backend** → Render (free Web Service), build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set `GROQ_API_KEY`, `JWT_SECRET_KEY`, and `FRONTEND_URL` as environment variables.
- **Frontend** → Vercel or Netlify Drop. Before deploying, update `API_BASE` in `index.html` to your deployed backend URL.

Because auth here uses a Bearer token (not a cookie), you **won't** need the SameSite/`--proxy-headers`/cookie dance from PDF-LEARNER — cross-domain auth just works once CORS `FRONTEND_URL` is set correctly.

## Notes on the Groq free tier

The free tier caps you at 100k tokens/day (rolling 24-hour window, not a fixed midnight reset). Notes are cached per subject/topic after first generation specifically to conserve this — quizzes and interviews are not cached since they should vary each time.
