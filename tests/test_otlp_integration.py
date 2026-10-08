# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Test the complete OTLP export path against a local HTTP server.

The test reports all four events, decodes the exported protobuf requests, and
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
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from anaconda_opentelemetry.logging import _AnacondaLogger
from conda.exceptions import PackagesNotFoundInChannelsError
from conftest import SCHEMA_DIR
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from signal_schema_helpers import assert_matches_sample, refresh_sample

import conda_anaconda_telemetry.plugin as plugin_module

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
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


INSTALLER_INFO = {
    "name": "TestInstaller",
    "version": "1.0.0",
    "platform": "test-platform",
    "type": "sh",
}
TOKEN_VALUES = {
    "aau.version": "test-aau-version",
    "aau.client.token": "test-client-token",
    "aau.session.token": "test-session-token",
    "aau.environment.token": "test-environment-token",
    "aau.organization.tokens": '["test-organization-token"]',
    "aau.installer.tokens": '["test-installer-token"]',
    "aau.machine.tokens": '["test-machine-token"]',
    "aau.anaconda_auth.token": "test-auth-token",
}
# Native OTel settings that the plugin must ignore.
ENV_TO_IGNORE = {
    "OTEL_RESOURCE_ATTRIBUTES": "foo.bar=something",
    "OTEL_SDK_DISABLED": "true",
    "OTEL_ATTRIBUTE_COUNT_LIMIT": "0",
    "OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT": "1",
    "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT": "not-a-number",
}


@pytest.fixture
def telemetry_env(otlp_server: str, mocker: MockerFixture, tmp_path: Path) -> None:
    """Point the plugin at the local collector with fixed, fake inputs."""
    (tmp_path / ".installer.info").write_text(json.dumps(INSTALLER_INFO))
    mocker.patch.dict(
        os.environ,
        {
            "ATEL_DEFAULT_ENDPOINT": otlp_server,
            "ATEL_ENVIRONMENT": "test",
            "ATEL_SESSION_ENTROPY_VALUE": "test-session-entropy",
            **ENV_TO_IGNORE,
            "OTEL_EXPORTER_OTLP_LOGS_CLIENT_CERTIFICATE": str(tmp_path / "cert.pem"),
            "OTEL_EXPORTER_OTLP_LOGS_CLIENT_KEY": str(tmp_path / "key.pem"),
        },
    )
    mocker.patch(
        "anaconda_opentelemetry.attributes.TOKEN_FUNCS",
        [(name, lambda value=value: value) for name, value in TOKEN_VALUES.items()],
    )
    # Installer metadata is read from the root prefix.
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        SimpleNamespace(root_prefix=str(tmp_path)),
    )
    mocker.patch(
        "conda_anaconda_telemetry.otel.context",
        SimpleNamespace(channel_priority="strict", proxy_servers={}),
    )
    # Telemetry is enabled and the run is a real one (no dry run).
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch("conda_anaconda_telemetry.plugin.context.dry_run", False)
    mocker.patch("conda_anaconda_telemetry.plugin.context.download_only", False)


def send_all_events() -> None:
    """Report one pnfe and one success event for each command."""
    commands = list(plugin_module.TelemetryCommand)
    request = plugin_module.command_request
    for command in commands:
        request.command = command
        request.requested_names = ["numpy"]
        plugin_module.report_error(
            SimpleNamespace(
                exc_type=PackagesNotFoundInChannelsError,
                exc_value=PackagesNotFoundInChannelsError(["numpy"], []),
                channels=(),
            )
        )
    for command in commands:
        request.command = command
        request.requested_names = ["numpy"]
        request.channels = ["defaults"]
        request.resolved_packages = ["numpy=2.0.0=py312_0"]
        plugin_module.report_success(command.value)


