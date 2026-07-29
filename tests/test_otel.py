# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
import logging
import re
import sys
from subprocess import run

import anaconda_opentelemetry.signals as sig
import pytest

from conda_anaconda_telemetry.otel import AnacondaTelemetry

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def test_telemetry_initialization() -> None:
    telemetry = AnacondaTelemetry()

    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is False

    try:
        telemetry.initialize()
    except Exception as e:
        pytest.fail(f"Failed to initialize Anaconda Telemetry: {e}")

    assert getattr(sig, "__ANACONDA_TELEMETRY_INITIALIZED") is True


def test_conda_exception_observers_hook() -> None:
    result = run(  # noqa: S603
        [sys.executable, "-m", "conda", "install", "-c", "defaults", "fakepackage"],
        capture_output=True,
        text=True,
    )

    match_signal = re.search(r"\{.*\}", result.stdout, re.DOTALL)  # Find JSON objects
    assert match_signal is not None
    assert match_signal.group(0) is not None  # Ensure the JSON object is not None

    try:
        json_signal = json.loads(match_signal.group(0))
    except json.JSONDecodeError:
        pytest.fail(f"Error parsing JSON from stdout: {match_signal.group(0)}")

    assert (
        json_signal is not None
    )  # TODO: Add more detailed assertions for signal once attributes are finalized
