"""Data contract for per-review analysis and the weekly report narrative."""

from __future__ import annotations

import re
from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

from reviewlens.sanitize import check_output

Sentiment = Literal["positive", "neutral", "negative"]
Category = Literal["food_quality", "delivery", "price", "staff", "packaging", "app"]
Urgency = Literal["low", "medium", "high"]
Language = Literal["English", "Tamil", "Tanglish", "Other"]

SENTIMENTS: tuple[str, ...] = get_args(Sentiment)
CATEGORIES: tuple[str, ...] = get_args(Category)
URGENCIES: tuple[str, ...] = get_args(Urgency)
LANGUAGES: tuple[str, ...] = get_args(Language)

NEEDS_REVIEW = "needs_review"

# Sentence end = terminal punctuation followed by whitespace and a capital letter.
# Abbreviations like "Rs. 50" or "9.10 pm" don't trigger it.
_SENTENCE_BREAK = re.compile(r"[.!?]\s+[A-Z]")
_SENTENCE_END = re.compile(r"[.!?]+(?=\s+[A-Z]|\s*$)")


class ReviewAnalysis(BaseModel):
    """Structured result for one review."""

    sentiment: Sentiment = Field(description="Overall customer sentiment.")
    category: Category = Field(description="The single aspect the review is mostly about.")
    urgency: Urgency = Field(description="How quickly the team must respond.")
    language: Language = Field(description="Language the review is written in.")
    summary: str = Field(
        ...,
        max_length=160,
        description="One plain English sentence describing what the customer said.",
    )
    suggested_reply: str = Field(
        ...,
        max_length=500,
        description="A polite 2-3 sentence public reply from the customer care team.",
    )
    topics: list[str] = Field(
        default_factory=list,
        max_length=4,
        description='1-4 short lowercase noun phrases, e.g. "biryani taste", "late delivery".',
    )
    is_spam: bool = Field(
        default=False,
        description="True only for spam, adverts, gibberish or pure abuse with no real feedback.",
    )

    @field_validator("summary")
    @classmethod
    def _one_sentence(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("summary must not be empty")
        if _SENTENCE_BREAK.search(v):
            raise ValueError("summary must be a single sentence")
        check_output(v)
        return v

    @field_validator("suggested_reply")
    @classmethod
    def _clean_reply(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("suggested_reply must not be empty")
        if len(_SENTENCE_END.findall(v)) > 3:
            raise ValueError("suggested_reply must be at most 3 sentences")
        check_output(v)
        return v

    @field_validator("topics")
    @classmethod
    def _clean_topics(cls, v: list[str]) -> list[str]:
        return [" ".join(t.lower().split()) for t in v if t and t.strip()]


class InsightNarrative(BaseModel):
    """Wording for the weekly report. Never contains numbers; Python inserts them."""

    complaint_notes: list[str] = Field(description="One short label per given complaint topic, same order, no numbers.")
    praise_notes: list[str] = Field(description="One short label per given praise topic, same order, no numbers.")
    action_items: list[str] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three concrete actions for the operations team.",
    )

    @field_validator("complaint_notes", "praise_notes", "action_items")
    @classmethod
    def _clean(cls, items: list[str]) -> list[str]:
        cleaned = [" ".join(s.split()) for s in items]
        for s in cleaned:
            check_output(s)
        return cleaned


class TopicMerge(BaseModel):
    """Mapping from raw topic strings to a smaller set of canonical topics."""

    mapping: dict[str, str] = Field(description="Every raw topic as a key, mapped to its canonical topic.")
