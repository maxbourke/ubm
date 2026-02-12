# UBM Product Roadmap

## Planned Features

### Export Functionality
**Command:** `ubm export`

Export bookmarks from the database to various formats:
- JSON (primary format - full data export)
- CSV (for spreadsheet analysis)
- HTML (readable bookmark page)
- Markdown (for note-taking tools)

**Options:**
- Filter by date range, author, source
- Full export vs filtered export
- Pretty-print vs compact JSON

**Use cases:**
- Backup/portability
- Data analysis in other tools
- Sharing curated bookmark collections
- Migration to other systems

---

### Auto-Import Watch Service
**Goal:** Automatically import bookmark files when they appear in watched directories

**Two potential approaches:**

#### Option 1: Standalone daemon (`ubm watch`)
- New command: `ubm watch [--config FILE]`
- Background service that monitors directories
- Config file specifies watch patterns and import rules
- Logs imports to a file

#### Option 2: Integration with existing download watcher
- User already has a download monitoring script
- Add UBM import logic to existing watcher
- Single unified watch service

**Configuration example:**
```yaml
watch:
  - path: ~/Downloads
    patterns:
      - "twitter-Bookmarks-*.json"
      - "Twitter-Bookmarks-*.json"
    action: import
    source_type: twitter
    archive_after_import: ~/Documents/bookmark-archives/
    notify: true
```

**Features needed:**
- Pattern matching (glob/regex)
- Duplicate detection (don't reimport same file)
- Optional: move/archive after successful import
- Optional: desktop notifications on import
- Optional: error handling/retry logic

**Questions to resolve:**
- Should this be `ubm watch` or integrate with existing watcher?
- Where should the config file live? (`~/.config/ubm/watch.yaml`?)
- How to handle errors (file is invalid JSON, already imported, etc.)?
- Should it watch multiple directories?

---

## Future Ideas (Backlog)

### Additional Import Sources
- Browser bookmark exports (Chrome, Firefox, Safari)
- Raindrop.io export
- Pocket export
- Reddit saved posts
- Mastodon/Bluesky bookmarks

### Enhanced Search
- Tag support
- Boolean operators UI helper
- Saved searches
- Search history

### Web Interface
- Simple local web UI for browsing bookmarks
- Better for browsing than CLI
- Shareable bookmark collections

### Sync & Backup
- Automatic backup to cloud storage
- Sync between machines

### AI Features
- Automatic tagging/categorisation
- Summary generation for long threads
- Duplicate/similar bookmark detection

---

## Technical Debt / Improvements

- Add comprehensive test suite
- Performance benchmarks for large datasets
- Documentation improvements
- Installation script (setup.py or pyproject.toml)
- Package for PyPI distribution

---

## Decisions Needed

1. **Watch service architecture:**
   - Standalone vs integration with existing watcher?
   - If standalone: daemon process or cron job?

2. **Export formats:**
   - Which formats are priorities?
   - Should we support custom export templates?

3. **Configuration:**
   - YAML, TOML, or JSON for config files?
   - Where should config files live?
