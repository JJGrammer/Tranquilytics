from app.schemas.preview import HorizonPreview, PreviewResponse
from app.services.daily_picks import pick_row_from_preview


def test_pick_accepts_safer_buy_short() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="TEST",
        risk_level="Moderate",
        short_term=HorizonPreview(tone="Safer Buy", confidence=0.82),
        long_term=HorizonPreview(tone="Neutral", confidence=0.5),
    )
    row = pick_row_from_preview(p, focus="short")
    assert row is not None
    assert row.symbol == "TEST"
    assert row.short_tone == "Safer Buy"
    assert row.screen_tone == "Safer Buy"
    assert row.screen_horizon == "short"


def test_pick_accepts_buy_when_low_vol_bucket_short() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="LOWV",
        risk_level="Low",
        short_term=HorizonPreview(tone="Buy", confidence=0.62),
        long_term=HorizonPreview(tone="Buy", confidence=0.55),
    )
    row = pick_row_from_preview(p, focus="short")
    assert row is not None
    assert row.short_tone == "Buy"
    assert row.screen_tone == "Buy"
    assert row.screen_horizon == "short"


def test_pick_rejects_buy_when_not_low_risk_short() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="HI",
        risk_level="Moderate",
        short_term=HorizonPreview(tone="Buy", confidence=0.62),
        long_term=HorizonPreview(tone="Buy", confidence=0.55),
    )
    assert pick_row_from_preview(p, focus="short") is None


def test_pick_rejects_neutral_short() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="N",
        risk_level="Low",
        short_term=HorizonPreview(tone="Neutral", confidence=0.4),
        long_term=None,
    )
    assert pick_row_from_preview(p, focus="short") is None


def test_pick_long_accepts_safer_buy() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="LONG1",
        risk_level="Moderate",
        short_term=HorizonPreview(tone="Neutral", confidence=0.5),
        long_term=HorizonPreview(tone="Safer Buy", confidence=0.88),
    )
    row = pick_row_from_preview(p, focus="long")
    assert row is not None
    assert row.long_tone == "Safer Buy"
    assert row.screen_tone == "Safer Buy"
    assert row.screen_horizon == "long"
    assert row.confidence == 0.88
    assert row.short_tone == "Neutral"


def test_pick_long_accepts_buy_when_low_risk() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="LONG2",
        risk_level="Low",
        short_term=HorizonPreview(tone="Sell", confidence=0.4),
        long_term=HorizonPreview(tone="Buy", confidence=0.61),
    )
    row = pick_row_from_preview(p, focus="long")
    assert row is not None
    assert row.screen_horizon == "long"
    assert row.screen_tone == "Buy"


def test_pick_long_rejects_without_long_term() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="X",
        risk_level="Low",
        short_term=HorizonPreview(tone="Safer Buy", confidence=0.9),
        long_term=None,
    )
    assert pick_row_from_preview(p, focus="long") is None


def test_pick_long_rejects_buy_when_not_low_risk() -> None:
    p = PreviewResponse(
        valid=True,
        symbol="Y",
        risk_level="High",
        short_term=HorizonPreview(tone="Buy", confidence=0.7),
        long_term=HorizonPreview(tone="Buy", confidence=0.65),
    )
    assert pick_row_from_preview(p, focus="long") is None
