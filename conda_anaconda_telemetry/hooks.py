# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that adds telemetry headers to requests made by conda."""

from __future__ import annotations

import functools
import logging
import re
import time
import typing
from contextlib import suppress
from urllib.parse import urlparse

from conda.base.context import context
from conda.cli.main_list import list_packages
from conda.common.configuration import PrimitiveParameter
from conda.common.constants import NULL
from conda.common.url import mask_anaconda_token
from conda.gateways.connection.session import get_session
from conda.models.channel import all_channel_urls
from conda.plugins import hookimpl
from conda.plugins.environment_exporters.environment_yml import (
    ENVIRONMENT_JSON_FORMAT,
    ENVIRONMENT_YAML_FORMAT,
)
from conda.plugins.types import (
    CondaPostCommand,
    CondaRequestHeader,
    CondaSetting,
)

try:
    from conda_build import __version__ as conda_build_version
except ImportError:
    conda_build_version = "n/a"

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from typing import Any, Callable

logger = logging.getLogger(__name__)

#: Field separator for request header
FIELD_SEPARATOR = ";"

#: Size limit in bytes for the payload in the request header
SIZE_LIMIT = 7_000

#: Prefix for all custom headers submitted via this plugin
# Note: header names are normalized to lowercase by the HTTP layer, so keep
# the prefix lowercased to match the actual header names emitted at runtime.
HEADER_PREFIX = "anaconda-telemetry"

#: Name of the virtual package header
HEADER_VIRTUAL_PACKAGES = f"{HEADER_PREFIX}-virtual-packages"

#: Name of the channels header
HEADER_CHANNELS = f"{HEADER_PREFIX}-channels"

#: Name of the packages header
HEADER_PACKAGES = f"{HEADER_PREFIX}-packages"

#: Name of the search header
HEADER_SEARCH = f"{HEADER_PREFIX}-search"

#: Name of the install header
HEADER_INSTALL = f"{HEADER_PREFIX}-install"

#: Name of the export header
HEADER_EXPORT = f"{HEADER_PREFIX}-export"

#: Name of the sys info header
HEADER_SYS_INFO = f"{HEADER_PREFIX}-sys-info"

#: Regex pattern for hosts and paths we want to submit request headers to
REQUEST_HEADER_PATTERN = re.compile(
    r"""
    ^                           # Start of string
    (?:                         # Non-capturing group for host patterns
        repo\.anaconda\.        # repo.anaconda. (literal dots)
        (?:com|cloud)           # Either "com" or "cloud"
        (?:/.*)?                # Optional path starting with forward slash
        |                       # OR
        conda\.anaconda\.org/   # conda.anaconda.org/ (literal dots and slash)
        (?:                     # Non-capturing group for channel paths
            anaconda|           # anaconda channel
            conda-forge|        # conda-forge channel
            main|               # main channel
            msys2|              # msys2 channel
            r                   # r channel
        )
        /.*                     # Forward slash followed by any characters
    )
    $                           # End of string
    """,
    re.VERBOSE,
)


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


@functools.lru_cache(None)
def _get_channel_urls() -> tuple[str, ...]:
    """Return a list of currently configured channel URLs."""
    return tuple(all_channel_urls(context.channels))


def get_channel_urls() -> tuple[str, ...]:
    """Return a list of currently configured channel URLs with tokens masked."""
    return tuple(mask_anaconda_token(c) for c in _get_channel_urls())


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


