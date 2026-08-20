# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from conda_anaconda_telemetry.resource_attributes import (
    get_conda_attributes,
    get_installer_attributes,
    to_environment_kind,
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
    "prefix,root_prefix,env_name_return,expected",
    [
        ("/opt/conda", "/opt/conda", "base", "base"),  # root prefix itself
        ("/opt/conda/envs/myenv", "/opt/conda", "myenv", "named"),  # under envs_dirs
        (
            "/some/random/path",
            "/opt/conda",
            "/some/random/path",  # env_name() falls back to the raw prefix
            "prefix",
        ),
    ],
)
def test_to_environment_kind(
    mocker: MockerFixture,
    prefix: str,
    root_prefix: str,
    env_name_return: str,
    expected: str,
) -> None:
    """Verify base/named/prefix are detected correctly."""
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(root_prefix=root_prefix),
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.env_name",
        return_value=env_name_return,
    )

    assert to_environment_kind(prefix) == expected


def test_get_conda_attributes(monkeypatch: MonkeyPatch, mocker: MockerFixture) -> None:
    """All six conda.* keys are assembled with the expected values."""
    mock_plugins = SimpleNamespace(anaconda_telemetry=False)
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(
            solver="asolver",
            active_prefix="/envs/myenv",
            plugins=mock_plugins,
        ),
    )
    mocker.patch("conda_anaconda_telemetry.resource_attributes.conda_version", "26.5")
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.platform.python_version",
        return_value="3.11.15",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.to_environment_kind",
        return_value="named",
    )
    monkeypatch.setenv("CI", "true")

    assert get_conda_attributes() == {
        "conda.version": "26.5",
        "conda.python_version": "3.11.15",
        "conda.solver": "asolver",
        "conda.environment_kind": "named",
        "conda.ci_detected": "true",
        "conda.plugins": '{"anaconda_telemetry": false}',
    }


def test_get_conda_attributes_no_ci(
    monkeypatch: MonkeyPatch, mocker: MockerFixture
) -> None:
    """ci_detected is false when the CI env var is absent."""
    mock_plugins = SimpleNamespace()
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(
            solver="classic",
            active_prefix=None,
            root_prefix="/root",
            plugins=mock_plugins,
        ),
    )
    mocker.patch("conda_anaconda_telemetry.resource_attributes.conda_version", "26.5")
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.platform.python_version",
        return_value="3.11.15",
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.to_environment_kind",
        return_value="base",
    )
    monkeypatch.delenv("CI", raising=False)

    result = get_conda_attributes()
    assert result["conda.ci_detected"] == "false"
    assert result["conda.plugins"] == "{}"
