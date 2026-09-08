#!/usr/bin/env python3
"""Extract the Zotero collection tree and print it in a simple JSON form."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def extract_collection_tree(zotero_payload: dict[str, Any]) -> dict[str, Any]:
    collections = zotero_payload.get("collections", []) if isinstance(zotero_payload, dict) else []
    nodes: dict[str, dict[str, Any]] = {}

    for collection in collections:
        if not isinstance(collection, dict):
            continue
        data = collection.get("data", {}) or {}
        key = str(collection.get("key") or data.get("key") or "")
        if not key:
            continue
        parent = data.get("parentCollection")
        nodes[key] = {
            "key": key,
            "name": str(data.get("name") or "Unnamed collection"),
            "parent": None if parent in {None, False} else str(parent),
            "children": [],
            "items": [],
            "items_by_year": {},
        }

    for node in nodes.values():
        parent_key = node["parent"]
        if parent_key and parent_key in nodes:
            nodes[parent_key]["children"].append(node)

    roots = [node for node in nodes.values() if node["parent"] is None]
    roots.sort(key=lambda item: item["name"].lower())
    return {"roots": roots, "nodes": nodes}


def populate_collection_tree(zotero_payload: dict[str, Any]) -> dict[str, Any]:
    tree = extract_collection_tree(zotero_payload)
    nodes = tree["nodes"]
    items = zotero_payload.get("items", []) if isinstance(zotero_payload, dict) else []

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data", {}) or {}
        if data.get("itemType") in {"attachment", "note"}:
            continue
        collection_keys = data.get("collections") or []
        if not collection_keys:
            continue
        for collection_key in collection_keys:
            node = nodes.get(str(collection_key))
            if not node:
                continue
            entry = {
                "key": item.get("key"),
                "title": str(data.get("title") or "Untitled"),
                "authors": ", ".join(
                    [
                        str(creator.get("firstName", "")) + " " + str(creator.get("lastName", ""))
                        for creator in (data.get("creators") or [])
                        if str(creator.get("creatorType", "")).lower() == "author"
                    ]
                ).strip(),
                "year": int(str(data.get("date", "") or "")[:4]) if str(data.get("date", ""))[:4].isdigit() else None,
                "url": str(data.get("url", "") or ""),
                "publicationTitle": str(data.get("publicationTitle", "") or ""),
                "itemType": str(data.get("itemType", "") or ""),
            }
            node["items"].append(entry)
            if entry["year"] is not None:
                node["items_by_year"].setdefault(entry["year"], []).append(entry)

    return tree


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract the Zotero collection tree from a saved JSON snapshot.")
    parser.add_argument("input", type=Path, help="Path to a Zotero JSON snapshot file.")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    tree = populate_collection_tree(payload)
    print(json.dumps({"roots": [node["name"] for node in tree["roots"]]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
