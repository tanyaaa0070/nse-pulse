"""Unit tests for processors: normalizer, deduplicator, quality scorer."""

from datetime import date
import pandas as pd
from app.processors.deduplicator import DuplicateDetector
from app.processors.normalizer import DataNormalizer
from app.processors.quality import DataQualityScorer
from app.validators.engine import ValidationEngine


def test_normalizer_cleans_numbers_and_text():
    normalizer = DataNormalizer()
    df = pd.DataFrame([
        {
            "symbol": " infy ",
            "series": "eq",
            "ltp": "1,540.50",
            "pct_change": "4.2%",
            "trade_date": "11-Nov-2026",
        }
    ])

    norm = normalizer.normalize(df, "test", numeric_columns=["ltp", "pct_change"])

    assert norm.loc[0, "symbol"] == "INFY"
    assert norm.loc[0, "series"] == "EQ"
    assert norm.loc[0, "ltp"] == 1540.50
    assert norm.loc[0, "pct_change"] == 4.2
    assert norm.loc[0, "trade_date"] == "2026-11-11"


def test_deduplicator_removes_dups_and_generates_report():
    deduplicator = DuplicateDetector()
    df = pd.DataFrame([
        {"symbol": "INFY", "ltp": 1500.0},
        {"symbol": "INFY", "ltp": 1500.0},  # Duplicate
        {"symbol": "TCS", "ltp": 3400.0},
    ])

    deduped_df, report = deduplicator.deduplicate(df, "test-dataset", key_columns=["symbol"])

    assert len(deduped_df) == 2
    assert report.duplicate_count == 1
    assert report.original_count == 3
    assert report.deduplicated_count == 2
    assert len(report.duplicate_records) == 1


def test_data_quality_scorer():
    engine = ValidationEngine()
    scorer = DataQualityScorer()

    df = pd.DataFrame([
        {"symbol": "INFY", "category": "gainer", "ltp": 1500.0, "pct_change": 3.0},
        {"symbol": "TCS", "category": "gainer", "ltp": 3400.0, "pct_change": 2.0},
    ])

    validated_df, v_report = engine.validate(df, "top-gainers-losers")
    q_report = scorer.compute_score(
        df=validated_df,
        dataset_name="top-gainers-losers",
        validation_report=v_report,
        expected_columns=["symbol", "category", "ltp", "pct_change"],
    )

    assert q_report.overall_score >= 90.0
    assert q_report.grade == "A"
    assert q_report.is_acceptable
    assert "completeness" in q_report.dimensions
    assert "schema_conformity" in q_report.dimensions

