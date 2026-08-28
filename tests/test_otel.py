# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import anaconda_opentelemetry.signals as sig
import pytest
from conda.exceptions import PackagesNotFoundError

from conda_anaconda_telemetry.otel import (
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


def test_tos_are_accepted_real_record(mocker: MockerFixture) -> None:
    """When a local ToS record exists, its tos_accepted value is returned."""
    fake_pair = mocker.MagicMock()
    fake_pair.metadata.tos_accepted = True
    mocker.patch(
        "conda_anaconda_telemetry.otel.get_local_metadata",
        mocker.MagicMock(return_value=fake_pair),
    )

    assert tos_are_accepted("main-x") is True


def test_get_install_attributes(mocker: MockerFixture) -> None:
    """All install.* keys are assembled from context / argparse args."""
    argparse_args = SimpleNamespace(
        cmd="install",
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

    event = SimpleNamespace(exc_type=PackagesNotFoundError)
    attributes = get_install_attributes(event)

    assert attributes == {
        "signal.name": "install",
        "signal.version": "1",
        "install.condarc.channels": [
            {"channel": "defaults", "tos_accepted": True},
            {"channel": "main-x", "tos_accepted": True},
        ],
        "install.condarc.channel_priority": "strict",
        "install.override_channels": False,
        "install.overrides": ["conda-forge", "foobar"],
        "install.packages": ["pkg_foo", "defaults::pkg_bar"],
        "exception.name": "PackagesNotFoundError",
    }
