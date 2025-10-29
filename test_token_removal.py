#!/usr/bin/env python3
"""
Test để verify token removal thành công
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import query_all


def test_statistics():
    """Test thống kê sau khi xóa"""
    print("=" * 80)
    print("TEST 1: Statistics after token removal")
    print("=" * 80)

    # Total count
    result = query_all("SELECT COUNT(*) as count FROM abbreviations")
    total = result[0]['count']
    print(f"\n✓ Total abbreviations: {total:,}")

    # Context distribution
    result = query_all("""
        SELECT
            COUNT(CASE WHEN province_context IS NULL AND district_context IS NULL THEN 1 END) as global,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NULL THEN 1 END) as province,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NOT NULL THEN 1 END) as district
        FROM abbreviations
    """)

    print(f"\n✓ Context distribution:")
    print(f"  - Global: {result[0]['global']:,}")
    print(f"  - Province: {result[0]['province']:,}")
    print(f"  - District: {result[0]['district']:,}")

    # Expected values
    expected_total = 49371
    if total == expected_total:
        print(f"\n✓ Total matches expected ({expected_total:,})")
        return True
    else:
        print(f"\n✗ Total mismatch! Expected {expected_total:,}, got {total:,}")
        return False


def test_problematic_removed():
    """Test các tokens problematic đã bị xóa"""
    print("\n" + "=" * 80)
    print("TEST 2: Verify problematic tokens removed")
    print("=" * 80)

    # Top problematic tokens that should be removed
    problematic = ['an', 'ha', 'ho', 'tu', 'ba', 'dong', 'thanh', 'phu', 'ta', 'la']

    all_removed = True
    for token in problematic:
        result = query_all("SELECT COUNT(*) as count FROM abbreviations WHERE key = ?", (token,))
        count = result[0]['count']

        if count == 0:
            print(f"  ✓ '{token}' removed ({count} records)")
        else:
            print(f"  ✗ '{token}' NOT removed ({count} records remaining)")
            all_removed = False

    return all_removed


def test_valid_abbreviations_kept():
    """Test các abbreviations valid vẫn còn"""
    print("\n" + "=" * 80)
    print("TEST 3: Verify valid abbreviations kept")
    print("=" * 80)

    # Some valid abbreviations that should NOT be tokens
    valid = [
        ('hn', 'ha noi'),  # Province
        ('hcm', 'ho chi minh'),  # Province
        ('bd', 'ba dinh'),  # District (has province context)
        ('tx', 'thanh xuan'),  # District (has province context)
    ]

    all_kept = True
    for abbr, expected_word in valid:
        result = query_all("""
            SELECT key, word
            FROM abbreviations
            WHERE key = ?
            LIMIT 1
        """, (abbr,))

        if result:
            word = result[0]['word']
            print(f"  ✓ '{abbr}' → '{word}' (kept)")
        else:
            print(f"  ✗ '{abbr}' removed (should be kept)")
            all_kept = False

    return all_kept


def test_unique_keys():
    """Test số lượng unique keys"""
    print("\n" + "=" * 80)
    print("TEST 4: Unique keys count")
    print("=" * 80)

    result = query_all("SELECT COUNT(DISTINCT key) as count FROM abbreviations")
    unique_keys = result[0]['count']

    print(f"\n✓ Unique abbreviation keys: {unique_keys:,}")

    # Should have removed ~308 keys
    original_keys = 14360
    expected_removed = 308
    expected_remaining = original_keys - expected_removed

    print(f"  Original keys: {original_keys:,}")
    print(f"  Keys removed: ~{expected_removed}")
    print(f"  Expected remaining: ~{expected_remaining:,}")
    print(f"  Actual remaining: {unique_keys:,}")

    # Allow some tolerance
    diff = abs(unique_keys - expected_remaining)
    if diff < 50:  # Within 50 keys
        print(f"  ✓ Within expected range (diff: {diff})")
        return True
    else:
        print(f"  ✗ Outside expected range (diff: {diff})")
        return False


def test_sample_queries():
    """Test một số queries thực tế"""
    print("\n" + "=" * 80)
    print("TEST 5: Sample queries")
    print("=" * 80)

    # Query 1: Get abbreviations for ha noi
    result = query_all("""
        SELECT key, word
        FROM abbreviations
        WHERE province_context = 'ha noi'
          AND district_context IS NULL
        ORDER BY key
        LIMIT 5
    """)

    print(f"\n✓ District abbreviations in Ha Noi:")
    for row in result:
        print(f"  {row['key']:10} → {row['word']}")

    # Query 2: Ensure no 'ha' key exists
    result = query_all("SELECT COUNT(*) as count FROM abbreviations WHERE key = 'ha'")
    if result[0]['count'] == 0:
        print(f"\n✓ Token 'ha' successfully removed")
    else:
        print(f"\n✗ Token 'ha' still exists ({result[0]['count']} records)")
        return False

    return True


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "TOKEN REMOVAL TEST SUITE" + " " * 29 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        test_statistics,
        test_problematic_removed,
        test_valid_abbreviations_kept,
        test_unique_keys,
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
