"""Classifier tests with a stub structured model; no network calls."""

import pandas as pd
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from reviewlens.cache import ResultCache
from reviewlens.classifier import ReviewClassifier
from reviewlens.config import Settings
from reviewlens.llm import AnalysisServiceError
from reviewlens.schema import NEEDS_REVIEW, ReviewAnalysis

GOOD = dict(
    sentiment="negative",
    category="delivery",
    urgency="medium",
    language="English",
    summary="Order arrived late.",
    suggested_reply="We are sorry your order was late. Please DM us your order ID.",
    topics=["late delivery"],
)


def _raw():
    return AIMessage(content="", usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})


def _ok(**overrides):
    return {"raw": _raw(), "parsed": ReviewAnalysis(**{**GOOD, **overrides}), "parsing_error": None}


def _bad(msg="sentiment: Input should be 'positive', 'neutral' or 'negative'"):
    return {"raw": _raw(), "parsed": None, "parsing_error": ValueError(msg)}


class Stub:
    """Returns scripted outputs per review text; records how many calls each got."""

    def __init__(self, script):
        self.script = script  # text -> list of outputs (last one repeats)
        self.calls: dict[str, int] = {}
        self.corrections: list[str] = []

    def __call__(self, prompt_value):
        msgs = prompt_value.to_messages()
        human = next(m.content for m in msgs if m.type == "human")
        text = human.split("<review>\n", 1)[1].split("\n</review>", 1)[0]
        if len([m for m in msgs if m.type == "human"]) > 1:
            self.corrections.append(msgs[-1].content)
        n = self.calls.get(text, 0)
        self.calls[text] = n + 1
        outputs = self.script[text]
        out = outputs[min(n, len(outputs) - 1)]
        if isinstance(out, BaseException):
            raise out
        return out


def _df(*texts):
    return pd.DataFrame(
        {
            "review_id": [f"R-{i}" for i in range(len(texts))],
            "date": ["2026-10-03"] * len(texts),
            "platform": ["Swiggy"] * len(texts),
            "rating": [2] * len(texts),
            "review_text": list(texts),
        }
    )


def _classifier(stub, cache=None, **settings):
    s = Settings(openai_api_key="test", chunk_size=2, max_concurrency=2, **settings)
    return ReviewClassifier(s, structured_llm=RunnableLambda(stub), cache=cache)


def test_valid_output_passes_through():
    stub = Stub({"late order": [_ok()]})
    result = _classifier(stub).classify(_df("late order"))
    row = result.df.iloc[0]
    assert row["status"] == "ok" and row["category"] == "delivery"
    assert result.usage.calls == 1 and result.usage.input_tokens == 100


def test_invalid_output_is_retried_then_succeeds():
    stub = Stub({"late order": [_bad(), _ok()]})
    result = _classifier(stub).classify(_df("late order"))
    assert result.df.iloc[0]["status"] == "ok"
    assert stub.calls["late order"] == 2
    assert result.usage.retries == 1
    assert "previous answer was invalid" in stub.corrections[0]


def test_still_invalid_after_retries_is_needs_review():
    stub = Stub({"late order": [_bad()], "fine": [_ok(sentiment="positive")]})
    result = _classifier(stub).classify(_df("late order", "fine"))
    bad = result.df.iloc[0]
    assert stub.calls["late order"] == 3  # first try + 2 retries
    assert bad["status"] == NEEDS_REVIEW
    assert bad["sentiment"] == bad["category"] == bad["urgency"] == NEEDS_REVIEW
    assert bad["summary"] == ""
    assert result.needs_review == 1
    assert result.df.iloc[1]["status"] == "ok"


def test_exception_rows_are_retried():
    stub = Stub({"late order": [TimeoutError("slow"), _ok()], "fine": [_ok()]})
    result = _classifier(stub).classify(_df("late order", "fine"))
    assert result.df.iloc[0]["status"] == "ok"


def test_all_service_errors_raise():
    stub = Stub({"a": [ConnectionError("down")], "b": [ConnectionError("down")]})
    with pytest.raises(AnalysisServiceError):
        _classifier(stub).classify(_df("a", "b"))


