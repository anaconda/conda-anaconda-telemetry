# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from conda_anaconda_telemetry.resource_attributes import (
    get_conda_attributes,
    get_conda_build_attributes,
    get_installer_attributes,
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
    "installer.name": INSTALLER_INFO["name"],
    "installer.version": INSTALLER_INFO["version"],
    "installer.platform": INSTALLER_INFO["platform"],
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


def test_get_conda_attributes(monkeypatch: MonkeyPatch, mocker: MockerFixture) -> None:
    """Both conda.* keys are assembled with the expected values."""
    mocker.patch("conda_anaconda_telemetry.resource_attributes.conda_version", "26.5")
    monkeypatch.setenv("CI", "true")

    assert get_conda_attributes() == {
        "conda.version": "26.5",
        "conda.ci_detected": "true",
    }


def test_get_conda_attributes_no_ci(monkeypatch: MonkeyPatch) -> None:
    """ci_detected is false when the CI env var is absent."""
    monkeypatch.delenv("CI", raising=False)

    result = get_conda_attributes()
    assert result["conda.ci_detected"] == "false"


def test_get_conda_build_version(mocker: MockerFixture) -> None:
    """conda.build.version is assembled with the expected value."""
    mock_conda_build = mocker.MagicMock()
    mock_conda_build.__version__ = "26.7.1"

    mocker.patch.dict(
        "sys.modules",
        {"conda_build": mock_conda_build},
    )

    assert get_conda_build_attributes() == {
        "conda.build.version": "26.7.1",
    }


def test_get_conda_build_version_not_installed(mocker: MockerFixture) -> None:
    """conda.build.version is 'n/a' when conda-build is not installed."""
    mocker.patch.dict(
        "sys.modules",
        {"conda_build": None},
    )

    assert get_conda_build_attributes() == {
        "conda.build.version": "n/a",
    }