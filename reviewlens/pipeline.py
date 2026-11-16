"""End-to-end run: classify -> merge topics -> aggregate -> report. UI-independent."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

import pandas as pd
from langchain_core.runnables import Runnable

from reviewlens import aggregate as agg_mod
from reviewlens.cache import ResultCache
from reviewlens.classifier import ProgressFn, ReviewClassifier
from reviewlens.config import Settings
from reviewlens.llm import AnalysisServiceError, Usage, make_chat_model, structured
from reviewlens.report import build_narrative, render_markdown, render_text
from reviewlens.schema import InsightNarrative, ReviewAnalysis, TopicMerge
from reviewlens.topics import apply_mapping, merge_topics
from reviewlens.usage import log_run

log = logging.getLogger(__name__)


@dataclass
class AnalysisRun:
    run_id: str
    business_name: str
    df: pd.DataFrame
    aggregates: agg_mod.Aggregates
    narrative: InsightNarrative
    report_text: str
    report_markdown: str
    usage: Usage = field(default_factory=Usage)
    cached: int = 0
    duration_s: float = 0.0
    report_fallback: bool = False


@dataclass
class Runnables:
    classify: Runnable
    report: Runnable | None
    merge: Runnable | None

    @classmethod
    def from_settings(cls, settings: Settings) -> Runnables:
        llm = make_chat_model(settings)
        return cls(
            classify=structured(llm, ReviewAnalysis),
            report=structured(llm, InsightNarrative),
            merge=structured(llm, TopicMerge),
        )


def run_analysis(
    df: pd.DataFrame,
    settings: Settings,
    business_name: str | None = None,
    progress: ProgressFn | None = None,
    use_cache: bool = True,
    runnables: Runnables | None = None,
    log_results: bool = True,
) -> AnalysisRun:
    run_id = uuid.uuid4().hex[:12]
    name = (business_name or "").strip() or settings.business_name
    started = time.perf_counter()
    outcome = "failed"
    usage = Usage()
    cached = 0
    try:
        runnables = runnables or Runnables.from_settings(settings)
        cache = ResultCache(settings.cache_dir / "reviews.sqlite")
        classifier = ReviewClassifier(settings, name, structured_llm=runnables.classify, cache=cache)
        result = classifier.classify(df, progress=progress, use_cache=use_cache)
        usage.merge(result.usage)
        cached = result.cached

        mapping = merge_topics(result.df, runnables.merge, usage)
        enriched = apply_mapping(result.df, mapping)
        aggregates = agg_mod.compute(enriched)
        narrative, used_fallback = build_narrative(aggregates, enriched, name, runnables.report, usage)
        text = render_text(aggregates, narrative, name)

        outcome = "partial" if result.needs_review else "ok"
        return AnalysisRun(
            run_id=run_id,
            business_name=name,
            df=enriched,
            aggregates=aggregates,
            narrative=narrative,
            report_text=text,
            report_markdown=render_markdown(text),
            usage=usage,
            cached=cached,
            duration_s=time.perf_counter() - started,
            report_fallback=used_fallback,
        )
    except AnalysisServiceError:
        outcome = "failed"
        raise
    finally:
        if log_results:
            log_run(
                settings.log_dir,
                {
                    "run_id": run_id,
                    "input_rows": len(df),
                    "cached_rows": cached,
                    "duration_s": round(time.perf_counter() - started, 2),
                    "model": settings.model_name,
                    "prompt_version": settings.prompt_version,
                    "model_calls": usage.calls,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "estimated_cost_usd": usage.cost_usd(settings),
                    "retries": usage.retries,
                    "outcome": outcome,
                },
            )
