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

1. Create a bot with [@BotFather](https://t.me/BotFather) and put its token in
   `TELEGRAM_BOT_TOKEN`. Disable `/setjoingroups`; the bot only talks in private chats.
2. Connect a student with a **one-time link**. Either:
    - the teacher presses **Telegram link** on the student's card and sends the copied link to
      the student, or
    - the student presses **Connect Telegram** on their own dashboard.
3. The student opens the link (`https://t.me/<bot>?start=<code>`) and presses **Start**. The bot
   replies "Повезано…", and Telegram reminders are switched on for that student.

Links work once and expire after `TELEGRAM_LINK_DAYS` (default 14). Making a new link cancels
the previous one. A student can send `/stop` to the bot at any time to disconnect.

The API listens for these messages with long polling (`getUpdates`). Nothing is configured on
Telegram's side and no webhook endpoint is exposed. Set `TELEGRAM_POLLING=false` to turn
listening off. A chat ID can still be entered by hand on the student's card.

## Email (Resend)

1. Create an API key at [resend.com](https://resend.com) and set `RESEND_API_KEY`.
2. Verify your sending domain in Resend and set `EMAIL_FROM`, e.g.
   `Chalkback <recaps@your-domain.com>`.
3. Email reminders are on by default for every student.

Emails include an HTML version (headline, recap, key points, practice, "Open the board" button)
and a plain-text fallback. Delivery code is in `api/app/notify.py`.
