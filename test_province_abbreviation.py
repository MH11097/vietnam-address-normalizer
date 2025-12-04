#!/usr/bin/env python3
"""
Test script for province abbreviation branching functionality.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import get_province_abbreviation_candidates
from src.main import process_single

def test_abbreviation_lookup():
    """Test the get_province_abbreviation_candidates function."""
    print("=" * 60)
    print("TEST 1: get_province_abbreviation_candidates()")
    print("=" * 60)

    # Test ambiguous abbreviation
    print("\n1. Testing 'dn' (ambiguous: Da Nang OR Dong Nai)")
    results = get_province_abbreviation_candidates('dn')
    print(f"   Results: {results}")
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert any('da nang' in r[0] for r in results), "Expected 'da nang' in results"
    assert any('dong nai' in r[0] for r in results), "Expected 'dong nai' in results"
    print("   ✓ PASSED")

    # Test unique abbreviation
    print("\n2. Testing 'hcm' (unique: Ho Chi Minh)")
    results = get_province_abbreviation_candidates('hcm')
    print(f"   Results: {results}")
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    print("   ✓ PASSED")

    # Test non-existent abbreviation
    print("\n3. Testing 'xyz' (non-existent)")
    results = get_province_abbreviation_candidates('xyz')
    print(f"   Results: {results}")
    assert len(results) == 0, f"Expected 0 results, got {len(results)}"
    print("   ✓ PASSED")


def test_address_parsing():
    """Test address parsing with province abbreviations."""
    print("\n" + "=" * 60)
    print("TEST 2: Address Parsing with Province Abbreviations")
    print("=" * 60)

    test_cases = [
        {
            "address": "phuong 3 dn",
            "expected_provinces": ["da nang", "dong nai"],
            "description": "Ambiguous 'dn' should create 2 branches"
        },
        {
            "address": "phuong ben thanh hcm",
            "expected_provinces": ["ho chi minh"],
            "description": "Unique 'hcm' should create 1 branch"
        },
        {
            "address": "phuong 5 quan 1 ho chi minh",
            "expected_provinces": ["ho chi minh"],
            "description": "Full province name should work"
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Input: '{test_case['address']}'")

        try:
            result = process_single(test_case['address'], output_format='dict')

            # Check if we got results
            if result and isinstance(result, dict) and 'candidates' in result:
                candidates = result['candidates']
                print(f"   Found {len(candidates)} candidate(s)")

                # Show first few candidates
                for j, cand in enumerate(candidates[:3], 1):
                    province = cand.get('province', 'N/A')
                    district = cand.get('district', 'N/A')
                    ward = cand.get('ward', 'N/A')
                    score = cand.get('combined_score', 0)
                    print(f"      {j}. Province: {province}, District: {district}, Ward: {ward} (score: {score:.3f})")

                # Check if expected provinces are present
                found_provinces = [c.get('province') for c in candidates]
                for expected_prov in test_case['expected_provinces']:
                    if any(expected_prov in str(p).lower() for p in found_provinces):
                        print(f"   ✓ Found expected province: {expected_prov}")
                    else:
                        print(f"   ✗ Missing expected province: {expected_prov}")
            else:
                print("   ✗ No candidates found")

        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    try:
        print("\n🚀 Starting Province Abbreviation Tests\n")

        # Test 1: Direct function test
        test_abbreviation_lookup()

        # Test 2: Full address parsing test
        test_address_parsing()

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
