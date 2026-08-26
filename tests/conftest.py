# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

from conda_anaconda_telemetry.resource_attributes import get_plugin_settings


@pytest.fixture(autouse=True)
def _clear_plugin_settings_cache() -> Generator[None, None, None]:
    """Prevent get_plugin_settings()'s lru_cache from leaking across tests.

    Applies to every test in the suite, not just tests that call it
    directly - anything that calls get_conda_attributes()/get_install_attributes()
    against a real or mocked context needs a clean cache first.
    """
    get_plugin_settings.cache_clear()
    yield
    get_plugin_settings.cache_clear()
