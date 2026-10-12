# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from conda_anaconda_telemetry.resource_attributes import (
    INSTALLER_INFO_FIELD_LENGTH_LIMIT,
    INSTALLER_INFO_FILE_SIZE_LIMIT,
    get_conda_attributes,
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

#: Sample metadata with a field longer than INSTALLER_INFO_FIELD_LENGTH_LIMIT
OVERSIZED_FIELD_INFO = {
    **INSTALLER_INFO,
    "name": "x" * (INSTALLER_INFO_FIELD_LENGTH_LIMIT + 10),
}

#: Sample metadata with a field exactly at INSTALLER_INFO_FIELD_LENGTH_LIMIT
MAX_LENGTH_FIELD_INFO = {
    **INSTALLER_INFO,
    "name": "x" * INSTALLER_INFO_FIELD_LENGTH_LIMIT,
}

#: Metadata whose serialized size exceeds INSTALLER_INFO_FILE_SIZE_LIMIT
OVERSIZED_FILE_INFO = {
    **INSTALLER_INFO,
    "name": "x" * INSTALLER_INFO_FILE_SIZE_LIMIT,
}


@pytest.mark.parametrize(
    "file_content,expected",
    [
        pytest.param(json.dumps(INSTALLER_INFO), INSTALLER_ATTRIBUTES, id="valid"),
        pytest.param(None, {}, id="missing-file"),
        pytest.param("not valid json", {}, id="malformed-json"),
        pytest.param(json.dumps({"name": "Foo"}), {}, id="missing-fields"),
        pytest.param(json.dumps(OVERSIZED_FIELD_INFO), {}, id="oversized-field"),
        pytest.param(
            json.dumps(MAX_LENGTH_FIELD_INFO),
            {**INSTALLER_ATTRIBUTES, "installer.name": MAX_LENGTH_FIELD_INFO["name"]},
            id="max-length-field",
        ),
        pytest.param(json.dumps(OVERSIZED_FILE_INFO), {}, id="oversized-file"),
    ],
)
def test_get_installer_attributes(
    tmp_path: Path,
    mocker: MockerFixture,
    file_content: str | None,
    expected: dict[str, str],
) -> None:
    """File present/missing/malformed/partial/oversized never raises."""
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
