# Copyright (C) 2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Anaconda OpenTelemetry SDK configuration and control functions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import anaconda_opentelemetry.signals as sig
from anaconda_opentelemetry.attributes import ResourceAttributes
from anaconda_opentelemetry.config import Configuration

from conda_anaconda_telemetry import APP_NAME, APP_VERSION


@dataclass
class AnacondaTelemetry:
    service_name: str = APP_NAME
    service_version: str = APP_VERSION.rsplit(".", 1)[0]
    platform: str = "conda"
    environment: str = field(default_factory=lambda: os.getenv("ATEL_ENVIRONMENT", "production"))
    default_endpoint: str = field(init=False)

    def __post_init__(self) -> None:
        """Set the default endpoint using ATEL_DEFAULT_ENDPOINT environment variable."""
        if self.environment in ("production", "prod"):
            self.default_endpoint = os.getenv(
                "ATEL_DEFAULT_ENDPOINT",
                "https://public.telemetry.anaconda.com/v1/logs",
            )
        elif self.environment in ("staging", "stage", "stg", "testing", "test"):
            self.default_endpoint = os.getenv(
                "ATEL_DEFAULT_ENDPOINT",
                "https://metrics.stage.anacondaconnect.com/v1/logs",
            )
        elif self.environment in ("development", "develop", "dev", "local"):
            self.default_endpoint = os.getenv(
                "ATEL_DEFAULT_ENDPOINT",
                "http://localhost:4318",
            )
        else:
            self.default_endpoint = os.getenv("ATEL_DEFAULT_ENDPOINT")

        if not self.default_endpoint.strip():
            raise ValueError("A default endpoint is not set.")

    def _make_config(self) -> Configuration:
        if "localhost" in self.default_endpoint.lower():
            config = Configuration(default_endpoint=self.default_endpoint)\
                .set_console_exporter(True).set_skip_internet_check(True)
        else:
            config = Configuration(default_endpoint=self.default_endpoint)
        return config

    def _make_attributes(self) -> ResourceAttributes:
        attributes = ResourceAttributes(self.service_name, self.service_version, anon_usage = True)
        attributes.set_attributes(
                platform=self.platform,
                environment=self.environment,
        )
        return attributes
    
    def initialize(self) -> None:
        self.config = self._make_config()
        self.attributes = self._make_attributes()
        sig.initialize_telemetry(self.config, self.attributes, signal_types=["logging"])

    def is_initialized(self) -> bool:
        if getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is False:
            return False
        elif getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is True:
            return True
        else:
            raise ValueError("Anaconda Telemetry is in an unknown state")

    def send_event(self, event_name: str, body: str, attributes: dict[str, Any] = {}) -> None:
        sig.send_event(
            event_name=event_name,
            body=body,
            attributes=attributes,
        )
