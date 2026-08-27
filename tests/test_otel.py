# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import anaconda_opentelemetry.signals as sig
import pytest

from conda_anaconda_telemetry import otel
from conda_anaconda_telemetry.otel import AnacondaTelemetry

DUMMY_ENDPOINT = "http://localhost:4318"


@pytest.mark.parametrize(
    "environment, default_endpoint",
    [
        ("production", "https://public.telemetry.anaconda.com/v1/logs"),
        ("staging", "https://metrics.stage.anacondaconnect.com/v1/logs"),
        ("test", DUMMY_ENDPOINT),
        ("development", DUMMY_ENDPOINT),
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
    "default_endpoint",
    [
        "http://other.example.com",
        "http://localhost.example.com",
        "http://127.0.0.1.example.com",
    ],
)
def test_anaconda_telemetry_rejects_non_loopback_cleartext(
    monkeypatch: pytest.MonkeyPatch, default_endpoint: str
) -> None:
    """An endpoint using cleartext http on a non-loopback host raises
    instead of silently sending telemetry to an arbitrary host.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    with pytest.raises(ValueError, match=r"^A valid default endpoint must be set\.$"):
        AnacondaTelemetry()


@pytest.mark.parametrize(
    "default_endpoint,expected_console_exporter",
    [
        (DUMMY_ENDPOINT, True),
        ("https://public.telemetry.anaconda.com/v1/logs", False),
    ],
)
def test_make_config(
    monkeypatch: pytest.MonkeyPatch,
    default_endpoint: str,
    expected_console_exporter: bool,
) -> None:
    """Only a localhost endpoint uses the console exporter, but every
    endpoint skips the internet check and defers shutdown timing to us
    (instead of an unbounded atexit handler), regardless of environment.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    config = AnacondaTelemetry()._make_config()

    # Never probe connectivity before sending an event, no matter the endpoint.
    assert config._get_skip_internet_check() is True
    # Never let the SDK register its own unbounded atexit shutdown; we call
    # AnacondaTelemetry.shutdown() ourselves with a fixed timeout instead.
    assert config._get_shutdown_on_exit() is False
    assert config._get_console_exporter() is expected_console_exporter


def test_anaconda_telemetry_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """shutdown() flushes and shuts down telemetry within a fixed time budget
    instead of relying on the SDK's own unbounded atexit handler.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", DUMMY_ENDPOINT)
    # Record what AnacondaTelemetry.shutdown() actually passes through to the
    # library, rather than calling the real shutdown_telemetry().
    recorded_kwargs = {}

    def fake_shutdown_telemetry(**kwargs: float) -> None:
        recorded_kwargs.update(kwargs)

    monkeypatch.setattr(sig, "shutdown_telemetry", fake_shutdown_telemetry)

    AnacondaTelemetry().shutdown()

    assert recorded_kwargs == {"timeout_seconds": otel._SHUTDOWN_TIMEOUT_SECONDS}


def test_send_event_always_shuts_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_event() must flush via shutdown() even when the send itself fails,
    since nothing else is left to flush a queued event (shutdown_on_exit is
    turned off in _make_config()).
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", DUMMY_ENDPOINT)

    def mock_send_event(**_kwargs: str) -> None:
        raise RuntimeError("fail")

    monkeypatch.setattr(sig, "send_event", mock_send_event)
    shutdown_calls = []
    monkeypatch.setattr(
        sig, "shutdown_telemetry", lambda **kwargs: shutdown_calls.append(kwargs)
    )

    with pytest.raises(RuntimeError, match="fail"):
        AnacondaTelemetry().send_event("install.error", "")

    assert shutdown_calls == [{"timeout_seconds": otel._SHUTDOWN_TIMEOUT_SECONDS}]
