from app.ai.claude import structured_call
from app.ai.scene import LessonSummary
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
    titles = [b.scene.get("title", "") for b in lesson.boards if b.scene] or [lesson.title]
    return LessonSummary(
        headline=f"{lesson.title}: {', '.join(titles)}",
        topics=titles,
        key_points=[
            "A quadratic equation has the form ax^2 + bx + c = 0 with a ≠ 0.",
            "The discriminant D = b^2 - 4ac tells you how many real roots there are.",
        ],
        formulas=["D = b^2 - 4ac", "x_{1,2} = \\frac{-b \\pm \\sqrt{D}}{2a}"],
        exercises=["Solved x^2 - 5x + 6 = 0 using the discriminant"],
        recap_message=(
            f"Hi {student_name}! Last time we worked on {lesson.title.lower()}. "
            "Remember: compute the discriminant first, then use the formula for the roots. "
            "You did great!"
        ),
        review_suggestions=["Solve two equations with D > 0 and one with D < 0."],
    )
