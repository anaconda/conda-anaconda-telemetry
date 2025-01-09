# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that adds telemetry headers to requests made by conda."""

from __future__ import annotations

import functools
import logging
import time
import typing

from conda.base.context import context
from conda.cli.main_list import list_packages
from conda.common.configuration import PrimitiveParameter
from conda.common.url import mask_anaconda_token
from conda.models.channel import all_channel_urls
from conda.plugins import CondaRequestHeader, CondaSetting, hookimpl

try:
    from conda_build import __version__ as conda_build_version
except ImportError:
    conda_build_version = "n/a"

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Callable

logger = logging.getLogger(__name__)

#: Field separator for request header
FIELD_SEPARATOR = ";"

#: Size limit in bytes for the payload in the request header
SIZE_LIMIT = 7_000

#: Prefix for all custom headers submitted via this plugin
HEADER_PREFIX = "Anaconda-Telemetry"

#: Name of the virtual package header
HEADER_VIRTUAL_PACKAGES = f"{HEADER_PREFIX}-Virtual-Packages"

#: Name of the channels header
HEADER_CHANNELS = f"{HEADER_PREFIX}-Channels"

#: Name of the packages header
HEADER_PACKAGES = f"{HEADER_PREFIX}-Packages"

#: Name of the search header
HEADER_SEARCH = f"{HEADER_PREFIX}-Search"

#: Name of the install header
HEADER_INSTALL = f"{HEADER_PREFIX}-Install"

#: Name of the sys info header
HEADER_SYS_INFO = f"{HEADER_PREFIX}-Sys-Info"

#: Hosts we want to submit request headers to
REQUEST_HEADER_HOSTS = {"repo.anaconda.com", "conda.anaconda.org"}


def timer(func: Callable) -> Callable:
    """Log the duration of a function call."""

    @functools.wraps(func)
    def wrapper_timer(*args: tuple, **kwargs: dict) -> Callable:
        """Wrap the given function."""
        if logger.getEffectiveLevel() <= logging.INFO:
            tic = time.perf_counter()
            value = func(*args, **kwargs)
            toc = time.perf_counter()
            elapsed_time = toc - tic
            logger.info(
                "function: %s; duration (seconds): %0.4f",
                func.__name__,
                elapsed_time,
            )
            return value

        return func(*args, **kwargs)

    return wrapper_timer


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


@timer
@functools.lru_cache(None)
def get_sys_info_header_value() -> str:
    """Return ``;`` delimited string of extra system information."""
    telemetry_data = {
        "conda_build_version": conda_build_version,
        "conda_command": get_conda_command(),
    }

    return FIELD_SEPARATOR.join(
        f"{key}:{value}" for key, value in telemetry_data.items()
    )


@timer
@functools.lru_cache(None)
def get_channel_urls_header_value() -> str:
    """Return ``FIELD_SEPARATOR`` delimited string of channel URLs."""
    return FIELD_SEPARATOR.join(get_channel_urls())


@timer
@functools.lru_cache(None)
def get_virtual_packages_header_value() -> str:
    """Return ``FIELD_SEPARATOR`` delimited string of virtual packages."""
    return FIELD_SEPARATOR.join(get_virtual_packages())


@timer
@functools.lru_cache(None)
def get_install_arguments_header_value() -> str:
    """Return ``FIELD_SEPARATOR`` delimited string of channel URLs."""
    return FIELD_SEPARATOR.join(get_install_arguments())


@timer
@functools.lru_cache(None)
def get_installed_packages_header_value() -> str:
    """Return ``FIELD_SEPARATOR`` delimited string of install arguments."""
    return FIELD_SEPARATOR.join(get_package_list())


class HeaderWrapper(typing.NamedTuple):
    """Object that wraps ``CondaRequestHeader`` and adds a ``size_limit`` field."""

    header: CondaRequestHeader
    size_limit: int


def validate_headers(
    header_wrappers: Sequence[HeaderWrapper],
) -> Iterator[CondaRequestHeader]:
    """Make sure that all headers combined are not larger than ``SIZE_LIMIT``.

    Any headers over their individual limits will be truncated.
    """
    for wrapper in header_wrappers:
        wrapper.header.value = wrapper.header.value[: wrapper.size_limit]
        yield wrapper.header


def _conda_request_headers() -> Sequence[HeaderWrapper]:
    custom_headers = [
        HeaderWrapper(
            header=CondaRequestHeader(
                name=HEADER_SYS_INFO,
                value=get_sys_info_header_value(),
            ),
            size_limit=500,
        ),
        HeaderWrapper(
            header=CondaRequestHeader(
                name=HEADER_CHANNELS,
                value=get_channel_urls_header_value(),
            ),
            size_limit=500,
        ),
        HeaderWrapper(
            header=CondaRequestHeader(
                name=HEADER_VIRTUAL_PACKAGES,
                value=get_virtual_packages_header_value(),
            ),
            size_limit=500,
        ),
        HeaderWrapper(
            header=CondaRequestHeader(
                name=HEADER_PACKAGES,
                value=get_installed_packages_header_value(),
            ),
            size_limit=5_000,
        ),
    ]

    command = get_conda_command()

    if command == "search":
        custom_headers.append(
            HeaderWrapper(
                header=CondaRequestHeader(
                    name=HEADER_SEARCH,
                    value=get_search_term(),
                ),
                size_limit=500,
            )
        )

    elif command in {"install", "create"}:
        custom_headers.append(
            HeaderWrapper(
                header=CondaRequestHeader(
                    name=HEADER_INSTALL,
                    value=get_install_arguments_header_value(),
                ),
                size_limit=500,
            )
        )

    return custom_headers


@hookimpl
def conda_session_headers(host: str) -> Iterator[CondaRequestHeader]:
    """Return a list of custom headers to be included in the request."""
    try:
        if context.plugins.anaconda_telemetry and host in REQUEST_HEADER_HOSTS:
            yield from validate_headers(_conda_request_headers())
    except Exception as exc:
        logger.debug("Failed to collect telemetry data", exc_info=exc)


@hookimpl
def conda_settings() -> Iterator[CondaSetting]:
    """Return a list of settings that can be configured by the user."""
    yield CondaSetting(
        name="anaconda_telemetry",
        description="Whether Anaconda Telemetry is enabled",
        parameter=PrimitiveParameter(True, element_type=bool),
    )
