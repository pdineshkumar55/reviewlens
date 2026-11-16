"""CSV export that opens correctly in Excel (UTF-8 with BOM keeps Tamil text intact)."""

from __future__ import annotations

import pandas as pd

EXPORT_COLUMNS = [
    "review_id",
    "date",
    "platform",
    "rating",
    "review_text",
    "language",
    "sentiment",
    "category",
    "urgency",
    "summary",
    "suggested_reply",
    "status",
]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df[EXPORT_COLUMNS].to_csv(index=False).encode("utf-8-sig")
