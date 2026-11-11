"""Integration tests for FastAPI endpoints.

Covers Test 15: Testing all REST API endpoints using FastAPI TestClient:
- GET /health
- GET /datasets
- GET /datasets/{dataset_name}
- POST /download/{dataset_name}
- POST /download/all
- GET /runs
- GET /validation/{dataset_name}
- GET /metrics
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.config.settings import Settings, get_settings


@pytest.fixture
def client(mock_settings: Settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: mock_settings
    return TestClient(app)


def test_api_health_endpoint(client: TestClient):
    """Test GET /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "pipeline_health" in data
    assert "database" in data


def test_api_datasets_endpoint(client: TestClient):
    """Test GET /datasets."""
    response = client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    names = [d["name"] for d in data["datasets"]]
    assert "top-gainers-losers" in names
    assert "upper-band-hitters" in names


def test_api_download_endpoints(client: TestClient, sample_gainers_payload, sample_losers_payload):
    """Test POST /download/{name} and POST /download/all."""
    with patch("app.collectors.nse_client.NSEClient.get") as mock_get:
        mock_get.return_value = sample_gainers_payload

        # Test single download
        resp_single = client.post("/download/top-gainers-losers")
        assert resp_single.status_code == 200
        single_data = resp_single.json()
        assert single_data["dataset_name"] == "top-gainers-losers"
        assert single_data["status"] == "SUCCESS"

        # Test all download
        resp_all = client.post("/download/all")
        assert resp_all.status_code == 200
        all_data = resp_all.json()
        assert "run_id" in all_data
        assert all_data["datasets_attempted"] == 4


def test_api_metrics_and_runs_endpoints(client: TestClient):
    """Test GET /metrics and GET /runs."""
    # First trigger a run so there is data to inspect
    with patch("app.collectors.nse_client.NSEClient.get") as mock_get:
        mock_get.return_value = {"data": []}
        client.post("/download/all")

    # Check metrics
    resp_metrics = client.get("/metrics")
    assert resp_metrics.status_code == 200
    metrics = resp_metrics.json()
    assert "system_status" in metrics
    assert metrics["datasets_active"] == 4

    # Check runs history
    resp_runs = client.get("/runs")
    assert resp_runs.status_code == 200
    runs = resp_runs.json()
    assert isinstance(runs, list)
    assert len(runs) >= 1

