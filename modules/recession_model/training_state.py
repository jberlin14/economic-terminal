"""
Training-state coordinator shared between the UI `/recession/train`
endpoint and the scheduler's `retrain_recession_model` job.

Without a shared coordinator, both call paths could call `model.train()`
simultaneously and write to the same artifact files in parallel — the
per-file atomic save in `persistence.save_model` doesn't prevent two
trains from interleaving their writes across files (e.g. logistic
artifact from train A, RF artifact from train B).

`acquire()` returns True only when no train is currently running.
The caller must call `mark_completed` / `mark_failed` exactly once
per successful `acquire`. A `threading.Lock` guards state transitions
so concurrent threads (uvicorn's thread pool + APScheduler's thread
pool) cannot both observe `status == idle` and both proceed.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


_state: Dict[str, Any] = {
    "status": "idle",  # idle | training | completed | failed
    "progress": None,
    "result": None,
    "error": None,
    "started_at": None,
    "completed_at": None,
    "owner": None,  # "ui" | "scheduler" — for observability
}
_lock = threading.Lock()


def snapshot() -> Dict[str, Any]:
    """Return a shallow copy of the current state for read-only inspection."""
    with _lock:
        return dict(_state)


def acquire(owner: str, progress: str = "Initializing...") -> bool:
    """Atomically transition idle → training. Returns True on success.

    A second concurrent caller (whether from UI or scheduler) sees the
    transitioned state and gets False back; it must NOT proceed with a
    redundant `model.train()` call.
    """
    with _lock:
        if _state["status"] == "training":
            return False
        _state["status"] = "training"
        _state["progress"] = progress
        _state["started_at"] = time.time()
        _state["completed_at"] = None
        _state["result"] = None
        _state["error"] = None
        _state["owner"] = owner
        return True


def update_progress(progress: str) -> None:
    with _lock:
        if _state["status"] == "training":
            _state["progress"] = progress


def mark_completed(result: Any = None) -> None:
    with _lock:
        _state["status"] = "completed"
        _state["progress"] = None
        _state["result"] = result
        _state["completed_at"] = time.time()


def mark_failed(error: str) -> None:
    with _lock:
        _state["status"] = "failed"
        _state["progress"] = None
        _state["error"] = error
        _state["completed_at"] = time.time()


def is_training() -> bool:
    with _lock:
        return _state["status"] == "training"


def reset_for_test() -> None:  # pragma: no cover — test helper
    with _lock:
        _state.update({
            "status": "idle",
            "progress": None,
            "result": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "owner": None,
        })
