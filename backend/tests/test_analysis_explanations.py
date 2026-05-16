from app.services.analysis_explanations import (
    get_confidence_explanation_dicts,
    get_synthesizer_explanation_dicts,
)


def test_confidence_sections_non_empty() -> None:
    rows = get_confidence_explanation_dicts()
    assert len(rows) >= 2
    assert all("heading" in r and "content" in r for r in rows)


def test_synthesizer_sections_non_empty() -> None:
    rows = get_synthesizer_explanation_dicts()
    assert len(rows) >= 2
