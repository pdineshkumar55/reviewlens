"""Chat model construction and helpers shared by the classifier and report chains."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.runnables import Runnable

from reviewlens.config import Settings


class AnalysisServiceError(RuntimeError):
    """The analysis service could not be reached (auth, network, quota...)."""


def _transient_errors() -> tuple[type[BaseException], ...]:
    try:
        import openai

        return (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        )
    except ImportError:  # pragma: no cover
        return (TimeoutError, ConnectionError)


def make_chat_model(settings: Settings):
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        raise AnalysisServiceError("OPENAI_API_KEY is not set in .env")
    return ChatOpenAI(
        model=settings.model_name,
        temperature=settings.temperature,
        timeout=settings.request_timeout,
        max_retries=0,  # retries are handled by with_retry below
        api_key=settings.openai_api_key,
    )


def structured(llm, schema) -> Runnable:
    """LLM -> {"raw", "parsed", "parsing_error"} with retry on transient API errors.

    ``include_raw=True`` means validation failures come back as ``parsing_error``
    instead of raising, and the raw message carries token usage.
    """
    return llm.with_structured_output(schema, method="function_calling", include_raw=True).with_retry(
        retry_if_exception_type=_transient_errors(),
        stop_after_attempt=3,
        wait_exponential_jitter=True,
    )


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0

    def add_raw(self, raw) -> None:
        self.calls += 1
        meta = getattr(raw, "usage_metadata", None) or {}
        self.input_tokens += int(meta.get("input_tokens", 0) or 0)
        self.output_tokens += int(meta.get("output_tokens", 0) or 0)

    def merge(self, other: Usage) -> None:
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.retries += other.retries

    def cost_usd(self, settings: Settings) -> float:
        p_in, p_out = settings.price_per_million
        return round(self.input_tokens / 1e6 * p_in + self.output_tokens / 1e6 * p_out, 5)


def is_service_error(exc: BaseException) -> bool:
    """True for errors talking to the API (as opposed to bad model output)."""
    try:
        import openai

        if isinstance(exc, openai.APIError):
            return True
    except ImportError:  # pragma: no cover
        pass
    return isinstance(exc, (AnalysisServiceError, TimeoutError, ConnectionError))
