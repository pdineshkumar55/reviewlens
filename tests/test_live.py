"""Live check against the real analysis service. Run with: pytest -m live"""

import pandas as pd
import pytest

from reviewlens.classifier import ReviewClassifier
from reviewlens.config import ROOT, get_settings

pytestmark = pytest.mark.live


def test_brief_rows():
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("your-"):
        pytest.skip("OPENAI_API_KEY not set")
    df = pd.read_csv(ROOT / "data" / "reviews_week40.csv", dtype=str)
    out = ReviewClassifier(settings).classify(df, use_cache=False).df.set_index("review_id")

    r42 = out.loc["R-1042"]
    assert (r42["category"], r42["sentiment"], r42["urgency"]) == ("delivery", "negative", "high")
    assert out.loc["R-1041", "sentiment"] == "positive"
    r43 = out.loc["R-1043"]
    assert (r43["category"], r43["language"]) == ("price", "Tanglish")
    assert "charge" in r43["summary"].lower()
