# Copyright (C) 2026 Anaconda, Inc
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
    from conda.plugins.types import CondaExceptionEvent

logger = logging.getLogger(__name__)

telemetry = AnacondaTelemetry()


def plugin_pre_command(command: str) -> None:
    if context.plugins.anaconda_telemetry:
        try:
            telemetry.initialize()
        except Exception as e:
            logger.debug("Failed to initialize Anaconda Telemetry", exc_info=e)


@plugins.hookimpl
def conda_pre_commands():
    yield plugins.types.CondaPreCommand(
        name="conda-anaconda-telemetry",
        action=plugin_pre_command,
        run_for={"install"},
    )
        

# Generic error reporting function which can be expanded to track any error, as needed.
def report_error(event: CondaExceptionEvent) -> None:
    if telemetry.is_initialized():
        try:
            if not isinstance(event.exc_value, PackagesNotFoundError):
                return
            # TODO: Determine appropriate event name and body, and map specific 
            # attributes associated with the event.
            event_name = str(event.exc_type)
            event_body = str(event.exc_value)
            telemetry.send_event(event_name, event_body)
        except Exception as e:
            logger.debug("Failed to send conda exception event data", exc_info=e)


@plugins.hookimpl
def conda_exception_observers():
    yield plugins.types.CondaExceptionObserver(
        name="conda-anaconda-telemetry",
        hook=report_error,
        watch_for={"PackagesNotFoundError"},
    )
