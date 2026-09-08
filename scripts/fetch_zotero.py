#!/usr/bin/env python3
"""Fetch and store the raw Zotero JSON payload as a snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

ZOTERO_PAGE_SIZE = 100  # Zotero API max is 100 per request

DEFAULT_LIBRARY_ID = "5816477"
DEFAULT_COLLECTION = ""  # empty means whole library


def _fetch_json(url: str, api_key: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Zotero-API-Key"] = api_key

    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=60) as response:
        payload = response.read().decode("utf-8")

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Zotero API did not return valid JSON: {exc}") from exc


def _fetch_all_pages(base_url: str, api_key: str | None = None, limit: int | None = None) -> list[Any]:
    """Fetch every page of a Zotero list endpoint, following start/limit until exhausted."""
    results: list[Any] = []
    start = 0
    page_size = ZOTERO_PAGE_SIZE if limit is None else min(limit, ZOTERO_PAGE_SIZE)

    while True:
        separator = "&" if "?" in base_url else "?"
        page_url = f"{base_url}{separator}start={start}&limit={page_size}"
        page = _fetch_json(page_url, api_key=api_key)
        if not isinstance(page, list) or not page:
            break

        results.extend(page)
        start += len(page)

        if limit is not None and len(results) >= limit:
            return results[:limit]
        if len(page) < page_size:
            break

    return results


def fetch_zotero_json(
    library_id: str,
    collection_key: str | None = None,
    api_key: str | None = None,
    limit: int | None = None,
) -> dict:
    items_url = f"https://api.zotero.org/groups/{library_id}/items?format=json"
    if collection_key:
        items_url = f"https://api.zotero.org/groups/{library_id}/collections/{collection_key}/items?format=json"

    collections_url = f"https://api.zotero.org/groups/{library_id}/collections?format=json"
    items_data = _fetch_all_pages(items_url, api_key=api_key, limit=limit)
    collections_data = _fetch_all_pages(collections_url, api_key=api_key)

    return {
        "library": {"id": int(library_id), "name": "WCRP-CORDEX"},
        "collections": collections_data,
        "items": items_data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the native Zotero JSON library snapshot.")
    parser.add_argument("--library-id", default=os.environ.get("ZOTERO_LIBRARY_ID", DEFAULT_LIBRARY_ID), help="Zotero group/library ID")
    parser.add_argument("--collection-key", default=os.environ.get("ZOTERO_COLLECTION_KEY", DEFAULT_COLLECTION), help="Optional collection key to restrict the fetch")
    parser.add_argument("--api-key", default=os.environ.get("ZOTERO_API_KEY"), help="Optional Zotero API key")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for number of items downloaded")
    parser.add_argument("--output", type=Path, default=Path("docs/data/zotero-library.json"), help="Where to save the raw JSON snapshot")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = fetch_zotero_json(args.library_id, args.collection_key or None, args.api_key, limit=args.limit)
    except error.HTTPError as exc:
        raise SystemExit(f"Zotero API request failed with HTTP {exc.code}: {exc.reason}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Unable to reach Zotero API: {exc}") from exc

    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved Zotero snapshot to {output}")
    print(f"Saved {len(payload.get('collections', []))} collections and {len(payload.get('items', []))} items")


if __name__ == "__main__":
    main()
