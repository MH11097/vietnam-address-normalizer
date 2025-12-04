#!/usr/bin/env python3
"""
Simple test to verify province abbreviation branching is working.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import get_province_abbreviation_candidates
from src.utils.extraction_utils import extract_province_candidates, build_search_tree
from src.processors.phase1_preprocessing import preprocess

def test_province_extraction():
    """Test province extraction with abbreviations."""
    print("=" * 60)
    print("TEST: Province Extraction with Abbreviations")
    print("=" * 60)

    test_cases = [
        {
            "address": "phuong 3 dn",
            "description": "Ambiguous 'dn' (Da Nang OR Dong Nai)"
        },
        {
            "address": "phuong ben thanh hcm",
            "description": "Unique 'hcm' (Ho Chi Minh)"
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

            # Extract province candidates
            province_candidates = extract_province_candidates(tokens)
            print(f"   Found {len(province_candidates)} province candidate(s):")

            for j, cand in enumerate(province_candidates, 1):
                if len(cand) >= 5:
                    prov, score, source, collision, token_pos = cand
                elif len(cand) == 4:
                    prov, score, source, collision = cand
                    token_pos = None
                else:
                    prov, score, source = cand
                    collision = False
                    token_pos = None

                print(f"      {j}. '{prov}' (score: {score:.3f}, source: {source})")

            # Build search tree to see branching
            print(f"\n   Building search tree...")
            candidates = build_search_tree(tokens)
            print(f"   Created {len(candidates)} final candidate(s):")

            for j, cand in enumerate(candidates[:5], 1):
                province = cand.get('province', 'N/A')
                district = cand.get('district', 'N/A')
                ward = cand.get('ward', 'N/A')
                score = cand.get('combined_score', 0)
                print(f"      {j}. Province: {province}, District: {district}, Ward: {ward} (score: {score:.3f})")

            print(f"   ✓ Test completed")

        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    try:
        print("\n🚀 Starting Province Branching Test\n")
        test_province_extraction()
        print("\n" + "=" * 60)
        print("✅ Test completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
