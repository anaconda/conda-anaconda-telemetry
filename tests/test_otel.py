# Copyright (C) 2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
import pytest
import re
import subprocess


def test_conda_exception_observers_hook():
    result = subprocess.run(
        ["conda", "install", "-c", "defaults", "fakepackage"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    
    assert match is not None
    assert match.group(0) is not None

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        pytest.fail("Error parsing JSON in stdout: %s" % match.group(0))

    assert data is not None
