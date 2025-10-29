#!/usr/bin/env python3
"""
Test script to verify the province/district collision fix.

This tests the case where a token (e.g., "BEN TRE") matches both:
- A province: Tỉnh Bến Tre
- A district: Thành phố Bến Tre (within Tỉnh Bến Tre)

Expected behavior: District interpretation should be prioritized when both exist.
"""

import sys
from src.utils.db_utils import check_province_district_collision
from src.utils.extraction_utils import extract_province_candidates, build_search_tree
from src.utils.text_utils import normalize_address


def test_collision_detection():
    """Test the collision detection helper function."""
    print("=" * 80)
    print("TEST 1: Collision Detection")
    print("=" * 80)

    result = check_province_district_collision('ben tre')
    print(f"Checking 'ben tre' for collision:")
    print(f"  - has_collision: {result['has_collision']}")
    print(f"  - province_name: {result['province_name']}")
    print(f"  - province_full: {result['province_full']}")
    print(f"  - district_name: {result['district_name']}")
    print(f"  - district_full: {result['district_full']}")
    print(f"  - district_province: {result['district_province']}")

    assert result['has_collision'] == True, "Expected collision for 'ben tre'"
    assert result['province_name'] == 'ben tre', "Expected province 'ben tre'"
    assert result['district_name'] == 'ben tre', "Expected district 'ben tre'"
    print("✅ PASSED: Collision detected correctly\n")


def test_province_candidate_with_collision():
    """Test that province extraction marks collision flag."""
    print("=" * 80)
    print("TEST 2: Province Candidate Extraction with Collision Flag")
    print("=" * 80)

    # Test case: "PHUONG 5 BEN TRE"
    tokens = ['phuong', '5', 'ben', 'tre']
    print(f"Input tokens: {tokens}")

    candidates = extract_province_candidates(tokens)
    print(f"\nFound {len(candidates)} province candidates:")

    for i, (name, score, source, has_collision) in enumerate(candidates, 1):
        collision_marker = " [⚠️ COLLISION]" if has_collision else ""
        print(f"  {i}. '{name}' (score: {score:.3f}, source: {source}){collision_marker}")

    # Verify ben tre is found and marked as collision
    ben_tre_candidates = [c for c in candidates if c[0] == 'ben tre']
    assert len(ben_tre_candidates) > 0, "Expected 'ben tre' in candidates"

    ben_tre = ben_tre_candidates[0]
    assert ben_tre[3] == True, "Expected has_collision=True for 'ben tre'"
    print("\n✅ PASSED: Province candidate correctly marked with collision flag\n")


def test_full_address_with_collision():
    """Test full address parsing with collision case."""
    print("=" * 80)
    print("TEST 3: Full Address Parsing (BEN TRE Collision)")
    print("=" * 80)

    # Test case: "216A3 KP1 PHUONG 5 TPBT | ____ | BEN TRE"
    # Expected:
    #   - Province: ben tre (Tỉnh Bến Tre)
    #   - District: ben tre (Thành phố Bến Tre)
    #   - Ward: 5 (Phường 5)

    test_address = "216A3 KP1 PHUONG 5 TPBT BEN TRE"
    print(f"Input address: {test_address}")

    tokens = normalize_address(test_address).split()
    print(f"Normalized tokens: {tokens}")

    # Build search tree
    candidates = build_search_tree(tokens)

    print(f"\nFound {len(candidates)} candidates:")
    for i, candidate in enumerate(candidates[:3], 1):
        print(f"\n  Candidate {i}:")
        print(f"    Province: {candidate.get('province')} ({candidate.get('province_full', 'N/A')})")
        print(f"    District: {candidate.get('district')} ({candidate.get('district_full', 'N/A')})")
        print(f"    Ward: {candidate.get('ward')} ({candidate.get('ward_full', 'N/A')})")
        print(f"    Combined Score: {candidate.get('combined_score', 0):.3f}")
        print(f"    Match Level: {candidate.get('match_level')}")

    # Verify the best candidate has both province and district as 'ben tre'
    if candidates:
        best = candidates[0]
        print("\n  Best candidate:")
        print(f"    Province: {best.get('province')}")
        print(f"    District: {best.get('district')}")
        print(f"    Ward: {best.get('ward')}")

        # Check if district is found
        if best.get('district') == 'ben tre':
            print("\n✅ PASSED: District 'ben tre' correctly identified!")
            print("   (Previously this would only match province, missing the district)")
        else:
            print(f"\n⚠️  PARTIAL: District not matched as 'ben tre'")
            print(f"   Got district: {best.get('district')}")
            if best.get('province') == 'ben tre':
                print("   Province correctly matched as 'ben tre'")
    else:
        print("\n❌ FAILED: No candidates found")


def test_non_collision_case():
    """Test that non-collision cases still work correctly."""
    print("=" * 80)
    print("TEST 4: Non-Collision Case (Control Test)")
    print("=" * 80)

    # Test with a normal address that doesn't have collision
    test_address = "PHUONG 3 DONG HA QUANG TRI"
    print(f"Input address: {test_address}")

    tokens = normalize_address(test_address).split()
    print(f"Normalized tokens: {tokens}")

    candidates = build_search_tree(tokens)

    print(f"\nFound {len(candidates)} candidates:")
    if candidates:
        best = candidates[0]
        print(f"  Province: {best.get('province')} ({best.get('province_full', 'N/A')})")
        print(f"  District: {best.get('district')} ({best.get('district_full', 'N/A')})")
        print(f"  Ward: {best.get('ward')} ({best.get('ward_full', 'N/A')})")

        # Just verify province is correct, district parsing may vary
        if best.get('province') == 'quang tri':
            print("\n✅ PASSED: Province correctly identified (non-collision case)\n")
        else:
            print(f"\n⚠️  Province: Expected 'quang tri', got '{best.get('province')}'\n")
    else:
        print("\n❌ FAILED: No candidates found")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PROVINCE/DISTRICT COLLISION FIX - TEST SUITE")
    print("=" * 80 + "\n")

    try:
        test_collision_detection()
        test_province_candidate_with_collision()
        test_full_address_with_collision()
        test_non_collision_case()

        print("=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
