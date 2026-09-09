# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

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
    package_names,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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


def test_get_install_attributes(mocker: MockerFixture) -> None:
    """All install.* keys are assembled from the event and the captured request."""
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(channel_priority="strict"),
    )

    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=("pkg_foo",)),
        channels=("defaults", "main-x", "some-private-channel"),
    )
    attributes = get_install_attributes(
        event, command="install", requested_names=["pkg_foo", "pkg_bar"]
    )

    assert attributes == {
        "command": "install",
        "event.schema_version": "1",
        "install.channels": ["defaults", "main-x", OTHER_CHANNEL_LABEL],
        "install.channel_priority": "strict",
        "requested.packages": ["pkg_foo", "pkg_bar"],
        "exception.name": "PackagesNotFoundError",
        "exception.missing_specs": ["pkg_foo"],
        "truncated": False,
    }


def test_get_install_attributes_cant_normalize() -> None:
    """The event is skipped when the exception's specs can't be normalized."""
    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=("*",)),
        channels=(),
    )

    assert (
        get_install_attributes(event, command="install", requested_names=["pkg_foo"])
        is None
    )


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
