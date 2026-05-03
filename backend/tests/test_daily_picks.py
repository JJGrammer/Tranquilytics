from app.schemas.preview import HorizonPreview, PreviewResponse
from app.services.daily_picks import pick_row_from_preview


def test_pick_accepts_safer_buy() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="TEST",
        risk_level="Moderate",
        short_term=HorizonPreview(tone="Safer Buy", confidence=0.82),
        long_term=HorizonPreview(tone="Neutral", confidence=0.5),
    )
    row = pick_row_from_preview(p)
    assert row is not None
    assert row.symbol == "TEST"
    assert row.short_tone == "Safer Buy"


def test_pick_accepts_buy_when_low_vol_bucket() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="LOWV",
        risk_level="Low",
        short_term=HorizonPreview(tone="Buy", confidence=0.62),
        long_term=HorizonPreview(tone="Buy", confidence=0.55),
    )
    row = pick_row_from_preview(p)
    assert row is not None
    assert row.short_tone == "Buy"
    assert row.risk_level == "Low"


def test_pick_rejects_buy_when_not_low_risk() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="HI",
        risk_level="Moderate",
        short_term=HorizonPreview(tone="Buy", confidence=0.62),
        long_term=HorizonPreview(tone="Buy", confidence=0.55),
    )
    assert pick_row_from_preview(p) is None


def test_pick_rejects_neutral() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="N",
        risk_level="Low",
        short_term=HorizonPreview(tone="Neutral", confidence=0.4),
        long_term=None,
    )
    assert pick_row_from_preview(p) is None
