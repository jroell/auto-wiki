import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any


@contextmanager
def log_duration(logger: logging.Logger, label: str, extra: Optional[Dict[str, Any]] = None):
    """
    Context manager to log how long a block takes.

    Args:
        logger: Logger to emit timing to.
        label: Short description of the work being timed.
        extra: Optional dict of extra fields to include in the log.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        payload = {"duration_ms": round(elapsed_ms, 2)}
        if extra:
            payload.update(extra)
        logger.info(f"{label} completed", extra={"timing": payload})
