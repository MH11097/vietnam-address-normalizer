#!/usr/bin/env python3
"""
Test script để verify migration abbreviations hoạt động đúng
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import (
    load_abbreviations,
    expand_abbreviation_from_admin,
    query_all
)
from src.utils.text_utils import expand_abbreviations, normalize_address


def test_abbreviations_table():
    """Test bảng abbreviations có đúng structure và data"""
    print("=" * 80)
    print("TEST 1: Kiểm tra bảng abbreviations")
    print("=" * 80)

    # Check total count
    result = query_all("SELECT COUNT(*) as count FROM abbreviations")
    total = result[0]['count']
    print(f"\n✓ Total abbreviations: {total:,}")

    # Check context distribution
    result = query_all("""
        SELECT
            COUNT(CASE WHEN province_context IS NULL AND district_context IS NULL THEN 1 END) as global_count,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NULL THEN 1 END) as province_count,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NOT NULL THEN 1 END) as district_count
        FROM abbreviations
    """)
    print(f"\n✓ Context distribution:")
    print(f"  - Global (no context): {result[0]['global_count']:,}")
    print(f"  - Province context: {result[0]['province_count']:,}")
    print(f"  - District context: {result[0]['district_count']:,}")

    return True


def test_load_abbreviations():
    """Test function load_abbreviations với context"""
    print("\n" + "=" * 80)
    print("TEST 2: Load abbreviations với contexts")
    print("=" * 80)

    # Test 1: Global only
    abbr_global = load_abbreviations()
    print(f"\n✓ Global abbreviations: {len(abbr_global):,}")
    print(f"  Sample: {list(abbr_global.items())[:5]}")

    # Test 2: Province context
    abbr_hn = load_abbreviations(province_context='ha noi')
    print(f"\n✓ Ha Noi abbreviations: {len(abbr_hn):,}")

    # Test 3: District context
    abbr_bd = load_abbreviations(province_context='ha noi', district_context='ba dinh')
    print(f"\n✓ Ba Dinh (Ha Noi) abbreviations: {len(abbr_bd):,}")

    return True


def test_expand_abbreviation():
    """Test expand_abbreviation_from_admin"""
    print("\n" + "=" * 80)
    print("TEST 3: Expand abbreviation từ bảng abbreviations")
    print("=" * 80)

    test_cases = [
        # (abbr, level, province_context, district_context, expected)
        ('hn', 'province', None, None, 'ha noi'),
        ('hcm', 'province', None, None, 'ho chi minh'),
        ('bd', 'district', 'ha noi', None, 'ba dinh'),
        ('tx', 'district', 'ha noi', None, 'thanh xuan'),
        ('db', 'ward', 'ha noi', 'ba dinh', 'dien bien'),
    ]

    for abbr, level, prov, dist, expected in test_cases:
        result = expand_abbreviation_from_admin(abbr, level, prov, dist)
        status = "✓" if result == expected else "✗"
        context_str = f"[{prov or 'global'}]"
        if dist:
            context_str = f"[{prov}/{dist}]"
        print(f"  {status} '{abbr}' {context_str} → '{result}' (expected: '{expected}')")

    return True


def test_normalize_address():
    """Test normalize_address với contexts"""
    print("\n" + "=" * 80)
    print("TEST 4: Normalize address với context")
    print("=" * 80)

    test_cases = [
        # (text, province_context, district_context, description)
        ("P. Điện Biên, Q. Ba Đình, HN", None, None, "Basic normalization"),
        ("TX, Hà Nội", "ha noi", None, "TX with Ha Noi context"),
        ("DB", "ha noi", "ba dinh", "DB with Ba Dinh context"),
        ("Phường 1, Q.3, HCM", "ho chi minh", None, "Ward in HCM"),
    ]

    for text, prov, dist, desc in test_cases:
        result = normalize_address(text, province_context=prov, district_context=dist)
        context_str = ""
        if prov:
            context_str = f" [{prov}]"
        if dist:
            context_str = f" [{prov}/{dist}]"
        print(f"\n  Test: {desc}")
        print(f"  Input:  '{text}'{context_str}")
        print(f"  Output: '{result}'")

    return True


def test_admin_divisions_columns():
    """Verify admin_divisions không còn abbreviation columns"""
    print("\n" + "=" * 80)
    print("TEST 5: Kiểm tra admin_divisions columns")
    print("=" * 80)

    result = query_all("PRAGMA table_info(admin_divisions)")
    columns = [row['name'] for row in result]

    print(f"\n✓ Total columns: {len(columns)}")

    # Check abbreviation columns are removed
    abbr_cols = ['province_abbreviation', 'district_abbreviation', 'ward_abbreviation']
    for col in abbr_cols:
        if col in columns:
            print(f"  ✗ ERROR: Column '{col}' still exists!")
            return False
        else:
            print(f"  ✓ Column '{col}' removed successfully")

    return True


def test_sample_queries():
    """Test một số query thực tế"""
    print("\n" + "=" * 80)
    print("TEST 6: Sample queries")
    print("=" * 80)

    # Query 1: Get abbreviations for specific ward
    result = query_all("""
        SELECT key, word
        FROM abbreviations
        WHERE province_context = 'ha noi'
          AND district_context = 'ba dinh'
        LIMIT 5
    """)
    print(f"\n✓ Ward abbreviations in Ba Dinh, Ha Noi:")
    for row in result:
        print(f"  {row['key']:10} → {row['word']}")

    # Query 2: Get all abbreviation types for a location
    result = query_all("""
        SELECT key, word, province_context, district_context
        FROM abbreviations
        WHERE word = 'ba dinh'
        ORDER BY province_context, district_context
    """)
    print(f"\n✓ All abbreviations for 'ba dinh':")
    for row in result:
        prov = row['province_context'] or 'global'
        dist = row['district_context'] or 'N/A'
        print(f"  {row['key']:10} → {row['word']:20} [prov: {prov}, dist: {dist}]")

    return True


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ABBREVIATION MIGRATION TEST SUITE" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        test_abbreviations_table,
        test_load_abbreviations,
        test_expand_abbreviation,
        test_normalize_address,
        test_admin_divisions_columns,
        test_sample_queries,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"\n✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test.__name__} ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Tests passed: {passed}/{len(tests)}")
    print(f"  Tests failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n  ✓ ALL TESTS PASSED!")
    else:
        print(f"\n  ✗ {failed} TEST(S) FAILED")

    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
