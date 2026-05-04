"""Scrape OneTab Chrome extension via AppleScript + Chrome JS execution.

No external dependencies — uses osascript (built into macOS) to open OneTab
in a Chrome tab, extract data via JavaScript, and close the tab.
Works while Chrome is already running.
"""

import json
import subprocess
import sys
from datetime import datetime
from typing import List, Dict


ONETAB_URL = "chrome-extension://chphlpgkkbolifaimnlloiipkdnihall/onetab.html"

# JavaScript to extract all tabs from OneTab's live DOM.
#
# Live DOM structure (different from the HTML export):
#   .tabGroup — each group (index 0 is the "All" meta-group, skip it)
#   .tabGroupBody > first child div — header text containing date
#   .tabGroupLabelText — group label (e.g. "34 tabs")
#   .childContainer > .tab — individual tabs
#   .tab > a — link with href and title text
#   .tab[data-id] — OneTab's own stable ID per tab
#
# Pagination:
#   OneTab displays 250 groups per page. The pagination controls are
#   .button.button-hover-bg-change divs with text "Next N" / "Previous N".
#   The page indicator is a div matching /^\d+–\d+\s*\/\s*\d+$/.

EXTRACT_PAGE_JS = r"""
(function() {
    var tabs = [];
    var groups = document.querySelectorAll(".tabGroup");
    // Skip index 0 — it's the "All" meta-group
    for (var gi = 1; gi < groups.length; gi++) {
        var g = groups[gi];
        var body = g.querySelector(".tabGroupBody");
        if (!body) continue;

        // Date is in the first child div's text content
        var headerDiv = body.children[0];
        var headerText = headerDiv ? headerDiv.textContent.trim() : "";
        var dateMatch = headerText.match(/(\d{2}\/\d{2}\/\d{4})\s+(\d{2}:\d{2}:\d{2})/);
        var groupDate = dateMatch ? dateMatch[1] + " " + dateMatch[2] : "";

        // Group label (e.g. "34 tabs")
        var label = g.querySelector(".tabGroupLabelText");
        var groupLabel = label ? label.textContent.trim() : "";

        // Tabs inside childContainer
        var container = g.querySelector(".childContainer");
        if (!container) continue;
        var tabEls = container.querySelectorAll(".tab");

        for (var ti = 0; ti < tabEls.length; ti++) {
            var link = tabEls[ti].querySelector("a");
            if (!link || !link.href) continue;
            tabs.push({
                url: link.href,
                title: link.textContent.trim(),
                onetab_id: tabEls[ti].dataset.id || "",
                group_date: groupDate,
                group_label: groupLabel,
                group_index: gi - 1,
                tab_position: ti
            });
        }
    }
    return JSON.stringify(tabs);
})()
"""

GET_PAGINATION_JS = r"""
(function() {
    var divs = document.querySelectorAll("div");
    for (var i = 0; i < divs.length; i++) {
        var t = divs[i].textContent.trim();
        if (t.match(/^\d+.\d+\s*\/\s*\d+$/) && t.length < 20) {
            return t;
        }
    }
    return "";
})()
"""

CLICK_NEXT_JS = r"""
(function() {
    var btns = document.querySelectorAll(".button.button-hover-bg-change");
    for (var i = 0; i < btns.length; i++) {
        if (btns[i].textContent.trim().indexOf("Next") === 0) {
            btns[i].click();
            return "clicked";
        }
    }
    return "no_next";
})()
"""

CLICK_FIRST_PAGE_JS = r"""
(function() {
    var btns = document.querySelectorAll(".button.button-hover-bg-change");
    for (var i = 0; i < btns.length; i++) {
        var t = btns[i].textContent.trim();
        if (t === "\u23EE" || t === "\u23ee") {
            btns[i].click();
            return "clicked";
        }
    }
    return "no_first";
})()
"""


