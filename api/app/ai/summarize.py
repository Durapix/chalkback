from app.ai.claude import structured_call
from app.ai.schemas import LessonSummary
from app.config import get_settings
from app.flowchart import Chart, analyze
from app.models import Lesson
from app.scene import Scene

SYSTEM = """You are a tutor's assistant. From the contents of the whiteboards used in one \
tutoring lesson, write a concise, accurate lesson summary for the student.

Only include what is actually on the boards or in the tutor's notes; never invent topics \
or exercises. Keep formulas in LaTeX. Write every field in the requested language, in a \
friendly, encouraging tone suitable for a school student.

Many boards are flowcharts, given to you as algorithms (START, INPUT, OUTPUT, IF, REPEAT, \
CALLS, UNIT, "Boxed together"). Read them the way a programmer reads code:
- Follow the steps in order and work out what each algorithm computes. Trace it with small \
numbers if that helps (for example A = 2, B = 3), and state the result plainly: \
"adds A and B by counting up from A one step at a time, B times", not a list of its boxes.
- These algorithms are simple teaching examples. Prefer the simplest explanation that fits \
all the steps; do not over-interpret.
- Shapes boxed together, or joined into a UNIT, are one whole: a function, a block or one \
recursive call. Name what the whole does. A CALLS into a box that returns is a call; nested \
calls of the same step with smaller numbers are recursion.
- When several algorithms on a board build on each other (for example each one uses the \
previous one as its step), say so: that progression is usually the point of the lesson.
- Faded parts and notes that are not connected to a chart (task lists, legends such as \
"Нађи ми десну цифру = broj%10") are context that explains the vocabulary.
- An unfinished chart (arrows that stop, unanswered "?????") is an open question from the \
lesson; mention it as something to think about, not as a mistake.
- An "Entity-relationship diagram" uses the same symbols but is not an algorithm: its \
rectangles are entities (things stored in a database) and its diamonds are relationships \
between them. Explain what the data model says, and how example tables of keys fit it.
- "(red)" and "(green)" after table cells mark rows that were ruled out or kept, usually \
step by step during the lesson (for example, which rows a query's condition keeps).

Be honest when a board says little. Boards were used live, and parts of the explanation \
happened by moving things around (for example, moving arrows over boxes) and are not visible \
afterwards. If a board is very simple, fragmentary or ambiguous, say plainly that there is \
not much to recap from it, describe only what is actually there, and note that it was \
probably one part of a larger example. Never invent a purpose to fill the space; a short \
recap is better than a confident wrong one."""

# Languages written in more than one script: the script recaps always use.
SCRIPTS = {
    "serbian": "Serbian, written only in Cyrillic script (ћирилица), even where the boards "
    "use Latin script. Keep code, variable names, SQL, formulas and quoted labels exactly "
    "as written on the board.",
}


def language_instruction(language: str) -> str:
    return SCRIPTS.get(language.strip().lower(), language)


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
                f"Write the summary in: {language_instruction(language)}",
            }
        ],
        output=LessonSummary,
        effort=get_settings().summary_effort,
    )


def mock_summary(lesson: Lesson, student_name: str) -> LessonSummary:
    """Deterministic summary built from the boards' own content (no AI).

    Flowcharts are described by their structure (inputs, loops, decisions, calls, output);
    what an algorithm is *for* needs the real model.
    """
    scenes = [b.scene for b in lesson.boards if b.scene]
    charts = [c for s in scenes for c in analyze(Scene.model_validate(s))]
    if charts:
        return _algorithm_summary(lesson, student_name, charts)
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


def _algorithm_summary(lesson: Lesson, student_name: str, charts: list[Chart]) -> LessonSummary:
    named = [c.title for c in charts if c.title]
    topics = named or [lesson.title]
    first_with_input = next((c for c in charts if c.inputs), None)
    loops = sum(len(c.loops) for c in charts)
    return LessonSummary(
        headline=f"{lesson.title}: {len(charts)} algorithm(s) as flowcharts",
        topics=topics,
        key_points=[c.describe() for c in charts[:4]],
        formulas=[],
        exercises=[f"Followed the algorithm “{t}” step by step" for t in named[:3]]
        or ["Followed the flowcharts step by step"],
        recap_message=(
            f"Hi {student_name}! Last time we read {len(charts)} algorithm(s) drawn as "
            "flowcharts"
            + (f" ({', '.join(named[:3])})" if named else "")
            + (", with loops that repeat steps until a condition changes" if loops else "")
            + ". Try following each one with small numbers and say what it computes."
        ),
        review_suggestions=[
            f"Trace “{first_with_input.title or 'the first algorithm'}” by hand with small "
            f"inputs for {', '.join(first_with_input.inputs)}."
            if first_with_input
            else "Trace each flowchart by hand from START to END."
        ],
    )
