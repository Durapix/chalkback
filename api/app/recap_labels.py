"""Section titles around a recap, in the language the recap is written in.

The recap itself is written by the model; these are the fixed words we put around it
(in reminders, and mirrored in web/src/recapLabels.ts for the lesson page).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecapLabels:
    key_points: str
    formulas: str
    exercises: str
    before_next_lesson: str
    open_board: str
    subject: str  # e-mail subject, "{headline}" is filled in
    fallback: str  # when there is no recap message, "{title}" is filled in


ENGLISH = RecapLabels(
    key_points="Key points",
    formulas="Formulas",
    exercises="Exercises",
    before_next_lesson="Before next lesson",
    open_board="Open the board",
    subject="Recap: {headline}",
    fallback="Last time we covered: {title}.",
)

# Serbian recaps are written in Cyrillic (see app.ai.summarize.SCRIPTS).
SERBIAN = RecapLabels(
    key_points="Најважније",
    formulas="Формуле",
    exercises="Вежбе",
    before_next_lesson="Пре следећег часа",
    open_board="Отвори таблу",
    subject="Подсетник: {headline}",
    fallback="Прошли пут смо радили: {title}.",
)

LABELS = {"english": ENGLISH, "serbian": SERBIAN, "srpski": SERBIAN, "српски": SERBIAN}


def recap_labels(language: str | None) -> RecapLabels:
    return LABELS.get((language or "").strip().lower(), ENGLISH)
