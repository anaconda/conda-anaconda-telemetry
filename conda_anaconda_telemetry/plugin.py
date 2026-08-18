# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that sends telemetry data when conda commands are executed."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from conda import plugins
from conda.base.context import context

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
        # Only send telemetry during install command
        if conda_command != "install":
            return
        try:
            telemetry = AnacondaTelemetry()
            telemetry.initialize()
        except Exception as e:
            logger.debug(
                "Failed to initialize telemetry for %s", event.exc_type, exc_info=e
            )
            return
        try:
            # anaconda-client's telemetry event naming convention: bare verb
            # for the command, no "conda-" prefix.
            telemetry.send_event(conda_command, "")
        except Exception as e:
            logger.debug("Failed to send telemetry for %s", event.exc_type, exc_info=e)


@plugins.hookimpl
def conda_exception_observers() -> Generator[CondaExceptionObserver, None, None]:
    """Register report_error() function as a conda exception observers hook."""
    yield plugins.types.CondaExceptionObserver(
        name="conda-anaconda-telemetry",
        hook=report_error,
        watch_for={"PackagesNotFoundError"},
    )
