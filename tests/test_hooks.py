import logging

import pytest

from anaconda_conda_telemetry.hooks import (
    conda_request_headers,
    HEADER_INSTALL,
    HEADER_CHANNELS,
    HEADER_SYS_INFO,
    HEADER_VIRTUAL_PACKAGES,
    HEADER_PACKAGES,
    HEADER_SEARCH,
    timer,
)


@pytest.fixture(autouse=True)
def packages(mocker):
    """
    Mocks ``anaconda_conda_telemetry.hooks.list_packages``
    """
    packages = [
        "defaults/osx-arm64::sqlite-3.45.3-h80987f9_0",
        "defaults/osx-arm64::pcre2-10.42-hb066dcc_1",
        "defaults/osx-arm64::libxml2-2.13.1-h0b34f26_2",
    ]

    def mock_list_packages(*args, **kwargs):
        return 0, packages

    mocker.patch("anaconda_conda_telemetry.hooks.list_packages", mock_list_packages)

    return packages


def test_conda_request_header_default_headers(mocker):
    """
    Ensure default headers are returned
    """
    mock_argparse_args = mocker.MagicMock(match_spec="package", cmd="search")
    mocker.patch(
        "anaconda_conda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )
    headers = {header.name: header for header in tuple(conda_request_headers())}

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


def test_conda_request_header_with_search(monkeypatch, mocker):
    """
    Ensure default headers are returned when conda search is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "search", "package"])
    mock_argparse_args = mocker.MagicMock(match_spec="package", cmd="search")
    mocker.patch(
        "anaconda_conda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers())}
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


def test_conda_request_header_with_install(monkeypatch, mocker):
    """
    Ensure default headers are returned when conda search is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "install", "package"])
    mock_argparse_args = mocker.MagicMock(packages=["package"], cmd="install")
    mocker.patch(
        "anaconda_conda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers())}
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


def test_timer_in_info_mode(caplog):
    """
    Ensure the timer decorator works and logs the time taken in INFO mode
    """
    caplog.set_level(logging.INFO)

    @timer
    def test():
        return 1

    assert test() == 1

    assert caplog.records[0].levelname == "INFO"

    assert "INFO     anaconda_conda_telemetry.hooks" in caplog.text
    assert "function: test; duration (seconds):" in caplog.text
