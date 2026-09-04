# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that sends telemetry data when conda commands are executed."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from conda.base.context import context

from conda_anaconda_telemetry.otel import AnacondaTelemetry, get_install_attributes

if TYPE_CHECKING:
    from conda.plugins.types import (
        CondaExceptionEvent,
    )

logger = logging.getLogger(__name__)


# Generic error reporting function which can be expanded to track any error, as needed.
def report_error(event: CondaExceptionEvent) -> None:
    """Report an error to telemetry."""
    if context.plugins.anaconda_telemetry:  # Confirm plugin is enabled
        conda_command = context._argparse_args.cmd
        # Only send telemetry during install and create commands.
        # Note: conda has a pre-existing edge case where a third-party solver
        # can cause install() to raise PackageNotInstalledError even outside
        # of update, which this guard wouldn't catch. Needs its own follow-up.
        if conda_command not in {"install", "create"}:
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
            # anaconda-client's telemetry event naming convention
            event_name = f"{conda_command}.pnfe"
            attributes = get_install_attributes(event)
            telemetry.send_event(event_name, "", attributes)
        except Exception as e:
            logger.debug("Failed to send telemetry for %s", event.exc_type, exc_info=e)
