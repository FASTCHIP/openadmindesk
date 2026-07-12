"""Transfer job model and queue for SFTP uploads/downloads.

This module defines:
- TransferDirection (UPLOAD, DOWNLOAD)
- TransferStatus (QUEUED, RUNNING, DONE, FAILED, CANCELLED)
- TransferJob — a single transfer operation
- TransferQueue — processes jobs sequentially with callbacks

The queue is independent of Qt and the UI layer.
"""

from __future__ import annotations

import enum
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class TransferDirection(enum.Enum):
    """Direction of a transfer job."""

    UPLOAD = "upload"
    DOWNLOAD = "download"


class TransferStatus(enum.Enum):
    """Lifecycle state of a transfer job."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConflictResolution(enum.Enum):
    """How to handle a destination conflict."""

    PROMPT = "prompt"  # ask user (default before queuing)
    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


@dataclass
class TransferJob:
    """A single file transfer operation.

    Attributes:
        id: Unique job identifier.
        direction: Upload or download.
        local_path: Path on the local filesystem.
        remote_path: Path on the remote (SFTP) filesystem.
        size_bytes: Total file size in bytes (0 if unknown at creation).
        status: Current lifecycle state.
        progress: Bytes transferred so far.
        error: Error message if status is FAILED.
        retry_count: Number of automatic retries attempted.
        max_retries: Maximum automatic retries before giving up.
        started_at: Unix timestamp when transfer started.
        finished_at: Unix timestamp when transfer finished (done/failed/cancelled).
        conflict_resolution: How to handle existing destination file.
        rename_suffix: Suffix to append when resolution is RENAME.
    """

    id: str
    direction: TransferDirection
    local_path: str
    remote_path: str
    size_bytes: int = 0
    status: TransferStatus = TransferStatus.QUEUED
    progress: int = 0
    error: str = ""
    retry_count: int = 0
    max_retries: int = 2
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    conflict_resolution: ConflictResolution = ConflictResolution.OVERWRITE
    rename_suffix: str = ""

    @property
    def display_name(self) -> str:
        """Human-readable file name for UI."""
        if self.direction == TransferDirection.UPLOAD:
            return os.path.basename(self.local_path)
        return os.path.basename(self.remote_path)

    @property
    def progress_pct(self) -> float:
        """Progress as a percentage (0.0–100.0)."""
        if self.size_bytes <= 0:
            return 0.0
        return min(100.0, self.progress / self.size_bytes * 100.0)

    def destination_path(self) -> str:
        """Return the effective destination path considering rename."""
        if self.conflict_resolution == ConflictResolution.RENAME and self.rename_suffix:
            if self.direction == TransferDirection.UPLOAD:
                base, ext = os.path.splitext(self.remote_path)
                return f"{base}{self.rename_suffix}{ext}"
            else:
                base, ext = os.path.splitext(self.local_path)
                return f"{base}{self.rename_suffix}{ext}"
        if self.direction == TransferDirection.UPLOAD:
            return self.remote_path
        return self.local_path

    def retry_allowed(self) -> bool:
        """Whether the job can be retried (failed or cancelled)."""
        return self.status in (TransferStatus.FAILED, TransferStatus.CANCELLED)

    def cancel_allowed(self) -> bool:
        """Whether the job can be cancelled."""
        return self.status in (TransferStatus.QUEUED, TransferStatus.RUNNING)


# Shared callback type: (transferred_bytes, total_bytes) -> bool (True=continue, False=cancel)
ProgressCallback = Callable[[int, int], bool]


class TransferQueue:
    """Processes transfer jobs sequentially on a background thread.

    Typical usage:
        queue = TransferQueue()
        queue.add_job(job)
        queue.start()
        # ... later ...
        queue.cancel_job(job.id)
    """

    def __init__(self, max_parallel: int = 1) -> None:
        self._jobs: list[TransferJob] = []
        self._jobs_by_id: dict[str, TransferJob] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._max_parallel = max(1, max_parallel)
        self._current_jobs: set[str] = set()
        self._cancel_requested: set[str] = set()

        # Callbacks (called from the worker thread — dispatch to UI thread externally)
        self.on_progress: Optional[Callable[[TransferJob], None]] = None
        self.on_completed: Optional[Callable[[TransferJob], None]] = None
        self.on_failed: Optional[Callable[[TransferJob], None]] = None
        self.on_queue_empty: Optional[Callable[[], None]] = None

        # Upload/download implementation functions.
        # Set externally so the queue stays backend-agnostic.
        self._upload_fn: Optional[
            Callable[[str, str, Optional[ProgressCallback]], bool]
        ] = None
        self._download_fn: Optional[
            Callable[[str, str, Optional[ProgressCallback]], bool]
        ] = None

    # ── public API ──────────────────────────────────────────────────────────

    def set_upload_fn(
        self, fn: Callable[[str, str, Optional[ProgressCallback]], bool]
    ) -> None:
        """Set the function that performs a single upload."""
        self._upload_fn = fn

    def set_download_fn(
        self, fn: Callable[[str, str, Optional[ProgressCallback]], bool]
    ) -> None:
        """Set the function that performs a single download."""
        self._download_fn = fn

    def add_job(self, job: TransferJob) -> None:
        """Add a transfer job to the queue."""
        with self._lock:
            self._jobs.append(job)
            self._jobs_by_id[job.id] = job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job that has not started yet. Returns True if removed."""
        with self._lock:
            job = self._jobs_by_id.get(job_id)
            if job is None or job.status not in (TransferStatus.QUEUED,):
                return False
            self._jobs = [j for j in self._jobs if j.id != job_id]
            del self._jobs_by_id[job_id]
            return True

    def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a queued or running job."""
        with self._lock:
            job = self._jobs_by_id.get(job_id)
            if job is None:
                return False
            if job.status in (TransferStatus.QUEUED,):
                job.status = TransferStatus.CANCELLED
                job.finished_at = time.time()
                return True
            if job.status == TransferStatus.RUNNING:
                self._cancel_requested.add(job_id)
                return True
            return False

    def retry_job(self, job_id: str) -> bool:
        """Re-queue a failed or cancelled job."""
        with self._lock:
            job = self._jobs_by_id.get(job_id)
            if job is None or not job.retry_allowed():
                return False
            job.status = TransferStatus.QUEUED
            job.progress = 0
            job.error = ""
            job.started_at = None
            job.finished_at = None
            self._cancel_requested.discard(job_id)
            return True

    def clear_completed(self) -> int:
        """Remove all DONE / FAILED / CANCELLED jobs. Returns count removed."""
        with self._lock:
            before = len(self._jobs)
            self._jobs = [
                j
                for j in self._jobs
                if j.status
                in (TransferStatus.QUEUED, TransferStatus.RUNNING)
            ]
            self._jobs_by_id = {j.id: j for j in self._jobs}
            return before - len(self._jobs)

    def all_jobs(self) -> list[TransferJob]:
        """Return a snapshot of all jobs."""
        with self._lock:
            return list(self._jobs)

    def job_by_id(self, job_id: str) -> Optional[TransferJob]:
        """Look up a job by ID."""
        with self._lock:
            return self._jobs_by_id.get(job_id)

    def active_count(self) -> int:
        """Number of jobs that are queued or running."""
        with self._lock:
            return sum(
                1
                for j in self._jobs
                if j.status
                in (TransferStatus.QUEUED, TransferStatus.RUNNING)
            )

    def start(self) -> None:
        """Start the queue processing thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self, wait: bool = True) -> None:
        """Stop the queue processing thread."""
        self._running = False
        if wait and self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    # ── internal processing ─────────────────────────────────────────────────

    def _process_loop(self) -> None:
        """Main loop: pick queued jobs and process them."""
        while self._running:
            job = self._pick_next()
            if job is None:
                # No work — sleep briefly
                if self._running:
                    self._on_queue_empty()
                    time.sleep(0.2)
                continue

            self._execute(job)

    def _pick_next(self) -> Optional[TransferJob]:
        """Return the next queued job, or None."""
        with self._lock:
            for j in self._jobs:
                if j.status == TransferStatus.QUEUED:
                    j.status = TransferStatus.RUNNING
                    j.started_at = time.time()
                    j.progress = 0
                    self._current_jobs.add(j.id)
                    return j
        return None

    def _execute(self, job: TransferJob) -> None:
        """Execute a single transfer job."""
        try:
            if job.direction == TransferDirection.UPLOAD:
                fn = self._upload_fn
            else:
                fn = self._download_fn

            if fn is None:
                job.status = TransferStatus.FAILED
                job.error = "Transfer function not set"
                self._finalise(job)
                return

            # Build a progress callback that checks cancellation
            def _progress_cb(transferred: int, total: int) -> bool:
                with self._lock:
                    if job.id in self._cancel_requested:
                        return False  # signal paramiko to stop
                job.progress = transferred
                job.size_bytes = max(job.size_bytes, total)
                if self.on_progress:
                    self.on_progress(job)
                return True

            success = fn(job.local_path, job.destination_path(), _progress_cb)

            with self._lock:
                cancelled = job.id in self._cancel_requested
                self._cancel_requested.discard(job.id)

            if cancelled:
                job.status = TransferStatus.CANCELLED
            elif success:
                job.status = TransferStatus.DONE
            else:
                job.status = TransferStatus.FAILED
                if not job.error:
                    job.error = "Transfer failed"
        except Exception as exc:
            with self._lock:
                self._cancel_requested.discard(job.id)
            job.status = TransferStatus.FAILED
            job.error = str(exc)

        self._finalise(job)

    def _finalise(self, job: TransferJob) -> None:
        """Mark job as finished and dispatch callbacks."""
        job.finished_at = time.time()
        with self._lock:
            self._current_jobs.discard(job.id)

        if job.status == TransferStatus.DONE:
            if self.on_completed:
                self.on_completed(job)
        elif job.status == TransferStatus.FAILED:
            # Auto-retry if allowed
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = TransferStatus.QUEUED
                job.progress = 0
                job.error = ""
                job.started_at = None
                job.finished_at = None
                logger.info("Retrying job %s (attempt %d)", job.id, job.retry_count)
                return  # will be picked up by _pick_next
            if self.on_failed:
                self.on_failed(job)
        # No callback for CANCELLED (user already knows)

    def _on_queue_empty(self) -> None:
        """Called when no jobs remain to process."""
        if self.on_queue_empty:
            self.on_queue_empty()
