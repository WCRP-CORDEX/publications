import json

from scripts.build_all_publications import generate_markdown
from scripts.build_all_publications_by_year import generate_markdown as generate_markdown_by_year


def _write_payload(tmp_path, payload):
    source = tmp_path / "zotero.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    return source


def test_toc_indents_subcollections_and_skips_years(tmp_path):
    payload = {
        "collections": [
            {"key": "root", "data": {"name": "Domain A", "parentCollection": None}},
            {"key": "child", "data": {"name": "Subcollection", "parentCollection": "root"}},
        ],
        "items": [
            {
                "key": "b",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Zulu Research",
                    "creators": [{"creatorType": "author", "firstName": "Dana", "lastName": "Smith"}],
                    "date": "2022-05-01",
                    "publicationTitle": "Journal of Tests",
                    "url": "https://example.com/zulu",
                    "collections": ["child"],
                },
            },
            {
                "key": "c",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Gamma Research",
                    "creators": [{"creatorType": "author", "firstName": "Gina", "lastName": "White"}],
                    "date": "2023-06-01",
                    "publicationTitle": "Journal of Tests",
                    "url": "https://example.com/gamma",
                    "collections": ["root"],
                },
            },
        ],
    }

    result = generate_markdown(_write_payload(tmp_path, payload))
    toc = result.split("---")[0]

    assert "- [Domain A](#collection-root) (2)" in toc
    assert "  - [Subcollection](#collection-child) (1)" in toc
    # Years must never appear in the table of contents.
    assert "2022" not in toc
    assert "2023" not in toc


def test_duplicate_collection_names_get_distinct_anchors(tmp_path):
    payload = {
        "collections": [
            {"key": "rootA", "data": {"name": "Root A", "parentCollection": None}},
            {"key": "rootB", "data": {"name": "Root B", "parentCollection": None}},
            {"key": "childA", "data": {"name": "Same Name", "parentCollection": "rootA"}},
            {"key": "childB", "data": {"name": "Same Name", "parentCollection": "rootB"}},
        ],
        "items": [],
    }

    result = generate_markdown(_write_payload(tmp_path, payload))

    assert '<a id="collection-childa"></a>' in result
    assert '<a id="collection-childb"></a>' in result
    assert "#collection-childa" in result
    assert "#collection-childb" in result


def test_entry_formatting_prefers_doi_over_url(tmp_path):
    payload = {
        "collections": [{"key": "root", "data": {"name": "Domain A", "parentCollection": None}}],
        "items": [
            {
                "key": "a",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Paper With DOI",
                    "creators": [{"creatorType": "author", "firstName": "Alicia", "lastName": "Brown"}],
                    "date": "2021-04-20",
                    "publicationTitle": "Journal of Tests",
                    "url": "https://example.com/should-not-be-used",
                    "DOI": "10.1234/abcd",
                    "collections": ["root"],
                },
            },
            {
                "key": "b",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Paper Without DOI",
                    "creators": [{"creatorType": "author", "firstName": "Dana", "lastName": "Smith"}],
                    "date": "2021-01-01",
                    "publicationTitle": "Journal of Tests",
                    "url": "https://example.com/fallback",
                    "collections": ["root"],
                },
            },
        ],
    }

    result = generate_markdown(_write_payload(tmp_path, payload))

    assert "- Brown A. (2021) **Paper With DOI**. *Journal of Tests*. [10.1234/abcd](https://doi.org/10.1234/abcd)" in result
    assert "- Smith D. (2021) **Paper Without DOI**. *Journal of Tests*. [https://example.com/fallback](https://example.com/fallback)" in result
    assert "https://example.com/should-not-be-used" not in result


