from app.ai.claude import structured_call
from app.ai.schemas import LessonSummary
from app.config import get_settings
from app.models import Lesson

SYSTEM = """You are a tutor's assistant. From the contents of the whiteboards used in one \
tutoring lesson, write a concise, accurate lesson summary for the student.

Only include what is actually on the boards or in the tutor's notes; never invent topics \
or exercises. Keep formulas in LaTeX. Write every field in the requested language, in a \
friendly, encouraging tone suitable for a school student."""


def lesson_material(lesson: Lesson) -> str:
    parts = [f"Lesson: {lesson.title}", f"Subject: {lesson.subject}"]
    if lesson.notes.strip():
        parts.append(f"Tutor's notes:\n{lesson.notes.strip()}")
    for i, board in enumerate(lesson.boards, start=1):
        if board.scene:
            parts.append(f"--- Board {i}: {board.scene.get('title', '')} ---")
            parts.append(board.scene.get("transcript", ""))
    return "\n\n".join(parts)


async def summarize(lesson: Lesson, student_name: str, language: str) -> LessonSummary:
    material = lesson_material(lesson)
    if not get_settings().ai_enabled:
        return mock_summary(lesson, student_name)
    return await structured_call(
        system=SYSTEM,
        content=[
            {
                "type": "text",
                "text": f"<material>\n{material}\n</material>\n\n"
                f"Student's first name: {student_name}\n"
                f"Write the summary in: {language}",
            }
        ],
        output=LessonSummary,
        effort=get_settings().summary_effort,
    )


def mock_summary(lesson: Lesson, student_name: str) -> LessonSummary:
    """Deterministic summary built from the boards' own content (no AI)."""
    scenes = [b.scene for b in lesson.boards if b.scene]
    titles = [s.get("title", "") for s in scenes if s.get("title")] or [lesson.title]
    lines = [
        line.strip()
        for s in scenes
        for line in s.get("transcript", "").splitlines()
        if len(line.strip()) > 3 and line.strip() != "Connections:"
    ]
    formulas = [
        el["latex"] for s in scenes for el in s.get("elements", []) if el.get("kind") == "math"
    ]
    return LessonSummary(
        headline=f"{lesson.title}: {', '.join(titles)}",
        topics=titles,
        key_points=lines[:3] or [lesson.notes or lesson.title],
        formulas=formulas[:3],
        exercises=[f"Worked through the board “{t}”" for t in titles[:3]],
        recap_message=(
            f"Hi {student_name}! Last time we worked on {lesson.title}. "
            "Open the boards again and try to explain each step in your own words."
        ),
        review_suggestions=[f"Redo the example from “{titles[0]}” on your own."],
    )
