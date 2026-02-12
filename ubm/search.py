"""Search and query functionality using SQLite FTS5."""

import sqlite3
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class SearchOptions:
    """Options for search queries."""
    query: Optional[str] = None
    author: Optional[str] = None
    after: Optional[str] = None      # ISO date string
    before: Optional[str] = None     # ISO date string
    source_type: Optional[str] = None
    limit: int = 50
    offset: int = 0
    order_by: str = 'rank'  # 'rank', 'date_desc', 'date_asc'


def search_bookmarks(conn: sqlite3.Connection, options: SearchOptions) -> List[Dict]:
    """Search bookmarks with FTS5 and filters.

    Args:
        conn: Database connection
        options: Search options (query, filters, pagination)

    Returns:
        List of matching bookmarks (as dictionaries)
    """
    cursor = conn.cursor()

    # Build query based on options
    if options.query:
        # Full-text search with FTS5
        query, params = _build_fts_query(options)
    else:
        # List/browse without FTS (just filters)
        query, params = _build_browse_query(options)

    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_bookmark_by_id(conn: sqlite3.Connection, bookmark_id: str) -> Optional[Dict]:
    """Get a single bookmark by ID.

    Args:
        conn: Database connection
        bookmark_id: Bookmark ID to retrieve

    Returns:
        Bookmark dictionary or None if not found
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            id, source_type, source_file, imported_at,
            created_at, title, url, content,
            author_handle, author_name, metadata_json
        FROM bookmarks
        WHERE id = ?
    """, (bookmark_id,))

    row = cursor.fetchone()
    return dict(row) if row else None


def list_bookmarks(
    conn: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    author: Optional[str] = None,
    source_type: Optional[str] = None
) -> List[Dict]:
    """List bookmarks (most recent first) without search.

    Args:
        conn: Database connection
        limit: Maximum number of results
        offset: Number of results to skip (for pagination)
        author: Filter by author handle or name (optional)
        source_type: Filter by source type (optional)

    Returns:
        List of bookmarks (as dictionaries)
    """
    options = SearchOptions(
        query=None,
        author=author,
        source_type=source_type,
        limit=limit,
        offset=offset,
        order_by='date_desc'
    )
    return search_bookmarks(conn, options)


def _build_fts_query(options: SearchOptions) -> tuple[str, tuple]:
    """Build FTS5 query with filters.

    Returns:
        (SQL query string, parameter tuple)
    """
    # Base FTS5 query
    query_parts = ["""
        SELECT
            b.id, b.source_type, b.source_file, b.imported_at,
            b.created_at, b.title, b.url, b.content,
            b.author_handle, b.author_name, b.metadata_json,
            fts.rank
        FROM bookmarks b
        JOIN bookmarks_fts fts ON b.rowid = fts.rowid
        WHERE bookmarks_fts MATCH ?
    """]

    params = [options.query]

    # Add filters
    if options.author:
        query_parts.append("AND (b.author_handle LIKE ? OR b.author_name LIKE ?)")
        author_pattern = f"%{options.author}%"
        params.extend([author_pattern, author_pattern])

    if options.after:
        query_parts.append("AND b.created_at >= ?")
        params.append(options.after)

    if options.before:
        query_parts.append("AND b.created_at < ?")
        params.append(options.before)

    if options.source_type:
        query_parts.append("AND b.source_type = ?")
        params.append(options.source_type)

    # Order by
    if options.order_by == 'rank':
        query_parts.append("ORDER BY fts.rank")
    elif options.order_by == 'date_desc':
        query_parts.append("ORDER BY b.created_at DESC")
    elif options.order_by == 'date_asc':
        query_parts.append("ORDER BY b.created_at ASC")

    # Pagination
    query_parts.append("LIMIT ? OFFSET ?")
    params.extend([options.limit, options.offset])

    return '\n'.join(query_parts), tuple(params)


def _build_browse_query(options: SearchOptions) -> tuple[str, tuple]:
    """Build query for browsing without FTS (list/filter only).

    Returns:
        (SQL query string, parameter tuple)
    """
    query_parts = ["""
        SELECT
            id, source_type, source_file, imported_at,
            created_at, title, url, content,
            author_handle, author_name, metadata_json
        FROM bookmarks
        WHERE 1=1
    """]

    params = []

    # Add filters
    if options.author:
        query_parts.append("AND (author_handle LIKE ? OR author_name LIKE ?)")
        author_pattern = f"%{options.author}%"
        params.extend([author_pattern, author_pattern])

    if options.after:
        query_parts.append("AND created_at >= ?")
        params.append(options.after)

    if options.before:
        query_parts.append("AND created_at < ?")
        params.append(options.before)

    if options.source_type:
        query_parts.append("AND source_type = ?")
        params.append(options.source_type)

    # Order by (default to date desc for browsing)
    if options.order_by == 'date_desc':
        query_parts.append("ORDER BY created_at DESC")
    elif options.order_by == 'date_asc':
        query_parts.append("ORDER BY created_at ASC")
    else:
        # Default to date desc if no rank available
        query_parts.append("ORDER BY created_at DESC")

    # Pagination
    query_parts.append("LIMIT ? OFFSET ?")
    params.extend([options.limit, options.offset])

    return '\n'.join(query_parts), tuple(params)


def count_matches(conn: sqlite3.Connection, options: SearchOptions) -> int:
    """Count matching bookmarks without retrieving them.

    Args:
        conn: Database connection
        options: Search options

    Returns:
        Number of matching bookmarks
    """
    cursor = conn.cursor()

    if options.query:
        # Count FTS matches
        query_parts = ["""
            SELECT COUNT(*) as count
            FROM bookmarks b
            JOIN bookmarks_fts fts ON b.rowid = fts.rowid
            WHERE bookmarks_fts MATCH ?
        """]
        params = [options.query]
    else:
        # Count without FTS
        query_parts = ["SELECT COUNT(*) as count FROM bookmarks WHERE 1=1"]
        params = []

    # Add filters (same logic as search)
    if options.author:
        query_parts.append("AND (b.author_handle LIKE ? OR b.author_name LIKE ?)" if options.query else
                          "AND (author_handle LIKE ? OR author_name LIKE ?)")
        author_pattern = f"%{options.author}%"
        params.extend([author_pattern, author_pattern])

    if options.after:
        prefix = "b." if options.query else ""
        query_parts.append(f"AND {prefix}created_at >= ?")
        params.append(options.after)

    if options.before:
        prefix = "b." if options.query else ""
        query_parts.append(f"AND {prefix}created_at < ?")
        params.append(options.before)

    if options.source_type:
        prefix = "b." if options.query else ""
        query_parts.append(f"AND {prefix}source_type = ?")
        params.append(options.source_type)

    cursor.execute('\n'.join(query_parts), tuple(params))
    return cursor.fetchone()['count']
