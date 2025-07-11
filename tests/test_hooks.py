# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from conda_anaconda_telemetry.hooks import (
    HEADER_CHANNELS,
    HEADER_INSTALL,
    HEADER_PACKAGES,
    HEADER_SEARCH,
    HEADER_SYS_INFO,
    HEADER_VIRTUAL_PACKAGES,
    SIZE_LIMIT,
    _conda_request_headers,
    conda_request_headers,
    conda_settings,
    should_submit_request_headers,
    timer,
)

if TYPE_CHECKING:
    from pytest import CaptureFixture, MonkeyPatch
    from pytest_mock import MockerFixture


#: Host used across all tests
TEST_HOST = "repo.anaconda.com"

TEST_PACKAGES = [
    "defaults/osx-arm64::sqlite-3.45.3-h80987f9_0",
    "defaults/osx-arm64::pcre2-10.42-hb066dcc_1",
    "defaults/osx-arm64::libxml2-2.13.1-h0b34f26_2",
]


def mock_list_packages(*args: tuple, **kwargs: dict) -> tuple:  # noqa: ARG001
    return 0, TEST_PACKAGES


@pytest.fixture(autouse=True)
def packages(mocker: MockerFixture) -> list:
    """
    Mocks ``conda_anaconda_telemetry.hooks.list_packages``
    """
    mocker.patch("conda_anaconda_telemetry.hooks.list_packages", mock_list_packages)
    return TEST_PACKAGES


