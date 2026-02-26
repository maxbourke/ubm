#!/bin/bash
# Rollback categorisation - removes all categorisation data but keeps bookmarks intact

set -e

DB_PATH="${UBM_DB_PATH:-$HOME/.ubm/ubm.db}"

echo "UBM Categorisation Rollback"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Database: $DB_PATH"
echo ""
echo "This will DELETE all categorisation data:"
echo "  - All categories and taxonomy"
echo "  - All bookmark category assignments"
echo "  - All categorisation state and logs"
echo ""
echo "Your bookmarks will NOT be affected."
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Creating backup..."
BACKUP="${DB_PATH}.backup-$(date +%Y%m%d-%H%M%S)"
cp "$DB_PATH" "$BACKUP"
echo "Backup created: $BACKUP"

echo ""
echo "Removing categorisation tables..."
sqlite3 "$DB_PATH" <<'SQL'
-- Drop all categorisation tables
DROP TABLE IF EXISTS bookmark_categories;
DROP TABLE IF EXISTS categorisation_state;
DROP TABLE IF EXISTS categorisation_log;
DROP TABLE IF EXISTS taxonomy_history;
DROP TABLE IF EXISTS categories;

-- Reset schema version to 0 (pre-categorisation)
DELETE FROM schema_metadata WHERE key = 'version';

-- Verify bookmarks are intact
SELECT COUNT(*) as bookmark_count FROM bookmarks;
SQL

echo ""
echo "✓ Categorisation removed successfully!"
echo ""
echo "Summary:"
echo "  - Categorisation tables dropped"
echo "  - Schema version reset to 0"
echo "  - Bookmarks remain intact"
echo ""
echo "To restore categorisation:"
echo "  1. Run any ubm command to trigger migration"
echo "  2. Generate new taxonomy: ubm categorise init"
echo ""
echo "To restore from backup:"
echo "  cp \"$BACKUP\" \"$DB_PATH\""
