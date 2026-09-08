from __future__ import annotations

import os
import hashlib
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


def _lock_key(path: Path) -> str:
    value = str(path.resolve())
    return value.casefold() if os.name == "nt" else value


def _thread_lock(key: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _windows_named_mutex(key: str) -> Iterator[None]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    wait = kernel32.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    release = kernel32.ReleaseMutex
    release.argtypes = (wintypes.HANDLE,)
    release.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL

    name = "shawei-" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    handle = create_mutex(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        result = wait(handle, 0xFFFFFFFF)
        if result not in (0x00000000, 0x00000080):
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = True
        yield
    finally:
        if acquired:
            release(handle)
        close(handle)


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Lock one target without creating a sidecar file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = _lock_key(path)
    with _thread_lock(key):
        if os.name == "nt":
            with _windows_named_mutex(key):
                yield
        else:
            # ponytail: current deployment is Windows; add a platform-native
            # named mutex here only if cross-process POSIX writers are deployed.
            yield


def _atomic_write_text_unlocked(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    with file_lock(path):
        _atomic_write_text_unlocked(path, text, encoding)
