"""Reminder delivery: Telegram bot messages and email via Resend."""

import asyncio
import html
import logging
from datetime import datetime, timedelta

import httpx
import resend
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import JobStatus, Lesson, Reminder, User, utcnow
from app.recap_labels import RecapLabels, recap_labels

log = logging.getLogger(__name__)


class DeliveryError(RuntimeError):
    pass


def labels_for(student: User, lesson: Lesson) -> RecapLabels:
    """Labels in the language the recap was written in (older recaps: the student's)."""
    return recap_labels((lesson.summary or {}).get("language") or student.language)


def render_text(student: User, lesson: Lesson) -> str:
    s, t = lesson.summary or {}, labels_for(student, lesson)
    lines = [s.get("recap_message", t.fallback.format(title=lesson.title)), ""]
    if s.get("key_points"):
        lines.append(f"{t.key_points}:")
        lines += [f"• {p}" for p in s["key_points"]]
    if s.get("review_suggestions"):
        lines += ["", f"{t.before_next_lesson}:"]
        lines += [f"• {p}" for p in s["review_suggestions"]]
    lines += ["", f"{t.open_board}: {get_settings().app_base_url}/lessons/{lesson.id}"]
    return "\n".join(lines)


def render_html(student: User, lesson: Lesson) -> str:
    s, t = lesson.summary or {}, labels_for(student, lesson)
    e = html.escape

    def items(key: str) -> str:
        return "".join(f"<li>{e(x)}</li>" for x in s.get(key, []))

    url = f"{get_settings().app_base_url}/lessons/{lesson.id}"
    return f"""<div style="font-family:system-ui,sans-serif;max-width:560px;margin:auto;color:#1c1b22">
<h2 style="margin:0 0 12px">{e(s.get("headline", lesson.title))}</h2>
<p style="font-size:16px;line-height:1.5">{e(s.get("recap_message", ""))}</p>
<h3>{e(t.key_points)}</h3><ul>{items("key_points")}</ul>
<h3>{e(t.before_next_lesson)}</h3><ul>{items("review_suggestions")}</ul>
<p><a href="{e(url)}" style="background:#5b4cff;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">{e(t.open_board)}</a></p>
</div>"""


async def send_telegram(chat_id: str, text: str) -> None:
    token = get_settings().telegram_bot_token
    if not token:
        raise DeliveryError("TELEGRAM_BOT_TOKEN is not configured")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        )
    if r.status_code != 200:
        raise DeliveryError(f"Telegram responded {r.status_code}: {r.text[:200]}")


async def send_email(to: str, subject: str, text: str, html_body: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise DeliveryError("RESEND_API_KEY is not configured")
    resend.api_key = settings.resend_api_key
    params: resend.Emails.SendParams = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "text": text,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
    except Exception as exc:
        raise DeliveryError(f"Resend failed: {exc}") from exc


def channels_for(student: User) -> list[str]:
    channels = []
    if student.remind_by_telegram and student.telegram_chat_id:
        channels.append("telegram")
    if student.remind_by_email:
        channels.append("email")
    return channels


async def send_reminder(
    db: Session, student: User, lesson: Lesson, for_session: datetime | None = None
) -> list[Reminder]:
    """Send the recap of `lesson` to `student` on every enabled channel and log each attempt."""
    text = render_text(student, lesson)
    headline = (lesson.summary or {}).get("headline", lesson.title)
    subject = labels_for(student, lesson).subject.format(headline=headline)
    results = []
    for channel in channels_for(student):
        try:
            if channel == "telegram":
                await send_telegram(student.telegram_chat_id, text)
            else:
                await send_email(student.email, subject, text, render_html(student, lesson))
            status, detail = "sent", None
        except DeliveryError as exc:
            status, detail = "failed", str(exc)
            log.warning("Reminder to student %s via %s failed: %s", student.id, channel, exc)
        reminder = Reminder(
            student_id=student.id,
            lesson_id=lesson.id,
            channel=channel,
            for_session=for_session,
            status=status,
            detail=detail,
        )
        db.add(reminder)
        results.append(reminder)
    db.commit()
    return results


def latest_summarized_lesson(db: Session, student: User) -> Lesson | None:
    return db.scalars(
        select(Lesson)
        .where(Lesson.student_id == student.id, Lesson.summary_status == JobStatus.ready)
        .order_by(Lesson.taught_at.desc())
        .limit(1)
    ).first()


async def dispatch_due_reminders(db: Session) -> int:
    """Remind every student whose next lesson starts within the lead window. Idempotent."""
    now = utcnow()
    horizon = now + timedelta(hours=get_settings().reminder_lead_hours)
    students = db.scalars(
        select(User).where(
            User.next_lesson_at.is_not(None),
            User.next_lesson_at > now,
            User.next_lesson_at <= horizon,
        )
    ).all()
    sent = 0
    for student in students:
        lesson = latest_summarized_lesson(db, student)
        if lesson is None:
            continue
        already = db.scalars(
            select(Reminder.id).where(
                Reminder.student_id == student.id,
                Reminder.for_session == student.next_lesson_at,
            )
        ).first()
        if already:
            continue
        sent += len(await send_reminder(db, student, lesson, for_session=student.next_lesson_at))
    return sent
