"""Scrape OneTab Chrome extension and extract tabs."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict


ONETAB_EXTENSION_URL = "chrome-extension://chphlpgkkbolifaimnlloiipkdnihall/onetab.html"
CHROME_PROFILE = Path.home() / "Library/Application Support/Google/Chrome"


def scrape_onetab() -> List[Dict]:
    """Scrape OneTab extension using real Chrome profile.

    Returns a list of tab dicts with:
    - url: tab URL
    - title: tab title
    - group_date: ISO datetime when group was created (parsed from DOM)
    - group_index: 0 = newest group, increments downward
    - tab_position: 0-based position within group
    - scraped_at: ISO datetime when this scrape ran

    Requires:
    - Real Chrome browser with OneTab extension installed
    - playwright installed: pip install playwright
    - Browser binaries: playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    tabs = []
    scraped_at = datetime.now().isoformat()

    with sync_playwright() as p:
        # Use persistent context to access real Chrome profile with OneTab extension
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE),
            channel="chrome",  # Use system Chrome, not Playwright's bundled version
            headless=False,    # Non-headless required for extension access
        )

        page = context.new_page()
        page.goto(ONETAB_EXTENSION_URL, wait_until="domcontentloaded")

        # Wait for tab groups to load
        page.wait_for_selector(".tabGroup", timeout=5000)

        # Extract all groups
        groups = page.query_selector_all(".tabGroup")

        for group_index, group_elem in enumerate(groups):
            # Parse group creation date
            created_date_elem = group_elem.query_selector(".createdDate")
            if not created_date_elem:
                continue

            created_text = created_date_elem.text_content().strip()
            # Format: "Created 04/05/2026, 16:44:59" (DD/MM/YYYY, HH:MM:SS)
            group_date_iso = _parse_onetab_date(created_text)

            # Extract tabs in this group
            tab_elements = group_elem.query_selector_all(".tabList .tab a.tabLink")

            for tab_position, tab_elem in enumerate(tab_elements):
                url = tab_elem.get_attribute("href")
                title = tab_elem.text_content().strip()

                if url:  # Only include if URL is present
                    tabs.append({
                        "url": url,
                        "title": title,
                        "group_date": group_date_iso,
                        "group_index": group_index,
                        "tab_position": tab_position,
                        "scraped_at": scraped_at,
                    })

        context.close()

    return tabs


def _parse_onetab_date(date_text: str) -> str:
    """Parse OneTab date string to ISO format.

    Input: "Created 04/05/2026, 16:44:59" (DD/MM/YYYY, HH:MM:SS — Australian locale)
    Output: "2026-05-04T16:44:59" (ISO 8601)
    """
    # Extract the date/time part after "Created "
    if date_text.startswith("Created "):
        date_part = date_text[8:].strip()
    else:
        date_part = date_text

    # Parse DD/MM/YYYY, HH:MM:SS
    try:
        dt = datetime.strptime(date_part, "%d/%m/%Y, %H:%M:%S")
        return dt.isoformat()
    except ValueError as e:
        raise ValueError(f"Could not parse OneTab date: {date_text}") from e


def generate_onetab_id(group_date: str, url: str) -> str:
    """Generate stable ID for OneTab bookmark.

    ID = onetab_{sha256(group_date|url)[:16]}

    This preserves same URL in different groups as separate records,
    while being stable across re-imports.
    """
    combined = f"{group_date}|{url}"
    hash_hex = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"onetab_{hash_hex}"


if __name__ == "__main__":
    # Standalone test: scrape and print JSON
    import sys

    try:
        tabs = scrape_onetab()
        print(f"Scraped {len(tabs)} tabs")
        print(json.dumps(tabs, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
