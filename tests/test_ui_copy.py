from pathlib import Path

from scripts.check_ui_copy import check, strings_in


def test_ui_copy_is_clean():
    assert check() == []


def test_checker_catches_banned_words(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        '"""Docstrings are ignored: AI model."""\nLABEL = "Smart insights powered by AI"\nX = "Unlock insights"\n',
        encoding="utf-8",
    )
    assert [s for _, s in strings_in(bad)] == ["Smart insights powered by AI", "Unlock insights"]
    problems = check([bad])
    assert len(problems) == 2
