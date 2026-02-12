"""Database layer for UBM - schema, connections, and migrations."""

import os
import sqlite3
from pathlib import Path
from typing import Optional


# Database path: configurable via environment variable
# Default: ~/.ubm/ubm.db (portable, works on all platforms)
# Override: Set UBM_DB_PATH=/custom/path/ubm.db
DEFAULT_DB_PATH = Path(os.getenv('UBM_DB_PATH', str(Path.home() / '.ubm' / 'ubm.db')))


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get database connection, initialising schema if needed.

    Args:
        db_path: Path to database file (default: ~/.ubm/ubm.db or $UBM_DB_PATH)

    Returns:
        SQLite connection object
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if database exists
    is_new_db = not db_path.exists()

    # Connect to database
    conn = sqlite3.Connection(db_path)
    conn.row_factory = sqlite3.Row  # Access columns by name

    # Initialise schema if new database
    if is_new_db:
        init_schema(conn)

    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialise database schema with tables and indexes.

    Creates:
    - bookmarks table (core data)
    - bookmarks_fts FTS5 virtual table (full-text search)
    - import_history table (tracking imports)
    - Triggers to keep FTS index synced
    - Indexes for fast queries
    """
    cursor = conn.cursor()

    # Core bookmarks table (source-agnostic design)
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

    # FTS5 virtual table for fast full-text search
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

    # Trigger to keep FTS index synced on INSERT
    cursor.execute("""
        CREATE TRIGGER bookmarks_ai AFTER INSERT ON bookmarks BEGIN
            INSERT INTO bookmarks_fts(rowid, content, author_handle, author_name, url)
            VALUES (new.rowid, new.content, new.author_handle, new.author_name, new.url);
        END
    """)

    # Trigger to keep FTS index synced on UPDATE
    cursor.execute("""
        CREATE TRIGGER bookmarks_au AFTER UPDATE ON bookmarks BEGIN
            UPDATE bookmarks_fts
            SET content = new.content,
                author_handle = new.author_handle,
                author_name = new.author_name,
                url = new.url
            WHERE rowid = new.rowid;
        END
    """)

    # Trigger to keep FTS index synced on DELETE
    cursor.execute("""
        CREATE TRIGGER bookmarks_ad AFTER DELETE ON bookmarks BEGIN
            DELETE FROM bookmarks_fts WHERE rowid = old.rowid;
        END
    """)

    # Import history tracking (for deduplication and reporting)
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

    # Indexes for fast queries
    cursor.execute("CREATE INDEX idx_created_at ON bookmarks(created_at)")
    cursor.execute("CREATE INDEX idx_source_type ON bookmarks(source_type)")
    cursor.execute("CREATE INDEX idx_author_handle ON bookmarks(author_handle)")

    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    """Get database statistics.

    Returns:
        Dictionary with stats: total bookmarks, by source type, date range, db size
    """
    cursor = conn.cursor()

    # Total bookmarks
    cursor.execute("SELECT COUNT(*) as total FROM bookmarks")
    total = cursor.fetchone()['total']

    # By source type
    cursor.execute("""
        SELECT source_type, COUNT(*) as count
        FROM bookmarks
        GROUP BY source_type
    """)
    by_source = {row['source_type']: row['count'] for row in cursor.fetchall()}

    # Date range
    cursor.execute("""
        SELECT
            MIN(created_at) as earliest,
            MAX(created_at) as latest
        FROM bookmarks
        WHERE created_at IS NOT NULL
    """)
    date_range = cursor.fetchone()

    # Database size (in bytes)
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    db_size = cursor.fetchone()['size']

    # Import count
    cursor.execute("SELECT COUNT(*) as import_count FROM import_history")
    import_count = cursor.fetchone()['import_count']

    return {
        'total': total,
        'by_source': by_source,
        'earliest': date_range['earliest'] if date_range else None,
        'latest': date_range['latest'] if date_range else None,
        'db_size': db_size,
        'import_count': import_count
    }
