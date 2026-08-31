# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import anaconda_opentelemetry.signals as sig
import pytest

from conda_anaconda_telemetry.otel import AnacondaTelemetry

# The three endpoints AnacondaTelemetry actually hardcodes per environment.
DUMMY_ENDPOINT = "http://localhost:4318"
PRODUCTION_ENDPOINT = "https://public.telemetry.anaconda.com/v1/logs"
STAGING_ENDPOINT = "https://metrics.stage.anacondaconnect.com/v1/logs"
# Made-up values standing in for an attacker/trusted endpoint or proxy, not real.
ATTACKER_ENDPOINT = "https://attacker.example.com:1234/v1/logs"
ATTACKER_PROXY = "http://attacker-proxy.example.com:1234"
TRUSTED_PROXY = "http://trusted-proxy.example.com:1234"


@pytest.mark.parametrize(
    "environment, default_endpoint",
    [
        ("production", PRODUCTION_ENDPOINT),
        ("staging", STAGING_ENDPOINT),
        ("test", DUMMY_ENDPOINT),
        ("development", DUMMY_ENDPOINT),
        ("", PRODUCTION_ENDPOINT),
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
    [
        "ftp://example.com",
        "not-a-url",
        "http://other.example.com",
        "http://localhost.example.com",
        "http://127.0.0.1.example.com",
        "http://[::1]:1234",
        ATTACKER_ENDPOINT,
        "grpc://attacker.example.com:1234",
    ],
)
def test_atel_default_endpoint_falls_through_for_untrusted_values(
    monkeypatch: pytest.MonkeyPatch, default_endpoint: str
) -> None:
    """Any ATEL_DEFAULT_ENDPOINT that isn't a loopback http collector is
    ignored, falling through to the fixed default_endpoint, instead of
    raising or letting it redirect telemetry to an arbitrary host.
    """
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    telemetry = AnacondaTelemetry()

    assert telemetry.default_endpoint == PRODUCTION_ENDPOINT


@pytest.mark.parametrize(
    "default_endpoint,expected",
    [
        (DUMMY_ENDPOINT, True),
        (PRODUCTION_ENDPOINT, False),
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


def test_atel_logging_endpoint_env_var_does_not_override_pinned_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ATEL_LOGGING_ENDPOINT is read directly by Configuration.__init__ and
    must not be able to redirect the exporter away from the pinned endpoint.
    """
    monkeypatch.setenv("ATEL_LOGGING_ENDPOINT", ATTACKER_ENDPOINT)

    telemetry = AnacondaTelemetry()
    config = telemetry._make_config()

    assert config._get_logging_endpoint() == telemetry.default_endpoint


@pytest.mark.parametrize(
    "environment, expected_default_endpoint",
    [
        ("production", PRODUCTION_ENDPOINT),
        ("staging", STAGING_ENDPOINT),
        ("test", DUMMY_ENDPOINT),
        ("development", DUMMY_ENDPOINT),
        ("", PRODUCTION_ENDPOINT),
    ],
)
def test_atel_environment_cannot_be_combined_with_atel_default_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    expected_default_endpoint: str,
) -> None:
    """ATEL_ENVIRONMENT only ever selects among the fixed per-environment
    URLs; combined with an attacker-chosen ATEL_DEFAULT_ENDPOINT it still
    cannot pick an arbitrary destination.
    """
    monkeypatch.setenv("ATEL_ENVIRONMENT", environment)
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", ATTACKER_ENDPOINT)

    telemetry = AnacondaTelemetry()

    assert telemetry.default_endpoint == expected_default_endpoint


@pytest.mark.parametrize(
    "env_var", ["ATEL_LOGGING_AUTH_TOKEN", "ATEL_DEFAULT_AUTH_TOKEN"]
)
def test_auth_token_env_vars_are_neutralized(
    monkeypatch: pytest.MonkeyPatch, env_var: str
) -> None:
    """Neither ATEL_LOGGING_AUTH_TOKEN nor ATEL_DEFAULT_AUTH_TOKEN may inject
    an auth token: the plugin does not send one today, so none should reach
    the resolved Configuration regardless of these variables.
    """
    monkeypatch.setenv(env_var, "attacker-supplied-token")

    config = AnacondaTelemetry()._make_config()

    assert config._get_auth_token_logging() is None


@pytest.mark.parametrize(
    "proxy_servers,expected_proxy_url",
    [
        ({}, None),
        ({"https": TRUSTED_PROXY}, TRUSTED_PROXY),
        ({"https://public.telemetry.anaconda.com": TRUSTED_PROXY}, TRUSTED_PROXY),
    ],
)
def test_proxy_url_comes_from_conda_not_atel_proxy_url(
    monkeypatch: pytest.MonkeyPatch,
    proxy_servers: dict[str, str],
    expected_proxy_url: str | None,
) -> None:
    """The resolved proxy must always come from conda's own proxy_servers
    config (bare scheme, scheme://host, or none configured), never from an
    attacker-controlled ATEL_PROXY_URL, which is read directly by
    Configuration.__init__.
    """
    from conda.base.context import context

    monkeypatch.setenv("ATEL_PROXY_URL", ATTACKER_PROXY)
    monkeypatch.setitem(context._cache_, "proxy_servers", proxy_servers)

    config = AnacondaTelemetry()._make_config()

    assert config._get_proxy_url() == expected_proxy_url
