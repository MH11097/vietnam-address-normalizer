#!/usr/bin/env python3
"""
Test script for district → province inheritance functionality.
Tests that when province is not found, the system searches for district and infers province.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import infer_province_from_district
from src.utils.extraction_utils import build_search_tree
from src.processors.phase1_preprocessing import preprocess

def test_infer_province_function():
    """Test the infer_province_from_district function."""
    print("=" * 60)
    print("TEST 1: infer_province_from_district()")
    print("=" * 60)

    # Test known districts
    test_cases = [
        ('hai ba trung', 'ha noi'),
        ('quan 1', 'ho chi minh'),
        ('dong ha', 'quang tri'),
        ('ben cat', 'binh duong'),
    ]

    for district, expected_province in test_cases:
        print(f"\n  Testing district: '{district}'")
        result = infer_province_from_district(district)
        print(f"    Expected province: '{expected_province}'")
        print(f"    Got province: '{result}'")
        if result and expected_province in result:
            print("    ✓ PASSED")
        else:
            print("    ✗ FAILED")


def test_district_to_province_inference():
    """Test full pipeline: no province in text → find district → infer province."""
    print("\n" + "=" * 60)
    print("TEST 2: District → Province Inference in Pipeline")
    print("=" * 60)

    test_cases = [
        {
            "address": "phuong bach khoa quan hai ba trung",
            "description": "No province name, has district name",
            "expected_province": "ha noi",
            "expected_district": "hai ba trung"
        },
        {
            "address": "phuong ben thanh quan 1",
            "description": "No province name, has district 'quan 1'",
            "expected_province": "ho chi minh",
            "expected_district": "1"
        },
        {
            "address": "xa dong luong dong ha",
            "description": "No province, has district 'dong ha'",
            "expected_province": "quang tri",
            "expected_district": "dong ha"
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['description']}")
        print(f"   Input: '{test_case['address']}'")

        try:
            # Phase 1: Preprocess
            preprocessed = preprocess(test_case['address'])
            normalized = preprocessed['normalized']
            tokens = normalized.split()
            print(f"   Normalized: '{normalized}'")
            print(f"   Tokens: {tokens}")

            # Build search tree (this should trigger district → province inference)
            candidates = build_search_tree(tokens)
            print(f"   Created {len(candidates)} candidate(s):")

            if candidates:
                for j, cand in enumerate(candidates[:3], 1):
                    province = cand.get('province', 'N/A')
                    district = cand.get('district', 'N/A')
                    ward = cand.get('ward', 'N/A')
                    score = cand.get('combined_score', 0)
                    search_path = cand.get('search_path', [])
                    print(f"      {j}. Province: {province}, District: {district}, Ward: {ward}")
                    print(f"         Score: {score:.3f}, Path: {search_path}")

                # Check if expected values match
                top_candidate = candidates[0]
                found_province = top_candidate.get('province', '')
                found_district = top_candidate.get('district', '')

                province_match = test_case['expected_province'] in str(found_province).lower()
                district_match = test_case['expected_district'] in str(found_district).lower()

                if province_match:
                    print(f"   ✓ Province match: {found_province}")
                else:
                    print(f"   ✗ Province mismatch: expected '{test_case['expected_province']}', got '{found_province}'")

                if district_match:
                    print(f"   ✓ District match: {found_district}")
                else:
                    print(f"   ✗ District mismatch: expected '{test_case['expected_district']}', got '{found_district}'")

                if province_match and district_match:
                    print("   ✓ PASSED")
                else:
                    print("   ⚠ PARTIAL PASS")
            else:
                print("   ✗ No candidates found")

        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    try:
        print("\n🚀 Starting District → Province Inheritance Tests\n")

        # Test 1: Direct function test
        test_infer_province_function()

        # Test 2: Full pipeline test
        test_district_to_province_inference()

        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
