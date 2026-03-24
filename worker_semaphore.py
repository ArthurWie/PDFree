"""Global concurrency cap for QThread save workers."""

import os
from PySide6.QtCore import QSemaphore

MAX_CONCURRENT = max(4, os.cpu_count() or 4)
_sem = QSemaphore(MAX_CONCURRENT)


def acquire():
    _sem.acquire(1)


def release():
    _sem.release(1)
