#!/usr/bin/env python3
"""Unit tests for OneTab importer (no browser needed)."""

import sqlite3
import json
from ubm.importer import _import_onetab_data, _transform_onetab_bookmark
from ubm.onetab_scraper import generate_onetab_id


def _make_tab(url="https://example.com", title="Example Page",
              onetab_id="abc123", group_date="04/05/2026 16:44:59",
              group_date_iso="2026-05-04T16:44:59", group_label="34 tabs",
              group_index=0, tab_position=0, scraped_at="2026-05-04T16:57:00"):
    """Helper to create a tab dict matching scraper output."""
    return {
        "url": url, "title": title, "onetab_id": onetab_id,
        "group_date": group_date, "group_date_iso": group_date_iso,
        "group_label": group_label, "group_index": group_index,
        "tab_position": tab_position, "scraped_at": scraped_at,
    }


def create_test_db() -> sqlite3.Connection:
    """Create in-memory test database with ubm schema."""
    conn = sqlite3.Connection(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE bookmarks (
            id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_file TEXT,
            imported_at TEXT NOT NULL, created_at TEXT, title TEXT,
            url TEXT NOT NULL, content TEXT, author_handle TEXT,
            author_name TEXT, metadata_json TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL,
            source_type TEXT NOT NULL, imported_at TEXT NOT NULL,
            bookmark_count INTEGER NOT NULL, new_count INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
            content, author_handle, author_name, url,
            content='bookmarks', content_rowid='rowid'
        )
    """)
    cursor.execute("""
        CREATE TRIGGER bookmarks_ai AFTER INSERT ON bookmarks BEGIN
            INSERT INTO bookmarks_fts(rowid, content, author_handle, author_name, url)
            VALUES (new.rowid, new.content, new.author_handle, new.author_name, new.url);
        END
    """)
    conn.commit()
    return conn


def test_transform_onetab_bookmark():
    """Test OneTab bookmark transformation."""
    tab = _make_tab(tab_position=5)
    record = _transform_onetab_bookmark(tab)

    assert record['source_type'] == 'onetab'
    assert record['url'] == "https://example.com"
    assert record['title'] == "Example Page"
    assert record['created_at'] == "2026-05-04T16:44:59"
    assert "34 tabs" in record['author_name']
    assert "Example Page" in record['content']
    assert record['id'] == "onetab_abc123"

    metadata = json.loads(record['metadata_json'])
    assert metadata['onetab_id'] == "abc123"
    assert metadata['group_index'] == 0
    assert metadata['tab_position'] == 5

    print("  Bookmark transformation test passed")


def test_import_empty():
    """Test importing empty list."""
    conn = create_test_db()
    stats = _import_onetab_data([], conn)
    assert stats.total == 0 and stats.new == 0
    print("  Empty import test passed")


def test_import_basic():
    """Test importing basic tab data."""
    conn = create_test_db()
    tabs = [
        _make_tab(url="https://example.com", onetab_id="id1"),
        _make_tab(url="https://python.org", title="Python", onetab_id="id2", tab_position=1),
    ]
    stats = _import_onetab_data(tabs, conn)

    assert stats.total == 2 and stats.new == 2 and stats.duplicates == 0

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks WHERE source_type = 'onetab'")
    assert cursor.fetchone()['count'] == 2

    cursor.execute("SELECT * FROM import_history WHERE source_type = 'onetab'")
    history = cursor.fetchone()
    assert history['new_count'] == 2

    print("  Basic import test passed")


def test_deduplication():
    """Test: same tab re-imported = skip."""
    conn = create_test_db()
    tabs = [_make_tab()]

    stats1 = _import_onetab_data(tabs, conn)
    assert stats1.new == 1

    stats2 = _import_onetab_data(tabs, conn)
    assert stats2.new == 0 and stats2.duplicates == 1

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks")
    assert cursor.fetchone()['count'] == 1

    print("  Deduplication test passed")


def test_same_url_different_groups():
    """Test: same URL in different groups = separate records."""
    conn = create_test_db()
    tabs = [
        _make_tab(onetab_id="id-group1", group_index=0),
        _make_tab(onetab_id="id-group2", group_index=1,
                  group_date_iso="2026-05-04T15:00:00"),
    ]
    stats = _import_onetab_data(tabs, conn)
    assert stats.total == 2 and stats.new == 2 and stats.duplicates == 0

    print("  Same URL, different groups test passed")


def test_search():
    """Test FTS search works for onetab source."""
    conn = create_test_db()
    tabs = [_make_tab(url="https://python.org", title="Python Programming", onetab_id="pyid")]
    _import_onetab_data(tabs, conn)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.* FROM bookmarks b
        WHERE b.source_type = 'onetab' AND b.content LIKE '%Python%'
    """)
    results = [dict(row) for row in cursor.fetchall()]
    assert len(results) == 1 and "Python" in results[0]['title']

    print("  Search test passed")


def test_dry_run():
    """Test dry_run doesn't write to database."""
    conn = create_test_db()
    stats = _import_onetab_data([_make_tab()], conn, dry_run=True)
    assert stats.total == 1 and stats.new == 1

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks")
    assert cursor.fetchone()['count'] == 0

    print("  Dry-run test passed")


if __name__ == "__main__":
    test_transform_onetab_bookmark()
    test_import_empty()
    test_import_basic()
    test_deduplication()
    test_same_url_different_groups()
    test_search()
    test_dry_run()
    print("\nAll importer tests passed!")
