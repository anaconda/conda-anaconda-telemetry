# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import logging
import os
import platform
from types import SimpleNamespace
from typing import TYPE_CHECKING

import anaconda_opentelemetry.signals as sig
import pytest
from conda import __version__ as conda_version
from conda.exceptions import PackagesNotFoundError

from conda_anaconda_telemetry.otel import (
    LIST_BYTE_LIMIT,
    LIST_ITEM_LIMIT,
    OTHER_CHANNEL_LABEL,
    AnacondaTelemetry,
    get_install_attributes,
    get_success_attributes,
    package_names,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# The two hardcoded endpoints
DUMMY_ENDPOINT = "http://localhost:4318"
PRODUCTION_ENDPOINT = "https://public.telemetry.anaconda.com/v1/logs"
# Fake endpoints/proxies.
ATTACKER_ENDPOINT = "https://attacker.example.com:1234/v1/logs"
ATTACKER_PROXY = "http://attacker-proxy.example.com:1234"
TRUSTED_PROXY = "http://trusted-proxy.example.com:1234"


@pytest.mark.parametrize(
    "environment, default_endpoint",
    [
        ("production", PRODUCTION_ENDPOINT),
        ("staging", PRODUCTION_ENDPOINT),
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
    monkeypatch.setenv("ATEL_ENVIRONMENT", "production")
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    telemetry = AnacondaTelemetry()

    assert telemetry.default_endpoint == PRODUCTION_ENDPOINT


@pytest.mark.parametrize(
    "environment,expected",
    [
        ("development", True),
        ("production", False),
    ],
)
def test_make_config(
    monkeypatch: pytest.MonkeyPatch, environment: str, expected: bool
) -> None:
    """Only a localhost endpoint skips the internet check and uses the
    console exporter. ATEL_DEFAULT_ENDPOINT can no longer pick a non-loopback
    endpoint (Task 1), so this now varies via ATEL_ENVIRONMENT instead.
    """
    monkeypatch.setenv("ATEL_ENVIRONMENT", environment)

    config = AnacondaTelemetry()._make_config()

    assert config._get_skip_internet_check() is expected
    assert config._get_console_exporter() is expected


def test_make_attributes_system_info() -> None:
    """OS, Python, and conda version attributes reflect the real running system."""
    attributes = AnacondaTelemetry()._make_attributes()

    assert attributes.os_type == platform.system()
    assert attributes.os_version == platform.release()
    assert attributes.python_version == platform.python_version()
    assert getattr(attributes, "conda.version") == conda_version


@pytest.mark.parametrize(
    "specs,expected",
    [
        (["python >=3.11", "conda-forge::numpy"], ["numpy", "python"]),
        (["numpy", "numpy=1.0"], ["numpy"]),
    ],
)
def test_package_names_normalizes_specs(specs: list[str], expected: list[str]) -> None:
    """Strip version constraints and channel qualifiers, and dedupe names."""
    assert package_names(specs) == expected


@pytest.mark.parametrize(
    "specs",
    [
        # explicit package URL
        ["https://repo.anaconda.com/pkgs/main/linux-64/numpy-1.0-py38_0.tar.bz2"],
        # no exact name (wildcard)
        ["*"],
        # unparseable spec
        ["==invalid==spec=="],
    ],
)
def test_package_names_none_when_not_representable(specs: list[str]) -> None:
    """Return None when a spec can't be reduced to an exact package name."""
    assert package_names(specs) is None


@pytest.mark.parametrize("command", ["create", "install"])
def test_get_install_attributes(mocker: MockerFixture, command: str) -> None:
    """All install.* keys are assembled from the event and the captured request."""
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(channel_priority="strict"),
    )

    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=("pkg_foo",)),
        channels=(
            "defaults",
            "main",
            "main-x",
            "conda-forge",
            "some-private-channel",
        ),
    )
    attributes = get_install_attributes(
        event, command=command, requested_names=["pkg_foo", "pkg_bar"]
    )

    assert attributes == {
        "command": command,
        "event.schema_version": "1",
        "install.channels": [
            "defaults",
            "main",
            "main-x",
            "conda-forge",
            OTHER_CHANNEL_LABEL,
        ],
        "install.channel_priority": "strict",
        "requested.packages": ["pkg_foo", "pkg_bar"],
        "exception.name": "PackagesNotFoundError",
        "exception.missing_specs": ["pkg_foo"],
        "truncated": False,
    }


