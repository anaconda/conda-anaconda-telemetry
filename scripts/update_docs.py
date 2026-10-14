# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause

"""Render the OTel signal into the FAQ document at docs/faq.md.

The --check flag does not write. It fails if the FAQ is stale, so a pre-commit
hook can keep the FAQ current.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BEGIN_MARKER = "<!-- BEGIN GENERATED OTEL SIGNAL -->"
END_MARKER = "<!-- END GENERATED OTEL SIGNAL -->"

ROOT = Path(__file__).resolve().parent.parent
FAQ_PATH = ROOT / "docs" / "faq.md"
SCHEMA_DIR = ROOT / "schema"

TOKEN_CLASSES = (
    ("persistent", "Persistent tokens stay the same between runs."),
    ("per-run", "Per-run tokens change with each run."),
    ("account-linked", "Account-linked tokens are tied to an Anaconda account."),
)


def _presence(info: dict) -> str:
    if info.get("optional"):
        return f"optional: {info.get('condition', '')}"
    return "always"


def _table(entries: list[tuple[str, dict]]) -> list[str]:
    lines = [
        "| Name | Description | Owner | Presence |",
        "| --- | --- | --- | --- |",
    ]
    for key, info in entries:
        lines.append(
            f"| `{key}` | {info['description']} | {info['owner']} | {_presence(info)} |"
        )
    return lines


def _outcome(event_name: str) -> str:
    return event_name.rsplit(".", 1)[-1]


def render_otel_section(schema: dict, description: dict) -> str:
    """Return the generated Markdown for the signal."""
    events = description["events"]
    first_event = next(iter(schema["events"].values()))
    out = [
        "### Signal version",
        "",
        (
            f"The signal version is `{first_event['event.schema_version']}`. "
            "It is sent as `event.schema_version`, which the plugin sets. "
            "It is separate from `schema.version`, which the SDK sets."
        ),
        "",
        "### Events",
        "",
    ]
    for name, info in events.items():
        out.append(f"- `{name}`: {info['description']}")

    out += ["", "### Resource attributes", ""]
    out += _table(list(description["resource"].items()))

    out += ["", "### Anaconda token classes", ""]
    for token_class, text in TOKEN_CLASSES:
        members = [
            f"`{key}`"
            for key, info in description["resource"].items()
            if info.get("token_class") == token_class
        ]
        out.append(f"- `{token_class}`: {text} Attributes: {', '.join(members)}.")

    outcomes = list(dict.fromkeys(_outcome(name) for name in events))
    for outcome in outcomes:
        names = ", ".join(f"`{n}`" for n in events if _outcome(n) == outcome)
        entries = [
            (key, info)
            for key, info in description["log"].items()
            if outcome in info.get("outcomes", [outcome])
        ]
        out += [
            "",
            f"### Log attributes: `{outcome}` outcome",
            "",
            f"Events: {names}.",
            "",
        ]
        out += _table(entries)
    return "\n".join(out) + "\n"


def update_faq(text: str, section: str) -> str:
    """Replace the text between the markers with the section."""
    if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise ValueError("Expected exactly one begin marker and one end marker.")
    begin = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER)
    if end < begin:
        raise ValueError("The end marker comes before the begin marker.")
    head = text[: begin + len(BEGIN_MARKER)]
    return f"{head}\n{section}{text[end:]}"


def main(
    argv: list[str] | None = None,
    *,
    faq_path: Path = FAQ_PATH,
    schema_dir: Path = SCHEMA_DIR,
) -> int:
    """Update the FAQ, or check it with --check. Return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if the FAQ is stale. Do not write."
    )
    args = parser.parse_args(argv)

    schema = json.loads((schema_dir / "signal_schema.json").read_text(encoding="utf-8"))
    description = json.loads(
        (schema_dir / "signal_schema_description.json").read_text(encoding="utf-8")
    )
    text = faq_path.read_text(encoding="utf-8")
    try:
        new_text = update_faq(text, render_otel_section(schema, description))
    except ValueError as exc:
        print(f"{faq_path}: {exc}", file=sys.stderr)
        return 1

    if new_text == text:
        return 0
    if args.check:
        print(f"{faq_path} is stale. Run scripts/update_docs.py.", file=sys.stderr)
        return 1
    faq_path.write_text(new_text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
