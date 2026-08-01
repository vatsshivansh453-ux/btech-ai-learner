from urllib.parse import quote
from utils.memory import get_quiz_attempts
from utils.subjects import list_subjects


def _youtube_search_url(query: str) -> str:
    """A plain YouTube search link (no API key needed) for a weak topic."""
    return f"https://www.youtube.com/results?search_query={quote(query)}"


def get_dashboard(user_id):
    """
    Aggregates quiz history into a per-subject strength/weakness view,
    plus overall stats and a "focus on these next" suggestion list.
    """
    attempts = get_quiz_attempts(user_id)

    per_subject = {}
    for a in attempts:
        subj = a["subject"]
        per_subject.setdefault(subj, {"score": 0, "total": 0, "attempts": 0})
        per_subject[subj]["score"] += a["score"]
        per_subject[subj]["total"] += a["total"]
        per_subject[subj]["attempts"] += 1

    subjects_summary = []
    weak_subjects = []

    for subject in list_subjects():
        data = per_subject.get(subject)
        if not data or data["total"] == 0:
            subjects_summary.append({
                "subject": subject, "percentage": None, "attempts": 0, "status": "not_started"
            })
            continue

        pct = round((data["score"] / data["total"]) * 100, 1)
        status = "strong" if pct >= 75 else ("weak" if pct < 50 else "moderate")

        if status == "weak":
            weak_subjects.append(subject)

        youtube_url = (
            _youtube_search_url(f"{subject} full course tutorial for beginners")
            if status in ("weak", "moderate")
            else None
        )

        subjects_summary.append({
            "subject": subject,
            "percentage": pct,
            "attempts": data["attempts"],
            "status": status,
            "youtube_url": youtube_url,
        })

    total_attempts = len(attempts)
    overall_pct = None
    if attempts:
        total_score = sum(a["score"] for a in attempts)
        total_qs = sum(a["total"] for a in attempts)
        overall_pct = round((total_score / total_qs) * 100, 1) if total_qs else None

    recommended_focus = [
        {"subject": s, "youtube_url": _youtube_search_url(f"{s} full course tutorial for beginners")}
        for s in weak_subjects
    ]

    return {
        "subjects": subjects_summary,
        "total_quiz_attempts": total_attempts,
        "overall_percentage": overall_pct,
        "recommended_focus": recommended_focus,
        "recent_attempts": attempts[:10],
    }