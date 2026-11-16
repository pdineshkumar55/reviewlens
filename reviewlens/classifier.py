"""Per-review classification (the map step).

Flow for each review:
1. Look up the cache.
2. Misses are sent in chunks through ``prompt | llm.with_structured_output``.
3. Invalid output (schema, sanitizer, unsafe reply) is retried up to two more
   times with the error appended. Still invalid -> ``needs_review``.
   A reply that stays unsafe is swapped for a template reply instead.
4. Deterministic safety keywords can raise urgency to ``high``, never lower it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable

from reviewlens.cache import ResultCache, cache_key
from reviewlens.config import Settings
from reviewlens.llm import AnalysisServiceError, Usage, is_service_error, make_chat_model, structured
from reviewlens.prompts import CORRECTION, classify_prompt
from reviewlens.rules import fallback_reply, forced_high_urgency, reply_problems
from reviewlens.schema import NEEDS_REVIEW, ReviewAnalysis

log = logging.getLogger(__name__)

RESULT_COLUMNS = [
    "language",
    "sentiment",
    "category",
    "urgency",
    "summary",
    "suggested_reply",
    "topics",
    "is_spam",
    "status",
    "urgency_rule",
    "reply_fallback",
]

MAX_EXTRA_ATTEMPTS = 2

ProgressFn = Callable[[int, int], None]


@dataclass
class ClassifyResult:
    df: pd.DataFrame
    usage: Usage = field(default_factory=Usage)
    cached: int = 0
    duration_s: float = 0.0

    @property
    def needs_review(self) -> int:
        return int((self.df["status"] == NEEDS_REVIEW).sum())


class ReviewClassifier:
    def __init__(
        self,
        settings: Settings,
        business_name: str | None = None,
        structured_llm: Runnable | None = None,
        cache: ResultCache | None = None,
    ):
        self.settings = settings
        self.business_name = (business_name or settings.business_name).strip() or settings.business_name
        self._structured = structured_llm
        self.cache = cache
        self.prompt = classify_prompt()

    # -- chain -------------------------------------------------------------

    @property
    def chain(self) -> Runnable:
        if self._structured is None:
            self._structured = structured(make_chat_model(self.settings), ReviewAnalysis)
        return self.prompt | self._structured

    def _inputs(self, row: dict, error: str | None = None) -> dict[str, Any]:
        contact = self.settings.support_contact
        text = str(row["review_text"]).replace("</review>", "</ review>")
        inputs: dict[str, Any] = {
            "business_name": self.business_name,
            "support_rule": f" other than {contact}" if contact else "",
            "platform": row.get("platform", ""),
            "rating": row.get("rating", ""),
            "date": str(row.get("date", "")),
            "review_text": text,
        }
        if error:
            inputs["correction"] = [HumanMessage(CORRECTION.format(error=error))]
        return inputs

    def _key(self, row: dict) -> str:
        # Everything the prompt sees except the date, so the same text with a
        # different rating or platform is analysed separately.
        return cache_key(
            self.settings.model_name,
            self.settings.prompt_version,
            self.business_name,
            self.settings.support_contact,
            str(row.get("platform", "")),
            str(row.get("rating", "")),
            str(row["review_text"]),
        )

    # -- result handling ---------------------------------------------------

    def _parse(self, output: Any, usage: Usage) -> tuple[ReviewAnalysis | None, str | None]:
        if isinstance(output, BaseException):
            return None, f"{type(output).__name__}: {str(output)[:300]}"
        usage.add_raw(output.get("raw"))
        parsed = output.get("parsed")
        err = output.get("parsing_error")
        if err is not None or parsed is None:
            return None, str(err or "no structured output returned")[:500]
        return parsed, None

    def _reply_issues(self, parsed: ReviewAnalysis) -> list[str]:
        issues = reply_problems(parsed.suggested_reply, self.settings.support_contact)
        if parsed.sentiment != "positive" and self.business_name.lower() in parsed.suggested_reply.lower():
            issues.append("uses the business name in a non-positive reply")
        if parsed.suggested_reply.lower().count(self.business_name.lower()) > 1:
            issues.append("uses the business name more than once")
        return issues

    @staticmethod
    def _language(text: str, predicted: str) -> str:
        """Script check: Tamil needs Tamil characters; mostly-Tamil-script text is Tamil."""
        letters = [c for c in text if c.isalpha()]
        tamil = sum(1 for c in letters if "஀" <= c <= "௿")
        if predicted == "Tamil" and tamil == 0:
            return "Tanglish"
        if predicted != "Tamil" and letters and tamil / len(letters) > 0.5:
            return "Tamil"
        return predicted

    def _finalise(self, text: str, parsed: ReviewAnalysis, use_fallback: bool) -> dict[str, Any]:
        urgency = parsed.urgency
        rule = forced_high_urgency(text) and urgency != "high"
        if rule:
            urgency = "high"
        if parsed.is_spam:
            reply = ""
        elif use_fallback:
            reply = fallback_reply(parsed.category, parsed.sentiment, self.settings.support_contact)
        else:
            reply = parsed.suggested_reply
        return {
            "language": self._language(text, parsed.language),
            "sentiment": parsed.sentiment,
            "category": parsed.category,
            "urgency": urgency,
            "summary": parsed.summary,
            "suggested_reply": reply,
            "topics": list(parsed.topics),
            "is_spam": bool(parsed.is_spam),
            "status": "spam" if parsed.is_spam else "ok",
            "urgency_rule": bool(rule),
            "reply_fallback": bool(use_fallback and not parsed.is_spam),
        }

    @staticmethod
    def _needs_review(text: str) -> dict[str, Any]:
        # Safety keywords still mark the row urgent so it is not lost in the queue.
        return {
            "language": NEEDS_REVIEW,
            "sentiment": NEEDS_REVIEW,
            "category": NEEDS_REVIEW,
            "urgency": "high" if forced_high_urgency(text) else NEEDS_REVIEW,
            "summary": "",
            "suggested_reply": "",
            "topics": [],
            "is_spam": False,
            "status": NEEDS_REVIEW,
            "urgency_rule": forced_high_urgency(text),
            "reply_fallback": False,
        }

    def _resolve(self, row: dict, first_output: Any) -> tuple[dict[str, Any], Usage]:
        usage = Usage()
        text = str(row["review_text"])
        output = first_output
        error: str | None = None
        unsafe_reply: ReviewAnalysis | None = None

        for attempt in range(1 + MAX_EXTRA_ATTEMPTS):
            if attempt:
                usage.retries += 1
                try:
                    output = self.chain.invoke(self._inputs(row, error))
                except Exception as exc:  # noqa: BLE001 - recorded and retried
                    output = exc
            parsed, error = self._parse(output, usage)
            if parsed is None:
                continue
            issues = self._reply_issues(parsed)
            if not issues:
                return self._finalise(text, parsed, use_fallback=False), usage
            unsafe_reply = parsed
            error = "suggested_reply " + "; ".join(issues)

        if unsafe_reply is not None:
            return self._finalise(text, unsafe_reply, use_fallback=True), usage
        log.warning("review %s marked needs_review: %s", row.get("review_id"), error)
        return self._needs_review(text), usage

    # -- public ------------------------------------------------------------

    def classify(
        self,
        df: pd.DataFrame,
        progress: ProgressFn | None = None,
        use_cache: bool = True,
    ) -> ClassifyResult:
        started = time.perf_counter()
        rows = df.to_dict("records")
        total = len(rows)
        results: list[dict | None] = [None] * total
        usage = Usage()

        keys = [self._key(r) for r in rows]
        cached_hits = self.cache.get_many(keys) if (self.cache and use_cache) else {}
        for i, key in enumerate(keys):
            if key in cached_hits:
                results[i] = cached_hits[key]
        cached = sum(r is not None for r in results)

        todo = [i for i in range(total) if results[i] is None]
        done = cached
        if progress:
            progress(done, total)

        size = max(1, self.settings.chunk_size)
        workers = max(1, self.settings.max_concurrency)
        for start in range(0, len(todo), size):
            idx = todo[start : start + size]
            outputs = self.chain.batch(
                [self._inputs(rows[i]) for i in idx],
                config={"max_concurrency": workers},
                return_exceptions=True,
            )
            if all(isinstance(o, BaseException) and is_service_error(o) for o in outputs):
                raise AnalysisServiceError(str(outputs[0])[:300])

            with ThreadPoolExecutor(max_workers=workers) as pool:
                resolved = list(pool.map(lambda pair: self._resolve(rows[pair[0]], pair[1]), zip(idx, outputs)))

            fresh: dict[str, dict] = {}
            for i, (result, row_usage) in zip(idx, resolved):
                results[i] = result
                usage.merge(row_usage)
                if result["status"] != NEEDS_REVIEW:
                    fresh[keys[i]] = result
            if self.cache:
                self.cache.put_many(fresh)

            done += len(idx)
            if progress:
                progress(done, total)

        out = df.reset_index(drop=True).copy()
        res = pd.DataFrame(results, columns=RESULT_COLUMNS)
        for col in RESULT_COLUMNS:
            out[col] = res[col]
        return ClassifyResult(df=out, usage=usage, cached=cached, duration_s=time.perf_counter() - started)
