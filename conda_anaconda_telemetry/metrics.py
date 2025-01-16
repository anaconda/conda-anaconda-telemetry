# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Holds the backend independent logic for collecting telemetry data about a conda
installation/environment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from conda import __version__ as conda_version
from conda.base.context import context
from conda.cli.main_list import list_packages
from conda.common.url import mask_anaconda_token
from conda.models.channel import all_channel_urls

try:
    from conda_build import __version__ as conda_build_version
except ImportError:
    conda_build_version = "n/a"


def get_virtual_packages() -> tuple[str, ...]:
    """Retrieve the registered virtual packages from conda's context."""
    return tuple(
        f"{package.name}={package.version}={package.build}"
        for package in context.plugin_manager.get_virtual_package_records()
    )


def get_channel_urls() -> tuple[str, ...]:
    """Return a list of currently configured channel URLs with tokens masked."""
    channels = list(all_channel_urls(context.channels))
    return tuple(mask_anaconda_token(c) for c in channels)


def get_conda_command() -> str:
    """Use ``sys.argv`` to determine the conda command that is current being run."""
    return context._argparse_args.cmd


def get_package_list() -> tuple[str, ...]:
    """Retrieve the list of packages in the current environment."""
    prefix = context.active_prefix or context.root_prefix
    _, packages = list_packages(prefix, format="canonical")

    return packages


def get_search_term() -> str:
    """Retrieve the search term being used when search command is run."""
    return context._argparse_args.match_spec


def get_install_arguments() -> tuple[str, ...]:
    """Get the parsed position argument."""
    return context._argparse_args.packages


@dataclass(frozen=True, slots=True)
class SysInfo:
    """Holds specific system information about a conda installation/environment."""

    conda_build_version: str
    conda_command: str
    python_implementation: str | None = None
    python_version: str | None = None
    conda_version: str | None = None
    solver_version: str | None = None
    platform_system: str | None = None
    platform_release: str | None = None

    dict = asdict


def get_sys_info(extra: bool = False) -> SysInfo:
    """When ``extra`` is True, return additional system information.

    The extra information provided is information normally submitted by the
    ``conda.base.context.Context.solver_user_agent`` method.
    """
    if extra:
        return SysInfo(
            conda_build_version=conda_build_version,
            conda_command=get_conda_command(),
            python_implementation=context.python_implementation_name_version[0],
            python_version=context.python_implementation_name_version[1],
            conda_version=conda_version,
            solver_version=context.solver_user_agent(),
            platform_system=context.platform_system_release[0],
            platform_release=context.platform_system_release[1],
        )

    return SysInfo(
        conda_build_version=conda_build_version,
        conda_command=get_conda_command(),
    )
