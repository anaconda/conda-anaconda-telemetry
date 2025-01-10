# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda plugin that adds telemetry headers to requests made by conda."""
import logging
from collections.abc import Iterator

from conda.base.context import context
from conda.common.configuration import PrimitiveParameter
from conda.plugins import hookimpl, CondaRequestHeader, CondaSetting

from .backends.request_headers import (
    get_conda_request_headers,
    validate_headers,
    REQUEST_HEADER_HOSTS
)

logger = logging.getLogger(__name__)


@hookimpl
def conda_session_headers(host: str) -> Iterator[CondaRequestHeader]:
    """Return a list of custom headers to be included in the request."""
    try:
        if context.plugins.anaconda_telemetry and host in REQUEST_HEADER_HOSTS:
            yield from validate_headers(get_conda_request_headers())
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
