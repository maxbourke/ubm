"""Import bookmarks from various sources (Twitter, Chrome, etc.)."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ImportStats:
    """Statistics from an import operation."""
    total: int
    new: int
    duplicates: int
    errors: int = 0


def _detect_twitter_format(file_path: Path) -> bool:
    """Check if file matches twitter-web-exporter format.

    Args:
        file_path: Path to file to check

    Returns:
        True if file appears to be twitter-web-exporter format
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # Check for twitter-specific fields in first bookmark
                first = data[0]
                required_fields = ['id', 'full_text', 'screen_name', 'url']
                return all(field in first for field in required_fields)
    except (json.JSONDecodeError, KeyError, IOError):
        return False
    return False


def _import_twitter_json(
    file_path: Path,
    conn: sqlite3.Connection,
    dry_run: bool = False
) -> ImportStats:
    """Import Twitter bookmarks from JSON file.

    Args:
        file_path: Path to Twitter bookmark JSON file
        conn: Database connection
        dry_run: If True, parse but don't write to database

    Returns:
        ImportStats with count of total, new, and duplicate bookmarks

    Raises:
        ValueError: If file is not valid JSON or missing required fields
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Load and validate JSON
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            bookmarks = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(bookmarks, list):
        raise ValueError("Expected JSON array of bookmarks")

    if len(bookmarks) == 0:
        return ImportStats(total=0, new=0, duplicates=0)

    # Transform to canonical schema
    transformed = []
    errors = 0
    for bm in bookmarks:
        try:
            transformed.append(_transform_twitter_bookmark(bm, file_path))
        except KeyError as e:
            errors += 1
            # Continue processing other bookmarks even if one fails

    if dry_run:
        return ImportStats(
            total=len(bookmarks),
            new=len(transformed),
            duplicates=0,
            errors=errors
        )

    # Bulk insert with deduplication
    cursor = conn.cursor()
    new_count = 0
    duplicate_count = 0

    for record in transformed:
        try:
            cursor.execute("""
                INSERT INTO bookmarks (
                    id, source_type, source_file, imported_at,
                    created_at, title, url, content,
                    author_handle, author_name, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['id'],
                record['source_type'],
                record['source_file'],
                record['imported_at'],
                record['created_at'],
                record['title'],
                record['url'],
                record['content'],
                record['author_handle'],
                record['author_name'],
                record['metadata_json']
            ))
            new_count += 1
        except sqlite3.IntegrityError:
            # Duplicate ID (PRIMARY KEY constraint)
            duplicate_count += 1

    # Record import history
    cursor.execute("""
        INSERT INTO import_history (
            source_file, source_type, imported_at,
            bookmark_count, new_count, duplicate_count
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        str(file_path),
        'twitter',
        datetime.now().isoformat(),
        len(bookmarks),
        new_count,
        duplicate_count
    ))

    conn.commit()

    return ImportStats(
        total=len(bookmarks),
        new=new_count,
        duplicates=duplicate_count,
        errors=errors
    )


def _transform_twitter_bookmark(bm: Dict, source_file: Path) -> Dict:
    """Transform Twitter bookmark JSON to canonical schema.

    Args:
        bm: Twitter bookmark dictionary
        source_file: Path to source file

    Returns:
        Dictionary with canonical bookmark fields

    Raises:
        KeyError: If required fields are missing
    """
    # Extract media thumbnail (first image/video if present)
    thumbnail_url = None
    media = bm.get('media', [])
    if media and len(media) > 0:
        first_media = media[0]
        # Try various thumbnail keys
        thumbnail_url = (
            first_media.get('media_url_https') or
            first_media.get('thumbnail') or
            first_media.get('url')
        )

    # Build metadata JSON with Twitter-specific fields
    metadata = {
        'favorite_count': bm.get('favorite_count', 0),
        'retweet_count': bm.get('retweet_count', 0),
        'bookmark_count': bm.get('bookmark_count', 0),
        'reply_count': bm.get('reply_count', 0),
        'quote_count': bm.get('quote_count', 0),
        'views_count': bm.get('views_count'),
        'profile_image_url': bm.get('profile_image_url'),
        'user_id': bm.get('user_id'),
        'media': media,
        'thumbnail_url': thumbnail_url,
        'favorited': bm.get('favorited', False),
        'retweeted': bm.get('retweeted', False),
    }

    # Required fields (will raise KeyError if missing)
    return {
        'id': bm['id'],
        'source_type': 'twitter',
        'source_file': str(source_file),
        'imported_at': datetime.now().isoformat(),
        'created_at': bm.get('created_at'),
        'title': None,  # Twitter doesn't have titles
        'url': bm['url'],
        'content': bm.get('full_text', ''),
        'author_handle': bm.get('screen_name', ''),
        'author_name': bm.get('name', ''),
        'metadata_json': json.dumps(metadata)
    }


def get_import_history(conn: sqlite3.Connection, limit: int = 10) -> List[Dict]:
    """Get recent import history.

    Args:
        conn: Database connection
        limit: Maximum number of records to return

    Returns:
        List of import history records (most recent first)
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            source_file,
            source_type,
            imported_at,
            bookmark_count,
            new_count,
            duplicate_count
        FROM import_history
        ORDER BY imported_at DESC
        LIMIT ?
    """, (limit,))

    return [dict(row) for row in cursor.fetchall()]


# Importer registry - maps source types to import functions
IMPORT_FUNCTIONS = {
    'twitter': _import_twitter_json,
    # Future: 'chrome': _import_chrome_json,
    # Future: 'firefox': _import_firefox_json,
}

# Detector registry - maps source types to detector functions
DETECTORS = {
    'twitter': _detect_twitter_format,
    # Future: 'chrome': _detect_chrome_format,
    # Future: 'firefox': _detect_firefox_format,
}


def detect_source_type(file_path: Path) -> str:
    """Auto-detect bookmark source type from file content.

    Args:
        file_path: Path to bookmark file

    Returns:
        Source type string ('twitter', 'chrome', etc.)

    Raises:
        ValueError: If source type cannot be detected
    """
    for source_type, detector_fn in DETECTORS.items():
        if detector_fn(file_path):
            return source_type

    raise ValueError(
        f"Could not detect bookmark format for: {file_path}\n"
        f"Supported formats: {', '.join(DETECTORS.keys())}"
    )


def import_bookmarks(
    file_path: Path,
    conn: sqlite3.Connection,
    source_type: Optional[str] = None,
    dry_run: bool = False
) -> ImportStats:
    """Import bookmarks from file with auto-detection support.

    This is the main public API for importing bookmarks. It supports
    auto-detection of source type or explicit specification.

    Args:
        file_path: Path to bookmark file
        conn: Database connection
        source_type: Explicit source type ('twitter', 'chrome', etc.)
                    or None for auto-detection
        dry_run: If True, parse but don't write to database

    Returns:
        ImportStats with count of total, new, and duplicate bookmarks

    Raises:
        ValueError: If source type is unknown or file format is invalid
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Auto-detect if not specified
    if source_type is None:
        source_type = detect_source_type(file_path)

    # Get import function for this source type
    import_fn = IMPORT_FUNCTIONS.get(source_type)
    if not import_fn:
        supported = ', '.join(IMPORT_FUNCTIONS.keys())
        raise ValueError(
            f"Unsupported source type '{source_type}'. "
            f"Supported types: {supported}"
        )

    # Delegate to source-specific importer
    return import_fn(file_path, conn, dry_run)


# Legacy public API - kept for backward compatibility
def import_twitter_json(
    file_path: Path,
    conn: sqlite3.Connection,
    dry_run: bool = False
) -> ImportStats:
    """Import Twitter bookmarks from JSON file.

    Legacy function - prefer using import_bookmarks() instead.
    Kept for backward compatibility.

    Args:
        file_path: Path to Twitter bookmark JSON file
        conn: Database connection
        dry_run: If True, parse but don't write to database

    Returns:
        ImportStats with count of total, new, and duplicate bookmarks

    Raises:
        ValueError: If file is not valid JSON or missing required fields
        FileNotFoundError: If file doesn't exist
    """
    return _import_twitter_json(file_path, conn, dry_run)
