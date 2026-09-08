PYTHON ?= python3
SCRIPT_DIR := scripts
DOCS_DIR := docs
DATA_DIR := $(DOCS_DIR)/data

.PHONY: fetch build docs all test

fetch:
	$(PYTHON) $(SCRIPT_DIR)/fetch_zotero.py --output $(DATA_DIR)/zotero-library.json

build:
	$(PYTHON) $(SCRIPT_DIR)/build_all_publications.py $(DATA_DIR)/zotero-library.json $(DOCS_DIR)/publications.md

docs: build

all: fetch build

test:
	pytest -q
