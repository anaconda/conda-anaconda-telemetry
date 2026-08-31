# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Gather installer and conda resource attributes for telemetry."""

from __future__ import annotations

import json
import os
from pathlib import Path

from conda import __version__ as conda_version
from conda.auxlib.type_coercion import boolify
from conda.base.context import context

#: Required fields in ``.installer.info``, as written by constructor
INSTALLER_INFO_FIELDS = ("name", "version", "platform", "type")

#: Subset of ``INSTALLER_INFO_FIELDS`` on the approved schema as attributes
INSTALLER_ATTRIBUTE_FIELDS = ("name", "version", "platform")


def get_installer_attributes() -> dict[str, str]:
    """Read constructor's installer metadata from the base prefix.

    Returns an empty dict if ``.installer.info`` is missing or malformed,
    rather than raising - telemetry init must not fail because of this file.

    TODO: this duplicates conda's own conda.cli.main_info.get_installer_info(),
    which isn't available in the minimum conda version we support yet
    """
    path = Path(context.root_prefix, ".installer.info")
    try:
        with path.open() as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}

    if not isinstance(data, dict) or any(
        not isinstance(data.get(field), str) or not data[field]
        for field in INSTALLER_INFO_FIELDS
    ):
        return {}

    return {f"installer.{field}": data[field] for field in INSTALLER_ATTRIBUTE_FIELDS}


def get_conda_attributes() -> dict[str, str]:
    """Gather all ``conda.*`` resource attributes.

    Some related attributes, such as ``python.version``, ``os.type``, and
    ``os.version``, are not gathered here since ``ResourceAttributes``
    already supplies them.

    Non-string values must be JSON-encoded before being returned:
    ``ResourceAttributes.set_attributes()`` stores wildcard values via
    ``str()``, not ``json.dumps()``, which would otherwise produce Python's
    ``repr()`` instead of valid JSON.
    """
    return {
        "conda.version": conda_version,
        "conda.ci_detected": json.dumps(boolify(os.environ.get("CI", ""))),
    }
