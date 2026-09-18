#!/usr/bin/env python
# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
# scripts/_summarize_benchmarks.py
"""Combine several hyperfine --export-json files into one markdown table.

Internal helper for benchmark_timing.sh - not meant to be run standalone.
Each input file must contain exactly two results: telemetry disabled first,
then enabled (the order benchmark_timing.sh passes commands to hyperfine).

Usage:
    python scripts/_summarize_benchmarks.py <label>=<path.json> ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    headers = ["Benchmark", "Disabled (s)", "Enabled (s)", "Overhead"]
    rows = []
    for arg in sys.argv[1:]:
        label, p = arg.split("=", 1)
        path = Path(p)
        with path.open() as fh:
            results = json.load(fh)["results"]
        if len(results) != 2:
            raise ValueError(
                f"{path}: expected exactly 2 hyperfine results (disabled, enabled), "
                f"got {len(results)}"
            )
        disabled, enabled = results[0], results[1]
        overhead_pct = (enabled["mean"] - disabled["mean"]) / disabled["mean"] * 100
        rows.append(
            (
                label,
                f"{disabled['mean']:.3f} ± {disabled['stddev']:.3f}",
                f"{enabled['mean']:.3f} ± {enabled['stddev']:.3f}",
                f"{overhead_pct:+.1f}%",
            )
        )

    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(4)]

    def render_row(cells: tuple[str, ...]) -> str:
        return (
            "| "
            + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))
            + " |"
        )

    print(render_row(tuple(headers)))
    print("|" + "|".join(":" + "-" * (widths[i] - 1) for i in range(4)) + "|")
    for row in rows:
        print(render_row(row))


if __name__ == "__main__":
    main()
