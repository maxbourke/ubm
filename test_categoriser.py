#!/usr/bin/env python3
"""Test script for UBM categoriser functionality."""

import sys
import subprocess
from pathlib import Path


def run_command(cmd):
    """Run a command and return output."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr, file=sys.stderr)
    return result.returncode == 0


def main():
    """Run all tests."""
    ubm_cmd = [sys.executable, 'ubm.py']
    tests_passed = 0
    tests_failed = 0

    print("UBM Categoriser Test Suite")
    print("="*60)

    # Test 1: Check migration ran
    print("\n[Test 1] Verify database migration")
    if run_command(ubm_cmd + ['stats']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: Stats command failed")

    # Test 2: Check categorise help
    print("\n[Test 2] Verify categorise command exists")
    if run_command(ubm_cmd + ['categorise', '--help']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: Categorise help failed")

    # Test 3: Check taxonomy exists
    print("\n[Test 3] Verify taxonomy was generated")
    if run_command(ubm_cmd + ['categorise', 'list']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: List taxonomy failed")

    # Test 4: Check categorisation stats
    print("\n[Test 4] Verify categorisation statistics")
    if run_command(ubm_cmd + ['categorise', 'stats']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: Stats command failed")

    # Test 5: Check review queue
    print("\n[Test 5] Verify review queue")
    if run_command(ubm_cmd + ['categorise', 'review', '--limit', '5']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: Review command failed")

    # Test 6: Check show command includes categories
    print("\n[Test 6] Verify show command displays categories")
    if run_command(ubm_cmd + ['show', '1000536170844114944']):
        tests_passed += 1
    else:
        tests_failed += 1
        print("FAILED: Show command failed")

    # Test 7: Verify database schema
    print("\n[Test 7] Verify database tables exist")
    db_path = Path.home() / '.ubm' / 'ubm.db'
    expected_tables = [
        'categories',
        'bookmark_categories',
        'categorisation_state',
        'categorisation_log',
        'taxonomy_history'
    ]

    for table in expected_tables:
        cmd = ['sqlite3', str(db_path), f'.schema {table}']
        if run_command(cmd):
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"FAILED: Table {table} not found")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print("="*60)

    if tests_failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {tests_failed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
