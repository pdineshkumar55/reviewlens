"""All counts and percentages, computed in pandas from the enriched table.

Only rows with ``status == "ok"`` count towards sentiment/category percentages;
``needs_review`` and ``spam`` rows are reported separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from reviewlens.schema import CATEGORIES, NEEDS_REVIEW, SENTIMENTS


def largest_remainder(counts: dict[str, int]) -> dict[str, int]:
    """Whole-number percentages that always sum to 100 (or all zero)."""
    total = sum(counts.values())
    if total == 0:
        return {k: 0 for k in counts}
    raw = {k: v * 100 / total for k, v in counts.items()}
    floors = {k: math.floor(v) for k, v in raw.items()}
    short = 100 - sum(floors.values())
    order = sorted(raw, key=lambda k: (raw[k] - floors[k], counts[k]), reverse=True)
    for k in order[:short]:
        floors[k] += 1
    return floors


_KEEP_S = ("ss", "us", "is", "ous")


def normalise_topic(topic: str) -> str:
    words = " ".join(str(topic).lower().strip().strip(".,;:!").split()).split(" ")
    last = words[-1]
    if len(last) > 4 and last.endswith("ies"):
        last = last[:-3] + "y"  # deliveries -> delivery
    elif last.endswith(("sses", "xes", "ches", "shes")):
        last = last[:-2]  # boxes -> box
    elif len(last) > 3 and last.endswith("s") and not last.endswith(_KEEP_S):
        last = last[:-1]  # charges -> charge
    words[-1] = last
    return " ".join(w for w in words if w)


def apply_topic_mapping(topics: list[str], mapping: dict[str, str] | None) -> list[str]:
    out: list[str] = []
    for t in topics or []:
        n = normalise_topic(t)
        if mapping:
            n = normalise_topic(mapping.get(n, mapping.get(t, n)))
        if n and n not in out:
            out.append(n)
    return out


@dataclass
class TopicStat:
    topic: str
    reviews: int
    platforms: dict[str, int] = field(default_factory=dict)

    @property
    def platform_note(self) -> str:
        if not self.platforms or self.reviews == 0:
            return ""
        top, n = max(self.platforms.items(), key=lambda kv: (kv[1], kv[0]))
        share = n / self.reviews
        if share == 1:
            return top
        if share >= 0.5:
            return f"mostly {top}"
        return ""


@dataclass
class Aggregates:
    total_rows: int
    analysed: int
    needs_review: int
    spam: int
    sentiment_counts: dict[str, int]
    sentiment_pct: dict[str, int]
    category_table: pd.DataFrame
    platform_table: pd.DataFrame
    urgent: int
    complaint_topics: list[TopicStat]
    praise_topics: list[TopicStat]
    date_from: date | None
    date_to: date | None

    def to_prompt_data(self, top_n: int = 5) -> dict:
        return {
            "reviews_analysed": self.analysed,
            "sentiment_percent": self.sentiment_pct,
            "urgent_reviews": self.urgent,
            "complaint_topics": [
                {"topic": t.topic, "reviews": t.reviews, "platforms": t.platforms}
                for t in self.complaint_topics[:top_n]
            ],
            "praise_topics": [{"topic": t.topic, "mentions": t.reviews} for t in self.praise_topics[:top_n]],
            "categories": self.category_table.reset_index().to_dict("records"),
        }


def _topic_stats(rows: pd.DataFrame) -> list[TopicStat]:
    if rows.empty:
        return []
    exploded = rows[["review_id", "platform", "topics"]].explode("topics").dropna(subset=["topics"])
    exploded = exploded[exploded["topics"].astype(str) != ""].drop_duplicates(["review_id", "topics"])
    if exploded.empty:
        return []
    stats: list[TopicStat] = []
    for topic, grp in exploded.groupby("topics"):
        stats.append(
            TopicStat(
                topic=str(topic),
                reviews=int(grp["review_id"].nunique()),
                platforms={str(k): int(v) for k, v in grp["platform"].value_counts().items()},
            )
        )
    stats.sort(key=lambda s: (-s.reviews, s.topic))
    return stats


def compute(df: pd.DataFrame) -> Aggregates:
    ok = df[df["status"] == "ok"]
    sentiment_counts = {s: int((ok["sentiment"] == s).sum()) for s in SENTIMENTS}

    cat = (
        pd.crosstab(ok["category"], ok["sentiment"])
        .reindex(index=list(CATEGORIES), columns=list(SENTIMENTS), fill_value=0)
        .astype(int)
    )
    cat.insert(0, "total", cat.sum(axis=1))
    neg = ok[ok["sentiment"] == "negative"]
    neg_platforms = pd.crosstab(neg["category"], neg["platform"]).reindex(index=list(CATEGORIES), fill_value=0)
    cat["negative_by_platform"] = [{str(p): int(n) for p, n in row.items() if n} for _, row in neg_platforms.iterrows()]
    cat.index.name = "category"

    plat = pd.crosstab(ok["platform"], ok["sentiment"]).reindex(columns=list(SENTIMENTS), fill_value=0).astype(int)
    plat.insert(0, "total", plat.sum(axis=1))

    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    not_spam = df[df["status"] != "spam"]

    return Aggregates(
        total_rows=len(df),
        analysed=len(ok),
        needs_review=int((df["status"] == NEEDS_REVIEW).sum()),
        spam=int((df["status"] == "spam").sum()),
        sentiment_counts=sentiment_counts,
        sentiment_pct=largest_remainder(sentiment_counts),
        category_table=cat,
        platform_table=plat,
        urgent=int((not_spam["urgency"] == "high").sum()),
        complaint_topics=_topic_stats(neg),
        praise_topics=_topic_stats(ok[ok["sentiment"] == "positive"]),
        date_from=dates.min().date() if not dates.empty else None,
        date_to=dates.max().date() if not dates.empty else None,
    )
