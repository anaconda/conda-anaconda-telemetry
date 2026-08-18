# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from conda_anaconda_telemetry.resource_attributes import (
    get_ci_detected,
    get_conda_attributes,
    get_installer_attributes,
    get_plugin_names,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch
    from pytest_mock import MockerFixture

#: Sample installer metadata, as constructor would write it
INSTALLER_INFO = {
    "name": "Foo",
    "version": "1.2.3",
    "platform": "linux-64",
    "type": "sh",
}

#: Expected result of gathering ``INSTALLER_INFO``
INSTALLER_ATTRIBUTES = {
    "installer.name": "Foo",
    "installer.version": "1.2.3",
    "installer.platform": "linux-64",
    "installer.type": "sh",
}


@pytest.mark.parametrize(
    "file_content,expected",
    [
        (json.dumps(INSTALLER_INFO), INSTALLER_ATTRIBUTES),
        (None, {}),  # file missing entirely
        ("not valid json", {}),  # malformed JSON
        (json.dumps({"name": "Foo"}), {}),  # missing required fields
    ],
)
def test_get_installer_attributes(
    tmp_path: Path,
    mocker: MockerFixture,
    file_content: str | None,
    expected: dict[str, str],
) -> None:
    """File present/missing/malformed/partial never raises."""
    if file_content is not None:
        (tmp_path / ".installer.info").write_text(file_content)
    # context.root_prefix is a read-only property, so the whole `context`
    # reference used by this module is swapped out instead of patching it.
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(root_prefix=str(tmp_path)),
    )

    assert get_installer_attributes() == expected


@pytest.mark.parametrize(
    "env_value,expected",
    [("true", True), (None, False)],
)
def test_get_ci_detected(
    monkeypatch: MonkeyPatch, env_value: str | None, expected: bool
) -> None:
    if env_value is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", env_value)

    assert get_ci_detected() is expected


def test_get_plugin_names(mocker: MockerFixture) -> None:
    mock_manager = mocker.MagicMock()
    mock_manager.list_name_plugin.return_value = [
        ("conda_anaconda_telemetry.plugin", object()),
        ("conda_lockfiles.plugin", object()),
    ]
    # context.plugin_manager is a read-only property, so the whole `context`
    # reference used by this module is swapped out instead of patching it.
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(plugin_manager=mock_manager),
    )

    assert get_plugin_names() == [
        "conda_anaconda_telemetry.plugin",
        "conda_lockfiles.plugin",
    ]


def test_get_conda_attributes(mocker: MockerFixture) -> None:
    """All six conda.* keys are assembled with the expected values."""
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_conda_version",
        return_value="26.5",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_python_version",
        return_value="3.11.15",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_solver",
        return_value="asolver",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_environment_name",
        return_value="myenv",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_ci_detected",
        return_value=True,
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.get_plugin_names",
        return_value=["conda_anaconda_telemetry.plugin"],
    )

    assert get_conda_attributes() == {
        "conda.version": "26.5",
        "conda.python_version": "3.11.15",
        "conda.solver": "asolver",
        "conda.environment_name": "myenv",
        "conda.ci_detected": "true",
        "conda.plugins": '["conda_anaconda_telemetry.plugin"]',
    }
