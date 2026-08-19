# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Gather installer and conda resource attributes for telemetry."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from conda import __version__ as conda_version
from conda.base.context import context, env_name

#: Required fields in ``.installer.info``, as written by constructor
INSTALLER_INFO_FIELDS = ("name", "version", "platform", "type")


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

    return {f"installer.{field}": data[field] for field in INSTALLER_INFO_FIELDS}


def get_conda_attributes() -> dict[str, str]:
    """Gather all ``conda.*`` resource attributes.

    ``ResourceAttributes.set_attributes()`` stores wildcard values via plain
    ``str()``, not ``json.dumps()`` - so non-string values (the bool and the
    dict here) are JSON-encoded ourselves first, otherwise they'd land in the
    signal as Python's ``repr()`` (single-quoted dicts), which isn't
    valid JSON.
    """
    plugins = context.plugins
    plugin_settings = {name: getattr(plugins, name) for name in plugins.parameter_names}
    # TODO: env_name() falls back to returning the full prefix path when the
    # env isn't under envs_dirs. Is that okay to
    # send as telemetry, or do we need to handle that case differently?
    return {
        "conda.version": conda_version,
        "conda.python_version": platform.python_version(),
        "conda.solver": context.solver,
        "conda.environment_name": env_name(
            context.active_prefix or context.root_prefix
        ),
        "conda.ci_detected": json.dumps(bool(os.environ.get("CI"))),
        "conda.plugins": json.dumps(plugin_settings),
    }
