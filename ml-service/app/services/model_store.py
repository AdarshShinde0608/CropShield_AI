from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import platform
import re
import time
from pathlib import Path
from typing import Any

from app.core.model import ModelRuntime, load_model

logger = logging.getLogger(__name__)
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def process_memory_bytes() -> int:
    """Return current resident memory on supported Linux and Windows hosts."""
    host_platform = platform.system()
    if host_platform == "Linux":
        with Path("/proc/self/statm").open(encoding="ascii") as source:
            resident_pages = int(source.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    if host_platform == "Windows":
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.WorkingSetSize)
    raise OSError("process RSS measurement is supported only on Linux and Windows")


class ModelStore:
    """Atomically manages checksum-verified, image-baked model runtimes."""

    def __init__(
        self,
        collection: Any,
        models_root: Path,
        refresh_interval_seconds: float,
    ) -> None:
        self._collection = collection
        self._models_root = models_root
        self._refresh_interval_seconds = refresh_interval_seconds
        self._runtime = ModelRuntime(None, None, {}, False, "MODEL_NOT_LOADED")
        self._readiness_error: str | None = None
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self._model_load_time_ms: float | None = None

    @property
    def runtime(self) -> ModelRuntime:
        return self._runtime

    @property
    def ready(self) -> bool:
        return self._runtime.ready and self._readiness_error is None

    @property
    def error_code(self) -> str | None:
        if self._readiness_error is not None:
            return self._readiness_error
        return self._runtime.error_code

    async def start(self) -> None:
        started = time.perf_counter()
        await self.refresh_once()
        try:
            memory = process_memory_bytes()
        except (OSError, ValueError, IndexError) as error:
            memory = None
            logger.warning(
                "process_memory_measurement_failed",
                extra={
                    "event": "process_memory_measurement_failed",
                    "error_type": type(error).__name__,
                },
            )
        logger.info(
            "model_store_startup",
            extra={
                "event": "model_store_startup",
                "startup_elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "model_load_time_ms": self._model_load_time_ms,
                "process_memory_bytes": memory,
                "model_loaded": self._runtime.ready,
                "model_version": self._runtime.version,
            },
        )
        self._refresh_task = asyncio.create_task(
            self._refresh_loop(),
            name="active-model-refresh",
        )

    async def stop(self) -> None:
        task = self._refresh_task
        self._refresh_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def refresh_once(self) -> bool:
        """Load and atomically publish a newer active version if fully verified."""
        async with self._refresh_lock:
            try:
                record = await self._collection.find_one(
                    {"status": "active"},
                    {
                        "_id": 0,
                        "model_version": 1,
                        "artifact_checksums": 1,
                        "weights_stored": 1,
                    },
                )
            except Exception as error:
                logger.warning(
                    "active_model_lookup_failed",
                    extra={
                        "event": "active_model_lookup_failed",
                        "error_type": type(error).__name__,
                    },
                )
                if not self._runtime.ready:
                    self._readiness_error = None
                    self._runtime = ModelRuntime(
                        None, None, {}, False, "MODEL_NOT_LOADED"
                    )
                return False

            if record is None:
                if not self._runtime.ready:
                    self._readiness_error = None
                    self._runtime = ModelRuntime(
                        None, None, {}, False, "MODEL_NOT_LOADED"
                    )
                return False

            version = record.get("model_version")
            checksums = record.get("artifact_checksums")
            if (
                not isinstance(version, str)
                or not _VERSION_PATTERN.fullmatch(version)
                or not isinstance(checksums, dict)
                or not checksums
                or any(
                    not isinstance(name, str)
                    or not isinstance(checksum, str)
                    or not _SHA256_PATTERN.fullmatch(checksum)
                    for name, checksum in checksums.items()
                )
                or record.get("weights_stored") is True
            ):
                return self._reject_candidate("MODEL_MISMATCH")

            if self._runtime.ready and self._runtime.version == version:
                card_checksums = (self._runtime.card or {}).get("artifact_checksums")
                if card_checksums != checksums:
                    return self._reject_candidate("MODEL_MISMATCH")
                self._readiness_error = None
                return True

            version_dir = self._version_directory(version)
            load_started = time.perf_counter()
            candidate = load_model(
                version_dir,
                expected_version=version,
                expected_checksums=checksums,
            )
            self._model_load_time_ms = round(
                (time.perf_counter() - load_started) * 1000,
                2,
            )
            if not candidate.ready:
                return self._reject_candidate(
                    candidate.error_code or "MODEL_MISMATCH"
                )

            self._runtime = candidate
            self._readiness_error = None
            logger.info(
                "active_model_loaded",
                extra={
                    "event": "active_model_loaded",
                    "model_version": version,
                    "model_load_time_ms": self._model_load_time_ms,
                },
            )
            return True

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_interval_seconds)
            await self.refresh_once()

    def _version_directory(self, version: str) -> Path:
        root = self._models_root.resolve()
        path = root / version
        resolved = path.resolve()
        if (
            path.is_symlink()
            or not path.is_dir()
            or root not in resolved.parents
        ):
            return root / "__missing_active_model_version__"
        return path

    def _reject_candidate(self, error_code: str) -> bool:
        if not self._runtime.ready:
            self._runtime = ModelRuntime(
                self._runtime.version,
                None,
                {},
                False,
                error_code,
            )
        self._readiness_error = error_code
        logger.error(
            "active_model_rejected",
            extra={
                "event": "active_model_rejected",
                "failure_code": error_code,
                "previous_model_retained": self._runtime.ready,
            },
        )
        return False