@pytest.mark.parametrize(
    "host,path",
    [
        ("repo.anaconda.com", ""),  # Empty path should work for repo.anaconda.com
        (
            "repo.anaconda.com",
            "/some/path",
        ),  # Any path should work for repo.anaconda.com
        ("conda.anaconda.org", "/conda-forge/"),  # Exact match for conda.anaconda.org
        ("conda.anaconda.org", "/conda-forge/noarch/pkg.conda"),  # Prefix match
    ],
)
def test_default_headers(mocker: MockerFixture, host: str, path: str) -> None:
    """
    Ensure default headers are returned for matching host/path combinations
    """
    mock_argparse_args = mocker.MagicMock(match_spec="package", cmd="search")
    mocker.patch(
        "conda_anaconda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )
    headers = {
        header.name: header for header in tuple(conda_request_headers(host, path))
    }

    expected_header_names_values = {
        HEADER_SYS_INFO: "",
        HEADER_CHANNELS: "",
        HEADER_PACKAGES: "",
        HEADER_VIRTUAL_PACKAGES: "",
    }
    expected_header_names = {key for key, _ in expected_header_names_values.items()}

    assert len(set(headers.keys()).intersection(expected_header_names)) == len(
        expected_header_names
    )


@pytest.mark.parametrize(
    "host,path",
    [
        ("repo.anaconda.com", ""),
        ("conda.anaconda.org", "/conda-forge/"),
    ],
)
def test_search_headers(
    monkeypatch: MonkeyPatch, mocker: MockerFixture, host: str, path: str
) -> None:
    """
    Ensure search headers are returned when conda search is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "search", "package"])
    mock_argparse_args = mocker.MagicMock(match_spec="package", cmd="search")
    mocker.patch(
        "conda_anaconda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers(host, path))}
    expected_header_names = {
        HEADER_SYS_INFO,
        HEADER_CHANNELS,
        HEADER_PACKAGES,
        HEADER_VIRTUAL_PACKAGES,
        HEADER_SEARCH,
    }

    assert len(header_names.intersection(expected_header_names)) == len(
        expected_header_names
    )


@pytest.mark.parametrize(
    "host,path",
    [
        ("repo.anaconda.com", ""),
        ("conda.anaconda.org", "/conda-forge/"),
    ],
)
def test_install_headers(
    monkeypatch: MonkeyPatch, mocker: MockerFixture, host: str, path: str
) -> None:
    """
    Ensure install headers are returned when conda install is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "install", "package"])
    mock_argparse_args = mocker.MagicMock(packages=["package"], cmd="install")
    mocker.patch(
        "conda_anaconda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers(host, path))}
    expected_header_names = {
        HEADER_SYS_INFO,
        HEADER_CHANNELS,
        HEADER_PACKAGES,
        HEADER_VIRTUAL_PACKAGES,
        HEADER_INSTALL,
    }

    assert len(header_names.intersection(expected_header_names)) == len(
        expected_header_names
    )


def test_disabled_plugin(mocker: MockerFixture) -> None:
    """
    Make sure that nothing is returned when the plugin is disabled via settings
    """
    mocker.patch(
        "conda_anaconda_telemetry.hooks.context.plugins.anaconda_telemetry", False
    )
    assert not tuple(conda_request_headers(TEST_HOST, ""))


def test_timer_in_info_mode(caplog: CaptureFixture) -> None:
    """
    Ensure the timer decorator works and logs the time taken in INFO mode
    """
    caplog.set_level(logging.INFO)

    @timer
    def test() -> int:
        return 1

    assert test() == 1

    assert caplog.records[0].levelname == "INFO"

    assert "INFO     conda_anaconda_telemetry.hooks" in caplog.text
    assert "function: test; duration (seconds):" in caplog.text


def test_conda_settings() -> None:
    """
    Ensure the correct conda settings are returned
    """
    settings = list(conda_settings())

    assert len(settings) == 1
    assert settings[0].name == "anaconda_telemetry"
    assert settings[0].description == "Whether Anaconda Telemetry is enabled"
    assert settings[0].parameter.default.value is True


def test_exception_handling(mocker: MockerFixture, caplog: CaptureFixture) -> None:
    """
    When any exception is encountered, ``conda_request_headers`` should return nothing
    and log a debug message.
    """
    caplog.set_level(logging.DEBUG)
    mocker.patch(
        "conda_anaconda_telemetry.hooks.get_sys_info_header_value",
        side_effect=Exception("Boom"),
    )

    assert list(conda_request_headers(TEST_HOST, "")) == []
    assert caplog.records[0].levelname == "DEBUG"
    assert "Failed to collect telemetry data" in caplog.text
    assert "Exception: Boom" in caplog.text


def test_conda_request_headers_with_non_matching_url() -> None:
    """
    When a non-matching host is used, ``conda_request_headers`` should return nothing.
    """
    assert list(conda_request_headers("https://example.com", "")) == []


@pytest.mark.parametrize(
    "command,argparse_mock",
    (
        (
            ["conda", "install", "package"],
            MagicMock(packages=["package"], cmd="install"),
        ),
        (
            ["conda", "search", "package"],
            MagicMock(match_spec=["package"], cmd="search"),
        ),
        (["conda", "update", "package"], MagicMock(packages=["package"], cmd="update")),
    ),
)
def test_header_wrapper_size_limit_constraint(
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    command: list[str],
    argparse_mock: MagicMock,
) -> None:
    """
    Ensures that the size limit is being adhered to when all ``HeaderWrapper``
    objects are combined
    """
    monkeypatch.setattr("sys.argv", command)
    mocker.patch("conda_anaconda_telemetry.hooks.context._argparse_args", argparse_mock)

    headers = _conda_request_headers()
    assert sum(header.size_limit for header in headers) <= SIZE_LIMIT


@pytest.mark.parametrize(
    "host,path,expected",
    [
        # repo.anaconda.com with empty path pattern - should match any path
        ("repo.anaconda.com", "", True),
        ("repo.anaconda.com", "/some/path", True),
        ("repo.anaconda.com", "/anaconda-cloud/noarch/package.conda", True),
        # conda.anaconda.org with /conda-forge/ path pattern - should match prefix
        ("conda.anaconda.org", "/conda-forge/", True),
        ("conda.anaconda.org", "/conda-forge/noarch/package.conda", True),
        ("conda.anaconda.org", "/conda-forge/linux-64/package.conda", True),
        # conda.anaconda.org with non-matching paths
        ("conda.anaconda.org", "/conda-forge", False),  # Missing trailing slash
        ("conda.anaconda.org", "/different-channel", False),
        ("conda.anaconda.org", "", False),
        # Non-matching hosts
        ("example.com", "", False),
        ("example.com", "/conda-forge/", False),
        ("other.anaconda.com", "/conda-forge/", False),
    ],
)
def test_should_submit_request_headers(host: str, path: str, expected: bool) -> None:
    """
    Test that should_submit_request_headers correctly matches host and path patterns.
    """
    assert should_submit_request_headers(host, path) == expected


def test_patterns_validation() -> None:
    """
    Test that should_submit_request_headers works with the actual
    REQUEST_HEADER_PATTERN regex.
    """
    from conda_anaconda_telemetry.hooks import REQUEST_HEADER_PATTERN

    # Verify the REQUEST_HEADER_PATTERN is a compiled regex
    assert hasattr(REQUEST_HEADER_PATTERN, 'match')
    assert hasattr(REQUEST_HEADER_PATTERN, 'pattern')

    # Test matching cases
    assert should_submit_request_headers("repo.anaconda.com", "/any/path") is True
    assert (
        should_submit_request_headers(
            "conda.anaconda.org", "/conda-forge/linux-64/pkg.conda"
        )
        is True
    )

    # Test non-matching cases
    assert (
        should_submit_request_headers("conda.anaconda.org", "/other-channel") is False
    )
    assert (
        should_submit_request_headers("conda.anaconda.org", "/conda-forge") is False
    )  # Missing trailing slash
    assert should_submit_request_headers("unknown.com", "/conda-forge/") is False


@pytest.mark.parametrize(
    "host,path",
    [
        ("example.com", ""),  # Non-matching host
        ("conda.anaconda.org", "/different-channel"),  # Wrong path prefix
        ("conda.anaconda.org", "/conda-forge"),  # Missing trailing slash
        ("repo.anaconda.com.evil.com", "/conda-forge/"),  # Host spoofing attempt
    ],
)
def test_non_matching_patterns(mocker: MockerFixture, host: str, path: str) -> None:
    """
    Ensure no headers are returned for non-matching host/path combinations
    """
    mock_argparse_args = mocker.MagicMock(match_spec="package", cmd="search")
    mocker.patch(
        "conda_anaconda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    headers = list(conda_request_headers(host, path))
    assert headers == []
