"""Unit tests for NSEClient and dataset collectors.

Covers:
- Successful download
- Connection timeout and retry handling
- HTTP 403 Forbidden handling (respecting anti-bot restrictions)
- HTTP 500 Internal Server Error retry and backoff
- Invalid JSON response handling
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.collectors.nse_client import NSEClient
from app.collectors.top_gainers_losers import TopGainersLosersCollector
from app.config.settings import Settings


def test_successful_download(mock_settings: Settings, sample_gainers_payload):
    """Test 1: Successful data download with valid JSON response."""
    client = NSEClient(mock_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_gainers_payload
    mock_resp.content = b'{"data": []}'

    with patch.object(client, "_get_session") as mock_sess:
        mock_sess.return_value.get.return_value = mock_resp
        data = client.get("/api/live-analysis/gainers/allSec")

        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["symbol"] == "INFY"


def test_connection_timeout_and_retries(mock_settings: Settings):
    """Test 2 & 14: Connection timeout triggers configured retries before raising ConnectionError."""
    client = NSEClient(mock_settings)

    with patch.object(client, "_get_session") as mock_sess:
        mock_sess.return_value.get.side_effect = requests.exceptions.Timeout("Read timed out")

        with pytest.raises(ConnectionError) as exc_info:
            client.get("/test/timeout")

        assert "Failed to fetch" in str(exc_info.value)
        # Should have attempted nse_retry_count times
        assert mock_sess.return_value.get.call_count == mock_settings.nse_retry_count


def test_http_403_forbidden_respects_access_control(mock_settings: Settings):
    """Test 3: HTTP 403 halts immediately without retries to respect access restrictions."""
    client = NSEClient(mock_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch.object(client, "_get_session") as mock_sess:
        mock_sess.return_value.get.return_value = mock_resp

        with pytest.raises(ConnectionError) as exc_info:
            client.get("/restricted-endpoint")

        assert "HTTP 403 Forbidden" in str(exc_info.value)
        # Verify it did NOT hammer the server with retries
        assert mock_sess.return_value.get.call_count == 1


def test_http_500_server_error_retries_and_fails(mock_settings: Settings):
    """Test 3 & 14: HTTP 500 triggers exponential retries before failing."""
    client = NSEClient(mock_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")

    with patch.object(client, "_get_session") as mock_sess:
        mock_sess.return_value.get.return_value = mock_resp

        with pytest.raises(ConnectionError) as exc_info:
            client.get("/server-error")

        assert mock_sess.return_value.get.call_count == mock_settings.nse_retry_count


def test_invalid_json_response(mock_settings: Settings):
    """Test 4: HTML or corrupted non-JSON response raises ValueError."""
    client = NSEClient(mock_settings)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch.object(client, "_get_session") as mock_sess:
        mock_sess.return_value.get.return_value = mock_resp

        with pytest.raises(ValueError) as exc_info:
            client.get("/html-blocked-page")

        assert "Invalid JSON" in str(exc_info.value)


def test_top_gainers_losers_collector(mock_settings: Settings, sample_gainers_payload, sample_losers_payload):
    """Test collector fetches both gainers and losers sub-endpoints."""
    client = NSEClient(mock_settings)
    collector = TopGainersLosersCollector(client)

    def _mock_get(endpoint):
        if "gainers" in endpoint:
            return sample_gainers_payload
        return sample_losers_payload

    with patch.object(client, "get", side_effect=_mock_get):
        result = collector.fetch()
        assert "gainers" in result
        assert "losers" in result
        assert len(result["gainers"]["data"]) == 2
        assert len(result["losers"]["data"]) == 1

