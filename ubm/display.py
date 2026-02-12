"""Output formatting for search results and bookmark details."""

import json
from typing import Dict, List
from datetime import datetime


def format_list(bookmarks: List[Dict], show_source: bool = False, full: bool = False, show_ids: bool = True) -> str:
    """Format bookmarks as a compact list (one line per bookmark).

    Args:
        bookmarks: List of bookmark dictionaries
        show_source: Include source type in output
        full: Show full content instead of truncated preview
        show_ids: Show bookmark IDs (for use with 'show' command)

    Returns:
        Formatted string for display
    """
    if not bookmarks:
        return "No bookmarks found."

    lines = []
    for i, bm in enumerate(bookmarks, 1):
        # Parse date
        date_str = _format_date(bm.get('created_at'))

        # Author (handle or name)
        author = bm.get('author_handle') or bm.get('author_name') or 'Unknown'
        if author and not author.startswith('@'):
            author = f"@{author}"

        # Content
        content = bm.get('content') or bm.get('title') or bm.get('url', '')

        if full:
            # Full content mode - preserve newlines
            content = content.strip()
        else:
            # Compact mode - single line, truncated
            content = content.replace('\n', ' ').strip()
            if len(content) > 80:
                content = content[:77] + '...'

        # Build line
        parts = [f"{i}."]

        if show_ids:
            parts.append(f"[{bm['id']}]")

        parts.append(f"[{date_str}]")

        if show_source and bm.get('source_type'):
            parts.append(f"({bm['source_type']})")

        parts.append(f"{author}:")

        if full:
            # Full mode: author on one line, content below with indent
            header = ' '.join(parts)
            lines.append(header)
            lines.append(f"  {content}")
            if bm.get('url'):
                lines.append(f"  {bm['url']}")
            lines.append("")  # Blank line between bookmarks
        else:
            # Compact mode: everything on one line
            parts.append(content)
            lines.append(' '.join(parts))

    return '\n'.join(lines)


def format_show(bookmark: Dict) -> str:
    """Format a single bookmark with full details.

    Args:
        bookmark: Bookmark dictionary

    Returns:
        Formatted string with full bookmark details
    """
    if not bookmark:
        return "Bookmark not found."

    # Parse metadata JSON
    metadata = {}
    if bookmark.get('metadata_json'):
        try:
            metadata = json.loads(bookmark['metadata_json'])
        except json.JSONDecodeError:
            pass

    # Build output
    lines = []
    lines.append("━" * 60)

    # Header
    source_type = bookmark.get('source_type', 'unknown').capitalize()
    lines.append(f"{source_type} Bookmark: {bookmark['id']}")

    # Author (Twitter-specific)
    if bookmark.get('author_handle') or bookmark.get('author_name'):
        author_handle = bookmark.get('author_handle', '')
        author_name = bookmark.get('author_name', '')
        if author_handle and author_name:
            lines.append(f"Author: @{author_handle} ({author_name})")
        elif author_handle:
            lines.append(f"Author: @{author_handle}")
        elif author_name:
            lines.append(f"Author: {author_name}")

    # Date
    if bookmark.get('created_at'):
        lines.append(f"Date: {bookmark['created_at']}")

    # URL
    lines.append(f"URL: {bookmark['url']}")

    lines.append("━" * 60)
    lines.append("")

    # Content
    if bookmark.get('title'):
        lines.append(f"Title: {bookmark['title']}")
        lines.append("")

    if bookmark.get('content'):
        lines.append(bookmark['content'])
        lines.append("")

    # Engagement stats (Twitter-specific)
    if metadata:
        engagement = []
        if 'favorite_count' in metadata:
            engagement.append(f"Likes: {metadata['favorite_count']}")
        if 'retweet_count' in metadata:
            engagement.append(f"Retweets: {metadata['retweet_count']}")
        if 'bookmark_count' in metadata:
            engagement.append(f"Bookmarks: {metadata['bookmark_count']}")
        if 'views_count' in metadata and metadata['views_count']:
            engagement.append(f"Views: {_format_number(metadata['views_count'])}")

        if engagement:
            lines.append("Engagement:")
            lines.append("  " + "  |  ".join(engagement))
            lines.append("")

        # Media
        if 'media' in metadata and metadata['media']:
            media_count = len(metadata['media'])
            media_types = [m.get('type', 'unknown') for m in metadata['media']]
            lines.append(f"Media: {media_count} attachment(s) - {', '.join(media_types)}")
            lines.append("")

    # Footer
    lines.append("━" * 60)

    return '\n'.join(lines)


