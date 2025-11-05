"""
Test script for keyword context penalty/bonus feature.

This tests that numeric administrative division names are handled correctly
based on whether they are preceded by admin keywords (phuong, xa, quan, huyen, etc.)
"""
import sys
from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess

def parse_address(address: str, province_hint: str = None):
    """Parse an address using the full pipeline."""
    from src.utils.text_utils import normalize_hint
    from src.utils.extraction_utils import lookup_full_names
    from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative

    # Phase 1: Preprocessing
    use_iterative = should_use_iterative(address, province_hint)
    if use_iterative:
        p1 = iterative_preprocess(address, province_hint, None)
    else:
        p1 = preprocess(address, province_known=province_hint)

    # Phase 2: Structural parsing
    province_normalized = normalize_hint(province_hint) if province_hint else None
    p2 = structural_parse(
        p1['normalized'],
        province_known=province_normalized,
        district_known=None
    )

    # Phase 3: Extraction
    if p2['confidence'] >= 0.85:
        # Use structural parsing result
        province = p2.get('province')
        district = p2.get('district')
        ward = p2.get('ward')
        province_full, district_full, ward_full = lookup_full_names(province, district, ward)

        return {
            'province': province_full,
            'district': district_full,
            'ward': ward_full,
            'score': p2['confidence'],
            'at_rule': 3 if ward_full else (2 if district_full else 1)
        }
    else:
        # Use n-gram extraction
        p3 = extract_components({
            **p1,
            'province_known': province_normalized,
            'district_known': None,
            'structural_result': p2
        })

        p4 = generate_candidates(p3)
        p5 = validate_and_rank(p4)
        p6 = postprocess(p5)

        return p6

def test_keyword_context():
    """Test various scenarios with numeric administrative divisions."""

    test_cases = [
        {
            "description": "Number WITH keyword (Phuong 1 Quan 3)",
            "address": "123 Le Loi Phuong 1 Quan 3 TP HCM",
            "expected_ward": "1",
            "expected_district": "3",
            "expected_province": "ho chi minh"
        },
        {
            "description": "Number WITHOUT keyword - standalone '1' should have penalty",
            "address": "1 Le Loi Quan 3 TP HCM",
            "expected_ward": None,  # "1" should be less likely to match as ward
            "expected_district": "3",  # "Quan 3" should still match
            "expected_province": "ho chi minh"
        },
        {
            "description": "Mixed - Quan 12 with keyword",
            "address": "45 Nguyen Van Linh Phuong 5 Quan 12 TP HCM",
            "expected_ward": "5",
            "expected_district": "12",
            "expected_province": "ho chi minh"
        },
        {
            "description": "Xa with keyword",
            "address": "Xa My Hiep Huyen Cao Lanh Dong Thap",
            "expected_ward": "my hiep",
            "expected_district": "cao lanh",
            "expected_province": "dong thap"
        },
        {
            "description": "Number in street name vs admin division",
            "address": "12 Duong So 3 Phuong 1 Quan 3 TP HCM",
            "expected_ward": "1",  # "Phuong 1" with keyword
            "expected_district": "3",  # "Quan 3" with keyword
            "expected_province": "ho chi minh"
        },
        {
            "description": "Ba Ria Vung Tau - Phuong 1",
            "address": "Phuong 1 Vung Tau Ba Ria Vung Tau",
            "expected_ward": "1",
            "expected_district": "vung tau",
            "expected_province": "ba ria vung tau"
        },
        {
            "description": "Standalone '8' without keyword",
            "address": "8 Nguyen Hue Ben Nghe Quan 1 TP HCM",
            "expected_ward": "ben nghe",  # Should match "ben nghe" not "8"
            "expected_district": "1",
            "expected_province": "ho chi minh"
        }
    ]

    print("=" * 80)
    print("KEYWORD CONTEXT PENALTY/BONUS TEST")
    print("=" * 80)
    print("\nConfiguration:")
    print("  - Penalty for standalone numbers (no keyword): 0.7x (30% penalty)")
    print("  - Bonus for numbers with keywords: 1.2x (20% bonus)")
    print("  - Keywords: phuong, xa, quan, huyen, thanh, thi, tran, pho")
    print("  - Applies only to 1-2 digit numbers")
    print("\n" + "=" * 80)

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['description']}")
        print(f"Input: '{test['address']}'")

        result = parse_address(test['address'])

        print(f"\nResult:")
        print(f"  Province: {result.get('province', 'N/A')}")
        print(f"  District: {result.get('district', 'N/A')}")
        print(f"  Ward: {result.get('ward', 'N/A')}")
        print(f"  Score: {result.get('score', 'N/A'):.4f}" if result.get('score') else "  Score: N/A")
        print(f"  At Rule: {result.get('at_rule', 'N/A')}")

        # Check expectations
        checks = []
        if test['expected_province']:
            prov_match = result.get('province', '').lower() == test['expected_province'].lower()
            checks.append(('Province', prov_match, test['expected_province'], result.get('province', 'N/A')))

        if test['expected_district']:
            dist_match = result.get('district', '').lower() == test['expected_district'].lower()
            checks.append(('District', dist_match, test['expected_district'], result.get('district', 'N/A')))

        if test['expected_ward'] is not None:
            ward_match = result.get('ward', '').lower() == test['expected_ward'].lower()
            checks.append(('Ward', ward_match, test['expected_ward'], result.get('ward', 'N/A')))

        all_passed = all(check[1] for check in checks)

        print(f"\nExpected:")
        for field, match, expected, actual in checks:
            status = "✓" if match else "✗"
            print(f"  {status} {field}: expected='{expected}', actual='{actual}'")

        if all_passed:
            print("  ✓ PASSED")
            passed += 1
        else:
            print("  ✗ FAILED")
            failed += 1

        print("-" * 80)

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)

    return failed == 0

if __name__ == "__main__":
    success = test_keyword_context()
    sys.exit(0 if success else 1)
