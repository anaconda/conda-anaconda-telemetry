# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
import os
import re
import sys
from subprocess import run

import anaconda_opentelemetry.signals as sig
import pytest

from conda_anaconda_telemetry.otel import AnacondaTelemetry


@pytest.mark.parametrize(
    "environment, default_endpoint",
    [
        ("production", "https://public.telemetry.anaconda.com/v1/logs"),
        ("staging", "https://metrics.stage.anacondaconnect.com/v1/logs"),
        ("test", "http://localhost:4318"),
        ("development", "http://localhost:4318"),
        ("", "https://public.telemetry.anaconda.com/v1/logs"),
    ],
)
def test_anaconda_telemetry(environment: str, default_endpoint: str) -> None:
    # Save original environment for reset after test run
    orig_environment = os.getenv("ATEL_ENVIRONMENT")
    assert orig_environment in ("test", "development")

    # Set environment for test run
    os.environ["ATEL_ENVIRONMENT"] = environment

    telemetry = AnacondaTelemetry()
    # Confirm telemetry was configured correctly but not initialized
    assert telemetry.environment.value == environment
    assert telemetry.default_endpoint == default_endpoint
    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is False

    try:
        telemetry.initialize()
    except Exception as e:
        pytest.fail(f"Failed to initialize Anaconda Telemetry: {e}")

    # Confirm telemetry initialized successfully
    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is True

    # Reset environment and telemetry state after test run
    os.environ["ATEL_ENVIRONMENT"] = orig_environment
    setattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED", False)


def test_conda_exception_observers_hook() -> None:
    result = run(  # noqa: S603
        [sys.executable, "-m", "conda", "install", "-c", "defaults", "fakepackage"],
        capture_output=True,
        text=True,
    )

    match_signal = re.search(r"\{.*\}", result.stdout, re.DOTALL)  # Find JSON object
    assert match_signal is not None
    assert match_signal.group(0) is not None  # Ensure the JSON object is not None

    try:
        json_signal = json.loads(match_signal.group(0))
    except json.JSONDecodeError:
        pytest.fail(f"Error parsing JSON from stdout: {match_signal.group(0)}")

    assert (
        json_signal is not None
    )  # TODO: Add more detailed assertions for signal once attributes are finalized