def received_records() -> list[tuple[dict, dict, Any, Any]]:
    """Flatten the received requests to (resource attrs, log attrs, scope, record).

    Do not assume one request or one resource group per event.
    """

    def attrs(key_values: Iterable[KeyValue]) -> dict[str, object]:
        return {kv.key: otlp_value(kv.value) for kv in key_values}

    return [
        (
            attrs(resource_logs.resource.attributes),
            attrs(log_record.attributes),
            scope_logs.scope,
            log_record,
        )
        for request, _, _ in OTLPLogsReceiver.received
        for resource_logs in request.resource_logs
        for scope_logs in resource_logs.scope_logs
        for log_record in scope_logs.log_records
    ]


def without_service_instance_id(attrs: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in attrs.items() if k != "service.instance.id"}


@pytest.mark.usefixtures("telemetry_env")
def test_real_otlp_payload_received_by_local_collector(signal_schema: dict) -> None:
    """Send all four OTLP events without mocking the SDK and check what arrives."""
    send_all_events()
    # Environment variables the plugin must ignore stay untouched.
    for name, value in ENV_TO_IGNORE.items():
        assert os.environ[name] == value

    # Export is asynchronous. Flush this test's logger because the global
    # provider may belong to telemetry initialized by another test.
    _AnacondaLogger._instance._processor.force_flush()

    assert {path for _, path, _ in OTLPLogsReceiver.received} == {"/v1/logs"}
    assert {ct for _, _, ct in OTLPLogsReceiver.received} == {"application/x-protobuf"}
    records = received_records()
    assert len(records) == 4

    if os.environ.get("UPDATE_SIGNAL_SCHEMA") == "1":
        observed_keys = {"resource": list(records[0][0])}
        for _, log_attrs, _, _ in records:
            observed_keys[str(log_attrs["log.event.name"])] = list(log_attrs)
        signal_schema = refresh_sample(signal_schema, observed_keys)
        (SCHEMA_DIR / "signal_schema.json").write_text(
            json.dumps(signal_schema, indent=2) + "\n"
        )
    assert {r[1]["log.event.name"] for r in records} == set(signal_schema["events"])

    for resource_attrs, log_attrs, scope, log_record in records:
        # Attribute names and fixed values must match the sample signal.
        # service.instance.id is only emitted by newer OpenTelemetry versions,
        # so it is excluded from this comparison.
        assert_matches_sample(
            without_service_instance_id(resource_attrs),
            without_service_instance_id(signal_schema["resource"]),
        )
        assert_matches_sample(
            log_attrs, signal_schema["events"][log_attrs["log.event.name"]]
        )
        # Envelope.
        assert scope.name == "conda-anaconda-telemetry_event_logger"
        assert scope.version == ""
        assert log_record.body.string_value == ""
        assert log_record.observed_time_unix_nano > 0
        # Resource values that this test controls.
        assert resource_attrs["service.name"] == "conda-anaconda-telemetry"
        assert resource_attrs["environment"] == "test"
        for field, value in INSTALLER_INFO.items():
            if field != "type":
                assert resource_attrs[f"installer.{field}"] == value
        for name, value in TOKEN_VALUES.items():
            assert resource_attrs[name] == value
        # Only verify these attributes below exist since we test across multiple
        # platforms and Python versions
        assert resource_attrs["os.type"]
        assert resource_attrs["os.version"]
        assert resource_attrs["python.version"]

    # Event-specific values.
    by_name = {log_attrs["log.event.name"]: log_attrs for _, log_attrs, _, _ in records}
    for command in (c.value for c in plugin_module.TelemetryCommand):
        pnfe = by_name[f"{command}.pnfe"]
        assert pnfe["exception.missing_specs"] == ["numpy"]
        assert pnfe["exception.name"] == "PackagesNotFoundInChannelsError"
        assert pnfe["requested.packages"] == ["numpy"]
        assert pnfe["install.channels"] == []
        success = by_name[f"{command}.success"]
        assert success["resolved.packages"] == ["numpy=2.0.0=py312_0"]
