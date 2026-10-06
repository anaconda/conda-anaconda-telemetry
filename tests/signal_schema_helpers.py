# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Helpers to compare and update the sample signal."""

from __future__ import annotations

from typing import Any


def is_placeholder(value: object) -> bool:
    """Return True for a sample value in the form "<...>"."""
    return isinstance(value, str) and value.startswith("<") and value.endswith(">")


def assert_matches_sample(actual: dict[str, object], sample: dict[str, object]) -> None:
    """Check the keys and the fixed values against a sample signal.

    Sample values in the form "<...>" are placeholders and are not compared.
    """
    assert set(actual) == set(sample)
    for key, expected in sample.items():
        if isinstance(expected, str) and not is_placeholder(expected):
            assert actual[key] == expected, key


def assert_tokens_are_placeholders(sample: dict[str, Any]) -> None:
    """Check that no sample value of an aau.* resource attribute is real."""
    for key, value in sample["resource"].items():
        if key.startswith("aau."):
            assert is_placeholder(value), key


def refresh_sample(
    sample: dict[str, Any], observed_keys: dict[str, list[str]]
) -> dict[str, Any]:
    """Return a sample that has the observed keys.

    Only key names are used, to avoid writing real values to the sample.
    Known keys keep their sample value. New keys get "<string>".
    """

    def refresh(old: dict[str, object], keys: list[str]) -> dict[str, object]:
        kept = {key: value for key, value in old.items() if key in keys}
        return kept | {key: "<string>" for key in keys if key not in old}

    return {
        "resource": refresh(sample["resource"], observed_keys["resource"]),
        "events": {
            name: refresh(sample["events"].get(name, {}), keys)
            for name, keys in observed_keys.items()
            if name != "resource"
        },
    }
