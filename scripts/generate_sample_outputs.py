"""Generate sample output CSV files and execution report for project deliverables.

Uses realistic NSE market data fixtures to demonstrate end-to-end pipeline execution:
Acquisition → Parsing → Normalization → Validation → Deduplication → Scoring → CSV Export → Audit Report.
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import get_settings
from app.services.orchestrator import PipelineOrchestrator

SAMPLE_GAINERS = {
    "data": [
        {"symbol": "TCS", "series": "EQ", "openPrice": "3450.00", "highPrice": "3520.00", "lowPrice": "3440.00", "lastPrice": "3510.00", "previousPrice": "3430.00", "change": "80.00", "pChange": "2.33", "totalTradedVolume": "1420500", "date": "11-Nov-2026"},
        {"symbol": "INFY", "series": "EQ", "openPrice": "1520.00", "highPrice": "1565.00", "lowPrice": "1515.00", "lastPrice": "1558.00", "previousPrice": "1510.00", "change": "48.00", "pChange": "3.18", "totalTradedVolume": "3210400", "date": "11-Nov-2026"},
        {"symbol": "WIPRO", "series": "EQ", "openPrice": "480.00", "highPrice": "495.00", "lowPrice": "478.00", "lastPrice": "492.50", "previousPrice": "475.00", "change": "17.50", "pChange": "3.68", "totalTradedVolume": "2540100", "date": "11-Nov-2026"},
        {"symbol": "HCLTECH", "series": "EQ", "openPrice": "1340.00", "highPrice": "1380.00", "lowPrice": "1335.00", "lastPrice": "1375.00", "previousPrice": "1330.00", "change": "45.00", "pChange": "3.38", "totalTradedVolume": "1890200", "date": "11-Nov-2026"},
        {"symbol": "TECHM", "series": "EQ", "openPrice": "1190.00", "highPrice": "1225.00", "lowPrice": "1185.00", "lastPrice": "1218.00", "previousPrice": "1180.00", "change": "38.00", "pChange": "3.22", "totalTradedVolume": "1105300", "date": "11-Nov-2026"}
    ]
}

SAMPLE_LOSERS = {
    "data": [
        {"symbol": "RELIANCE", "series": "EQ", "openPrice": "2460.00", "highPrice": "2470.00", "lowPrice": "2390.00", "lastPrice": "2405.00", "previousPrice": "2455.00", "change": "-50.00", "pChange": "-2.04", "totalTradedVolume": "4210000", "date": "11-Nov-2026"},
        {"symbol": "ONGC", "series": "EQ", "openPrice": "210.00", "highPrice": "212.00", "lowPrice": "204.00", "lastPrice": "205.50", "previousPrice": "209.50", "change": "-4.00", "pChange": "-1.91", "totalTradedVolume": "7850000", "date": "11-Nov-2026"},
        {"symbol": "BPCL", "series": "EQ", "openPrice": "380.00", "highPrice": "382.00", "lowPrice": "371.00", "lastPrice": "373.00", "previousPrice": "379.00", "change": "-6.00", "pChange": "-1.58", "totalTradedVolume": "3120000", "date": "11-Nov-2026"},
        {"symbol": "IOC", "series": "EQ", "openPrice": "142.00", "highPrice": "143.00", "lowPrice": "138.50", "lastPrice": "139.20", "previousPrice": "141.50", "change": "-2.30", "pChange": "-1.63", "totalTradedVolume": "6540000", "date": "11-Nov-2026"}
    ]
}

SAMPLE_UPPER_BAND = {
    "data": [
        {"symbol": "TATAMOTORS", "series": "EQ", "openPrice": "720.00", "highPrice": "792.00", "lowPrice": "720.00", "lastPrice": "792.00", "previousPrice": "720.00", "change": "72.00", "pChange": "10.00", "totalTradedVolume": "18500000", "date": "11-Nov-2026"},
        {"symbol": "BHEL", "series": "EQ", "openPrice": "240.00", "highPrice": "264.00", "lowPrice": "239.00", "lastPrice": "264.00", "previousPrice": "240.00", "change": "24.00", "pChange": "10.00", "totalTradedVolume": "22400000", "date": "11-Nov-2026"},
        {"symbol": "SUZLON", "series": "EQ", "openPrice": "55.00", "highPrice": "57.75", "lowPrice": "55.00", "lastPrice": "57.75", "previousPrice": "55.00", "change": "2.75", "pChange": "5.00", "totalTradedVolume": "45200000", "date": "11-Nov-2026"},
        {"symbol": "YESBANK", "series": "EQ", "openPrice": "22.50", "highPrice": "24.75", "lowPrice": "22.40", "lastPrice": "24.75", "previousPrice": "22.50", "change": "2.25", "pChange": "10.00", "totalTradedVolume": "68100000", "date": "11-Nov-2026"}
    ]
}

SAMPLE_VOLUME_GAINERS = {
    "data": [
        {"symbol": "HDFCBANK", "series": "EQ", "lastPrice": "1655.00", "change": "35.00", "pChange": "2.16", "previousPrice": "1620.00", "totalTradedVolume": "28500000", "avgVolume": "5700000", "volumeChangePercent": "500.0", "date": "11-Nov-2026"},
        {"symbol": "ICICIBANK", "series": "EQ", "lastPrice": "1080.00", "change": "22.00", "pChange": "2.08", "previousPrice": "1058.00", "totalTradedVolume": "18400000", "avgVolume": "4600000", "volumeChangePercent": "400.0", "date": "11-Nov-2026"},
        {"symbol": "SBIN", "series": "EQ", "lastPrice": "745.00", "change": "18.50", "pChange": "2.55", "previousPrice": "726.50", "totalTradedVolume": "25100000", "avgVolume": "7170000", "volumeChangePercent": "350.0", "date": "11-Nov-2026"},
        {"symbol": "AXISBANK", "series": "EQ", "lastPrice": "1125.00", "change": "28.00", "pChange": "2.55", "previousPrice": "1097.00", "totalTradedVolume": "12800000", "avgVolume": "3880000", "volumeChangePercent": "330.0", "date": "11-Nov-2026"}
    ]
}

SAMPLE_52_WEEK_HIGH = {
    "data": [
        {"symbol": "BHARTIARTL", "series": "EQ", "lastPrice": "1245.00", "change": "25.00", "pChange": "2.05", "previousPrice": "1220.00", "yearHighPrice": "1245.00", "yearLowPrice": "760.00", "totalTradedVolume": "6400000", "date": "11-Nov-2026"},
        {"symbol": "SUNPHARMA", "series": "EQ", "lastPrice": "1620.00", "change": "32.00", "pChange": "2.02", "previousPrice": "1588.00", "yearHighPrice": "1620.00", "yearLowPrice": "980.00", "totalTradedVolume": "3800000", "date": "11-Nov-2026"},
        {"symbol": "ITC", "series": "EQ", "lastPrice": "495.00", "change": "8.50", "pChange": "1.75", "previousPrice": "486.50", "yearHighPrice": "495.00", "yearLowPrice": "399.00", "totalTradedVolume": "14200000", "date": "11-Nov-2026"},
        {"symbol": "TITAN", "series": "EQ", "lastPrice": "3780.00", "change": "65.00", "pChange": "1.75", "previousPrice": "3715.00", "yearHighPrice": "3780.00", "yearLowPrice": "2800.00", "totalTradedVolume": "1150000", "date": "11-Nov-2026"}
    ]
}


def main():
    settings = get_settings()
    settings.ensure_directories()

    mock_client = MagicMock()

    def _get(endpoint):
        if "gainers" in endpoint:
            return SAMPLE_GAINERS
        elif "losers" in endpoint:
            return SAMPLE_LOSERS
        elif "upperband" in endpoint:
            return SAMPLE_UPPER_BAND
        elif "volume" in endpoint:
            return SAMPLE_VOLUME_GAINERS
        elif "52-week" in endpoint:
            return SAMPLE_52_WEEK_HIGH
        return {"data": []}

    mock_client.get.side_effect = _get

    target_date = date(2026, 11, 11)
    orchestrator = PipelineOrchestrator(settings, client=mock_client)
    report = orchestrator.run(execution_date=target_date)

    print("Sample outputs successfully generated:")
    for name, sumry in report.datasets.items():
        print(f"  [{sumry.status}] {name} -> {sumry.csv_file_path} ({sumry.records_valid} records, Quality Score: {sumry.quality_score:.1f})")


if __name__ == "__main__":
    main()
