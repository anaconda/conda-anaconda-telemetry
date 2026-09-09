# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (C) Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Test the complete OTLP export path against a local HTTP server.

The test calls report_error(), decodes the exported protobuf request, and
checks the data a collector receives. Hook dispatch is tested separately in
tests/test_plugin.py.

Telemetry initialization is process-wide and cannot be reset, so the complete
flow is covered by a single test.
"""

from __future__ import annotations

import http.server
import json
import os
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar

import pytest
from anaconda_opentelemetry.logging import _AnacondaLogger
from conda.exceptions import PackagesNotFoundInChannelsError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)

import conda_anaconda_telemetry.plugin as plugin_module

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from opentelemetry.proto.common.v1.common_pb2 import AnyValue
    from pytest_mock import MockerFixture


class OTLPLogsReceiver(http.server.BaseHTTPRequestHandler):
    """Decode and store OTLP log requests."""

    #: Received requests, paths, and Content-Type headers.
    received: ClassVar[list[tuple[ExportLogsServiceRequest, str, str]]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        request = ExportLogsServiceRequest()
        request.ParseFromString(body)
        self.received.append((request, self.path, self.headers.get("Content-Type", "")))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format_: str, *args: object) -> None:
        pass  # Suppress HTTP request logging.


@pytest.fixture
def otlp_server() -> Iterator[str]:
    """Run a local HTTP server and yield its URL."""
    OTLPLogsReceiver.received.clear()
    server = http.server.HTTPServer(("127.0.0.1", 0), OTLPLogsReceiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        OTLPLogsReceiver.received.clear()


def otlp_value(value: AnyValue) -> object:
    """Convert an OTLP value to its Python value."""
    kind = value.WhichOneof("value")
    if kind == "array_value":
        return [otlp_value(item) for item in value.array_value.values]
    return getattr(value, kind)


def test_real_otlp_payload_received_by_local_collector(
    otlp_server: str, mocker: MockerFixture, tmp_path: Path
) -> None:
    """Send and validate an OTLP payload without mocking the SDK."""
    installer_info = {
        "name": "TestInstaller",
        "version": "1.0.0",
        "platform": "test-platform",
        "type": "sh",
    }
    (tmp_path / ".installer.info").write_text(json.dumps(installer_info))
    token_values = {
        "aau.version": "test-aau-version",
        "aau.client.token": "test-client-token",
        "aau.session.token": "test-session-token",
        "aau.environment.token": "test-environment-token",
        "aau.organization.tokens": '["test-organization-token"]',
        "aau.installer.tokens": '["test-installer-token"]',
        "aau.machine.tokens": '["test-machine-token"]',
        "aau.anaconda_auth.token": "test-auth-token",
    }

    # Avoid the localhost shortcut, which selects the console exporter.
    mocker.patch.dict(
        os.environ,
        {
            "ATEL_DEFAULT_ENDPOINT": otlp_server,
            "ATEL_ENVIRONMENT": "test",
            "ATEL_SESSION_ENTROPY_VALUE": "test-session-entropy",
        },
    )
    mocker.patch(
        "anaconda_opentelemetry.attributes.TOKEN_FUNCS",
        [(name, lambda value=value: value) for name, value in token_values.items()],
    )
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        SimpleNamespace(root_prefix=str(tmp_path)),
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        SimpleNamespace(channel_priority="strict"),
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    plugin_module.command_request.requested_names = ["numpy"]

    event = SimpleNamespace(
        exc_type=PackagesNotFoundInChannelsError,
        exc_value=PackagesNotFoundInChannelsError(["numpy"], []),
        channels=(),
    )
    plugin_module.report_error(event)

    # Export is asynchronous. Flush this test's logger because the global
    # provider may belong to telemetry initialized by another test.
    _AnacondaLogger._instance._processor.force_flush()

    ((request, path, content_type),) = OTLPLogsReceiver.received
    assert path == "/v1/logs"
    assert content_type == "application/x-protobuf"

    (resource_logs,) = request.resource_logs
    (scope_logs,) = resource_logs.scope_logs
    (log_record,) = scope_logs.log_records

    resource_attrs = {
        kv.key: otlp_value(kv.value) for kv in resource_logs.resource.attributes
    }
    assert set(resource_attrs) == {
        "aau.anaconda_auth.token",
        "aau.client.token",
        "aau.environment.token",
        "aau.installer.tokens",
        "aau.machine.tokens",
        "aau.organization.tokens",
        "aau.session.token",
        "aau.version",
        "client.sdk.version",
        "conda.ci_detected",
        "conda.version",
        "environment",
        "hostname",
        "installer.name",
        "installer.platform",
        "installer.version",
        "os.type",
        "os.version",
        "parameters",
        "platform",
        "python.version",
        "schema.version",
        "service.name",
        "service.version",
        "session.id",
        "telemetry.sdk.language",
        "telemetry.sdk.name",
        "telemetry.sdk.version",
    }
    assert resource_attrs["service.name"] == "conda-anaconda-telemetry"
    assert resource_attrs["environment"] == "test"
    assert resource_attrs["installer.name"] == "TestInstaller"
    assert resource_attrs["installer.version"] == "1.0.0"
    assert resource_attrs["installer.platform"] == "test-platform"
    for name, value in token_values.items():
        assert resource_attrs[name] == value
    # No exact assertion to simplify testing across Windows/Linux/macOS
    assert resource_attrs["os.type"]
    assert resource_attrs["os.version"]
    assert resource_attrs["python.version"]
    # Suppression is not yet supported, so verify these values are populated.
    assert resource_attrs["hostname"]
    assert resource_attrs["session.id"]

    assert scope_logs.scope.name == "conda-anaconda-telemetry_event_logger"
    assert scope_logs.scope.version == ""

    assert log_record.body.string_value == ""
    assert log_record.observed_time_unix_nano > 0
    log_attrs = {kv.key: otlp_value(kv.value) for kv in log_record.attributes}
    assert log_attrs == {
        "command": "install",
        "event.schema_version": "1",
        "exception.missing_specs": ["numpy"],
        "exception.name": "PackagesNotFoundInChannelsError",
        "install.channel_priority": "strict",
        "install.channels": [],
        "log.event.name": "install.pnfe",
        "requested.packages": ["numpy"],
        "truncated": False,
    }
