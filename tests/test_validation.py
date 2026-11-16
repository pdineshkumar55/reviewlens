import io

import pytest

from reviewlens.validation import ValidationError, load_reviews

HEADER = "review_id,date,platform,rating,review_text\n"


def _csv(body: str, header: str = HEADER) -> io.BytesIO:
    return io.BytesIO((header + body).encode("utf-8"))


def test_missing_column_raises():
    with pytest.raises(ValidationError, match="rating"):
        load_reviews(_csv("R-1,2026-10-01,Google,ok\n", "review_id,date,platform,review_text\n"))


def test_columns_are_case_insensitive_and_trimmed():
    df, _ = load_reviews(_csv("R-1,2026-10-01,Google,5,Nice\n", " Review_ID , DATE,Platform,Rating ,Review_Text\n"))
    assert list(df.columns) == ["review_id", "date", "platform", "rating", "review_text"]


def test_empty_rows_dropped():
    df, summary = load_reviews(_csv('R-1,2026-10-01,Google,5,Nice\nR-2,2026-10-01,Google,4,"   "\n'))
    assert list(df["review_id"]) == ["R-1"]
    assert summary.dropped == {"empty review text": 1}
    assert summary.rows_read == 2 and summary.rows_kept == 1


def test_duplicates_removed_keep_first():
    df, summary = load_reviews(_csv("R-1,2026-10-01,Google,5,First\nR-1,2026-10-02,Zomato,1,Second\n"))
    assert len(df) == 1 and df.loc[0, "review_text"] == "First"
    assert summary.dropped == {"duplicate review ID": 1}


def test_rating_coerced_and_invalid_dropped():
    df, summary = load_reviews(
        _csv("R-1,2026-10-01,Google,4.0,a\nR-2,2026-10-01,Google,9,b\nR-3,2026-10-01,Google,x,c\n")
    )
    assert df["rating"].tolist() == [4]
    assert df["rating"].dtype.kind == "i"
    assert summary.dropped == {"rating not between 1 and 5": 2}


def test_bad_date_dropped_and_dates_parsed():
    df, summary = load_reviews(_csv("R-1,2026-10-03,Google,5,a\nR-2,not a date,Google,5,b\n"))
    assert str(df.loc[0, "date"]) == "2026-10-03"
    assert summary.dropped == {"invalid date": 1}


def test_tamil_text_and_bom_survive():
    data = ("\ufeff" + HEADER + "R-1,2026-10-03,Google,5,சாப்பாடு நன்றாக இருந்தது\n").encode("utf-8")
    df, _ = load_reviews(io.BytesIO(data))
    assert df.loc[0, "review_text"] == "சாப்பாடு நன்றாக இருந்தது"


def test_row_cap():
    body = "".join(f"R-{i},2026-10-01,Google,5,ok {i}\n" for i in range(5))
    df, summary = load_reviews(_csv(body), max_rows=3)
    assert len(df) == 3 and summary.rows_dropped == 2
