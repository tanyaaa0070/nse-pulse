"""Unit tests for dataset parsers."""

from app.parsers.top_gainers_losers import TopGainersLosersParser
from app.parsers.upper_band_hitters import UpperBandHittersParser
from app.parsers.volume_gainers import VolumeGainersParser
from app.parsers.week52_high import Week52HighParser


def test_parse_top_gainers_losers(sample_gainers_payload, sample_losers_payload):
    """Test parsing both gainers and losers into a combined DataFrame with category tags."""
    parser = TopGainersLosersParser()
    raw_data = {
        "gainers": sample_gainers_payload,
        "losers": sample_losers_payload,
    }

    df = parser.parse(raw_data)

    assert len(df) == 3
    assert set(df["symbol"]) == {"INFY", "TCS", "RELIANCE"}
    assert "category" in df.columns
    assert list(df[df["symbol"] == "INFY"]["category"])[0] == "gainer"
    assert list(df[df["symbol"] == "RELIANCE"]["category"])[0] == "loser"


def test_parse_upper_band_hitters(sample_upper_band_payload):
    """Test parsing upper band hitters dataset."""
    parser = UpperBandHittersParser()
    raw_data = {"upper_band": sample_upper_band_payload}

    df = parser.parse(raw_data)

    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "TATAMOTORS"
    assert "ltp" in df.columns
    assert "pct_change" in df.columns


def test_parse_volume_gainers(sample_volume_gainers_payload):
    """Test parsing volume gainers/spurts dataset."""
    parser = VolumeGainersParser()
    raw_data = {"volume": sample_volume_gainers_payload}

    df = parser.parse(raw_data)

    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "HDFCBANK"
    assert "avg_volume" in df.columns
    assert "volume_change_pct" in df.columns


def test_parse_52_week_high(sample_52_week_high_payload):
    """Test parsing 52-week high equity dataset."""
    parser = Week52HighParser()
    raw_data = {"week52_high": sample_52_week_high_payload}

    df = parser.parse(raw_data)

    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "BHARTIARTL"
    assert "high_52_week" in df.columns
    assert "low_52_week" in df.columns


def test_parse_empty_dataset():
    """Test 5: Graceful parsing of empty API responses returns empty DataFrame with schema."""
    parser = TopGainersLosersParser()
    raw_data = {"gainers": {"data": []}, "losers": {"data": []}}

    df = parser.parse(raw_data)

    assert df.empty
    for col in parser.EXPECTED_COLUMNS:
        assert col in df.columns

