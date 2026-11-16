import random
import re
from datetime import date

import pandas as pd
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from reviewlens.aggregate import compute, largest_remainder, normalise_topic
from reviewlens.export import EXPORT_COLUMNS, to_csv_bytes
from reviewlens.report import build_narrative, format_range, render_markdown, render_text
from reviewlens.schema import InsightNarrative

PLATFORMS = ["Google", "Zomato", "Swiggy", "Amazon"]
NEG_TOPICS = ["late delivery", "extra charges", "small portion", "cold food", "rude staff"]
POS_TOPICS = ["biryani taste", "neat packaging", "filter coffee", "dosa taste"]


def enriched(n=120, seed=7) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        sentiment = rng.choices(["positive", "neutral", "negative"], [60, 15, 25])[0]
        topics = rng.sample(NEG_TOPICS if sentiment == "negative" else POS_TOPICS, k=rng.randint(1, 2))
        rows.append(
            {
                "review_id": f"R-{i}",
                "date": date(2026, 9, 29 + i % 2) if i % 3 else date(2026, 10, 1 + i % 5),
                "platform": rng.choice(PLATFORMS),
                "rating": rng.randint(1, 5),
                "review_text": f"text {i} சாப்பாடு",
                "language": "English",
                "sentiment": sentiment,
                "category": rng.choice(["food_quality", "delivery", "price", "staff", "packaging", "app"]),
                "urgency": rng.choice(["low", "medium", "high"]),
                "summary": f"Summary {i}.",
                "suggested_reply": "Thank you.",
                "topics": topics,
                "is_spam": False,
                "status": "ok",
            }
        )
    df = pd.DataFrame(rows)
    df.loc[3, ["status", "sentiment", "category", "urgency"]] = ["needs_review"] * 4
    df.loc[4, "status"] = "spam"
    return df


@pytest.mark.parametrize(
    "counts",
    [{"a": 1, "b": 1, "c": 1}, {"a": 151, "b": 35, "c": 62}, {"a": 0, "b": 0, "c": 0}, {"a": 2, "b": 0, "c": 1}],
)
def test_percentages_sum_to_100(counts):
    pct = largest_remainder(counts)
    assert sum(pct.values()) in (0, 100)
    if sum(counts.values()):
        assert sum(pct.values()) == 100


def test_counts_match_dataframe():
    df = enriched()
    agg = compute(df)
    ok = df[df["status"] == "ok"]
    assert agg.analysed == len(ok)
    assert agg.needs_review == 1 and agg.spam == 1
    assert agg.sentiment_counts == ok["sentiment"].value_counts().to_dict() | {
        k: 0 for k in ["positive", "neutral", "negative"] if k not in ok["sentiment"].values
    }
    assert sum(agg.sentiment_pct.values()) == 100
    assert agg.category_table["total"].sum() == len(ok)
    assert agg.urgent == int(((df["urgency"] == "high") & (df["status"] != "spam")).sum())
    neg = ok[ok["sentiment"] == "negative"]
    late = int(neg["topics"].apply(lambda t: "late delivery" in t).sum())
    assert next(t.reviews for t in agg.complaint_topics if t.topic == "late delivery") == late


def test_topic_normalisation():
    assert normalise_topic(" Extra Charges ") == "extra charge"
    assert normalise_topic("late deliveries") == "late delivery"
    assert normalise_topic("lunch boxes") == "lunch box"
    assert normalise_topic("glass") == "glass"


def test_report_numbers_equal_aggregates():
    df = enriched()
    agg = compute(df)
    narrative, used_fallback = build_narrative(agg, df, "Spice Route Kitchen", None)
    assert used_fallback
    text = render_text(agg, narrative, "Spice Route Kitchen")

    m = re.search(r"Total reviews: (\d+)\s+Positive (\d+)%\s+Neutral (\d+)%\s+Negative (\d+)%", text)
    assert m
    assert int(m.group(1)) == agg.analysed
    assert [int(m.group(i)) for i in (2, 3, 4)] == [
        agg.sentiment_pct["positive"],
        agg.sentiment_pct["neutral"],
        agg.sentiment_pct["negative"],
    ]

    complaint_counts = [int(c) for c in re.findall(r"^\d\. .*?\.+ (\d+) reviews?", text, re.M)]
    assert complaint_counts == [t.reviews for t in agg.complaint_topics[:3]]

    praise_line = text.split("TOP PRAISE\n", 1)[1].split("\n", 1)[0]
    assert [int(c) for c in re.findall(r"\((\d+) mentions?\)", praise_line)] == [
        t.reviews for t in agg.praise_topics[:3]
    ]

    urgent = int(re.search(r"URGENT: (\d+)", text).group(1))
    assert urgent == agg.urgent
    assert "Not counted: 1 need manual review, 1 marked as spam" in text


def test_dot_leaders_align_counts():
    df = enriched()
    agg = compute(df)
    text = render_text(agg, build_narrative(agg, df, "X", None)[0], "X")
    lines = [ln for ln in text.splitlines() if re.match(r"^\d\. .*\.{2,} \d", ln)]
    positions = {re.search(r"\.+ (\d)", ln).start(1) for ln in lines}
    assert len(lines) == 3 and len(positions) == 1


def test_report_header_has_business_and_range():
    df = enriched()
    agg = compute(df)
    text = render_text(agg, build_narrative(agg, df, "Spice Route Kitchen", None)[0], "Spice Route Kitchen")
    assert text.startswith("WEEKLY FEEDBACK REPORT | Spice Route Kitchen | 29 Sep to 5 Oct 2026")
    assert format_range(date(2025, 12, 29), date(2026, 1, 4)) == "29 Dec 2025 to 4 Jan 2026"
    assert render_markdown(text).startswith("# WEEKLY FEEDBACK REPORT")


def test_narrative_from_chain_keeps_python_numbers():
    df = enriched()
    agg = compute(df)
    narrative = InsightNarrative(
        complaint_notes=["Late delivery", "Bill has 5 extra charges", "Small portion size"],
        praise_notes=["biryani taste", "neat packaging", "filter coffee"],
        action_items=["Talk to the delivery partner.", "Check billing settings.", "Share praise with the kitchen."],
    )

    def stub(_):
        return {"raw": AIMessage(content=""), "parsed": narrative, "parsing_error": None}

    result, used_fallback = build_narrative(agg, df, "X", RunnableLambda(stub))
    assert not used_fallback
    # The note with a number is replaced by the plain topic label.
    assert "5" not in result.complaint_notes[1]
    assert result.action_items[0] == "Talk to the delivery partner."


def test_export_bom_and_columns():
    df = enriched()
    data = to_csv_bytes(df)
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert text.splitlines()[0] == ",".join(EXPORT_COLUMNS)
    assert "சாப்பாடு" in text
