# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Configuration and control class for Anaconda OpenTelemetry."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import anaconda_opentelemetry.signals as sig
from anaconda_opentelemetry.attributes import ResourceAttributes
from anaconda_opentelemetry.config import Configuration
from conda.base.context import context
from conda.exceptions import InvalidMatchSpec
from conda.models.match_spec import MatchSpec

from conda_anaconda_telemetry import APP_NAME, APP_VERSION
from conda_anaconda_telemetry.resource_attributes import (
    get_conda_attributes,
    get_installer_attributes,
)

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

#: Channel names allowed in the install.channels payload; anything else is
#: reported as OTHER_CHANNEL_LABEL so a channel URL or internal name can't
#: reach the payload.
KNOWN_INSTALL_CHANNELS = frozenset({"defaults", "main", "main-x", "conda-forge"})
OTHER_CHANNEL_LABEL = "other"


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
        # TODO(#236): Disable session IDs once the required SDK release is available.
        if "localhost" in self.default_endpoint.lower():
            # Set the configuration for test and development
            config.set_skip_internet_check(True)
            config.set_console_exporter(True)
        return config

    def _make_attributes(self) -> ResourceAttributes:
        # TODO(#236): Exclude hostname once the required SDK release is available.
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
        resource_attributes = os.environ.pop("OTEL_RESOURCE_ATTRIBUTES", None)
        try:
            sig.initialize_telemetry(
                config=self._make_config(),
                attributes=self._make_attributes(),
                signal_types=["logging"],
            )
        finally:
            if resource_attributes is not None:
                os.environ["OTEL_RESOURCE_ATTRIBUTES"] = resource_attributes

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


def package_names(specs: list[Any]) -> list[str] | None:
    """Return exact names, or None when the request cannot be represented."""
    names = set()
    for value in specs:
        try:
            spec = MatchSpec(value)
        except InvalidMatchSpec:
            return None

        name = spec.get_exact_value("name")
        if (
            spec.get_raw_value("url")
            or not name
            or not re.fullmatch(r"[a-z0-9_.-]+", name)
        ):
            return None
        names.add(name)

    return sorted(names)


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


def _get_command_attributes(
    *, command: str, channels: list[str], requested_names: list[str]
) -> tuple[dict[str, Any], bool]:
    """Build fields shared by install/create error and success events."""
    safe_channels, channels_truncated = _truncate(
        [
            channel if channel in KNOWN_INSTALL_CHANNELS else OTHER_CHANNEL_LABEL
            for channel in channels
        ]
    )
    packages, packages_truncated = _truncate(requested_names)
    return (
        {
            "command": command,
            "event.schema_version": SIGNAL_VERSION,
            "install.channels": safe_channels,
            "install.channel_priority": str(context.channel_priority),
            "requested.packages": packages,
        },
        channels_truncated or packages_truncated,
    )


def get_install_attributes(
    event: CondaExceptionEvent,
    *,
    command: str,
    requested_names: list[str],
) -> dict[str, Any] | None:
    """Build the event from captured package names and the failure snapshot."""
    missing_names = package_names(list(event.exc_value.packages))
    if missing_names is None:
        logger.debug("Skipping telemetry because package names could not be read.")
        return None

    attributes, truncated = _get_command_attributes(
        command=command,
        channels=list(event.channels or ()),
        requested_names=requested_names,
    )
    missing_specs, missing_specs_truncated = _truncate(missing_names)

    return {
        **attributes,
        "exception.name": event.exc_type.__name__,
        "exception.missing_specs": missing_specs,
        "truncated": truncated or missing_specs_truncated,
    }


def get_success_attributes(
    *,
    command: str,
    channels: list[str],
    requested_names: list[str],
    resolved_packages: list[str],
) -> dict[str, Any]:
    """Build attributes for an install/create success signal."""
    attributes, truncated = _get_command_attributes(
        command=command, channels=channels, requested_names=requested_names
    )
    resolved, resolved_truncated = _truncate(resolved_packages)

    return {
        **attributes,
        "resolved.packages": resolved,
        "truncated": truncated or resolved_truncated,
    }
