# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Holds the specific logic for submitting telemetry data to OTel supported
data collectors.
"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)

from ..metrics import (
    get_channel_urls,
    get_install_arguments,
    get_package_list,
    get_search_term,
    get_sys_info,
    get_virtual_packages,
)
from ..utils import timer

_provider = TracerProvider()
_exporter = OTLPSpanExporter(
    endpoint="http://localhost:4317/", insecure=True, timeout=1
)
_processor = BatchSpanProcessor(_exporter)
_provider.add_span_processor(_processor)

# Sets the global default tracer provider
trace.set_tracer_provider(_provider)

# Creates a tracer from the global tracer provider
_tracer = trace.get_tracer("conda-anaconda-telemetry")


@timer
def submit_telemetry_data(command: str) -> None:
    """Submits telemetry data to the configured data collector."""
    with _tracer.start_as_current_span("post_command_hook") as current_span:
        sys_info = get_sys_info(extra=True)

        # System Information
        current_span.set_attribute(
            "python_implementation", sys_info.python_implementation
        )
        current_span.set_attribute("python_version", sys_info.conda_version)
        current_span.set_attribute("conda_version", sys_info.conda_version)
        current_span.set_attribute("solver_version", sys_info.solver_version)
        current_span.set_attribute("conda_build_version", sys_info.conda_build_version)
        current_span.set_attribute("platform_system", sys_info.platform_system)
        current_span.set_attribute("platform_release", sys_info.platform_release)

        # Channel URLs
        current_span.set_attribute("channel_urls", get_channel_urls())

        # Virtual packages
        current_span.set_attribute("virtual_packages", get_virtual_packages())

        # Command
        current_span.set_attribute("conda_command", command)

        # Package List
        current_span.set_attribute("package_list", get_package_list())

        # Search Term
        if command == "search":
            current_span.set_attribute("search_term", get_search_term())

        # Install Arguments
        if command in {"create", "install", "update"}:
            current_span.set_attribute("install_arguments", get_install_arguments())
