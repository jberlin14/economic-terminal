"""Tests for the shared training-state coordinator (pass-5 finding)."""
import pytest

from modules.recession_model import training_state as ts


@pytest.fixture(autouse=True)
def reset_state():
    ts.reset_for_test()
    yield
    ts.reset_for_test()


def test_acquire_succeeds_from_idle():
    assert ts.acquire(owner="ui") is True
    assert ts.is_training()
    snap = ts.snapshot()
    assert snap["status"] == "training"
    assert snap["owner"] == "ui"
    assert snap["started_at"] is not None


def test_second_concurrent_acquire_returns_false():
    """Whether the second caller is UI or scheduler, it must NOT proceed."""
    assert ts.acquire(owner="ui") is True
    assert ts.acquire(owner="scheduler") is False
    # state still reflects the first owner
    assert ts.snapshot()["owner"] == "ui"


def test_mark_completed_releases_for_next_train():
    ts.acquire(owner="scheduler")
    ts.mark_completed({"ok": True})
    assert not ts.is_training()
    # next acquire works
    assert ts.acquire(owner="ui") is True


def test_mark_failed_releases_and_records_error():
    ts.acquire(owner="ui")
    ts.mark_failed("FRED unreachable")
    snap = ts.snapshot()
    assert snap["status"] == "failed"
    assert snap["error"] == "FRED unreachable"
    assert snap["completed_at"] is not None
    # next acquire works
    assert ts.acquire(owner="scheduler") is True


def test_update_progress_only_during_training():
    ts.acquire(owner="ui")
    ts.update_progress("Fetching FRED...")
    assert ts.snapshot()["progress"] == "Fetching FRED..."
    ts.mark_completed()
    # post-completion update is a no-op (state has moved on)
    ts.update_progress("This should be ignored")
    assert ts.snapshot()["progress"] is None
