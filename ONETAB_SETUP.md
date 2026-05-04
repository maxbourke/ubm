# OneTab Integration for ubm

This guide explains how to set up and use automatic OneTab syncing with ubm (Universal Bookmarks Manager).

## What It Does

OneTab integration allows you to:
- Automatically sync tabs saved in the OneTab Chrome extension to ubm's SQLite database
- Search OneTab tabs alongside Twitter bookmarks: `ubm search "query" --source onetab`
- List OneTab tabs by group: `ubm list --source onetab`
- Filter searches: `ubm search "python" --source onetab`

## Prerequisites

1. **OneTab Chrome extension installed** — https://www.one-tab.com/
2. **Python 3.11+** (already installed)
3. **Google Chrome** (real browser, not Brave/Edge)
4. **Playwright browser binaries**

## Setup

### Step 1: Install Playwright Binaries (One-Time)

The scraper uses Playwright to access the OneTab extension. You need to install the Chromium binary:

```bash
playwright install chromium
```

This downloads ~400MB of browser binaries to `~/.cache/ms-playwright/` and is a one-time operation.

### Step 2: Manual Sync (Test)

Test that the scraper works before setting up automation:

```bash
# Dry-run preview (no database changes)
ubm onetab --dry-run

# Actual import
ubm onetab
```

The command will:
1. Launch Chrome with your real user profile (non-headless)
2. Navigate to `chrome-extension://chphlpgkkbolifaimnlloiipkdnihall/onetab.html`
3. Scrape all groups and tabs
4. Insert into `~/.ubm/ubm.db` with `source_type='onetab'`

### Step 3: Automatic Syncing (Optional)

Set up daily automatic syncing at 9am:

```bash
# Load the LaunchAgent (runs daily at 9am)
launchctl load ~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist

# To disable:
launchctl unload ~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist

# Check recent runs:
tail -f ~/.ubm/onetab-sync.log
```

## How It Works

### Scraping

The `ubm onetab` command:
1. Uses Playwright + real Chrome profile to access the extension URL
2. Scrapes DOM elements: `.tabGroup`, `.createdDate`, `.tabLink`
3. Extracts: URL, title, group creation date, position in group
4. Returns structured data to the importer

### Deduplication

Each tab gets a stable ID based on:
```
id = onetab_{sha256(group_date|url)[:16]}
```

This means:
- **Same URL in different groups** → separate records (group context is preserved)
- **Same URL, same group, re-imported** → skipped (idempotent)
- **Re-running `ubm onetab`** → safe; only new/changed entries are added

### Data Mapping

| OneTab | ubm Column | Value |
|---|---|---|
| Tab URL | `url` | Direct |
| Tab title | `title` | Direct |
| Group date | `created_at` | ISO datetime (e.g., `2026-05-04T16:44:59`) |
| Group date | `author_name` | `"Group: 2026-05-04T16:44:59"` |
| Title + group | `content` | FTS-indexed for search |
| Metadata | `metadata_json` | group_index, tab_position, scraped_at |

## Searching

```bash
# Search all bookmarks (Twitter + OneTab)
ubm search "python"

# OneTab only
ubm search "python" --source onetab

# Twitter only
ubm search "python" --source twitter

# List recent OneTab entries
ubm list --source onetab --limit 50
```

## Troubleshooting

### Playwright not found
```
Error: playwright not installed
```
Solution: `playwright install chromium`

### Chrome won't launch
The scraper needs **real Chrome**, not Brave or Edge. Ensure you have:
```bash
which google-chrome  # or /Applications/Google\ Chrome.app on macOS
```

### Extension not found
```
Error: No tabs loaded from OneTab
```
Possible causes:
- OneTab extension not installed or disabled
- Chrome profile path wrong (hardcoded to `~/Library/Application Support/Google/Chrome`)

### Sync log shows errors
Check the log for details:
```bash
cat ~/.ubm/onetab-sync.log
tail -f ~/.ubm/onetab-sync.log  # Follow live
```

## Manual Backup

Before syncing large numbers of tabs, back up your ubm database:
```bash
cp ~/.ubm/ubm.db ~/.ubm/ubm.db.backup-$(date +%Y-%m-%d-%H%M)
```

## Disabling OneTab Sync

To stop automatic syncing:
```bash
launchctl unload ~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist
```

The plist file can be deleted, but keeping it allows easy re-enable:
```bash
launchctl load ~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist
```

## Files

- **Scraper**: `ubm/onetab_scraper.py`
- **Importer**: `ubm/importer.py` (functions: `import_onetab`, `_import_onetab_data`)
- **CLI**: `ubm.py` (command: `onetab`)
- **Scheduler**: `scripts/onetab-sync.sh` + `~/Library/LaunchAgents/com.maxbourke.ubm-onetab-sync.plist`
- **Tests**: `test_onetab_scraper.py`, `test_onetab_importer.py`

## Notes

- OneTab groups are **unnamed** — identified by creation date + tab count
- Group creation dates are stored, so you can see when tabs were saved: `ubm list --source onetab --full`
- The scraper is **read-only** — it doesn't modify OneTab or delete anything
- Chrome launches **non-headless** (visible window) to access the extension
