"""Unit tests for PostgreSQL repository and database failure handling."""

from app.storage.repository import PostgresRepository


def test_database_failure_operates_gracefully():
    """Test 13: Database failure/unavailability falls back gracefully to disabled mode."""
    # Invalid connection string to an unreachable port
    invalid_url = "postgresql://fake_user:fake_pass@127.0.0.1:59999/non_existent_db"

    repo = PostgresRepository(database_url=invalid_url, enabled=True)

    # Should not crash the application; should detect failure and disable itself
    assert not repo.enabled
    assert not repo.is_connected()

    # Operations should return None or no-op safely
    run = repo.create_run(run_id="test-run", datasets_attempted=4)
    assert run is None

    result_id = repo.record_dataset_result(
        run_id="test-run",
        dataset_name="top-gainers-losers",
        status="SUCCESS",
        records_fetched=10,
        records_valid=10,
        records_rejected=0,
        duplicates_found=0,
        quality_score=95.0,
        processing_seconds=1.2,
        csv_file_path="/fake/path.csv",
        validation_report={},
    )
    assert result_id is None


def test_sqlite_fallback_for_local_testing():
    """Test repository functions correctly when a valid database engine is provided (using sqlite memory)."""
    repo = PostgresRepository(database_url="sqlite:///:memory:", enabled=True)

    assert repo.enabled
    assert repo.is_connected()

    run = repo.create_run(run_id="test-sqlite", datasets_attempted=1)
    assert run is not None
    assert run.id == "test-sqlite"

