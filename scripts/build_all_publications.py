#!/usr/bin/env python3
"""Build markdown publications pages from a saved Zotero JSON snapshot."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from dateutil import parser as _date_parser
except ImportError:  # pragma: no cover - dateutil is a pinned dependency
    _date_parser = None

# Matches a plausible publication year anywhere in a string (1500-2199).
_YEAR_RE = re.compile(r"(1[5-9]\d{2}|2[01]\d{2})")


def _initials(first_name: str) -> str:
    """Turn "Jean-Pierre Klaus" into "J.-P.K." for compact author formatting."""
    if not first_name:
        return ""
    parts = []
    for word in first_name.split():
        pieces = [piece for piece in word.split("-") if piece]
        parts.append("-".join(f"{piece[0].upper()}." for piece in pieces))
    return "".join(parts)


def _normalize_creators(creators: list[dict[str, Any]] | None) -> list[str]:
    if not creators:
        return []

    names: list[str] = []
    for creator in creators:
        creator_type = str(creator.get("creatorType", "")).lower()
        if creator_type != "author":
            continue

        first_name = str(creator.get("firstName", "")).strip()
        last_name = str(creator.get("lastName", "")).strip()
        full_name = str(creator.get("name", "")).strip()

        if last_name and first_name:
            initials = _initials(first_name)
            names.append(f"{last_name} {initials}" if initials else last_name)
        elif last_name:
            names.append(last_name)
        elif first_name:
            names.append(first_name)
        elif full_name:
            names.append(full_name)
    return names


def _extract_year(item: dict[str, Any]) -> int | None:
    """Extract a publication year, preferring Zotero's own normalized date.

    Zotero dates have no consistent format, so we first trust the API's
    `meta.parsedDate` (computed server-side from the free-text date field).
    If that is missing, we fuzzy-parse the raw date with dateutil, and
    finally fall back to a plain regex search for a 4-digit year.
    """
    meta = item.get("meta", {}) if isinstance(item, dict) else {}
    parsed_date = str(meta.get("parsedDate", "")).strip()
    if parsed_date:
        match = _YEAR_RE.search(parsed_date)
        if match:
            return int(match.group(1))

    data = item.get("data", {}) if isinstance(item, dict) else {}
    raw_date = str(data.get("date", "")).strip()
    if not raw_date:
        return None

    if _date_parser is not None:
        try:
            parsed = _date_parser.parse(raw_date, fuzzy=True, default=datetime(1, 1, 1))
            if parsed.year != 1:
                return parsed.year
        except (ValueError, OverflowError, TypeError):
            pass

    match = _YEAR_RE.search(raw_date)
    return int(match.group(1)) if match else None


def _title_for_item(item: dict[str, Any]) -> str:
    data = item.get("data", {}) if isinstance(item, dict) else {}
    title = str(data.get("title", "Untitled")).strip()
    return title if title else "Untitled"


def _authors_for_item(item: dict[str, Any]) -> str:
    data = item.get("data", {}) if isinstance(item, dict) else {}
    authors = _normalize_creators(data.get("creators"))
    return ", ".join(authors) if authors else "Unknown author"


def _doi_url(data: dict[str, Any]) -> str:
    doi = str(data.get("DOI", "")).strip()
    if not doi:
        return ""
    if doi.startswith("http://") or doi.startswith("https://"):
        return doi
    return f"https://doi.org/{doi}"


def _build_collection_tree(collections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    raw: dict[str, dict[str, Any]] = {}
    for collection in collections:
        if not isinstance(collection, dict):
            continue
        data = collection.get("data", {}) or {}
        key = str(collection.get("key") or data.get("key") or "")
        if not key:
            continue
        parent = data.get("parentCollection")
        raw[key] = {
            "key": key,
            "name": str(data.get("name") or "Unnamed collection"),
            "parent": None if parent in {None, False} else str(parent),
            "deleted": bool(data.get("deleted")),
        }

    # A collection is excluded if it (or any of its ancestors) is trashed,
    # since Zotero does not mark descendants of a deleted collection.
    def _is_trashed(key: str, seen: set[str] | None = None) -> bool:
        seen = seen or set()
        if key in seen or key not in raw:
            return False
        seen.add(key)
        entry = raw[key]
        if entry["deleted"]:
            return True
        parent_key = entry["parent"]
        return bool(parent_key) and _is_trashed(parent_key, seen)

    nodes: dict[str, dict[str, Any]] = {}
    for key, entry in raw.items():
        if _is_trashed(key):
            continue
        nodes[key] = {
            "key": key,
            "name": entry["name"],
            "parent": entry["parent"],
            "children": [],
            "items": [],
            "items_by_year": {},
        }

    for node in list(nodes.values()):
        parent_key = node["parent"]
        if parent_key and parent_key in nodes:
            nodes[parent_key]["children"].append(node)
        elif parent_key and parent_key not in nodes:
            node["parent"] = None

    return nodes


def _sorted_year_keys(items_by_year: dict[int | None, list[dict[str, Any]]]) -> list[int | None]:
    """Return year keys sorted most-recent-first, with unknown years (None) last."""
    known_years = sorted((year for year in items_by_year if year is not None), reverse=True)
    if None in items_by_year:
        return known_years + [None]
    return known_years


def _anchor_id(key: str) -> str:
    # Zotero keys are unique per library, unlike collection names which can repeat
    # across the tree, so they make a safe and stable anchor identifier.
    return f"collection-{key.lower()}"


def _total_item_count(node: dict[str, Any]) -> int:
    """Count publications in a collection and all its descendant subcollections."""
    return len(node["items"]) + sum(_total_item_count(child) for child in node["children"])


def _attach_item_to_collection_node(node: dict[str, Any], item: dict[str, Any]) -> None:
    node["items"].append(item)
    node["items_by_year"].setdefault(item["year"], []).append(item)


def _populate_items_in_tree(tree: dict[str, dict[str, Any]], zotero_data: dict[str, Any] | list[dict[str, Any]]) -> None:
    if isinstance(zotero_data, list):
        items = zotero_data
    elif isinstance(zotero_data, dict):
        items = zotero_data.get("items", [])
    else:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data", {}) or {}
        if data.get("deleted"):
            continue
        if data.get("itemType") in {"attachment", "note"}:
            continue
        item_entry = {
            "key": item.get("key", ""),
            "title": _title_for_item(item),
            "authors": _authors_for_item(item),
            "year": _extract_year(item),
            "publication_title": str(data.get("publicationTitle", "")).strip() or str(data.get("libraryCatalog", "")).strip(),
            "url": _doi_url(data) or str(data.get("url", "")).strip(),
        }
        for collection_key in data.get("collections") or []:
            node = tree.get(str(collection_key))
            if node is not None:
                _attach_item_to_collection_node(node, item_entry)


def _format_entry_line(entry: dict[str, Any]) -> str:
    year_label = str(entry["year"]) if entry["year"] else "n.d."
    line = f"- {entry['authors']} ({year_label}) **{entry['title']}**."
    if entry["publication_title"]:
        line += f" *{entry['publication_title']}*."
    if entry["url"]:
        line += f" {entry['url']}"
    return line


def generate_markdown(zotero_file: Path | str) -> str:
    source = Path(zotero_file)
    payload = json.loads(source.read_text(encoding="utf-8"))

    collections = payload.get("collections", []) if isinstance(payload, dict) else []
    tree = _build_collection_tree(collections)
    _populate_items_in_tree(tree, payload)
    roots = sorted(
        [node for node in tree.values() if node["parent"] is None],
        key=lambda node: node["name"].lower(),
    )

    lines = [
        "# CORDEX Publications",
        "",
        "## Table of Contents",
        "",
    ]

    def write_toc(node: dict[str, Any], depth: int) -> None:
        indent = "  " * depth
        count = _total_item_count(node)
        lines.append(f"{indent}- [{node['name']}](#{_anchor_id(node['key'])}) ({count})")
        for child in sorted(node["children"], key=lambda item: item["name"].lower()):
            write_toc(child, depth + 1)

    for root in roots:
        write_toc(root, 0)

    lines.extend(["", "---", ""])

    def emit_year_block(node: dict[str, Any], heading_level: int) -> None:
        for year in _sorted_year_keys(node["items_by_year"]):
            year_label = str(year) if year is not None else "Undated"
            count = len(node["items_by_year"][year])
            lines.append(f"{'#' * heading_level} {year_label} ({count})")
            lines.append("")
            # Sort by the rendered line itself, which leads with the author surname.
            for entry in sorted(node["items_by_year"][year], key=lambda item: _format_entry_line(item).lower()):
                lines.append(_format_entry_line(entry))
            lines.append("")

    def emit_node(node: dict[str, Any], heading_level: int) -> None:
        lines.append(f'<a id="{_anchor_id(node["key"])}"></a>')
        lines.append(f"{'#' * heading_level} {node['name']} ({_total_item_count(node)})")
        lines.append("")
        emit_year_block(node, heading_level + 1)
        for child in sorted(node["children"], key=lambda item: item["name"].lower()):
            emit_node(child, heading_level + 1)

    for root in roots:
        emit_node(root, 2)

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build markdown publication pages from Zotero JSON.")
    parser.add_argument("input", type=Path, help="Path to a Zotero JSON snapshot file.")
    parser.add_argument("output", type=Path, help="Path to write the generated markdown page.")
    args = parser.parse_args()

    markdown = generate_markdown(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
