# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Contains various utilities used throughout the plugin."""

import functools
import logging
import time
from typing import Callable

logger = logging.getLogger("conda_anaconda_telemetry")


def timer(func: Callable) -> Callable:
    """Log the duration of a function call."""

    @functools.wraps(func)
    def wrapper_timer(*args: tuple, **kwargs: dict) -> Callable:
        """Wrap the given function."""
        if logger.getEffectiveLevel() <= logging.INFO:
            tic = time.perf_counter()
            value = func(*args, **kwargs)
            toc = time.perf_counter()
            elapsed_time = toc - tic
            logger.info(
                "function: %s; duration (seconds): %0.4f",
                func.__name__,
                elapsed_time,
            )
            return value

        return func(*args, **kwargs)

    return wrapper_timer
