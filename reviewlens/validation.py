"""Load and clean an uploaded reviews CSV."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS = ["review_id", "date", "platform", "rating", "review_text"]


class ValidationError(ValueError):
    """Raised when the file cannot be used at all (e.g. missing columns)."""


@dataclass
class ValidationSummary:
    rows_read: int = 0
    rows_kept: int = 0
    dropped: dict[str, int] = field(default_factory=dict)

    @property
    def rows_dropped(self) -> int:
        return sum(self.dropped.values())


def _read(source) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    # utf-8-sig strips the BOM that Excel adds when saving CSV.
    try:
        return pd.read_csv(source, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(source, dtype=str, keep_default_na=False, encoding="cp1252")
    except pd.errors.EmptyDataError as exc:
        raise ValidationError("The file is empty.") from exc


def load_reviews(source, max_rows: int | None = None) -> tuple[pd.DataFrame, ValidationSummary]:
    """Return the cleaned reviews and a summary of what was dropped.

    ``source`` can be a path, file-like object, bytes or DataFrame.
    """
    raw = _read(source)
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValidationError("Missing required columns: " + ", ".join(missing))

    df = raw[REQUIRED_COLUMNS].copy()
    summary = ValidationSummary(rows_read=len(df))

    def drop(mask: pd.Series, reason: str) -> None:
        nonlocal df
        count = int(mask.sum())
        if count:
            summary.dropped[reason] = summary.dropped.get(reason, 0) + count
            df = df[~mask]

    for col in REQUIRED_COLUMNS:
        df[col] = df[col].astype(str).str.strip()

    drop(df["review_text"] == "", "empty review text")
    drop(df["review_id"] == "", "missing review ID")
    drop(df["review_id"].duplicated(keep="first"), "duplicate review ID")

    ratings = pd.to_numeric(df["rating"], errors="coerce")
    drop(ratings.isna() | (ratings < 1) | (ratings > 5), "rating not between 1 and 5")
    df["rating"] = pd.to_numeric(df["rating"]).round().astype(int)

    dates = pd.to_datetime(df["date"], errors="coerce", format="mixed", dayfirst=False)
    drop(dates.isna(), "invalid date")
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.date

    df["platform"] = df["platform"].replace("", "Unknown")

    if max_rows is not None and len(df) > max_rows:
        summary.dropped[f"over the {max_rows}-row limit"] = len(df) - max_rows
        df = df.head(max_rows)

    df = df.reset_index(drop=True)
    summary.rows_kept = len(df)
    return df, summary
