# Reminders

Students get the recap of their **latest summarized lesson** before their next lesson.

## How scheduling works

- Each student has an optional `next_lesson_at`, set by the teacher on the dashboard.
- Every `REMINDER_INTERVAL_MINUTES` (default 15), the API checks for students whose next lesson
  starts within `REMINDER_LEAD_HOURS` (default 24).
- Each enabled channel is tried once and logged in `reminders`. The `(student, next_lesson_at)`
  pair is the dedup key, so restarts and repeated ticks never send twice.
- Teachers can also press **Send last recap now** on a student card
  (`POST /api/students/{id}/remind`).

## Telegram

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token into
   `TELEGRAM_BOT_TOKEN`.
2. The student opens the bot and presses **Start**.
3. Find the student's chat ID. For example, open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` after they message the bot and read
   `message.chat.id`.
4. Enter the chat ID on the student's card and enable **Telegram reminders**.

!!! note
    A `/start <code>` deep-link that links students automatically is on the [roadmap](roadmap.md).

## Email (Resend)

1. Create an API key at [resend.com](https://resend.com) and set `RESEND_API_KEY`.
2. Verify your sending domain in Resend and set `EMAIL_FROM`, e.g.
   `Chalkback <recaps@your-domain.com>`.
3. Email reminders are on by default for every student.

Emails include an HTML version (headline, recap, key points, practice, "Open the board" button)
and a plain-text fallback. Delivery code is in `api/app/notify.py`.
