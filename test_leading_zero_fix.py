"""Test script to verify leading zero normalization fix"""
import sys

from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess
from src.utils.text_utils import normalize_hint
from src.utils.extraction_utils import lookup_full_names
from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative

def test_address(raw_address, known_province=None, known_district=None):
    """Test a single address and print results"""
    print(f"\n{'='*70}")
    print(f"Testing: {raw_address}")
    if known_province:
        print(f"Known Province: {known_province}")
    if known_district:
        print(f"Known District: {known_district}")
    print('='*70)

    # Phase 1: Preprocessing
    use_iterative = should_use_iterative(raw_address, known_province)
    if use_iterative:
        p1 = iterative_preprocess(raw_address, known_province, known_district)
    else:
        p1 = preprocess(raw_address, province_known=known_province)

    print(f"Phase 1: {p1['normalized']}")

    # Phase 2: Structural parsing
    province_normalized = normalize_hint(known_province) if known_province else None
    district_normalized = normalize_hint(known_district) if known_district else None

    p2 = structural_parse(
        p1['normalized'],
        province_known=province_normalized,
        district_known=district_normalized
    )

    print(f"Phase 2: method={p2['method']}, confidence={p2['confidence']:.2f}")

    # Phase 3: N-gram extraction (or use structural result)
    if p2['confidence'] >= 0.85:
        # Use structural result
        province = p2.get('province')
        district = p2.get('district')
        ward = p2.get('ward')
        print(f"Phase 3: Using structural result")

        province_full, district_full, ward_full = lookup_full_names(province, district, ward)

        if province_full or district_full or ward_full:
            p3 = {
                'province_potentials': [(province, 100)] if province else [],
                'district_potentials': [(district, 95)] if district else [],
                'ward_potentials': [(ward, 95)] if ward else [],
            }
        else:
            p3 = {'province_potentials': [], 'district_potentials': [], 'ward_potentials': []}
    else:
        # Extract using n-grams
        p3 = extract_components(
            p1,  # Pass the full preprocessing result dict
            province_known=province_normalized,
            district_known=district_normalized
        )
        print(f"Phase 3: Extracted {len(p3.get('province_potentials', []))} provinces, "
              f"{len(p3.get('district_potentials', []))} districts, "
              f"{len(p3.get('ward_potentials', []))} wards")

    # Phase 4: Generate candidates
    p4 = generate_candidates(p3)
    print(f"Phase 4: Generated {len(p4.get('candidates', []))} candidates")

    # Phase 5: Validation and ranking
    p5 = validate_and_rank(p4)
    print(f"Phase 5: Best match confidence={p5.get('best_candidate', {}).get('final_confidence', 0):.2f}")

    # Phase 6: Postprocessing
    result = postprocess(p5, p3)

    print(f"\n✅ FINAL RESULTS:")
    print(f"  Ward:     {result.get('ward', '____')}")
    print(f"  District: {result.get('district', '____')}")
    print(f"  Province: {result.get('province', '____')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    print(f"  Quality: {result.get('quality_flag', 'unknown')}")

    # Check if successful
    has_district = result.get('district') and result.get('district') != '____'
    has_ward = result.get('ward') and result.get('ward') != '____'

    if has_district and has_ward:
        print(f"\n✅ SUCCESS: Found both district and ward!")
        return True
    elif has_district:
        print(f"\n⚠️  PARTIAL: Found district but not ward")
        return False
    else:
        print(f"\n❌ FAILED: Did not find district")
        return False

def main():
    print("\n" + "="*70)
    print(" LEADING ZERO NORMALIZATION FIX - TEST SUITE")
    print("="*70)

    test_cases = [
        # The problematic address from the user
        ("660/8 PHAM THE HIEN P4 Q8", "HO CHI MINH"),

        # Additional test cases with different formats
        ("123 NGUYEN TRAI P1 Q1", "HO CHI MINH"),
        ("PHUONG 2 QUAN 3", "HO CHI MINH"),
        ("P5 Q10", "HO CHI MINH"),

        # Test with zero-padded input (should still work)
        ("PHUONG 04 QUAN 08", "HO CHI MINH"),
    ]

    results = []
    for address, province in test_cases:
        success = test_address(address, province)
        results.append((address, success))

    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for address, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {address}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*70)

if __name__ == "__main__":
    main()
