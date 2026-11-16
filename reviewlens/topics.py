"""Optional topic merging: the chain maps raw topic strings to canonical ones.

Only distinct topic strings are sent (never reviews), and the chain never
produces counts. Counting happens afterwards in pandas.
"""

from __future__ import annotations

import logging

import pandas as pd
from langchain_core.runnables import Runnable

from reviewlens.aggregate import apply_topic_mapping, normalise_topic
from reviewlens.llm import Usage
from reviewlens.prompts import topic_merge_prompt

log = logging.getLogger(__name__)

MAX_TOPICS = 300


def distinct_topics(df: pd.DataFrame) -> list[str]:
    seen: dict[str, None] = {}
    for topics in df.loc[df["status"] == "ok", "topics"]:
        for t in topics or []:
            n = normalise_topic(t)
            if n:
                seen.setdefault(n, None)
    return list(seen)


def merge_topics(df: pd.DataFrame, structured_llm: Runnable | None, usage: Usage | None = None) -> dict[str, str]:
    topics = distinct_topics(df)
    if structured_llm is None or len(topics) < 2 or len(topics) > MAX_TOPICS:
        return {}
    try:
        out = (topic_merge_prompt() | structured_llm).invoke({"topics": "\n".join(topics)})
    except Exception as exc:  # noqa: BLE001
        log.warning("topic merge failed: %s", type(exc).__name__)
        return {}
    if usage is not None:
        usage.add_raw(out.get("raw"))
    parsed = out.get("parsed")
    if parsed is None:
        return {}
    known = set(topics)
    # Ignore keys the chain invented and blank targets.
    return {
        normalise_topic(k): normalise_topic(v)
        for k, v in parsed.mapping.items()
        if normalise_topic(k) in known and normalise_topic(v)
    }


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    out["topics"] = out["topics"].apply(lambda ts: apply_topic_mapping(ts, mapping))
    return out
