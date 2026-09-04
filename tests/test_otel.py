# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
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
    AnacondaTelemetry,
    get_install_attributes,
    tos_are_accepted,
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


def test_tos_are_accepted_package_not_installed(mocker: MockerFixture) -> None:
    """When conda_anaconda_tos isn't importable, ToS acceptance is None."""
    mocker.patch("conda_anaconda_telemetry.otel.get_local_metadata", None)

    assert tos_are_accepted("defaults") is None


def test_tos_are_accepted_no_local_record(mocker: MockerFixture) -> None:
    """When the channel has no local ToS record, ToS acceptance is None."""

    class _FakeMissingError(Exception):
        pass

    mocker.patch(
        "conda_anaconda_telemetry.otel.CondaToSMissingError", _FakeMissingError
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.get_local_metadata",
        mocker.MagicMock(side_effect=_FakeMissingError("no record")),
    )

    assert tos_are_accepted("main-x") is None


def test_tos_are_accepted_permission_error(mocker: MockerFixture) -> None:
    """A permission error reading local ToS metadata means ToS acceptance is None."""

    class _FakeMissingError(Exception):
        pass

    class _FakePermissionError(Exception):
        pass

    mocker.patch(
        "conda_anaconda_telemetry.otel.CondaToSMissingError", _FakeMissingError
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.CondaToSPermissionError", _FakePermissionError
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.get_local_metadata",
        mocker.MagicMock(side_effect=_FakePermissionError("permission denied")),
    )

    assert tos_are_accepted("main-x") is None


def test_tos_are_accepted_real_record(mocker: MockerFixture) -> None:
    """When a local ToS record exists, its tos_accepted value is returned."""
    fake_pair = mocker.MagicMock()
    fake_pair.metadata.tos_accepted = True
    mocker.patch(
        "conda_anaconda_telemetry.otel.get_local_metadata",
        mocker.MagicMock(return_value=fake_pair),
    )

    assert tos_are_accepted("main-x") is True


@pytest.mark.parametrize("cmd", ["install", "create"])
def test_get_install_attributes(mocker: MockerFixture, cmd: str) -> None:
    """All install.* keys are assembled from context / argparse args.

    Key names stay `install.*`-prefixed regardless of command.
    """
    argparse_args = SimpleNamespace(
        cmd=cmd,
        override_channels=False,
        channel_priority="strict",
        channel=["conda-forge", "foobar"],
        packages=["pkg_foo", "defaults::pkg_bar"],
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(
            _argparse_args=argparse_args,
            channels=("defaults", "main-x"),
            channel_priority="strict",
        ),
    )
    mocker.patch("conda_anaconda_telemetry.otel.tos_are_accepted", return_value=True)

    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=("pkg_foo",)),
    )
    attributes = get_install_attributes(event)

    assert attributes == {
        "command": cmd,
        "event.schema_version": "1",
        "install.condarc.channels": json.dumps(
            [
                {"channel": "defaults", "tos_accepted": True},
                {"channel": "main-x", "tos_accepted": True},
            ]
        ),
        "install.condarc.channel_priority": "strict",
        "install.override_channels": False,
        "install.cli.channels": ["conda-forge", "foobar"],
        "requested.packages": ["pkg_foo", "defaults::pkg_bar"],
        "exception.name": "PackagesNotFoundError",
        "exception.missing_specs": ["pkg_foo"],
        "truncated": False,
    }


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
    """install.packages is capped by item count and by serialized byte size."""
    argparse_args = SimpleNamespace(
        cmd="install",
        override_channels=False,
        channel_priority="strict",
        channel=[],
        packages=packages,
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        mocker.MagicMock(
            _argparse_args=argparse_args,
            channels=(),
            channel_priority="strict",
        ),
    )
    mocker.patch("conda_anaconda_telemetry.otel.tos_are_accepted", return_value=True)

    event = SimpleNamespace(
        exc_type=PackagesNotFoundError,
        exc_value=SimpleNamespace(packages=()),
    )
    attributes = get_install_attributes(event)

    assert attributes["requested.packages"] == expected_kept
    assert attributes["truncated"] == expected_truncated
