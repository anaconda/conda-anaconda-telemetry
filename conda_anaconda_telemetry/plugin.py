# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that sends telemetry data when conda commands are executed."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from conda import plugins
from conda.base.context import context
from conda.exceptions import PackagesNotFoundError

from conda_anaconda_telemetry.otel import AnacondaTelemetry

if TYPE_CHECKING:
    from collections.abc import Generator

    from conda.plugins.types import (
        CondaExceptionEvent,
        CondaExceptionObserver,
    )

logger = logging.getLogger(__name__)


# Generic error reporting function which can be expanded to track any error, as needed.
def report_error(event: CondaExceptionEvent) -> None:
    """Report an error to telemetry."""
    if context.plugins.anaconda_telemetry:  # Confirm plugin is enabled
        conda_command = context._argparse_args.cmd
        # Only send telemetry for PackagesNotFoundError (and its subclasses)
        # during install command
        if not (
            isinstance(event.exc_value, PackagesNotFoundError)
            and conda_command == "install"
        ):
            return
        try:
            telemetry = AnacondaTelemetry()
            logger.info("Initializing telemetry...")
            telemetry.initialize()
            logger.info("Telemetry initialized successfully!")
        except Exception as e:
            logger.debug("Failed to initialize telemetry", exc_info=e)
            return
        logger.info(
            "Using send_event to send a signal for conda exception event: %s",
            event.exc_type,
        )
        try:
            # TODO: Determine appropriate event name and body, and map specific
            # attributes associated with the event.
            event_name = ""
            event_body = ""
            telemetry.send_event(event_name, event_body)
        except Exception as e:
            logger.debug(
                "Failed to send telemetry for conda exception event", exc_info=e
            )


@plugins.hookimpl
def conda_exception_observers() -> Generator[CondaExceptionObserver, None, None]:
    """Register report_error() function as a conda exception observers hook."""
    yield plugins.types.CondaExceptionObserver(
        name="conda-anaconda-telemetry",
        hook=report_error,
        watch_for={"PackagesNotFoundError"},
    )
