# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Configuration and control class for Anaconda OpenTelemetry."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import anaconda_opentelemetry.signals as sig
from anaconda_opentelemetry.attributes import ResourceAttributes
from anaconda_opentelemetry.config import Configuration
from conda.base.context import context

from conda_anaconda_telemetry import APP_NAME, APP_VERSION
from conda_anaconda_telemetry.resource_attributes import (
    get_conda_attributes,
    get_installer_attributes,
)

try:
    from conda_anaconda_tos.exceptions import (
        CondaToSMissingError,
        CondaToSPermissionError,
    )
    from conda_anaconda_tos.local import get_local_metadata
except ImportError:
    get_local_metadata = None
    CondaToSMissingError = None
    CondaToSPermissionError = None

if TYPE_CHECKING:
    from typing import Any

    from conda.plugins.types import CondaExceptionEvent

logger = logging.getLogger(__name__)

#: Schema version for the created signal,
#: bump manually whenever this contents/shape change.
SIGNAL_VERSION = "1"

#: Placeholder item limit for list-valued event attributes.
LIST_ITEM_LIMIT = 50

#: Placeholder UTF-8 byte limit for list-valued event attributes.
LIST_BYTE_LIMIT = 500


class Environment(Enum):
    """Environment enum."""

    DEFAULT = ""
    TEST = "test"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class AnacondaTelemetry:
    """Anaconda Telemetry configuration and control class."""

    service_name: str = APP_NAME
    service_version: str = APP_VERSION.partition(".dev")[0]
    platform: str = "conda"
    environment: Environment = field(
        init=False,
        default_factory=lambda: Environment(
            os.getenv("ATEL_ENVIRONMENT", "production")
        ),
    )
    default_endpoint: str = field(init=False)

    def __post_init__(self) -> None:
        """Set the default endpoint based on the environment.

        If ATEL_DEFAULT_ENDPOINT is set, it will be used instead.
        """
        default_endpoint = os.getenv("ATEL_DEFAULT_ENDPOINT")
        if default_endpoint is not None:
            self.default_endpoint = default_endpoint
        elif self.environment.value == "staging":
            self.default_endpoint = "https://metrics.stage.anacondaconnect.com/v1/logs"
        elif self.environment.value in ("test", "development"):
            self.default_endpoint = "http://localhost:4318"
        else:
            self.default_endpoint = "https://public.telemetry.anaconda.com/v1/logs"

        parsed_endpoint = urlparse(self.default_endpoint)
        if parsed_endpoint.scheme not in ("http", "https", "grpc"):
            raise ValueError("A valid default endpoint must be set.")

        if parsed_endpoint.scheme == "http" and parsed_endpoint.hostname not in (
            "localhost",
            "127.0.0.1",
        ):
            raise ValueError("A valid default endpoint must be set.")

    def _make_config(self) -> Configuration:
        config = Configuration(default_endpoint=self.default_endpoint)
        if "localhost" in self.default_endpoint.lower():
            # Set the configuration for test and development
            config.set_skip_internet_check(True)
            config.set_console_exporter(True)
        return config

    def _make_attributes(self) -> ResourceAttributes:
        attributes = ResourceAttributes(
            self.service_name, self.service_version, anon_usage=True
        )
        attributes.set_attributes(
            platform=self.platform,
            environment=self.environment.value,
        )
        # Apply setattr() directly to ensure these are top-level attributes.
        for key, value in {
            **get_installer_attributes(),
            **get_conda_attributes(),
        }.items():
            setattr(attributes, key, value)
        return attributes

    def initialize(self) -> None:
        """Initialize telemetry."""
        sig.initialize_telemetry(
            config=self._make_config(),
            attributes=self._make_attributes(),
            signal_types=["logging"],
        )

    def send_event(
        self, event_name: str, body: str, attributes: dict[str, Any] | None = None
    ) -> None:
        """Send a telemetry event."""
        if attributes is None:
            attributes = {}

        logger.info("Sending a signal with event log data to the telemetry collector.")

        result = sig.send_event(
            event_name=event_name,
            body=body,
            attributes=attributes,
        )

        if result is True:
            logger.info("Event log sent successfully!")
        else:
            logger.debug("Event log failed to send.")


def tos_are_accepted(channel: str) -> bool | None:
    """Return whether channel's Terms of Service have been accepted.

    Returns None if conda-anaconda-tos is not installed, or if the channel
    has no local Terms of Service record at all.
    """
    if get_local_metadata is None:
        return None
    try:
        return get_local_metadata(channel).metadata.tos_accepted
    except CondaToSMissingError:
        # TODO: Discuss what action to take if no ToS record exists
        return None
    except CondaToSPermissionError:
        return None


def _truncate(
    items: list[Any],
    item_limit: int = LIST_ITEM_LIMIT,
    byte_limit: int = LIST_BYTE_LIMIT,
) -> tuple[list[Any], bool]:
    """Truncate a list to an item count and a serialized UTF-8 byte limit.

    Returns the possibly-shortened list and whether anything was dropped.
    """
    truncated = len(items) > item_limit
    kept: list[Any] = []
    for item in items[:item_limit]:
        candidate = [*kept, item]
        if len(json.dumps(candidate).encode("utf-8")) > byte_limit:
            truncated = True
            break
        kept = candidate
    return kept, truncated


def get_install_attributes(event: CondaExceptionEvent) -> dict[str, Any]:
    """Gather event attributes for the install-command PackagesNotFoundError signal."""
    argparse_args = context._argparse_args

    # context.channels is the fully merged channel list (CLI + condarc +
    # defaults); contrast with install.overrides below.
    channels, channels_truncated = _truncate(
        [
            {"channel": channel, "tos_accepted": tos_are_accepted(channel)}
            for channel in context.channels
        ]
    )
    # This invocation's -c/--channel overrides, not the merged channel list.
    overrides, overrides_truncated = _truncate(list(argparse_args.channel or []))
    packages, packages_truncated = _truncate(list(argparse_args.packages or []))
    missing_specs, missing_specs_truncated = _truncate(
        [str(spec) for spec in event.exc_value.packages]
    )

    return {
        "command": argparse_args.cmd,
        "event.schema_version": SIGNAL_VERSION,
        # JSON-encoded because OTel attributes can't hold a list of dicts.
        "install.condarc.channels": json.dumps(channels),
        "install.condarc.channel_priority": str(context.channel_priority),
        "install.override_channels": bool(argparse_args.override_channels),
        "install.cli.channels": overrides,
        "requested.packages": packages,
        "exception.name": event.exc_type.__name__,
        "exception.missing_specs": missing_specs,
        "truncated": channels_truncated
        or overrides_truncated
        or packages_truncated
        or missing_specs_truncated,
    }
