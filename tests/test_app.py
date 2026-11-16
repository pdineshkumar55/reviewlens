"""Drive the Streamlit app headlessly with a stub service (no network)."""

from functools import partial

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from streamlit.testing.v1 import AppTest

import reviewlens.pipeline as pipeline
from reviewlens.config import ROOT
from reviewlens.schema import ReviewAnalysis


def _fake(prompt_value):
    text = prompt_value.to_messages()[1].content.lower()
    negative = any(w in text for w in ["late", "cold", "bad", "charge", "kammi", "cockroach", "mudi", "small", "salty"])
    parsed = ReviewAnalysis(
        sentiment="negative" if negative else "positive",
        category="delivery" if "late" in text else "food_quality",
        urgency="medium" if negative else "low",
        language="English",
        summary="Customer shared feedback about the order.",
        suggested_reply="Thank you for your feedback." if not negative else "We are sorry. Please DM us your order ID.",
        topics=["late delivery"] if "late" in text else ["biryani taste"],
    )
    return {"raw": AIMessage(content=""), "parsed": parsed, "parsing_error": None}


@pytest.fixture
def app(monkeypatch, tmp_path):
    from reviewlens import config

    stub = pipeline.Runnables(classify=RunnableLambda(_fake), report=None, merge=None)
    real = pipeline.run_analysis
    settings = config.Settings(openai_api_key="test", cache_dir=tmp_path / "cache", log_dir=tmp_path / "logs")
    monkeypatch.setattr(pipeline, "run_analysis", partial(real, runnables=stub))
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)


def test_empty_state(app):
    app.run()
    assert not app.exception
    assert app.title[0].value == "ReviewLens"
    assert any("No reviews analysed yet" in s.value for s in app.subheader)


def test_sample_run_end_to_end(app):
    app.run()
    next(b for b in app.sidebar.button if b.label == "Try with sample data").click().run()
    assert not app.exception
    assert not app.error
    labels = [m.label for m in app.metric]
    assert labels == ["Reviews", "Positive", "Negative", "Urgent"]
    assert app.metric[0].value == "240"
    report = app.code[0].value
    assert report.startswith("WEEKLY FEEDBACK REPORT | Spice Route Kitchen | 29 Sep to 5 Oct 2026")

    # High-urgency toggle filters without re-running the analysis.
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert any("Showing" in c.value for c in app.caption)
