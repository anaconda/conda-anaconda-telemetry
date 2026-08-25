# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import anaconda_opentelemetry.signals as sig
import pytest

from conda_anaconda_telemetry.otel import AnacondaTelemetry


@pytest.mark.parametrize(
    "environment, default_endpoint",
    [
        ("production", "https://public.telemetry.anaconda.com/v1/logs"),
        ("staging", "https://metrics.stage.anacondaconnect.com/v1/logs"),
        ("test", "http://localhost:4318"),
        ("development", "http://localhost:4318"),
        ("", "https://public.telemetry.anaconda.com/v1/logs"),
    ],
)
def test_anaconda_telemetry(
    monkeypatch: pytest.MonkeyPatch, environment: str, default_endpoint: str
) -> None:
    monkeypatch.setenv("ATEL_ENVIRONMENT", environment)
    monkeypatch.setattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED", False)

    telemetry = AnacondaTelemetry()
    # Confirm telemetry was configured correctly but not initialized
    assert telemetry.environment.value == environment
    assert telemetry.default_endpoint == default_endpoint
    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is False

    try:
        telemetry.initialize()
    except Exception as e:
        pytest.fail(f"Failed to initialize Anaconda Telemetry: {e}")

    # Confirm telemetry initialized successfully
    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is True


@pytest.mark.parametrize(
    "default_endpoint",
    ["ftp://example.com", "not-a-url"],
)
def test_anaconda_telemetry_invalid_scheme(
    monkeypatch: pytest.MonkeyPatch, default_endpoint: str
) -> None:
    """An endpoint with an unsupported or missing scheme raises instead of
    silently accepting a broken default_endpoint.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    with pytest.raises(ValueError, match=r"^A valid default endpoint must be set\.$"):
        AnacondaTelemetry()


@pytest.mark.parametrize(
    "default_endpoint,expected",
    [
        ("http://localhost:4318", True),
        ("https://public.telemetry.anaconda.com/v1/logs", False),
    ],
)
def test_make_config(
    monkeypatch: pytest.MonkeyPatch, default_endpoint: str, expected: bool
) -> None:
    """Only a localhost endpoint skips the internet check and uses the
    console exporter.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    config = AnacondaTelemetry()._make_config()

    assert config._get_skip_internet_check() is expected
    assert config._get_console_exporter() is expected
