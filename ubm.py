#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""UBM - Universal Bookmarks Manager

A fast CLI tool for searching and retrieving bookmarks from multiple sources.

Usage:
    ubm x                               # Quick import: latest twitter-Bookmarks-*.json from ~/Downloads
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
from ubm import db, importer, search, display, categoriser


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

    # Quick import command (x = eXpress import)
    x_parser = subparsers.add_parser('x', help='Quick import: latest twitter-Bookmarks-*.json from ~/Downloads')
    x_parser.add_argument('--dry-run', action='store_true',
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

    # Categorise command group
    categorise_parser = subparsers.add_parser('categorise', help='Categorise bookmarks using AI')
    categorise_subparsers = categorise_parser.add_subparsers(dest='categorise_command', help='Categorise subcommand')

    # categorise init - Generate taxonomy
    init_parser = categorise_subparsers.add_parser('init', help='Generate taxonomy from sample')
    init_parser.add_argument('--sample-size', type=int, default=500, help='Sample size (default: 500)')
    init_parser.add_argument('--strategy', choices=['diverse', 'random'], default='diverse',
                            help='Sampling strategy (default: diverse)')
    init_parser.add_argument('--model', help='LLM model to use (default: qwen-3.3-80b)')
    init_parser.add_argument('--dry-run', action='store_true', help='Preview sample without generating taxonomy')
    init_parser.add_argument('--yes', '-y', action='store_true', help='Skip approval prompt')

    # categorise run - Categorise bookmarks
    run_parser = categorise_subparsers.add_parser('run', help='Categorise bookmarks')
    run_parser.add_argument('--limit', type=int, help='Maximum bookmarks to categorise')
    run_parser.add_argument('--ids', nargs='+', help='Specific bookmark IDs to categorise')
    run_parser.add_argument('--model', help='LLM model to use (default: step-3.5-flash)')
    run_parser.add_argument('--rate-limit', type=float, default=3.0,
                           help='Seconds between API calls (default: 3.0, use 0 for paid APIs)')
    run_parser.add_argument('--two-call', action='store_true',
                           help='Use two-call approach: free-form + ontology (2x cost, may find better categories)')

    # categorise stats - Show statistics
    categorise_subparsers.add_parser('stats', help='Show categorisation statistics')

    # categorise list - Display taxonomy
    list_tax_parser = categorise_subparsers.add_parser('list', help='Display taxonomy tree')
    list_tax_parser.add_argument('--counts', action='store_true', help='Show bookmark counts per category')

    # categorise review - Review edge cases
    review_parser = categorise_subparsers.add_parser('review', help='Review edge cases and suggestions')
    review_parser.add_argument('--type', choices=['low_confidence', 'taxonomy_suggestion', 'error'],
                              help='Filter by event type')
    review_parser.add_argument('--limit', type=int, default=50, help='Maximum items (default: 50)')

    # categorise reset - Remove all categorisation data
    reset_parser = categorise_subparsers.add_parser('reset', help='Remove all categorisation data (keeps bookmarks)')
    reset_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')

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
        elif args.command == 'x':
            cmd_x(conn, args)
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
        elif args.command == 'categorise':
            cmd_categorise(conn, args)
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


def cmd_x(conn, args):
    """Quick import: most recent Twitter bookmarks from ~/Downloads."""
    start_time = time.time()

    downloads = Path.home() / 'Downloads'
    twitter_files = sorted(downloads.glob('twitter-Bookmarks-*.json'),
                          key=lambda p: p.stat().st_mtime, reverse=True)

    if not twitter_files:
        print("Error: No twitter-Bookmarks-*.json files found in ~/Downloads", file=sys.stderr)
        sys.exit(1)

    file_path = twitter_files[0]
    print(f"Found: {file_path.name}")

    try:
        stats = importer.import_bookmarks(
            file_path, conn,
            source_type='twitter',
            dry_run=args.dry_run
        )
        elapsed = time.time() - start_time

        print(display.format_import_result(stats, str(file_path), elapsed))

        if stats.errors > 0:
            print(f"\nWarning: {stats.errors} bookmark(s) had errors and were skipped",
                  file=sys.stderr)

    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
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

    # Load categories if they exist
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, bc.confidence
        FROM bookmark_categories bc
        JOIN categories c ON bc.category_id = c.id
        WHERE bc.bookmark_id = ?
        ORDER BY bc.confidence DESC
    """, (args.id,))
    categories = [dict(row) for row in cursor.fetchall()]

    if args.json:
        import json
        bookmark_dict = dict(bookmark)
        if categories:
            bookmark_dict['categories'] = categories
        print(json.dumps(bookmark_dict, indent=2))
    else:
        print(display.format_show(bookmark, categories=categories if categories else None))


def cmd_stats(conn):
    """Show database statistics."""
    stats = db.get_stats(conn)
    print(display.format_stats(stats))


def cmd_sources(conn, args):
    """Show import history."""
    history = importer.get_import_history(conn, limit=args.limit)
    print(display.format_import_history(history))


def cmd_categorise(conn, args):
    """Handle categorise subcommands."""
    if not args.categorise_command:
        print("Error: Categorise subcommand required", file=sys.stderr)
        print("Use 'ubm categorise --help' for available commands", file=sys.stderr)
        sys.exit(1)

    if args.categorise_command == 'init':
        cmd_categorise_init(conn, args)
    elif args.categorise_command == 'run':
        cmd_categorise_run(conn, args)
    elif args.categorise_command == 'stats':
        cmd_categorise_stats(conn, args)
    elif args.categorise_command == 'list':
        cmd_categorise_list(conn, args)
    elif args.categorise_command == 'review':
        cmd_categorise_review(conn, args)
    elif args.categorise_command == 'reset':
        cmd_categorise_reset(conn, args)
    else:
        print(f"Error: Unknown categorise command: {args.categorise_command}", file=sys.stderr)
        sys.exit(1)


def cmd_categorise_init(conn, args):
    """Generate taxonomy from sample bookmarks."""
    # Check if API key is set
    if not categoriser.OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Check if taxonomy already exists
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    existing_count = cursor.fetchone()['count']

    if existing_count > 0:
        if not args.yes:
            print(f"Warning: Taxonomy already exists with {existing_count} categories", file=sys.stderr)
            response = input("Regenerate taxonomy? This will DELETE existing categories (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(0)

        # Clear existing taxonomy
        cursor.execute("DELETE FROM categories")
        conn.commit()
        print("Cleared existing taxonomy.")

    # Sample bookmarks
    print(f"Sampling {args.sample_size} bookmarks using '{args.strategy}' strategy...")
    strategy_func = categoriser.SAMPLING_STRATEGIES.get(args.strategy)
    if not strategy_func:
        print(f"Error: Unknown sampling strategy: {args.strategy}", file=sys.stderr)
        sys.exit(1)

    bookmarks = strategy_func(conn, args.sample_size)
    print(f"Sampled {len(bookmarks)} bookmarks")

    if args.dry_run:
        print("\nSample preview (first 10):")
        for i, bm in enumerate(bookmarks[:10], 1):
            author = bm.get('author_handle', 'unknown')
            content = (bm.get('content') or '')[:100]
            print(f"{i}. @{author}: {content}")
        print("\n[Dry run - no taxonomy generated]")
        return

    # Generate taxonomy
    print("\nGenerating taxonomy with LLM...")
    model = args.model or categoriser.DEFAULT_TAXONOMY_MODEL
    print(f"Using model: {model}")

    client = categoriser.LLMClient(categoriser.OPENROUTER_API_KEY)
    prompt = categoriser.generate_taxonomy_prompt(bookmarks, len(bookmarks))

    try:
        response = client.chat_completion(
            messages=[{'role': 'user', 'content': prompt}],
            model=model,
            temperature=0.7,
            max_tokens=4000,
            log_type='taxonomy_generation'
        )

        categories = categoriser.parse_taxonomy_response(response)
        print(f"\nGenerated {len(categories)} categories")

        # Display taxonomy tree - build name-to-id mapping for parent references
        name_to_id = {}
        category_dicts = []
        for i, cat in enumerate(categories, 1):
            name_to_id[cat.name] = i
            category_dicts.append({
                'id': i,
                'name': cat.name,
                'parent': cat.parent,  # Store parent name temporarily
                'description': cat.description,
                'level': cat.level
            })

        # Resolve parent names to IDs
        for cat_dict in category_dicts:
            parent_name = cat_dict.pop('parent')
            cat_dict['parent_id'] = name_to_id.get(parent_name) if parent_name else None

        print("\n" + display.format_taxonomy_tree(category_dicts, show_counts=False))

        # Approval prompt
        if not args.yes:
            print("\n" + "━" * 60)
            response = input("Save this taxonomy? (Y/n): ")
            if response.lower() == 'n':
                print("Aborted.")
                sys.exit(0)

        # Save taxonomy
        categoriser.save_taxonomy(conn, categories, len(bookmarks), model)
        print(f"\nTaxonomy saved! Use 'ubm categorise run' to start categorisation.")

    except Exception as e:
        print(f"\nError generating taxonomy: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_categorise_run(conn, args):
    """Categorise bookmarks using LLM."""
    # Check if API key is set
    if not categoriser.OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Check if taxonomy exists
    categories = categoriser.get_all_categories(conn)
    if not categories:
        print("Error: No taxonomy found. Run 'ubm categorise init' first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(categories)} categories")

    # Get bookmarks to categorise
    if args.ids:
        bookmark_ids = args.ids
        print(f"Categorising {len(bookmark_ids)} specified bookmarks...")
    else:
        bookmark_ids = categoriser.get_uncategorised_bookmarks(conn, limit=args.limit)
        print(f"Found {len(bookmark_ids)} uncategorised bookmarks")

        if not bookmark_ids:
            print("All bookmarks are already categorised!")
            return

    # Categorise bookmarks
    model = args.model or categoriser.DEFAULT_CATEGORISATION_MODEL
    rate_limit = args.rate_limit
    calls_per_bookmark = 2 if args.two_call else 1
    print(f"Using model: {model}")
    print(f"Mode: {'Two-call (free-form + ontology)' if args.two_call else 'Single-call (ontology only)'}")
    print(f"Rate limit: {rate_limit}s between requests")
    print(f"Estimated time: {len(bookmark_ids) * calls_per_bookmark * (rate_limit + 3) / 60:.1f} minutes\n")

    client = categoriser.LLMClient(categoriser.OPENROUTER_API_KEY, rate_limit_delay=rate_limit)
    cursor = conn.cursor()

    success_count = 0
    error_count = 0
    start_time = time.time()

    for i, bookmark_id in enumerate(bookmark_ids, 1):
        try:
            # Get bookmark details
            cursor.execute("""
                SELECT id, content, author_handle
                FROM bookmarks
                WHERE id = ?
            """, (bookmark_id,))
            bookmark = dict(cursor.fetchone())

            # Two-call approach (optional)
            freeform_suggestions = []
            if args.two_call:
                # Step 1: Free-form categorisation
                freeform_prompt = categoriser.categorise_bookmark_freeform_prompt(bookmark)
                freeform_response = client.chat_completion(
                    messages=[{'role': 'user', 'content': freeform_prompt}],
                    model=model,
                    temperature=0.3,
                    max_tokens=500,
                    log_type='categorisation_freeform',
                    bookmark_id=bookmark_id
                )
                freeform_suggestions = categoriser.parse_freeform_response(freeform_response)

            # Step 2: Ontology-based categorisation
            prompt = categoriser.categorise_bookmark_prompt(bookmark, categories)
            response = client.chat_completion(
                messages=[{'role': 'user', 'content': prompt}],
                model=model,
                temperature=0.3,
                max_tokens=500,
                log_type='categorisation_ontology',
                bookmark_id=bookmark_id
            )

            # Parse result
            result = categoriser.parse_categorisation_response(response)

            # Step 3: Merge free-form suggestions (if using two-call)
            if args.two_call and freeform_suggestions:
                # Add high-confidence free-form suggestions not already in ontology result
                ontology_suggestion_names = {s.name for s in result.suggestions}
                for free_sug in freeform_suggestions:
                    if free_sug.name not in ontology_suggestion_names:
                        result.suggestions.append(free_sug)

            # Save result
            categoriser.save_categorisation(conn, bookmark_id, result)

            success_count += 1

            # Progress update
            if i % 10 == 0 or i == len(bookmark_ids):
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(bookmark_ids) - i) / rate if rate > 0 else 0
                print(f"Progress: {i}/{len(bookmark_ids)} ({100*i/len(bookmark_ids):.1f}%) - "
                      f"Success: {success_count}, Errors: {error_count} - "
                      f"ETA: {remaining/60:.1f}m")

        except Exception as e:
            error_count += 1
            print(f"Error categorising {bookmark_id}: {e}", file=sys.stderr)

            # Log error
            cursor.execute("""
                INSERT INTO categorisation_log
                (bookmark_id, event_type, message, created_at)
                VALUES (?, 'error', ?, ?)
            """, (bookmark_id, str(e), time.strftime('%Y-%m-%dT%H:%M:%SZ')))
            conn.commit()

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed/60:.1f} minutes")
    print(f"Success: {success_count}, Errors: {error_count}")


def cmd_categorise_stats(conn, args):
    """Show categorisation statistics."""
    stats = categoriser.get_categorisation_stats(conn)
    print(display.format_categorisation_stats(stats))


def cmd_categorise_list(conn, args):
    """Display taxonomy tree."""
    categories = categoriser.get_all_categories(conn)

    if not categories:
        print("No taxonomy found. Run 'ubm categorise init' first.")
        return

    # Add bookmark counts if requested
    if args.counts:
        cursor = conn.cursor()
        for cat in categories:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM bookmark_categories
                WHERE category_id = ?
            """, (cat['id'],))
            cat['bookmark_count'] = cursor.fetchone()['count']

    print(display.format_taxonomy_tree(categories, show_counts=args.counts))


