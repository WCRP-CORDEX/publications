# Development workflow

This file contains the technical workflow for maintaining the Zotero-backed publication site.

## Overview

The repository stores a raw snapshot of the native Zotero JSON and derives a simple markdown publication page for the docs site. The raw snapshot remains the durable source of truth, so the site can be rebuilt even if the live Zotero library is unavailable or corrupted.

- Raw Zotero API snapshot: docs/data/zotero-library.json
- Generated markdown website: docs/publications.md
- Python scripts: scripts/

## Local automation

Use the Makefile for common tasks:

- make fetch: download the Zotero library as native JSON
- make build: generate the markdown publication page from the saved JSON
- make all: fetch and rebuild in one step
- make test: run the project tests

Example:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
make fetch
make build
```

The project uses a pinned dependency file so builds are reproducible across local runs and GitHub Actions.

The generated markdown includes a table of contents and a final publication-year subsection for each entry, and the entries are sorted by first author.

## Files

- scripts/fetch_zotero.py: fetches the live Zotero JSON output and saves it as a snapshot
- scripts/build_all_publications.py: basic builder that reads the JSON snapshot and renders the full publication list, grouped by collection then year, as a single markdown page.
- scripts/build_all_publications_by_year.py: alternate builder that ignores the collection hierarchy and groups every publication by year only, de-duplicating entries that share a DOI across collections. Future builders for other parts of the tree or output formats (e.g. HTML frames for embedding) will live alongside these in scripts/.
- docs/publications.md: generated website content, grouped by collection
- docs/publications_by_year.md: generated website content, grouped by year only
- docs/data/zotero-library.json: raw Zotero snapshot used as the source of truth

## Daily automation

The GitHub Actions workflow in .github/workflows/daily-zotero-sync.yml runs on a daily schedule and:

1. installs dependencies from requirements.txt
2. fetches the latest Zotero snapshot
3. rebuilds docs/publications.md
4. commits any updated docs back to the repository

## Reproducibility

To keep the setup stable:

- keep requirements.txt pinned
- prefer the saved JSON snapshot as the rebuild source
- do not edit the generated markdown manually when a fresh snapshot can be rebuilt automatically
