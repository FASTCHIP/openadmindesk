"""Tests for TransferQueue — state transitions independent of live SFTP."""

from __future__ import annotations

import time
from openadmindesk.core.transfer_queue import (
    ConflictResolution,
    TransferDirection,
    TransferJob,
    TransferQueue,
    TransferStatus,
)


def _make_job(
    job_id: str = "j1",
    direction: TransferDirection = TransferDirection.UPLOAD,
    size: int = 1000,
) -> TransferJob:
    return TransferJob(
        id=job_id,
        direction=direction,
        local_path=f"/local/{job_id}.dat",
        remote_path=f"/remote/{job_id}.dat",
        size_bytes=size,
    )


# ── TransferJob tests ────────────────────────────────────────────────────────


def test_transfer_job_defaults() -> None:
    """TransferJob default status is QUEUED."""
    job = _make_job()
    assert job.status == TransferStatus.QUEUED
    assert job.progress == 0
    assert job.error == ""
    assert job.retry_count == 0
    assert job.max_retries == 2


def test_transfer_job_display_name() -> None:
    """display_name returns the basename of the relevant path."""
    up = _make_job("u1", TransferDirection.UPLOAD)
    assert up.display_name == "u1.dat"

    dl = _make_job("d1", TransferDirection.DOWNLOAD)
    assert dl.display_name == "d1.dat"


def test_transfer_job_progress_pct() -> None:
    """progress_pct reflects bytes transferred."""
    job = _make_job(size=200)
    assert job.progress_pct == 0.0

    job.progress = 100
    assert job.progress_pct == 50.0

    job.progress = 200
    assert job.progress_pct == 100.0


def test_transfer_job_progress_pct_zero_size() -> None:
    """progress_pct is 0 when size is 0."""
    job = _make_job(size=0)
    assert job.progress_pct == 0.0


def test_transfer_job_retry_allowed() -> None:
    """retry_allowed is True only for FAILED or CANCELLED."""
    job = _make_job()
    assert not job.retry_allowed()

    job.status = TransferStatus.RUNNING
    assert not job.retry_allowed()

    job.status = TransferStatus.DONE
    assert not job.retry_allowed()

    job.status = TransferStatus.FAILED
    assert job.retry_allowed()

    job.status = TransferStatus.CANCELLED
    assert job.retry_allowed()


def test_transfer_job_cancel_allowed() -> None:
    """cancel_allowed is True only for QUEUED or RUNNING."""
    job = _make_job()
    assert job.cancel_allowed()

    job.status = TransferStatus.RUNNING
    assert job.cancel_allowed()

    job.status = TransferStatus.DONE
    assert not job.cancel_allowed()

    job.status = TransferStatus.FAILED
    assert not job.cancel_allowed()

    job.status = TransferStatus.CANCELLED
    assert not job.cancel_allowed()


def test_transfer_job_destination_path_overwrite() -> None:
    """destination_path returns the original remote path when resolution is OVERWRITE."""
    job = _make_job()
    assert job.destination_path() == "/remote/j1.dat"


def test_transfer_job_destination_path_rename() -> None:
    """destination_path appends suffix when resolution is RENAME."""
    job = _make_job()
    job.conflict_resolution = ConflictResolution.RENAME
    job.rename_suffix = "_1"
    assert job.destination_path() == "/remote/j1_1.dat"


def test_transfer_job_destination_path_rename_download() -> None:
    """destination_path appends suffix for downloads too."""
    job = _make_job(direction=TransferDirection.DOWNLOAD)
    job.conflict_resolution = ConflictResolution.RENAME
    job.rename_suffix = "_copy"
    expected = "/local/j1_copy.dat"
    assert job.destination_path() == expected


# ── TransferQueue unit tests ─────────────────────────────────────────────────


def test_queue_create() -> None:
    """A fresh queue has no jobs."""
    q = TransferQueue()
    assert q.all_jobs() == []
    assert q.active_count() == 0


def test_queue_add_and_list_jobs() -> None:
    """add_job adds a job that appears in all_jobs."""
    q = TransferQueue()
    job = _make_job()
    q.add_job(job)
    assert len(q.all_jobs()) == 1
    assert q.all_jobs()[0].id == "j1"
    assert q.active_count() == 1


def test_queue_job_by_id() -> None:
    """job_by_id returns the correct job or None."""
    q = TransferQueue()
    q.add_job(_make_job("a"))
    q.add_job(_make_job("b"))
    assert q.job_by_id("a") is not None
    assert q.job_by_id("a").id == "a"
    assert q.job_by_id("b") is not None
    assert q.job_by_id("nonexistent") is None


def test_queue_remove_job() -> None:
    """remove_job removes a queued job."""
    q = TransferQueue()
    job = _make_job()
    q.add_job(job)
    assert q.remove_job("j1") is True
    assert q.job_by_id("j1") is None
    assert q.active_count() == 0


