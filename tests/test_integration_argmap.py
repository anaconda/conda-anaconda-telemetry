# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import pytest
from pytest_mock import MockerFixture

from conda_anaconda_telemetry.hooks import get_export_header_value


@pytest.mark.parametrize(
    "arg_attrs, expected_substring",
    [
        ({"channel": ["c1", "c2"]}, "channels:c1,c2"),
        ({"override_channels": True}, "override_channels:True"),
        ({"export_platforms": ["osx-64", "linux-64"]}, "platforms:osx-64,linux-64"),
        ({"override_platforms": ["glibc"]}, "override_platforms:['glibc']"),
        ({"file": "environment.yml"}, "file:environment.yml"),
        ({"file": "/abs/path/to/env.yaml"}, "file:/abs/path/to/env.yaml"),
        ({"format": "json"}, "format:json"),
        ({"no_builds": True}, "no_builds:true"),
        ({"ignore_channels": True}, "ignore_channels:true"),
        ({"from_history": True}, "from_history:true"),
        ({"json": True}, "json:true"),
        # Combined
        ({"format": "yaml", "no_builds": True}, "format:yaml;no_builds:true"),
    ],
)
def test_integration_arg_map(
    mocker: MockerFixture, arg_attrs: dict, expected_substring: str
) -> None:
    """
    Integration-style test to verify arg_map definitions and transformations.
    """
    mock_argparse_args = mocker.MagicMock()

    # Defaults mimicking a clean state
    defaults: dict = {
        "channel": None,
        "override_channels": False,
        "export_platforms": None,
        "override_platforms": False,
        "file": None,
        "format": None,
        "no_builds": False,
        "ignore_channels": False,
        "from_history": False,
        "json": False,
        "cmd": "export",
        "packages": [],
        "match_spec": None,
    }
    mock_argparse_args.configure_mock(**defaults)
    mock_argparse_args.configure_mock(**arg_attrs)

    mock_pm = mocker.MagicMock()
    mock_exporter = mocker.MagicMock()
    mock_exporter.name = "test_exporter"
    mock_pm.detect_environment_exporter.return_value = mock_exporter
    mock_pm.get_environment_exporter_by_format.return_value = mock_exporter

    mock_context = mocker.MagicMock(
        _argparse_args=mock_argparse_args,
        plugin_manager=mock_pm,
        active_prefix=None,
        root_prefix="/opt/mock/prefix",
    )

    mocker.patch("conda_anaconda_telemetry.hooks.context", mock_context)
    mocker.patch(
        "conda_anaconda_telemetry.hooks.list_packages", return_value=(None, [])
    )

    # Clear the LRU cache to ensure we don't get stale results
    get_export_header_value.__wrapped__.cache_clear()  # type: ignore[attr-defined]

    value = get_export_header_value()

    # Split by separator to verify inclusion of the substring
    if ";" in expected_substring:
        sub_parts = expected_substring.split(";")
        parts = value.split(";")
        for part in sub_parts:
            assert part in parts
    else:
        # Check against full set of parts
        parts = value.split(";")
        assert expected_substring in parts
