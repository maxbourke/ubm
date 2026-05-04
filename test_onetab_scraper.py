#!/usr/bin/env python3
"""Unit tests for OneTab scraper logic (without browser)."""

import json
from pathlib import Path
from ubm.onetab_scraper import _parse_onetab_date, generate_onetab_id


def test_parse_onetab_date():
    """Test OneTab date parsing."""
    # Format: "Created 04/05/2026, 16:44:59" (DD/MM/YYYY, HH:MM:SS)
    result = _parse_onetab_date("Created 04/05/2026, 16:44:59")
    assert result == "2026-05-04T16:44:59", f"Expected 2026-05-04T16:44:59, got {result}"

    result = _parse_onetab_date("Created 01/01/2025, 00:00:00")
    assert result == "2025-01-01T00:00:00"

    print("✓ Date parsing tests passed")


def test_generate_onetab_id():
    """Test OneTab ID generation."""
    # Same group_date + url should produce same ID
    id1 = generate_onetab_id("2026-05-04T16:44:59", "https://example.com")
    id2 = generate_onetab_id("2026-05-04T16:44:59", "https://example.com")
    assert id1 == id2, f"IDs should be stable: {id1} vs {id2}"
    assert id1.startswith("onetab_")

    # Different URLs should produce different IDs
    id3 = generate_onetab_id("2026-05-04T16:44:59", "https://different.com")
    assert id1 != id3, f"Different URLs should produce different IDs"

    # Same URL in different groups should produce different IDs
    id4 = generate_onetab_id("2026-05-04T15:00:00", "https://example.com")
    assert id1 != id4, f"Same URL in different groups should produce different IDs"

    print("✓ ID generation tests passed")


if __name__ == "__main__":
    test_parse_onetab_date()
    test_generate_onetab_id()
    print("\nAll unit tests passed!")
