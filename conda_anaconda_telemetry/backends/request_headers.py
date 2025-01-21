# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Holds the specific logic for submitting telemetry data via request headers."""

from __future__ import annotations

import functools
import typing

from conda.plugins import CondaRequestHeader

from ..metrics import (
    get_channel_urls,
    get_conda_command,
    get_install_arguments,
    get_package_list,
    get_search_term,
    get_sys_info,
    get_virtual_packages,
)
from ..utils import timer

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

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


@timer
@functools.lru_cache(None)
def get_sys_info_header_value() -> str:
    """Return ``;`` delimited string of extra system information."""
    telemetry_data = get_sys_info()

    return FIELD_SEPARATOR.join(
        f"{key}:{value}" for key, value in telemetry_data.dict().items()
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


def get_conda_request_headers() -> Sequence[HeaderWrapper]:
    """Builds a list of custom headers to be included in the request."""
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