def test_unsafe_reply_falls_back_to_template():
    unsafe = _ok(suggested_reply="Sorry! We will refund Rs. 300 to you.")
    stub = Stub({"late order": [unsafe]})
    result = _classifier(stub).classify(_df("late order"))
    row = result.df.iloc[0]
    assert row["status"] == "ok" and row["reply_fallback"]
    assert "refund" not in row["suggested_reply"].lower()
    assert "order ID" in row["suggested_reply"]


def test_business_name_not_allowed_in_complaint_reply():
    named = _ok(suggested_reply="Spice Route Kitchen is sorry your order was late.")
    stub = Stub({"late order": [named, _ok()]})
    result = _classifier(stub).classify(_df("late order"))
    assert stub.calls["late order"] == 2
    assert "Spice Route" not in result.df.iloc[0]["suggested_reply"]


def test_safety_rule_forces_high_urgency():
    stub = Stub({"found a cockroach in parotta": [_ok(category="food_quality", urgency="low")]})
    row = _classifier(stub).classify(_df("found a cockroach in parotta")).df.iloc[0]
    assert row["urgency"] == "high" and row["urgency_rule"]


def test_rule_never_lowers_urgency():
    stub = Stub({"late order": [_ok(urgency="high")]})
    row = _classifier(stub).classify(_df("late order")).df.iloc[0]
    assert row["urgency"] == "high" and not row["urgency_rule"]


def test_spam_gets_no_reply():
    stub = Stub({"buy followers now": [_ok(sentiment="neutral", is_spam=True)]})
    row = _classifier(stub).classify(_df("buy followers now")).df.iloc[0]
    assert row["status"] == "spam" and row["suggested_reply"] == ""


def test_cache_makes_second_run_free(tmp_path):
    cache = ResultCache(tmp_path / "c.sqlite")
    stub = Stub({"late order": [_ok()], "fine": [_ok()]})
    _classifier(stub, cache).classify(_df("late order", "fine"))
    second = _classifier(stub, cache).classify(_df("late order", "fine"))
    assert second.cached == 2 and second.usage.calls == 0
    assert stub.calls == {"late order": 1, "fine": 1}
    # bypassing the cache calls the service again
    _classifier(stub, cache).classify(_df("late order"), use_cache=False)
    assert stub.calls["late order"] == 2


def test_needs_review_not_cached(tmp_path):
    cache = ResultCache(tmp_path / "c.sqlite")
    stub = Stub({"late order": [_bad()]})
    _classifier(stub, cache).classify(_df("late order"))
    assert _classifier(stub, cache).classify(_df("late order")).cached == 0


def test_progress_reports_chunks():
    stub = Stub({t: [_ok()] for t in "abcde"})
    seen = []
    _classifier(stub).classify(_df(*"abcde"), progress=lambda d, t: seen.append((d, t)))
    assert seen == [(0, 5), (2, 5), (4, 5), (5, 5)]


def test_review_id_comes_from_input_not_service():
    stub = Stub({"x": [_ok()]})
    df = _df("x")
    df.loc[0, "review_id"] = "R-1042"
    assert _classifier(stub).classify(df).df.iloc[0]["review_id"] == "R-1042"


def test_schema_rejects_unknown_category():
    with pytest.raises(ValidationError):
        ReviewAnalysis(**{**GOOD, "category": "ambience"})


def test_language_script_correction():
    assert ReviewClassifier._language("Biryani semma taste", "Tamil") == "Tanglish"
    assert ReviewClassifier._language("சாப்பாடு நன்றாக இருந்தது", "English") == "Tamil"
    assert ReviewClassifier._language("Biryani semma taste", "Tanglish") == "Tanglish"


def test_reply_longer_than_three_sentences_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysis(**{**GOOD, "suggested_reply": "Sorry. We will check. Please DM us. Thank you."})


def test_cache_key_includes_rating(tmp_path):
    cache = ResultCache(tmp_path / "c.sqlite")
    stub = Stub({"ok": [_ok()]})
    df = _df("ok", "ok")
    df.loc[1, "rating"] = 5
    result = _classifier(stub, cache).classify(df)
    assert result.cached == 0 and stub.calls["ok"] == 2
