#!/usr/bin/env python3
"""Unit tests for OneTab scraper logic (no browser needed)."""

from ubm.onetab_scraper import _parse_onetab_date, generate_onetab_id, _escape_applescript_js


def test_parse_onetab_date():
    """Test OneTab date parsing from live DOM format."""
    # Live DOM format: "DD/MM/YYYY HH:MM:SS" (no comma, unlike export)
    assert _parse_onetab_date("04/05/2026 16:44:59") == "2026-05-04T16:44:59"
    assert _parse_onetab_date("01/01/2025 00:00:00") == "2025-01-01T00:00:00"
    assert _parse_onetab_date("31/12/2024 23:59:59") == "2024-12-31T23:59:59"

    # Empty/invalid returns empty string
    assert _parse_onetab_date("") == ""
    assert _parse_onetab_date("garbage") == ""

    print("  Date parsing tests passed")


def test_generate_onetab_id_with_native_id():
    """Test ID generation uses OneTab's own data-id when available."""
    id1 = generate_onetab_id("eaDh-GNx5_rHE-_ps9rLPN", "2026-05-04T16:44:59", "https://example.com")
    assert id1 == "onetab_eaDh-GNx5_rHE-_ps9rLPN"

    # Different onetab_id = different bookmark ID
    id2 = generate_onetab_id("7boppOoV3jol3Agc153e2Q", "2026-05-04T16:44:59", "https://example.com")
    assert id1 != id2

    print("  Native ID tests passed")


def test_generate_onetab_id_fallback():
    """Test ID generation falls back to hash when no onetab_id."""
    id1 = generate_onetab_id("", "2026-05-04T16:44:59", "https://example.com")
    assert id1.startswith("onetab_")
    assert len(id1) > 10

    # Stable across calls
    id2 = generate_onetab_id("", "2026-05-04T16:44:59", "https://example.com")
    assert id1 == id2

    # Different group = different ID
    id3 = generate_onetab_id("", "2026-05-04T15:00:00", "https://example.com")
    assert id1 != id3

    print("  Fallback ID tests passed")


def test_escape_applescript_js():
    """Test JS escaping for AppleScript embedding."""
    assert _escape_applescript_js('"hello"') == '\\"hello\\"'
    assert _escape_applescript_js("line1\nline2") == "line1\\nline2"
    assert _escape_applescript_js("back\\slash") == "back\\\\slash"

    print("  AppleScript escape tests passed")


if __name__ == "__main__":
    test_parse_onetab_date()
    test_generate_onetab_id_with_native_id()
    test_generate_onetab_id_fallback()
    test_escape_applescript_js()
    print("\nAll scraper unit tests passed!")
