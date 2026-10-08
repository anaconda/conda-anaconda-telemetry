# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"


@pytest.fixture
def signal_schema() -> dict:
    """Return the sample signal."""
    return json.loads((SCHEMA_DIR / "signal_schema.json").read_text())


@pytest.fixture
def signal_description() -> dict:
    """Return the descriptions of the signal fields."""
    return json.loads((SCHEMA_DIR / "signal_schema_description.json").read_text())
