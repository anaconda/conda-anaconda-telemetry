# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Check that the signal schema and its description agree."""

from __future__ import annotations

import pytest
from signal_schema_helpers import (
    assert_matches_sample,
    assert_tokens_are_placeholders,
    refresh_sample,
)

from conda_anaconda_telemetry.otel import SIGNAL_VERSION
from conda_anaconda_telemetry.plugin import TelemetryCommand

OUTCOMES = ("pnfe", "success")
TOKEN_CLASSES = {
    "persistent": {
        "aau.client.token",
        "aau.environment.token",
        "aau.organization.tokens",
        "aau.installer.tokens",
        "aau.machine.tokens",
    },
    "per-run": {"aau.session.token"},
    "account-linked": {"aau.anaconda_auth.token"},
}


def test_events_match(signal_schema: dict, signal_description: dict) -> None:
    assert set(signal_schema["events"]) == set(signal_description["events"])


def test_resource_keys_match(signal_schema: dict, signal_description: dict) -> None:
    assert set(signal_schema["resource"]) == set(signal_description["resource"])


def test_log_keys_match_outcomes(signal_schema: dict, signal_description: dict) -> None:
    log = signal_description["log"]
    for event_name, attributes in signal_schema["events"].items():
        outcome = event_name.split(".")[1]
        expected = {
            key
            for key, meta in log.items()
            if outcome in meta.get("outcomes", OUTCOMES)
        }
        assert set(attributes) == expected, event_name
    used = {
        key for attributes in signal_schema["events"].values() for key in attributes
    }
    assert set(log) <= used


def test_metadata_rules(signal_description: dict) -> None:
    entries = {
        **{f"resource:{k}": v for k, v in signal_description["resource"].items()},
        **{f"log:{k}": v for k, v in signal_description["log"].items()},
    }
    for name, meta in entries.items():
        assert meta["description"].strip(), name
        assert meta["owner"] in {"plugin", "sdk"}, name
        assert isinstance(meta["optional"], bool), name
        if meta["optional"]:
            assert meta["condition"].strip(), name
        else:
            assert "condition" not in meta, name
        assert set(meta.get("outcomes", OUTCOMES)) <= set(OUTCOMES), name

    actual_classes = {
        key: meta["token_class"]
        for key, meta in signal_description["resource"].items()
        if "token_class" in meta
    }
    assert set(actual_classes) == {
        key
        for key in signal_description["resource"]
        if key.startswith("aau.") and key != "aau.version"
    }
    for token_class, keys in TOKEN_CLASSES.items():
        assert {k for k, v in actual_classes.items() if v == token_class} == keys
    for name, meta in signal_description["log"].items():
        assert "token_class" not in meta, name


def test_optional_resource_attributes(signal_description: dict) -> None:
    """Only installer.* and aau.* resource attributes are optional."""
    optional = {k for k, v in signal_description["resource"].items() if v["optional"]}
    expected = {
        k
        for k in signal_description["resource"]
        if k.startswith(("installer.", "aau."))
    }
    assert optional == expected


def test_event_descriptions(signal_description: dict) -> None:
    for name, meta in signal_description["events"].items():
        assert meta["description"].strip(), name


def test_commands_match(signal_schema: dict) -> None:
    events = set(signal_schema["events"])
    assert {name.split(".")[0] for name in events} == {
        c.value for c in TelemetryCommand
    }
    assert events == {f"{c.value}.{o}" for c in TelemetryCommand for o in OUTCOMES}


def test_sample_values_are_safe(signal_schema: dict) -> None:
    assert_tokens_are_placeholders(signal_schema)


def test_assert_matches_sample() -> None:
    """Placeholders match any value; other strings must be equal."""
    assert_matches_sample({"a": "x", "b": "y"}, {"a": "<string>", "b": "y"})
    with pytest.raises(AssertionError):
        assert_matches_sample({"a": "x", "b": "z"}, {"a": "<string>", "b": "y"})
    with pytest.raises(AssertionError):
        assert_matches_sample({"a": "x"}, {"a": "<string>", "b": "y"})


def test_refresh_sample() -> None:
    """Known keys keep values and order. New keys are placeholders."""
    sample = {
        "resource": {"a": "<string>", "b": "<string>"},
        "events": {"x.y": {"k": "fixed", "gone": "<string>", "m": "<string>"}},
    }
    observed = {
        "resource": ["a", "b"],
        "x.y": ["new", "m", "k"],
        "z.w": ["p", "q"],
    }
    refreshed = refresh_sample(sample, observed)
    assert refreshed["events"]["x.y"] == {
        "k": "fixed",
        "m": "<string>",
        "new": "<string>",
    }
    assert list(refreshed["events"]["x.y"]) == ["k", "m", "new"]
    assert refreshed["events"]["z.w"] == {"p": "<string>", "q": "<string>"}
    assert refreshed["resource"] == sample["resource"]
    assert "gone" not in refreshed["events"]["x.y"]


def test_refreshed_sample_is_safe() -> None:
    """A new token key is a placeholder."""
    refreshed = refresh_sample(
        {"resource": {}, "events": {}}, {"resource": ["aau.new.token"]}
    )
    assert_tokens_are_placeholders(refreshed)


def test_signal_version(signal_schema: dict) -> None:
    for name, attributes in signal_schema["events"].items():
        assert attributes["event.schema_version"] == SIGNAL_VERSION, name
        assert attributes["log.event.name"] == name, name
        assert attributes["command"] == name.split(".")[0], name