def test_year_extraction_uses_parsed_date_and_fuzzy_fallback(tmp_path):
    payload = {
        "collections": [{"key": "root", "data": {"name": "Domain A", "parentCollection": None}}],
        "items": [
            {
                "key": "a",
                "meta": {"parsedDate": "2020"},
                "data": {
                    "itemType": "journalArticle",
                    "title": "Uses parsedDate",
                    "creators": [{"creatorType": "author", "firstName": "A", "lastName": "One"}],
                    "date": "garbage that only dateutil could guess 2020",
                    "collections": ["root"],
                },
            },
            {
                "key": "b",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Fuzzy parsed only",
                    "creators": [{"creatorType": "author", "firstName": "B", "lastName": "Two"}],
                    "date": "Spring 2019, revised",
                    "collections": ["root"],
                },
            },
            {
                "key": "c",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Undated entry",
                    "creators": [{"creatorType": "author", "firstName": "C", "lastName": "Three"}],
                    "date": "",
                    "collections": ["root"],
                },
            },
        ],
    }

    result = generate_markdown(_write_payload(tmp_path, payload))

    assert "### 2020 (1)" in result
    assert "### 2019 (1)" in result
    assert "### Undated (1)" in result
    assert result.index("### 2020 (1)") < result.index("### 2019 (1)")
    assert result.index("### 2019 (1)") < result.index("### Undated (1)")


def test_entries_within_a_year_are_sorted_by_author_surname(tmp_path):
    payload = {
        "collections": [{"key": "root", "data": {"name": "Domain A", "parentCollection": None}}],
        "items": [
            {
                "key": "z",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Zulu title comes first alphabetically",
                    "creators": [{"creatorType": "author", "firstName": "Alicia", "lastName": "Alpha"}],
                    "date": "2024-01-01",
                    "collections": ["root"],
                },
            },
            {
                "key": "a",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Alpha title comes last alphabetically",
                    "creators": [{"creatorType": "author", "firstName": "Zoe", "lastName": "Zulu"}],
                    "date": "2024-01-01",
                    "collections": ["root"],
                },
            },
        ],
    }

    result = generate_markdown(_write_payload(tmp_path, payload))

    # Sorting must follow the rendered entry (author surname first), not the title.
    assert result.index("Alpha A.") < result.index("Zulu Z.")


def test_by_year_builder_ignores_collections_and_lists_all_years(tmp_path):
    payload = {
        "collections": [
            {"key": "rootA", "data": {"name": "Collection One", "parentCollection": None}},
            {"key": "rootB", "data": {"name": "Collection Two", "parentCollection": None}},
        ],
        "items": [
            {
                "key": "a",
                "data": {
                    "itemType": "journalArticle",
                    "title": "First Paper",
                    "creators": [{"creatorType": "author", "firstName": "Alicia", "lastName": "Brown"}],
                    "date": "2023-01-01",
                    "collections": ["rootA"],
                },
            },
            {
                "key": "b",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Second Paper",
                    "creators": [{"creatorType": "author", "firstName": "Dana", "lastName": "Smith"}],
                    "date": "2022-01-01",
                    "collections": ["rootB"],
                },
            },
        ],
    }

    result = generate_markdown_by_year(_write_payload(tmp_path, payload))

    assert result.startswith("# CORDEX Publications by Year\n\n")
    assert "## 2023 (1)" in result
    assert "## 2022 (1)" in result
    assert result.index("## 2023 (1)") < result.index("## 2022 (1)")
    assert "Collection One" not in result
    assert "Collection Two" not in result


def test_by_year_builder_deduplicates_by_doi_across_collections(tmp_path):
    payload = {
        "collections": [
            {"key": "rootA", "data": {"name": "Domain A", "parentCollection": None}},
            {"key": "rootB", "data": {"name": "Domain B", "parentCollection": None}},
        ],
        "items": [
            {
                "key": "a1",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Same Paper Added Twice",
                    "creators": [{"creatorType": "author", "firstName": "Alicia", "lastName": "Brown"}],
                    "date": "2023-01-01",
                    "DOI": "10.1234/dup",
                    "collections": ["rootA"],
                },
            },
            {
                "key": "a2",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Same Paper Added Twice",
                    "creators": [{"creatorType": "author", "firstName": "Alicia", "lastName": "Brown"}],
                    "date": "2023-01-01",
                    "DOI": "HTTPS://DOI.ORG/10.1234/DUP",
                    "collections": ["rootB"],
                },
            },
            {
                "key": "b1",
                "data": {
                    "itemType": "journalArticle",
                    "title": "Unique Paper Without DOI",
                    "creators": [{"creatorType": "author", "firstName": "Dana", "lastName": "Smith"}],
                    "date": "2023-01-01",
                    "collections": ["rootA"],
                },
            },
        ],
    }

    result = generate_markdown_by_year(_write_payload(tmp_path, payload))

    assert result.count("Same Paper Added Twice") == 1
    assert "Unique Paper Without DOI" in result
    assert "## 2023 (2)" in result
