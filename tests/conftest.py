# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import pytest
from conda.base.context import context


@pytest.fixture(autouse=True, scope="session")
def reset_context() -> None:
    """
    We reset the context to ignore local configuration
    """

    context.__init__(search_path=())
