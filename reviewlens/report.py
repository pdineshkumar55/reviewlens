"""Weekly report: the chain writes labels and action items, Python inserts every number."""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable

from reviewlens.aggregate import Aggregates
from reviewlens.llm import Usage
from reviewlens.prompts import CORRECTION, report_prompt
from reviewlens.sanitize import output_problems
from reviewlens.schema import InsightNarrative

log = logging.getLogger(__name__)

TOP_COMPLAINTS = 3
TOP_PRAISE = 3
MAX_SUMMARIES = 30
_DIGIT = re.compile(r"\d")


def format_range(d1: date | None, d2: date | None) -> str:
    if not d1 or not d2:
        return "No dates"
    if d1.year == d2.year:
        return f"{d1.day} {d1:%b} to {d2.day} {d2:%b %Y}"
    return f"{d1.day} {d1:%b %Y} to {d2.day} {d2:%b %Y}"


def representative_summaries(df: pd.DataFrame, limit: int = MAX_SUMMARIES) -> list[str]:
    ok = df[(df["status"] == "ok") & (df["summary"].astype(str) != "")].copy()
    ok["_s"] = ok["sentiment"].map({"negative": 0, "neutral": 1, "positive": 2})
    ok["_u"] = ok["urgency"].map({"high": 0, "medium": 1, "low": 2})
    ok = ok.sort_values(["_s", "_u", "review_id"])
    return ok["summary"].head(limit).tolist()


def fallback_narrative(agg: Aggregates) -> InsightNarrative:
    complaints = [t.topic.capitalize() for t in agg.complaint_topics[:TOP_COMPLAINTS]]
    praise = [t.topic for t in agg.praise_topics[:TOP_PRAISE]]
    top = complaints[0].lower() if complaints else "the most common complaint"
    actions = [
        "Reply to every urgent review within 24 hours and follow up on each order.",
        f"Review the causes of {top} with the outlet managers this week and agree a fix.",
        f"Share the praise for {praise[0] if praise else 'our food'} with the kitchen team and keep that standard.",
    ]
    return InsightNarrative(complaint_notes=complaints, praise_notes=praise, action_items=actions)


def _merge_notes(given: list[str], fallback: list[str]) -> list[str]:
    """Use the chain's label where it is usable, otherwise the topic name."""
    out = []
    for i, fb in enumerate(fallback):
        note = given[i].strip() if i < len(given) else ""
        if not note or _DIGIT.search(note) or output_problems(note):
            note = fb
        out.append(note.rstrip("."))
    return out


def build_narrative(
    agg: Aggregates,
    df: pd.DataFrame,
    business_name: str,
    structured_llm: Runnable | None,
    usage: Usage | None = None,
) -> tuple[InsightNarrative, bool]:
    """Return (narrative, used_fallback)."""
    fb = fallback_narrative(agg)
    if structured_llm is None or agg.analysed == 0:
        return fb, True

    data = agg.to_prompt_data()
    data["complaint_topics"] = data["complaint_topics"][:TOP_COMPLAINTS]
    data["praise_topics"] = data["praise_topics"][:TOP_PRAISE]
    data["review_summaries"] = representative_summaries(df)
    inputs = {"business_name": business_name, "data": json.dumps(data, ensure_ascii=False, default=str)}
    chain = report_prompt() | structured_llm

    error = None
    for _ in range(2):
        if error:
            inputs["correction"] = [HumanMessage(CORRECTION.format(error=error))]
        try:
            out = chain.invoke(inputs)
        except Exception as exc:  # noqa: BLE001
            log.warning("report chain failed: %s", type(exc).__name__)
            return fb, True
        if usage is not None:
            usage.add_raw(out.get("raw"))
        parsed = out.get("parsed")
        if parsed is None or out.get("parsing_error") is not None:
            error = str(out.get("parsing_error"))[:300]
            continue
        actions = [a for a in parsed.action_items if not _DIGIT.search(a)]
        if len(actions) < 3:
            error = "action_items must not contain numbers"
            continue
        return (
            InsightNarrative(
                complaint_notes=_merge_notes(parsed.complaint_notes, fb.complaint_notes),
                praise_notes=_merge_notes(parsed.praise_notes, fb.praise_notes),
                action_items=[a.strip() for a in actions[:3]],
            ),
            False,
        )
    return fb, True


def render_text(agg: Aggregates, narrative: InsightNarrative, business_name: str) -> str:
    pct = agg.sentiment_pct
    lines = [
        f"WEEKLY FEEDBACK REPORT | {business_name} | {format_range(agg.date_from, agg.date_to)}",
        f"Total reviews: {agg.analysed}   Positive {pct['positive']}%   "
        f"Neutral {pct['neutral']}%   Negative {pct['negative']}%",
    ]
    excluded = []
    if agg.needs_review:
        excluded.append(f"{agg.needs_review} need manual review")
    if agg.spam:
        excluded.append(f"{agg.spam} marked as spam")
    if excluded:
        lines.append("Not counted: " + ", ".join(excluded))
    lines.append("")

    lines.append(f"TOP {TOP_COMPLAINTS} COMPLAINTS")
    complaints = agg.complaint_topics[:TOP_COMPLAINTS]
    if complaints:
        labels = [f"{i}. {note} " for i, note in enumerate(narrative.complaint_notes[: len(complaints)], 1)]
        width = max(len(s) for s in labels) + 4
        for label, stat in zip(labels, complaints):
            noun = "review" if stat.reviews == 1 else "reviews"
            where = f" ({stat.platform_note})" if stat.platform_note else ""
            lines.append(f"{label.ljust(width, '.')} {stat.reviews} {noun}{where}")
    else:
        lines.append("No complaints this week.")
    lines.append("")

    lines.append("TOP PRAISE")
    praise = agg.praise_topics[:TOP_PRAISE]
    if praise:
        parts = []
        for note, stat in zip(narrative.praise_notes, praise):
            noun = "mention" if stat.reviews == 1 else "mentions"
            parts.append(f"{note[:1].upper() + note[1:] if not parts else note} ({stat.reviews} {noun})")
        lines.append(", ".join(parts))
    else:
        lines.append("No praise topics this week.")
    lines.append("")

    noun = "review needs" if agg.urgent == 1 else "reviews need"
    lines.append(f"URGENT: {agg.urgent} {noun} a reply within 24 hours")
    lines.append("")

    lines.append("ACTION ITEMS")
    for i, item in enumerate(narrative.action_items, 1):
        lines.append(f"{i}. {item}")
    return "\n".join(lines) + "\n"


def render_markdown(report_text: str) -> str:
    """Markdown version for download: header as a heading, body kept aligned in a code block."""
    head, _, body = report_text.partition("\n")
    return f"# {head.strip()}\n\n```text\n{body.rstrip()}\n```\n"
