#!/usr/bin/env python3
"""Build a markdown publications page grouped only by year, ignoring collections.

Unlike build_all_publications.py, this builder flattens the whole library into
a single list of years (still respecting trashed items via "deleted": true).
Since the same publication can be added to the library more than once under
different Zotero item keys, entries are de-duplicated by DOI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_all_publications import (  # noqa: E402
    _build_entry,
    _format_entry_line,
    _iter_active_items,
    _sorted_year_keys,
)


def _canonical_doi(item: dict[str, Any]) -> str:
    data = item.get("data", {}) if isinstance(item, dict) else {}
    doi = str(data.get("DOI", "")).strip().lower()
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/") :]
    return doi


def _deduplicate_by_doi(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop items sharing a DOI with an earlier item; items without a DOI are kept as-is."""
    seen_dois: set[str] = set()
    unique_items = []
    for item in items:
        doi = _canonical_doi(item)
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)
        unique_items.append(item)
    return unique_items


def generate_markdown(zotero_file: Path | str) -> str:
    source = Path(zotero_file)
    payload = json.loads(source.read_text(encoding="utf-8"))

    items = _deduplicate_by_doi(_iter_active_items(payload))
    entries_by_year: dict[int | None, list[dict[str, Any]]] = {}
    for item in items:
        entry = _build_entry(item)
        entries_by_year.setdefault(entry["year"], []).append(entry)

    lines = [
        "# CORDEX Publications by Year",
        "",
        "## Table of Contents",
        "",
    ]

    for year in _sorted_year_keys(entries_by_year):
        year_label = str(year) if year is not None else "Undated"
        anchor = f"year-{year_label.lower()}"
        count = len(entries_by_year[year])
        lines.append(f"- [{year_label}](#{anchor}) ({count})")

    lines.extend(["", "---", ""])

    for year in _sorted_year_keys(entries_by_year):
        year_label = str(year) if year is not None else "Undated"
        anchor = f"year-{year_label.lower()}"
        count = len(entries_by_year[year])
        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"## {year_label} ({count})")
        lines.append("")
        # Sort by the rendered line itself, which leads with the author surname.
        for entry in sorted(entries_by_year[year], key=lambda item: _format_entry_line(item).lower()):
            lines.append(_format_entry_line(entry))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a year-only markdown publication page from Zotero JSON.")
    parser.add_argument("input", type=Path, help="Path to a Zotero JSON snapshot file.")
    parser.add_argument("output", type=Path, help="Path to write the generated markdown page.")
    args = parser.parse_args()

    markdown = generate_markdown(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
