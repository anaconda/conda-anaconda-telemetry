#!/usr/bin/env python
# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
# scripts/measure_payload.py
"""Measure the JSON-serialised byte size of each telemetry signal payload.

Run inside a conda environment where conda_anaconda_telemetry is installed:
    conda run -n <env> python scripts/measure_payload.py

Payload size = len(json.dumps(...)) — local assembly only, not wire bytes.
"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import cast

from conda.exceptions import PackagesNotFoundInChannelsError

from conda_anaconda_telemetry.otel import (
    AnacondaTelemetry,
    get_install_attributes,
    get_success_attributes,
)
from conda_anaconda_telemetry.resource_attributes import get_installer_attributes


def _get_resource_attributes() -> tuple[dict[str, object], bool]:
    """Assemble the full set of resource attributes as sent to initialize_telemetry.

    Builds the actual ResourceAttributes object AnacondaTelemetry sends (via
    its private _make_attributes()), so this includes the os/python/hostname
    and aau.* token fields added by anon_usage=True, not just a hand-picked
    subset.

    Returns (attributes, installer_is_synthetic).
    """
    attributes = AnacondaTelemetry()._make_attributes()

    # .installer.info may be absent on this machine, which would undercount
    # payload size relative to what a real installed distribution sends.
    installer_is_synthetic = not get_installer_attributes()
    if installer_is_synthetic:
        attributes.set_attributes(
            **{
                "installer.name": "FooBar",
                "installer.version": "12345",
                "installer.platform": "linux-64",
                "installer.type": "sh",
            }
        )
    return attributes._get_attributes(), installer_is_synthetic


def _get_error_signal_attributes() -> dict[str, object]:
    """install.pnfe's event attributes, built from a fabricated failure.

    Mirrors what report_error() sends when a PackagesNotFoundInChannelsError
    is raised while requesting "numpy" from "defaults".
    """
    event = SimpleNamespace(
        exc_type=PackagesNotFoundInChannelsError,
        exc_value=SimpleNamespace(packages=("numpy",)),
        channels=("defaults",),
    )
    attributes = get_install_attributes(
        event, command="install", requested_names=["numpy"]
    )
    if attributes is None:
        # This shouldn't happen but added for safety
        raise RuntimeError("get_install_attributes returned None")
    return attributes


def _get_success_signal_attributes() -> dict[str, object]:
    """install.success's event attributes, built from a fabricated result."""
    return get_success_attributes(
        command="install",
        channels=["defaults"],
        requested_names=["numpy"],
        resolved_packages=["numpy=1.26.4=py311h1234567_0"],
    )


def _build_signals() -> tuple[dict[str, object], dict[str, object]]:
    """Build the error and success signal payloads."""
    error_signal: dict[str, object] = {
        "event_name": "install.pnfe",
        "body": "",
        "attributes": _get_error_signal_attributes(),
    }
    success_signal: dict[str, object] = {
        "event_name": "install.success",
        "body": "",
        "attributes": _get_success_signal_attributes(),
    }
    return error_signal, success_signal


def _byte_size(obj: object) -> int:
    return len(json.dumps(obj, default=str))


def _print_row(label: str, size: int, width: int = 40) -> None:
    print(f"  {label:<{width}} {size:>8} bytes")


def main() -> None:
    """See docstring at the top of this file."""
    print("=" * 60)
    print("Telemetry payload size measurement")
    print("=" * 60)

    # Resource attributes and signal payloads, built together so a failure
    # in either (e.g. reading system/installer info) prints one clean error.
    try:
        resource_attrs, installer_is_synthetic = _get_resource_attributes()
        error_signal, success_signal = _build_signals()
    except Exception as exc:
        print(f"\nERROR: could not assemble telemetry payloads: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n[Resource attributes]")
    for key, value in resource_attrs.items():
        _print_row(key, _byte_size(value))
    resource_total = _byte_size(resource_attrs)
    _print_row("TOTAL (resource attrs)", resource_total)

    if installer_is_synthetic:
        print(
            "  NOTE: no real .installer.info found on this machine, so the"
            " installer.* numbers above are made-up placeholder values, not"
            " a real measurement."
        )

    # Per-signal payloads
    for signal in (error_signal, success_signal):
        event_name = signal["event_name"]
        print(f"\n[{event_name} signal payload]")
        _print_row("event_name", _byte_size(signal["event_name"]))
        _print_row("body", _byte_size(signal["body"]))

        # Need to cast below to satisfy pre-commit
        attrs = cast("dict[str, object]", signal["attributes"])
        for key, value in attrs.items():
            _print_row(f"  attributes.{key}", _byte_size(value))
        event_total = _byte_size(signal)
        combined = resource_total + event_total
        _print_row("event payload total", event_total)
        _print_row(f"combined ({event_name})", combined)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