@timer
@functools.lru_cache(None)
def get_export_header_value() -> str:
    """Return separated string of export arguments and used exporter."""
    args = context._argparse_args
    telemetry_data = {}

    # Map arg attribute to telemetry key and transformation
    arg_map: dict[str, tuple[str, Callable[[Any], str]]] = {
        "channel": ("channels", lambda x: ",".join(x)),
        "override_channels": ("override_channels", str),
        "export_platforms": ("platforms", lambda x: ",".join(x)),
        "override_platforms": ("override_platforms", str),
        "file": ("file", str),
        "format": ("format", str),
        "no_builds": ("no_builds", lambda _: "true"),
        "ignore_channels": ("ignore_channels", lambda _: "true"),
        "from_history": ("from_history", lambda _: "true"),
        "json": ("json", lambda _: "true"),
    }

    for attr, (key, transform) in arg_map.items():
        val = getattr(args, attr, None)
        if val and val is not NULL:
            telemetry_data[key] = transform(val)

    # Determine exporter
    target_format = getattr(args, "format", NULL)
    environment_exporter = None

    if target_format is not NULL:
        pass
    elif getattr(args, "file", None):
        with suppress(Exception):
            environment_exporter = context.plugin_manager.detect_environment_exporter(
                args.file
            )
            target_format = environment_exporter.name
    elif getattr(args, "json", None):
        target_format = ENVIRONMENT_JSON_FORMAT
    else:
        target_format = ENVIRONMENT_YAML_FORMAT

    if not environment_exporter:
        with suppress(Exception):
            environment_exporter = (
                context.plugin_manager.get_environment_exporter_by_format(target_format)
            )

    if environment_exporter:
        telemetry_data["exporter"] = environment_exporter.name

    return FIELD_SEPARATOR.join(
        f"{key}:{value}" for key, value in telemetry_data.items()
    )


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

    elif command == "export":
        custom_headers.append(
            HeaderWrapper(
                header=CondaRequestHeader(
                    name=HEADER_EXPORT,
                    value=get_export_header_value(),
                ),
                size_limit=500,
            )
        )

    return custom_headers


def should_submit_request_headers(host: str, path: str) -> bool:
    """Return whether we should submit request headers to the given host and path."""
    return REQUEST_HEADER_PATTERN.match(f"{host}{path}") is not None


@hookimpl
def conda_request_headers(host: str, path: str) -> Iterator[CondaRequestHeader]:
    """Return a list of custom headers to be included in the request."""
    try:
        # Check if attribute exists on plugin config
        # Use getattr with a default value of True because older conda versions
        # might not have the setting, but we still want telemetry enabled by default
        enabled = getattr(context.plugins, "anaconda_telemetry", True)

        if enabled and should_submit_request_headers(host, path):
            yield from validate_headers(_conda_request_headers())
    except Exception as exc:
        logger.debug("Failed to collect telemetry data", exc_info=exc)


def action_conda_export_telemetry(command: str) -> None:
    """Submit telemetry data for ``conda export``."""
    # Check if telemetry is enabled before making request
    # Since we make a request, and that request triggers the header hook,
    # and the header hook checks if telemetry is enabled,
    # we could just fire the request.
    # But to avoid unnecessary network traffic if disabled:
    if not getattr(context.plugins, "anaconda_telemetry", True):
        return

    # Check if the command is "export" just to be safe and satisfy linter ARG001
    if command != "export":
        return

    # Determine the best URL to ping.
    # We start with the default location:
    url = "https://repo.anaconda.com/"

    # But we check if one of the configured channels is a better match.
    # This allows us to submit telemetry to the channel that the user is
    # actually using, provided it matches our ALLOWED hosts/paths.
    for channel_url in _get_channel_urls():
        with suppress(Exception):
            parsed = urlparse(channel_url)
            if should_submit_request_headers(parsed.netloc, parsed.path):
                url = channel_url
                break

    session = get_session(url)
    with suppress(Exception):
        # We use a HEAD request to trigger the conda_request_headers hook
        # which will attach the export telemetry header.
        session.head(url, timeout=1.0)


@hookimpl
def conda_post_commands() -> Iterable[CondaPostCommand]:
    """Register post-command functions in conda."""
    yield CondaPostCommand(
        name="anaconda-telemetry-export",
        action=action_conda_export_telemetry,
        run_for={"export"},
    )


@hookimpl
def conda_settings() -> Iterator[CondaSetting]:
    """Return a list of settings that can be configured by the user."""
    yield CondaSetting(
        name="anaconda_telemetry",
        description="Whether Anaconda Telemetry is enabled",
        parameter=PrimitiveParameter(True, element_type=bool),
    )