def format_stats(stats: Dict) -> str:
    """Format database statistics.

    Args:
        stats: Statistics dictionary from db.get_stats()

    Returns:
        Formatted statistics string
    """
    lines = []
    lines.append("Database Statistics")
    lines.append("━" * 40)

    # Total
    lines.append(f"Total bookmarks: {_format_number(stats['total'])}")

    # By source
    if stats.get('by_source'):
        for source, count in stats['by_source'].items():
            lines.append(f"  - {source.capitalize()}: {_format_number(count)}")

    # Date range
    if stats.get('earliest') and stats.get('latest'):
        earliest = _format_date(stats['earliest'])
        latest = _format_date(stats['latest'])
        lines.append(f"Date range: {earliest} to {latest}")

    # Import count
    if stats.get('import_count'):
        lines.append(f"Imports: {stats['import_count']} file(s)")

    # Database size
    if stats.get('db_size'):
        size_mb = stats['db_size'] / (1024 * 1024)
        lines.append(f"Database size: {size_mb:.1f} MB")

    return '\n'.join(lines)


def format_import_result(stats: 'ImportStats', file_path: str, elapsed: float) -> str:
    """Format import operation results.

    Args:
        stats: ImportStats from importer
        file_path: Path to imported file
        elapsed: Time elapsed in seconds

    Returns:
        Formatted import summary
    """
    lines = []
    lines.append(f"Importing from {file_path}...")
    lines.append(f"Found {stats.total} bookmark(s)")
    lines.append(f"  - New: {stats.new}")
    lines.append(f"  - Duplicates: {stats.duplicates}")
    if stats.errors > 0:
        lines.append(f"  - Errors: {stats.errors}")
    lines.append(f"Import completed in {elapsed:.1f}s")

    return '\n'.join(lines)


def format_import_history(history: List[Dict]) -> str:
    """Format import history.

    Args:
        history: List of import history records

    Returns:
        Formatted import history
    """
    if not history:
        return "No imports found."

    lines = []
    lines.append("Import History")
    lines.append("━" * 60)

    for record in history:
        date = _format_date(record['imported_at'])
        source_type = record['source_type'].capitalize()
        file_name = record['source_file'].split('/')[-1]  # Just filename

        lines.append(f"[{date}] {source_type}")
        lines.append(f"  File: {file_name}")
        lines.append(f"  Total: {record['bookmark_count']}, "
                    f"New: {record['new_count']}, "
                    f"Duplicates: {record['duplicate_count']}")
        lines.append("")

    return '\n'.join(lines)


def _format_date(date_str: str) -> str:
    """Format ISO date string to readable format.

    Args:
        date_str: ISO 8601 date string

    Returns:
        Formatted date (YYYY-MM-DD)
    """
    if not date_str:
        return "Unknown"

    try:
        # Parse ISO date (may have timezone offset)
        # Try parsing with timezone first
        if '+' in date_str or date_str.endswith('Z'):
            # Has timezone info
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # No timezone
            dt = datetime.fromisoformat(date_str)

        return dt.strftime('%Y-%m-%d')
    except (ValueError, AttributeError):
        # Fallback: return first 10 chars if it looks like YYYY-MM-DD
        if len(date_str) >= 10:
            return date_str[:10]
        return date_str


def _format_number(num: int) -> str:
    """Format large numbers with commas.

    Args:
        num: Number to format

    Returns:
        Formatted number string
    """
    return f"{num:,}"
