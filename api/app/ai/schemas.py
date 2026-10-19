"""Structured output schemas for text-only AI calls."""

from pydantic import BaseModel, Field


class LessonSummary(BaseModel):
    headline: str = Field(description="One-line summary of the lesson")
    topics: list[str]
    key_points: list[str] = Field(description="The most important ideas, one sentence each")
    formulas: list[str] = Field(description="Key formulas in LaTeX, no $ delimiters")
    exercises: list[str] = Field(description="Exercises that were solved, briefly")
    recap_message: str = Field(
        description="A warm 2-4 sentence message to the student reminding them what was "
        "covered, written directly to them"
    )
    review_suggestions: list[str] = Field(description="What to practise before next lesson")
