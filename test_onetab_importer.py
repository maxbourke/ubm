#!/usr/bin/env python3
"""Unit tests for OneTab importer (without browser)."""

import sqlite3
import json
from pathlib import Path
from ubm.importer import _import_onetab_data, _transform_onetab_bookmark
from ubm.onetab_scraper import generate_onetab_id


def create_test_db() -> sqlite3.Connection:
    """Create in-memory test database with ubm schema."""
    conn = sqlite3.Connection(":memory:")
    conn.row_factory = sqlite3.Row

    # Create schema
    cursor = conn.cursor()

    # Core bookmarks table
    cursor.execute("""
        CREATE TABLE bookmarks (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_file TEXT,
            imported_at TEXT NOT NULL,
            created_at TEXT,
            title TEXT,
            url TEXT NOT NULL,
            content TEXT,
            author_handle TEXT,
            author_name TEXT,
            metadata_json TEXT
        )
    """)

    # Import history table
    cursor.execute("""
        CREATE TABLE import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            source_type TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            bookmark_count INTEGER NOT NULL,
            new_count INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL
        )
    """)

    # FTS5 virtual table for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
            content,
            author_handle,
            author_name,
            url,
            content='bookmarks',
            content_rowid='rowid'
        )
    """)

    # Triggers to keep FTS index synced on INSERT
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
    tab = {
        "url": "https://example.com",
        "title": "Example Page",
        "group_date": "2026-05-04T16:44:59",
        "group_index": 0,
        "tab_position": 5,
        "scraped_at": "2026-05-04T16:57:00"
    }

    record = _transform_onetab_bookmark(tab)

    assert record['source_type'] == 'onetab'
    assert record['url'] == "https://example.com"
    assert record['title'] == "Example Page"
    assert record['created_at'] == "2026-05-04T16:44:59"
    assert record['author_name'] == "Group: 2026-05-04T16:44:59"
    assert "Example Page" in record['content']
    assert "2026-05-04T16:44:59" in record['content']
    assert record['id'].startswith("onetab_")

    # Verify metadata
    metadata = json.loads(record['metadata_json'])
    assert metadata['group_date'] == "2026-05-04T16:44:59"
    assert metadata['group_index'] == 0
    assert metadata['tab_position'] == 5

    print("✓ Bookmark transformation test passed")


def test_import_onetab_data_empty():
    """Test importing empty list."""
    conn = create_test_db()
    tabs_data = []

    stats = _import_onetab_data(tabs_data, conn, dry_run=False)

    assert stats.total == 0
    assert stats.new == 0
    assert stats.duplicates == 0
    assert stats.errors == 0

    print("✓ Empty import test passed")


def test_import_onetab_data_basic():
    """Test importing basic tab data."""
    conn = create_test_db()

    tabs_data = [
        {
            "url": "https://example.com",
            "title": "Example Page",
            "group_date": "2026-05-04T16:44:59",
            "group_index": 0,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        },
        {
            "url": "https://python.org",
            "title": "Python Official",
            "group_date": "2026-05-04T16:44:59",
            "group_index": 0,
            "tab_position": 1,
            "scraped_at": "2026-05-04T16:57:00"
        }
    ]

    stats = _import_onetab_data(tabs_data, conn, dry_run=False)

    assert stats.total == 2
    assert stats.new == 2
    assert stats.duplicates == 0
    assert stats.errors == 0

    # Verify data in database
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks WHERE source_type = 'onetab'")
    count = cursor.fetchone()['count']
    assert count == 2

    # Verify import history
    cursor.execute("SELECT * FROM import_history WHERE source_type = 'onetab'")
    history = cursor.fetchone()
    assert history['bookmark_count'] == 2
    assert history['new_count'] == 2
    assert history['duplicate_count'] == 0

    print("✓ Basic import test passed")


def test_import_onetab_data_deduplication():
    """Test deduplication: same group_date + url = skip on re-import."""
    conn = create_test_db()

    tabs_data = [
        {
            "url": "https://example.com",
            "title": "Example Page",
            "group_date": "2026-05-04T16:44:59",
            "group_index": 0,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        }
    ]

    # First import
    stats1 = _import_onetab_data(tabs_data, conn, dry_run=False)
    assert stats1.new == 1

    # Second import with identical data
    stats2 = _import_onetab_data(tabs_data, conn, dry_run=False)
    assert stats2.new == 0
    assert stats2.duplicates == 1

    # Verify only one record in DB
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks")
    count = cursor.fetchone()['count']
    assert count == 1

    print("✓ Deduplication test passed")


def test_import_onetab_data_same_url_different_groups():
    """Test: same URL in different groups = separate records."""
    conn = create_test_db()

    tabs_data = [
        {
            "url": "https://example.com",
            "title": "Example Page",
            "group_date": "2026-05-04T16:44:59",  # Group 1
            "group_index": 0,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        },
        {
            "url": "https://example.com",  # Same URL
            "title": "Example Page",
            "group_date": "2026-05-04T15:00:00",  # Group 2 (different time)
            "group_index": 1,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        }
    ]

    stats = _import_onetab_data(tabs_data, conn, dry_run=False)

    assert stats.total == 2
    assert stats.new == 2
    assert stats.duplicates == 0

    # Verify both records in DB with different IDs
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM bookmarks ORDER BY id")
    ids = [row['id'] for row in cursor.fetchall()]
    assert len(ids) == 2
    assert ids[0] != ids[1]

    print("✓ Same URL, different groups test passed")


def test_search_onetab():
    """Test FTS search works for onetab source."""
    conn = create_test_db()

    tabs_data = [
        {
            "url": "https://python.org",
            "title": "Python Programming Language",
            "group_date": "2026-05-04T16:44:59",
            "group_index": 0,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        }
    ]

    _import_onetab_data(tabs_data, conn, dry_run=False)

    # Search for "python"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.* FROM bookmarks b
        WHERE b.source_type = 'onetab'
        AND b.content LIKE '%python%'
    """, ())
    results = [dict(row) for row in cursor.fetchall()]

    assert len(results) == 1
    assert "Python" in results[0]['title']

    print("✓ Search test passed")


def test_import_onetab_data_dry_run():
    """Test dry_run doesn't write to database."""
    conn = create_test_db()

    tabs_data = [
        {
            "url": "https://example.com",
            "title": "Example Page",
            "group_date": "2026-05-04T16:44:59",
            "group_index": 0,
            "tab_position": 0,
            "scraped_at": "2026-05-04T16:57:00"
        }
    ]

    stats = _import_onetab_data(tabs_data, conn, dry_run=True)

    assert stats.total == 1
    assert stats.new == 1

    # Verify database is empty (dry_run didn't write)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks")
    count = cursor.fetchone()['count']
    assert count == 0

    print("✓ Dry-run test passed")


if __name__ == "__main__":
    test_transform_onetab_bookmark()
    test_import_onetab_data_empty()
    test_import_onetab_data_basic()
    test_import_onetab_data_deduplication()
    test_import_onetab_data_same_url_different_groups()
    test_search_onetab()
    test_import_onetab_data_dry_run()
    print("\n✅ All importer tests passed!")
