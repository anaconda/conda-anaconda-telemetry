# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that sends telemetry data when conda commands are executed."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from conda.base.context import context
from conda.exceptions import PackagesNotFoundInChannelsError

from conda_anaconda_telemetry.otel import (
    AnacondaTelemetry,
    get_install_attributes,
    package_names,
)

if TYPE_CHECKING:
    from conda.models.match_spec import MatchSpec
    from conda.plugins.types import (
        CondaExceptionEvent,
    )

logger = logging.getLogger(__name__)


# Change `str, Enum` to StrEnum once we drop Python 3.10.
class TelemetryCommand(str, Enum):
    """Supported commands for telemetry tracking."""

    INSTALL = "install"


@dataclass
class CommandRequest:
    """Tracks telemetry state for the current command.

    Populated during pre-command/pre-solve hooks.
    Read and cleared by the exception observer or post-command hook.
    """

    command: TelemetryCommand | None = None
    requested_names: list[str] | None = None


command_request = CommandRequest()


def capture_command(command: str) -> None:
    """Pre-command hook to record the active command and reset old state."""
    command_request.requested_names = None
    if context.plugins.anaconda_telemetry and command == TelemetryCommand.INSTALL:
        command_request.command = TelemetryCommand(command)
    else:
        command_request.command = None


def capture_requested_packages(
    specs_to_add: frozenset[MatchSpec], _specs_to_remove: frozenset[MatchSpec]
) -> None:
    """Pre-solve hook to extract and save requested package names from specs."""
    if (
        context.plugins.anaconda_telemetry
        and command_request.command == TelemetryCommand.INSTALL
    ):
        command_request.requested_names = package_names(list(specs_to_add))


def clear_command(_command_name: str | None = None) -> None:
    """Reset telemetry state.

    Runs after commands finish or inside error handling blocks when hooks fail.
    """
    command_request.command = None
    command_request.requested_names = None


# Generic error reporting function which can be expanded to track any error, as needed.
def report_error(event: CondaExceptionEvent) -> None:
    """Report an error to telemetry."""
    try:
        if not context.plugins.anaconda_telemetry:  # Confirm plugin is enabled
            return
        command = command_request.command
        requested_names = command_request.requested_names
        if command != TelemetryCommand.INSTALL or requested_names is None:
            return
        # Guard again even though the observer is only registered for this
        # class, in case of a name collision in `watch_for`.
        if not isinstance(event.exc_value, PackagesNotFoundInChannelsError):
            return

        attributes = get_install_attributes(
            event, command=command.value, requested_names=requested_names
        )
        if attributes is None:
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
            event_name = f"{command.value}.pnfe"
            telemetry.send_event(event_name, "", attributes)
        except Exception as e:
            logger.debug("Failed to send telemetry for %s", event.exc_type, exc_info=e)
    finally:
        # Post-command hooks don't run on failure, so clear state here too.
        clear_command()
