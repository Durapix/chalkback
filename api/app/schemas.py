from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import JobStatus, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(LoginIn):
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(ORM):
    id: int
    email: str
    name: str
    role: Role
    language: str


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    language: str = "Serbian"
    telegram_chat_id: str | None = None
    remind_by_email: bool = True
    remind_by_telegram: bool = False
    next_lesson_at: datetime | None = None


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    language: str | None = None
    telegram_chat_id: str | None = None
    remind_by_email: bool | None = None
    remind_by_telegram: bool | None = None
    remind_by_push: bool | None = None
    next_lesson_at: datetime | None = None


class StudentOut(UserOut):
    language: str
    telegram_chat_id: str | None
    remind_by_email: bool
    remind_by_telegram: bool
    remind_by_push: bool
    push_devices: int
    next_lesson_at: datetime | None


class TelegramLinkOut(BaseModel):
    url: str
    expires_at: datetime


class LessonIn(BaseModel):
    student_id: int
    title: str = Field(min_length=1, max_length=200)
    subject: str = "Mathematics"
    taught_at: datetime | None = None
    notes: str = ""


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = None
    taught_at: datetime | None = None
    notes: str | None = None


class BoardBrief(ORM):
    id: int
    position: int
    status: JobStatus
    error: str | None
    image_url: str | None
    width: int
    height: int
    title: str | None


class BoardOut(BoardBrief):
    lesson_id: int
    scene: dict | None
    snapshot: dict | None
    updated_at: datetime


class LessonOut(ORM):
    id: int
    title: str
    subject: str
    taught_at: datetime
    notes: str
    student: UserOut
    summary: dict | None
    summary_status: JobStatus | None
    summary_error: str | None
    boards: list[BoardBrief]


class SnapshotIn(BaseModel):
    snapshot: dict


class ReminderOut(ORM):
    id: int
    lesson_id: int
    channel: str
    status: str
    detail: str | None
    sent_at: datetime


TokenOut.model_rebuild()