def test_queue_remove_job_not_queued() -> None:
    """remove_job returns False if job is not QUEUED."""
    q = TransferQueue()
    job = _make_job()
    job.status = TransferStatus.RUNNING
    q.add_job(job)
    assert q.remove_job("j1") is False


def test_queue_cancel_queued_job() -> None:
    """cancel_job sets a queued job to CANCELLED immediately."""
    q = TransferQueue()
    q.add_job(_make_job())
    assert q.cancel_job("j1") is True
    job = q.job_by_id("j1")
    assert job is not None
    assert job.status == TransferStatus.CANCELLED
    assert job.finished_at is not None


def test_queue_retry_job() -> None:
    """retry_job resets a FAILED job to QUEUED."""
    q = TransferQueue()
    job = _make_job()
    job.status = TransferStatus.FAILED
    job.error = "something broke"
    job.progress = 500
    q.add_job(job)

    assert q.retry_job("j1") is True
    job = q.job_by_id("j1")
    assert job.status == TransferStatus.QUEUED
    assert job.progress == 0
    assert job.error == ""
    assert job.started_at is None


def test_queue_retry_job_not_allowed() -> None:
    """retry_job returns False for non-retryable status."""
    q = TransferQueue()
    q.add_job(_make_job())
    assert q.retry_job("j1") is False  # job is QUEUED, not failed


def test_queue_clear_completed() -> None:
    """clear_completed removes DONE/FAILED/CANCELLED jobs."""
    q = TransferQueue()

    def _add(jid, status):
        job = _make_job(jid)
        job.status = status
        q.add_job(job)

    _add("a", TransferStatus.DONE)
    _add("b", TransferStatus.FAILED)
    _add("c", TransferStatus.CANCELLED)
    _add("d", TransferStatus.QUEUED)
    _add("e", TransferStatus.RUNNING)

    removed = q.clear_completed()
    assert removed == 3
    remaining = q.all_jobs()
    assert {j.id for j in remaining} == {"d", "e"}


# ── Queue processing tests (using mock transfer functions) ───────────────────


def test_queue_processes_job_to_done() -> None:
    """A queued job with a successful mock transfer reaches DONE."""
    q = TransferQueue()

    def _upload(local, remote, callback):
        callback(1000, 1000)
        return True

    q.set_upload_fn(_upload)
    q.add_job(_make_job("u1", TransferDirection.UPLOAD, size=1000))
    q.start()
    time.sleep(0.3)

    job = q.job_by_id("u1")
    assert job is not None
    assert job.status == TransferStatus.DONE
    q.stop(wait=True)


def test_queue_processes_job_to_failed() -> None:
    """A queued job with a failing mock transfer reaches FAILED after retries."""
    q = TransferQueue()

    def _upload_fail(local, remote, callback):
        callback(0, 1000)
        return False

    q.set_upload_fn(_upload_fail)
    job = _make_job("u1", TransferDirection.UPLOAD, size=1000)
    job.max_retries = 1  # only one retry
    q.add_job(job)
    q.start()
    time.sleep(0.5)

    job = q.job_by_id("u1")
    assert job is not None
    assert job.status == TransferStatus.FAILED
    assert job.retry_count == 1  # one retry attempted
    q.stop(wait=True)


def test_queue_cancel_running_job() -> None:
    """A running job can be cancelled via cancel_job."""
    q = TransferQueue()
    _cancelled = False

    def _upload_slow(local, remote, callback):
        nonlocal _cancelled
        # Simulate partial progress then cancellation
        for i in range(10):
            time.sleep(0.05)
            if not callback(i * 100, 1000):
                _cancelled = True
                return False
        return True

    q.set_upload_fn(_upload_slow)
    q.add_job(_make_job("u1", TransferDirection.UPLOAD, size=1000))
    q.start()
    time.sleep(0.1)
    q.cancel_job("u1")
    time.sleep(0.3)

    job = q.job_by_id("u1")
    assert job is not None
    assert job.status == TransferStatus.CANCELLED
    assert _cancelled
    q.stop(wait=True)


def test_queue_empty_callback() -> None:
    """on_queue_empty is called when the queue has no jobs."""
    q = TransferQueue()
    empty_called = []

    def _on_empty():
        empty_called.append(True)

    q.on_queue_empty = _on_empty
    q.start()
    time.sleep(0.3)
    q.stop(wait=True)

    assert len(empty_called) >= 1


def test_queue_sequential_processing() -> None:
    """Jobs are processed one at a time in order."""
    q = TransferQueue()
    order: list[str] = []

    def _upload_fn(local, remote, callback):
        callback(100, 100)
        order.append(local)
        return True

    q.set_upload_fn(_upload_fn)
    q.add_job(_make_job("a", TransferDirection.UPLOAD))
    q.add_job(_make_job("b", TransferDirection.UPLOAD))
    q.add_job(_make_job("c", TransferDirection.UPLOAD))
    q.start()
    time.sleep(0.5)

    assert len(order) == 3
    assert "a.dat" in order[0]
    assert "b.dat" in order[1]
    assert "c.dat" in order[2]
    q.stop(wait=True)