def cmd_categorise_review(conn, args):
    """Review edge cases and suggestions."""
    cursor = conn.cursor()

    # Build query
    query = """
        SELECT bookmark_id, event_type, message, suggested_category, confidence, created_at
        FROM categorisation_log
        WHERE reviewed = FALSE
    """

    if args.type:
        query += f" AND event_type = ?"
        params = (args.type,)
    else:
        params = ()

    query += " ORDER BY created_at DESC LIMIT ?"
    params = (*params, args.limit)

    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]

    print(display.format_review_items(items))


def cmd_categorise_reset(conn, args):
    """Remove all categorisation data (keeps bookmarks intact)."""
    cursor = conn.cursor()

    # Check if categorisation exists
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    category_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM bookmark_categories")
    assignment_count = cursor.fetchone()['count']

    if category_count == 0 and assignment_count == 0:
        print("No categorisation data found.")
        return

    # Show what will be deleted
    print("WARNING: This will DELETE all categorisation data:")
    print(f"  - {category_count} categories")
    print(f"  - {assignment_count} bookmark-category assignments")
    print(f"  - All categorisation state and logs")
    print()
    print("Your bookmarks will NOT be affected.")
    print()

    if not args.yes:
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    # Create backup
    import shutil
    from datetime import datetime
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    backup_path = db_path.parent / f"{db_path.name}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")
    print()

    # Drop tables
    print("Removing categorisation tables...")
    cursor.execute("DROP TABLE IF EXISTS bookmark_categories")
    cursor.execute("DROP TABLE IF EXISTS categorisation_state")
    cursor.execute("DROP TABLE IF EXISTS categorisation_log")
    cursor.execute("DROP TABLE IF EXISTS taxonomy_history")
    cursor.execute("DROP TABLE IF EXISTS categories")

    # Reset schema version
    cursor.execute("DELETE FROM schema_metadata WHERE key = 'version'")

    conn.commit()

    # Verify bookmarks intact
    cursor.execute("SELECT COUNT(*) as count FROM bookmarks")
    bookmark_count = cursor.fetchone()['count']

    print("✓ Categorisation removed successfully!")
    print()
    print(f"Bookmarks: {bookmark_count} (intact)")
    print(f"Backup: {backup_path}")
    print()
    print("To restore categorisation:")
    print("  1. Run any ubm command to trigger migration")
    print("  2. Generate new taxonomy: ubm categorise init")


if __name__ == '__main__':
    main()
