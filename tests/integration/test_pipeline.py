"""Integration tests for PipelineOrchestrator.

Covers:
- Test 11: Individual dataset download
- Test 12: All four datasets downloading independently
- Failure isolation: Failure in one dataset does not block the other three
- End-to-end artifact creation (CSVs and JSON audit reports)
"""

from unittest.mock import MagicMock, patch
from app.config.settings import Settings
from app.services.orchestrator import PipelineOrchestrator


def _create_mock_client_for_all(
    sample_gainers_payload,
    sample_losers_payload,
    sample_upper_band_payload,
    sample_volume_gainers_payload,
    sample_52_week_high_payload,
):
    mock_client = MagicMock()

    def _get(endpoint):
        if "gainers" in endpoint:
            return sample_gainers_payload
        elif "losers" in endpoint:
            return sample_losers_payload
        elif "upperband" in endpoint:
            return sample_upper_band_payload
        elif "volume" in endpoint:
            return sample_volume_gainers_payload
        elif "52-week" in endpoint:
            return sample_52_week_high_payload
        return {"data": []}

    mock_client.get.side_effect = _get
    return mock_client


def test_individual_dataset_download(
    mock_settings: Settings,
    sample_gainers_payload,
    sample_losers_payload,
    sample_upper_band_payload,
    sample_volume_gainers_payload,
    sample_52_week_high_payload,
):
    """Test 11: Individual dataset download via process_dataset."""
    mock_client = _create_mock_client_for_all(
        sample_gainers_payload,
        sample_losers_payload,
        sample_upper_band_payload,
        sample_volume_gainers_payload,
        sample_52_week_high_payload,
    )

    orchestrator = PipelineOrchestrator(mock_settings, client=mock_client)
    summary, df = orchestrator.process_dataset("top-gainers-losers")

    assert summary.status == "SUCCESS"
    assert summary.records_valid == 3
    assert df is not None
    assert len(df) == 3
    assert (mock_settings.output_dir / "top_gainers_losers_2026-11-11.csv").exists() or any(
        mock_settings.output_dir.glob("top_gainers_losers_*.csv")
    )


def test_all_four_datasets_download_and_produce_csvs(
    mock_settings: Settings,
    sample_gainers_payload,
    sample_losers_payload,
    sample_upper_band_payload,
    sample_volume_gainers_payload,
    sample_52_week_high_payload,
):
    """Test 12: All four datasets download independently and produce 4 separate CSV files."""
    mock_client = _create_mock_client_for_all(
        sample_gainers_payload,
        sample_losers_payload,
        sample_upper_band_payload,
        sample_volume_gainers_payload,
        sample_52_week_high_payload,
    )

    orchestrator = PipelineOrchestrator(mock_settings, client=mock_client)
    report = orchestrator.run()

    assert report.overall_status == "SUCCESS"
    assert report.datasets_attempted == 4
    assert report.datasets_succeeded == 4
    assert report.datasets_failed == 0

    # Verify all four CSV files were produced
    produced_csvs = list(mock_settings.output_dir.glob("*.csv"))
    assert len(produced_csvs) == 4

    csv_names = [f.name for f in produced_csvs]
    assert any("top_gainers_losers" in n for n in csv_names)
    assert any("upper_band_hitters" in n for n in csv_names)
    assert any("volume_gainers_spurts" in n for n in csv_names)
    assert any("52_week_high_equity" in n for n in csv_names)

    # Verify JSON audit report was generated
    report_files = list(mock_settings.reports_dir.glob("run_*.json"))
    assert len(report_files) == 1


def test_dataset_failure_isolation(
    mock_settings: Settings,
    sample_gainers_payload,
    sample_losers_payload,
    sample_volume_gainers_payload,
    sample_52_week_high_payload,
):
    """Failure isolation: If upper-band-hitters throws an error, the other 3 datasets still succeed."""
    mock_client = MagicMock()

    def _get_with_failure(endpoint):
        if "upperband" in endpoint:  # Upper band hitters endpoint
            raise ConnectionError("NSE blocked upper band hitters endpoint (Simulated 403)")
        elif "gainers" in endpoint:
            return sample_gainers_payload
        elif "losers" in endpoint:
            return sample_losers_payload
        elif "volume" in endpoint:
            return sample_volume_gainers_payload
        elif "52-week" in endpoint:
            return sample_52_week_high_payload
        return {"data": []}

    mock_client.get.side_effect = _get_with_failure

    orchestrator = PipelineOrchestrator(mock_settings, client=mock_client)
    report = orchestrator.run()

    # Overall should be PARTIAL_SUCCESS, NOT total crash!
    assert report.overall_status == "PARTIAL_SUCCESS"
    assert report.datasets_succeeded == 3
    assert report.datasets_failed == 1
    assert report.datasets["upper-band-hitters"].status == "FAILED"
    assert report.datasets["top-gainers-losers"].status == "SUCCESS"
    assert report.datasets["volume-gainers-spurts"].status == "SUCCESS"
    assert report.datasets["52-week-high-equity"].status == "SUCCESS"
