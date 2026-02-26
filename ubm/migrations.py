"""Database migration system for versioned schema changes."""

import sqlite3
from typing import Callable, Dict


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from metadata table.

    Args:
        conn: Database connection

    Returns:
        Current schema version (0 if no migrations have run)
    """
    cursor = conn.cursor()

    # Check if metadata table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_metadata'
    """)

    if not cursor.fetchone():
        return 0

    # Get version
    cursor.execute("SELECT value FROM schema_metadata WHERE key='version'")
    row = cursor.fetchone()

    return int(row[0]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Update schema version in metadata table.

    Args:
        conn: Database connection
        version: New schema version
    """
    cursor = conn.cursor()

    # Create metadata table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Insert or update version
    cursor.execute("""
        INSERT OR REPLACE INTO schema_metadata (key, value)
        VALUES ('version', ?)
    """, (str(version),))

    conn.commit()


def migration_001_add_categorisation_tables(conn: sqlite3.Connection) -> None:
    """Migration 001: Add categorisation system tables.

    Creates:
    - categories (hierarchical taxonomy)
    - bookmark_categories (many-to-many assignments)
    - categorisation_state (processing status)
    - categorisation_log (edge cases and suggestions)
    - taxonomy_history (audit trail)
    - 8 indexes for performance
    """
    cursor = conn.cursor()

    # Table 1: Categories - Hierarchical taxonomy structure
    cursor.execute("""
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            parent_id INTEGER,
            description TEXT,
            level INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    """)

    # Table 2: Bookmark Categories - Many-to-many assignments
    cursor.execute("""
        CREATE TABLE bookmark_categories (
            bookmark_id TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            confidence REAL DEFAULT 1.0,
            assigned_at TEXT NOT NULL,
            assigned_by TEXT DEFAULT 'auto',
            PRIMARY KEY (bookmark_id, category_id),
            FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    """)

    # Table 3: Categorisation State - Track processing status
    cursor.execute("""
        CREATE TABLE categorisation_state (
            bookmark_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            last_attempt TEXT,
            attempt_count INTEGER DEFAULT 0,
            error_message TEXT,
            FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE
        )
    """)

    # Table 4: Categorisation Log - Edge cases and suggestions
    cursor.execute("""
        CREATE TABLE categorisation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bookmark_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            suggested_category TEXT,
            confidence REAL,
            created_at TEXT NOT NULL,
            reviewed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE
        )
    """)

    # Table 5: Taxonomy History - Audit trail
    cursor.execute("""
        CREATE TABLE taxonomy_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            description TEXT,
            sample_size INTEGER,
            model_used TEXT,
            created_at TEXT NOT NULL,
            metadata_json TEXT
        )
    """)

    # Indexes for performance
    cursor.execute("CREATE INDEX idx_categories_parent ON categories(parent_id)")
    cursor.execute("CREATE INDEX idx_categories_level ON categories(level)")
    cursor.execute("CREATE INDEX idx_bookmark_categories_bookmark ON bookmark_categories(bookmark_id)")
    cursor.execute("CREATE INDEX idx_bookmark_categories_category ON bookmark_categories(category_id)")
    cursor.execute("CREATE INDEX idx_bookmark_categories_confidence ON bookmark_categories(confidence)")
    cursor.execute("CREATE INDEX idx_categorisation_state_status ON categorisation_state(status)")
    cursor.execute("CREATE INDEX idx_categorisation_log_reviewed ON categorisation_log(reviewed)")
    cursor.execute("CREATE INDEX idx_categorisation_log_event_type ON categorisation_log(event_type)")

    conn.commit()


# Migration registry: version -> migration function
MIGRATIONS: Dict[int, Callable[[sqlite3.Connection], None]] = {
    1: migration_001_add_categorisation_tables,
}


def run_migrations(conn: sqlite3.Connection) -> None:
    """Execute all pending migrations in order.

    Args:
        conn: Database connection
    """
    current_version = get_schema_version(conn)
    target_version = max(MIGRATIONS.keys())

    if current_version >= target_version:
        # No migrations needed
        return

    # Run migrations in order
    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            migration_func = MIGRATIONS[version]

            # Run migration in transaction
            try:
                migration_func(conn)
                set_schema_version(conn, version)
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Migration {version} failed: {e}") from e