def scrape_onetab() -> List[Dict]:
    """Scrape all tabs from OneTab extension via AppleScript.

    Opens OneTab in a new Chrome tab, paginates through all pages,
    extracts all tabs, closes the tab, and returns structured data.

    Returns a list of tab dicts with:
    - url: tab URL
    - title: tab title
    - onetab_id: OneTab's own stable ID for this tab
    - group_date: date string "DD/MM/YYYY HH:MM:SS" from OneTab DOM
    - group_date_iso: parsed ISO datetime
    - group_label: group label (e.g. "34 tabs")
    - group_index: 0-based position within current page
    - tab_position: 0-based position within group
    - scraped_at: ISO datetime when this scrape ran

    Requires:
    - macOS (uses osascript)
    - Google Chrome running with OneTab extension installed
    """
    if sys.platform != "darwin":
        raise RuntimeError("OneTab scraper requires macOS (uses osascript)")

    scraped_at = datetime.now().isoformat()

    # Find existing OneTab tab or open a new one
    _applescript(f'''
        tell application "Google Chrome"
            set foundTab to false
            set winCount to count of windows
            repeat with wi from 1 to winCount
                set w to window wi
                set tabCount to count of tabs of w
                repeat with ti from 1 to tabCount
                    if URL of tab ti of w starts with "chrome-extension://chphlpgkkbolifaimnlloiipkdnihall/onetab.html" then
                        set active tab index of w to ti
                        set index of w to 1
                        set foundTab to true
                        exit repeat
                    end if
                end repeat
                if foundTab then exit repeat
            end repeat
            if not foundTab then
                tell front window
                    make new tab with properties {{URL:"{ONETAB_URL}"}}
                end tell
                delay 2
            end if
        end tell
    ''')

    all_tabs = []
    page = 0
    prev_page_text = None

    # Navigate to first page to be safe
    result = _chrome_js(CLICK_FIRST_PAGE_JS)
    if result == "clicked":
        _applescript('delay 1.5')

    while True:
        page += 1

        # Check pagination state
        page_text = _chrome_js(GET_PAGINATION_JS)

        # Extract tabs from current page
        raw_json = _chrome_js(EXTRACT_PAGE_JS)
        if not raw_json or not raw_json.strip():
            break

        page_tabs = json.loads(raw_json.strip())

        # Offset group_index by pages already scraped
        group_offset = max(t["group_index"] for t in all_tabs) + 1 if all_tabs else 0
        for tab in page_tabs:
            tab["group_index"] += group_offset

        all_tabs.extend(page_tabs)

        if page_text:
            print(f"  Page {page}: {page_text} — {len(page_tabs)} tabs", file=sys.stderr)

        # Try to go to next page
        click_result = _chrome_js(CLICK_NEXT_JS)
        if click_result != "clicked":
            break  # No Next button at all

        _applescript('delay 1.5')

        # Check if the page actually changed
        new_page_text = _chrome_js(GET_PAGINATION_JS)
        if new_page_text == page_text:
            break  # Page didn't change — we're on the last page

    # Navigate back to first page so OneTab is left in its normal state
    _chrome_js(CLICK_FIRST_PAGE_JS)

    # Post-process: parse dates, add scraped_at
    for tab in all_tabs:
        tab["group_date_iso"] = _parse_onetab_date(tab.get("group_date", ""))
        tab["scraped_at"] = scraped_at

    return all_tabs


def _applescript(script: str) -> str:
    """Execute AppleScript and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
    return result.stdout


def _chrome_js(js: str) -> str:
    """Execute JavaScript in Chrome's active tab via AppleScript."""
    escaped = _escape_applescript_js(js)
    result = _applescript(f'''
        tell application "Google Chrome"
            tell front window
                set result to execute active tab javascript "{escaped}"
                return result
            end tell
        end tell
    ''')
    return result.strip()


def _escape_applescript_js(js: str) -> str:
    """Escape JavaScript for embedding in AppleScript string."""
    return js.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _parse_onetab_date(date_text: str) -> str:
    """Parse OneTab date string to ISO format.

    Input: "04/05/2026 16:44:59" (DD/MM/YYYY HH:MM:SS — Australian locale)
    Output: "2026-05-04T16:44:59" (ISO 8601)

    Returns empty string if parsing fails.
    """
    if not date_text:
        return ""

    try:
        dt = datetime.strptime(date_text.strip(), "%d/%m/%Y %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return ""


def generate_onetab_id(onetab_id: str, group_date: str, url: str) -> str:
    """Return a stable ID for a OneTab bookmark.

    Uses OneTab's own data-id if available, otherwise falls back to
    a hash of group_date + url.
    """
    if onetab_id:
        return f"onetab_{onetab_id}"

    import hashlib
    combined = f"{group_date}|{url}"
    hash_hex = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return f"onetab_{hash_hex}"


if __name__ == "__main__":
    try:
        tabs = scrape_onetab()
        groups = max(t['group_index'] for t in tabs) + 1 if tabs else 0
        print(f"Scraped {len(tabs)} tabs from {groups} groups")
        if tabs:
            print(f"First: {tabs[0]['title'][:60]}... ({tabs[0]['group_date_iso']})")
            print(f"Last:  {tabs[-1]['title'][:60]}... ({tabs[-1]['group_date_iso']})")
        print(json.dumps(tabs[:3], indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
