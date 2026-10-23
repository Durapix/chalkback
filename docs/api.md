# API

All endpoints are under `/api` and, except login and registration, require
`Authorization: Bearer <token>`. FastAPI serves interactive docs at `/docs` and the OpenAPI schema
at `/openapi.json`.

## Auth

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/auth/login` | anyone | Email + password → JWT |
| POST | `/auth/register` | anyone | Create a teacher account (`ALLOW_REGISTRATION`) |
| GET | `/auth/me` | any user | Current user |

## Students

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/students` | teacher | The teacher's students |
| POST | `/students` | teacher | Create a student account |
| PATCH | `/students/{id}` | teacher | Update language, reminder channels, Telegram chat ID, next lesson |
| POST | `/students/{id}/telegram-link` | teacher | One-time `t.me/<bot>?start=<code>` link that connects the student's Telegram |
| POST | `/students/{id}/remind` | teacher | Send the latest recap now |
| GET | `/students/{id}/reminders` | teacher | Reminder log |
| GET | `/students/me` | student | The student's own settings (channels, connected devices) |
| POST | `/students/me/telegram-link` | student | Connect link for the student's own Telegram |

## Notifications (Web Push)

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/push/key` | any user | The server's public VAPID key (`applicationServerKey`) |
| POST | `/push/subscriptions` | student | Save this device's push subscription (browser push services only) |
| POST | `/push/unsubscribe` | owner | Forget a device by its endpoint |

## Lessons

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/lessons?student_id=` | teacher / student | Teacher: own lessons (optionally per student). Student: own lessons |
| POST | `/lessons` | teacher | Create a lesson |
| GET | `/lessons/{id}` | owner | Lesson with boards and summary |
| PATCH | `/lessons/{id}` | teacher | Edit title, notes, time |
| DELETE | `/lessons/{id}` | teacher | Delete lesson, boards and images |
| POST | `/lessons/{id}/boards` | teacher | Multipart `files`: PNG/JPEG/WebP/GIF or PDF (one board per page), max 25 MB each. Starts reconstruction |
| POST | `/lessons/{id}/summarize` | teacher | (Re)generate the recap |

## Boards

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/boards/{id}` | owner | Board with scene and saved tldraw snapshot |
| PUT | `/boards/{id}/snapshot` | owner | Save the tldraw snapshot (teachers and students) |
| POST | `/boards/{id}/reconstruct` | teacher | Re-run AI reconstruction |
| DELETE | `/boards/{id}` | teacher | Delete board and its image |

Board images are served at `/files/<random-token>.png`. The names are unguessable 192-bit
tokens, so the images can be shown in `<img>` tags and tldraw without auth headers.

## Statuses

Boards and summaries move through `pending → processing → ready | failed`. The web app polls
every 2 s while anything in the lesson is `pending` or `processing`.
