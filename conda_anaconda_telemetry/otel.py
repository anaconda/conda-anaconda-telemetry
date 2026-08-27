# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Configuration and control class for Anaconda OpenTelemetry."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import anaconda_opentelemetry.signals as sig
from anaconda_opentelemetry.attributes import ResourceAttributes
from anaconda_opentelemetry.config import Configuration

from conda_anaconda_telemetry import APP_NAME, APP_VERSION
from conda_anaconda_telemetry.resource_attributes import (
    get_conda_attributes,
    get_installer_attributes,
)

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


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

        if urlparse(self.default_endpoint).scheme not in ("http", "https", "grpc"):
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
            **get_installer_attributes(),
            **get_conda_attributes(),
        )
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
