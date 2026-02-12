#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""UBM - Universal Bookmarks Manager

A fast CLI tool for searching and retrieving bookmarks from multiple sources.

Usage:
    ubm import <file>                   # Import Twitter bookmark JSON
    ubm search <query>                  # Search bookmarks
    ubm list                            # List recent bookmarks
    ubm show <id>                       # Show bookmark details
    ubm stats                           # Database statistics
"""

import argparse
import sys
import time
from pathlib import Path

# Import from ubm package
from ubm import db, importer, search, display


def main():
    """Main entry point for UBM CLI."""
    parser = argparse.ArgumentParser(
        description='UBM - Universal Bookmarks Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import bookmarks from file')
    import_parser.add_argument('file', type=Path, help='Path to bookmark file')
    import_parser.add_argument('--type', dest='source_type', choices=['twitter'],
                              help='Bookmark source type (auto-detected if not specified)')
    import_parser.add_argument('--dry-run', action='store_true',
                              help='Preview import without writing to database')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search bookmarks')
    search_parser.add_argument('query', nargs='?', help='Search query (FTS5 syntax)')
    search_parser.add_argument('--author', help='Filter by author (handle or name)')
    search_parser.add_argument('--after', help='Filter by date (YYYY-MM-DD or ISO format)')
    search_parser.add_argument('--before', help='Filter by date (YYYY-MM-DD or ISO format)')
    search_parser.add_argument('--source', dest='source_type', help='Filter by source type')
    search_parser.add_argument('--limit', type=int, default=50, help='Maximum results (default: 50)')
    search_parser.add_argument('--offset', type=int, default=0, help='Skip first N results')
    search_parser.add_argument('--order', dest='order_by', default='rank',
                              choices=['rank', 'date_desc', 'date_asc'],
                              help='Sort order (default: rank)')
    search_parser.add_argument('--full', action='store_true',
                              help='Show full content (not truncated)')
    search_parser.add_argument('--no-ids', dest='show_ids', action='store_false',
                              help='Hide bookmark IDs from output')

    # List command
    list_parser = subparsers.add_parser('list', help='List recent bookmarks')
    list_parser.add_argument('--author', help='Filter by author (handle or name)')
    list_parser.add_argument('--source', dest='source_type', help='Filter by source type')
    list_parser.add_argument('--limit', type=int, default=20, help='Maximum results (default: 20)')
    list_parser.add_argument('--offset', type=int, default=0, help='Skip first N results')
    list_parser.add_argument('--full', action='store_true',
                              help='Show full content (not truncated)')
    list_parser.add_argument('--no-ids', dest='show_ids', action='store_false',
                              help='Hide bookmark IDs from output')

    # Show command
    show_parser = subparsers.add_parser('show', help='Show bookmark details')
    show_parser.add_argument('id', help='Bookmark ID')
    show_parser.add_argument('--json', action='store_true', help='Output as JSON')

    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')

    # Sources command (import history)
    sources_parser = subparsers.add_parser('sources', help='Show import history')
    sources_parser.add_argument('--limit', type=int, default=10, help='Maximum records (default: 10)')

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Get database connection (auto-initialises on first run)
    conn = None
    try:
        conn = db.get_connection()
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)

    # Execute command
    try:
        if args.command == 'import':
            cmd_import(conn, args)
        elif args.command == 'search':
            cmd_search(conn, args)
        elif args.command == 'list':
            cmd_list(conn, args)
        elif args.command == 'show':
            cmd_show(conn, args)
        elif args.command == 'stats':
            cmd_stats(conn)
        elif args.command == 'sources':
            cmd_sources(conn, args)
        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()


def cmd_import(conn, args):
    """Import bookmarks from file."""
    start_time = time.time()

    try:
        stats = importer.import_bookmarks(
            args.file, conn,
            source_type=getattr(args, 'source_type', None),
            dry_run=args.dry_run
        )
        elapsed = time.time() - start_time

        print(display.format_import_result(stats, str(args.file), elapsed))

        if stats.errors > 0:
            print(f"\nWarning: {stats.errors} bookmark(s) had errors and were skipped",
                  file=sys.stderr)

    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_search(conn, args):
    """Search bookmarks."""
    if not args.query:
        print("Error: Search query required", file=sys.stderr)
        sys.exit(1)

    # Build search options
    options = search.SearchOptions(
        query=args.query,
        author=args.author,
        after=args.after,
        before=args.before,
        source_type=args.source_type,
        limit=args.limit,
        offset=args.offset,
        order_by=args.order_by
    )

    # Count total matches
    total = search.count_matches(conn, options)

    if total == 0:
        print("No bookmarks found matching your query.")
        return

    # Get results
    results = search.search_bookmarks(conn, options)

    # Display results
    showing = min(args.limit, len(results))
    print(f"Searched for: {args.query}")
    print(f"Showing {showing} of {total} results\n")
    print(display.format_list(results, show_source=True, full=args.full, show_ids=args.show_ids))


def cmd_list(conn, args):
    """List recent bookmarks."""
    results = search.list_bookmarks(
        conn,
        limit=args.limit,
        offset=args.offset,
        author=args.author,
        source_type=args.source_type
    )

    if not results:
        print("No bookmarks found.")
        return

    print(display.format_list(results, show_source=True, full=args.full, show_ids=args.show_ids))


def cmd_show(conn, args):
    """Show bookmark details."""
    bookmark = search.get_bookmark_by_id(conn, args.id)

    if not bookmark:
        print(f"Bookmark not found: {args.id}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        import json
        print(json.dumps(bookmark, indent=2))
    else:
        print(display.format_show(bookmark))


def cmd_stats(conn):
    """Show database statistics."""
    stats = db.get_stats(conn)
    print(display.format_stats(stats))


def cmd_sources(conn, args):
    """Show import history."""
    history = importer.get_import_history(conn, limit=args.limit)
    print(display.format_import_history(history))


if __name__ == '__main__':
    main()