def test_get_install_attributes_cant_normalize(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The event is skipped when the exception's specs can't be normalized."""
    caplog.set_level(logging.DEBUG, logger="conda_anaconda_telemetry.otel")
    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=("*",)),
        channels=(),
    )

    assert (
        get_install_attributes(event, command="install", requested_names=["pkg_foo"])
        is None
    )
    assert caplog.messages == [
        "Skipping telemetry because package names could not be read."
    ]
    assert "*" not in caplog.text


@pytest.mark.parametrize(
    "packages,expected_kept,expected_truncated",
    [
        (["pkg_foo", "pkg_bar"], ["pkg_foo", "pkg_bar"], False),
        (
            # One more package than LIST_ITEM_LIMIT allows.
            [f"pkg_{i}" for i in range(LIST_ITEM_LIMIT + 1)],
            [f"pkg_{i}" for i in range(LIST_ITEM_LIMIT)],
            True,
        ),
        (
            # A first package that fits comfortably, and a second one whose
            # own serialized size alone already exceeds LIST_BYTE_LIMIT.
            ["pkg_foo", "x" * LIST_BYTE_LIMIT],
            ["pkg_foo"],
            True,
        ),
        (
            # Each item's raw length is well under the byte limit, but
            # summing them ignores the ", " separators added by JSON
            # serialization. This verifies the limit is checked against
            # the actual serialized size, not the raw concatenated length.
            ["x" * 163, "x" * 163, "x" * 163],
            ["x" * 163, "x" * 163],
            True,
        ),
    ],
)
def test_get_install_attributes_truncation(
    mocker: MockerFixture,
    packages: list[str],
    expected_kept: list[str],
    expected_truncated: bool,
) -> None:
    """requested.packages is capped by item count and by serialized byte size."""
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(channel_priority="strict"),
    )

    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=()),
        channels=(),
    )
    attributes = get_install_attributes(
        event, command="install", requested_names=packages
    )

    assert attributes is not None
    assert attributes["requested.packages"] == expected_kept
    assert attributes["truncated"] == expected_truncated


@pytest.mark.parametrize("command", ["install", "create"])
def test_get_success_attributes(mocker: MockerFixture, command: str) -> None:
    """Success attributes use the current schema plus resolved packages."""
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(channel_priority="strict"),
    )

    attributes = get_success_attributes(
        command=command,
        channels=["defaults", "main-x", "private-channel"],
        requested_names=["pkg_bar", "pkg_foo"],
        resolved_packages=["pkg_foo=9.9.9=1"],
    )

    assert attributes == {
        "command": command,
        "event.schema_version": "1",
        "install.channels": ["defaults", "main-x", OTHER_CHANNEL_LABEL],
        "install.channel_priority": "strict",
        "requested.packages": ["pkg_bar", "pkg_foo"],
        "resolved.packages": ["pkg_foo=9.9.9=1"],
        "truncated": False,
    }


def test_get_success_attributes_truncated_resolved_packages(
    mocker: MockerFixture,
) -> None:
    """truncated reflects resolved.packages truncation too, not just shared fields."""
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(channel_priority="strict"),
    )

    attributes = get_success_attributes(
        command="install",
        channels=[],
        requested_names=[],
        resolved_packages=[f"pkg_{i}=1=0" for i in range(LIST_ITEM_LIMIT + 1)],
    )

    # Byte limit (not item limit) is what trips first for these longer,
    # version-qualified package strings - see LIST_BYTE_LIMIT.
    assert len(attributes["resolved.packages"]) < LIST_ITEM_LIMIT
    assert attributes["truncated"] is True


def test_atel_default_endpoint_env_var_does_not_override_probe_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ATEL_DEFAULT_ENDPOINT must not redirect the SDK's internet-connectivity
    check to an attacker's host.
    """
    monkeypatch.setenv("ATEL_ENVIRONMENT", "production")
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", ATTACKER_ENDPOINT)

    telemetry = AnacondaTelemetry()
    config = telemetry._make_config()

    assert config._get_default_endpoint() == PRODUCTION_ENDPOINT
    assert config._endpoints["default_endpoint"].host == "public.telemetry.anaconda.com"


@pytest.mark.parametrize(
    "default_endpoint",
    [DUMMY_ENDPOINT, "http://127.0.0.1:4318"],
)
def test_make_config_loopback_forms_behave_the_same(
    monkeypatch: pytest.MonkeyPatch, default_endpoint: str
) -> None:
    """localhost and 127.0.0.1 should be treated the same way."""
    monkeypatch.setenv("ATEL_DEFAULT_ENDPOINT", default_endpoint)

    config = AnacondaTelemetry()._make_config()

    assert config._get_console_exporter() is True
    assert config._get_skip_internet_check() is True


def test_atel_logging_endpoint_env_var_does_not_override_pinned_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ATEL_LOGGING_ENDPOINT is read directly by Configuration.__init__ and
    must not be able to redirect the exporter away from the pinned endpoint.
    """
    monkeypatch.setenv("ATEL_LOGGING_ENDPOINT", ATTACKER_ENDPOINT)

    telemetry = AnacondaTelemetry()
    config = telemetry._make_config()

    # _get_logging_endpoint() appends "/v1/logs" when default_endpoint doesn't
    # already end with it, so compare with startswith rather than equality.
    assert config._get_logging_endpoint() != ATTACKER_ENDPOINT
    assert config._get_logging_endpoint().startswith(telemetry.default_endpoint)


@pytest.mark.parametrize(
    "environment, expected_default_endpoint",
    [
        ("production", PRODUCTION_ENDPOINT),
        ("staging", PRODUCTION_ENDPOINT),
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
    "env_var", ["OTEL_EXPORTER_OTLP_HEADERS", "OTEL_EXPORTER_OTLP_LOGS_HEADERS"]
)
def test_otlp_header_env_vars_are_neutralized(
    monkeypatch: pytest.MonkeyPatch, env_var: str
) -> None:
    """These headers must not reach the collector. The exporter reads them
    directly, so ignore_environment_variables=True alone does not stop them.
    """
    monkeypatch.setenv("ATEL_ENVIRONMENT", "production")
    monkeypatch.setenv(env_var, "x-injected=malicious")
    monkeypatch.setattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED", False)

    telemetry = AnacondaTelemetry()
    telemetry.initialize()

    exporter = sig._AnacondaLogger._instance.exporter._exporter
    assert "x-injected" not in exporter._session.headers


def test_otel_resource_attributes_env_var_is_neutralized_during_init(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """OTEL_RESOURCE_ATTRIBUTES must be absent during SDK init, then
    restored afterward for other tools that rely on it.
    """
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "foo.bar=something")
    monkeypatch.setattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED", False)

    seen_during_init = []

    def _capture_env(*_args: object, **_kwargs: object) -> None:
        seen_during_init.append(os.environ.get("OTEL_RESOURCE_ATTRIBUTES"))

    mocker.patch.object(sig, "initialize_telemetry", side_effect=_capture_env)

    AnacondaTelemetry().initialize()

    assert seen_during_init == [None]
    assert os.environ["OTEL_RESOURCE_ATTRIBUTES"] == "foo.bar=something"


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
    """The proxy must come from conda's own settings, never from
    ATEL_PROXY_URL. Pins ATEL_ENVIRONMENT=production so the test doesn't
    rely on CI's global ATEL_ENVIRONMENT=test env var to pass.
    """
    from conda.base.context import context

    monkeypatch.setenv("ATEL_ENVIRONMENT", "production")
    monkeypatch.setenv("ATEL_PROXY_URL", ATTACKER_PROXY)
    monkeypatch.setitem(context._cache_, "proxy_servers", proxy_servers)

    config = AnacondaTelemetry()._make_config()

    assert config._get_proxy_url() == expected_proxy_url
