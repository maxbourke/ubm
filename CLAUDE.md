# ubm Project Guidelines

## OneTab Importer Status (2026-05-09)

**Stage**: Working in dev; production isolated in `/Users/maxbourke/Code/PROD/ubm`

**Current State**:
- Scraper (`ubm/onetab_scraper.py`) uses AppleScript + Chrome JavaScript on macOS
- No Playwright dependency; relies on `osascript` plus a running Google Chrome with OneTab installed
- CLI integration is present via `ubm onetab`
- Lightweight unit tests pass: `test_onetab_scraper.py`, `test_onetab_importer.py`
- Production launcher now points at `/Users/maxbourke/Code/PROD/ubm/ubm.py`, not this working tree

**Rollback Strategy**:
- **Current dev HEAD**: `83eb140` (`Rewrite OneTab scraper to use AppleScript instead of Playwright`)
- **Rollback branch**: `rollback-point` → `d4592fd`
- **Production launcher backup**: `~/bin/ubm.backup-20260509-134247`

**Local Validation**:
```bash
python3 -c "from ubm.onetab_scraper import scrape_onetab; tabs = scrape_onetab(); print(f'Scraped {len(tabs)} tabs')"
python3 test_onetab_scraper.py
python3 test_onetab_importer.py
```

**Git Commits (OneTab work)**:
- `bb83272` — Add OneTab importer for ubm (scraper + importer + CLI)
- `a25900f` — Add OneTab scheduling and documentation
- `83eb140` — Rewrite OneTab scraper to use AppleScript instead of Playwright

**Files Changed**:
- Modified: `ubm.py`, `ubm/importer.py`
- Created: `ubm/onetab_scraper.py`, `test_*.py`, `ONETAB_SETUP.md`, scheduler files

---

## Standalone Instagram Work (Codex)

- Additional work has been done with Codex in `instagram-saved-sync/`
- This is currently a separate standalone Instagram saved-post / collection-sync prototype, not integrated into the main UBM CLI
- It includes collection discovery, lightweight collection membership scraping, staged Instagram sync ideas, and local state/roadmap work
- More work is still needed before integration, but the expectation is that it will eventually feed into UBM in some form

---

## x-thread-getter

A companion tool for fetching full X.com threads and X Articles as Markdown + JSON. Lives in `x-thread-getter/` within this repo.

- **Script:** `x-thread-getter/x-thread-getter.py` → symlinked as `~/bin/x-thread-getter`
- **README:** `x-thread-getter/README.md` (usage, output format, dependencies)
- **Design history:** `~/Documents/mb Obsidian Vault/PROJECTS/CODING/X-Thread-Getter - Scraping X (twitter) posts and threads via logged in account.md`
- **Output:** `~/Documents/mb Obsidian Vault/Clippings/X.com Clippings/`

---

## General Notes

(Add project-specific guidelines here as needed)
