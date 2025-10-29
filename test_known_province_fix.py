"""
Test to verify that when province_known is provided,
no additional province candidates are extracted from the text.
"""

import sys
sys.path.insert(0, '/Users/minhhieu/Library/CloudStorage/OneDrive-Personal/Coding/Python/company/address_mapping')

from src.utils.extraction_utils import extract_province_candidates
from src.utils.text_utils import normalize_address

print("=" * 100)
print("TEST: Known Province Should Skip Candidate Search")
print("=" * 100)

# Test case from user: "SO 128 /191 DA NANG | ____ | HAI PHONG"
# Known province: HAI PHONG
# Expected: Should only return HAI PHONG, not DA NANG

test_cases = [
    {
        "address": "SO 128 /191 DA NANG | ____ | HAI PHONG",
        "known_province": "HAI PHONG",
        "expected_count": 1,
        "expected_province": "hai phong",
        "should_not_contain": "da nang"
    },
    {
        "address": "123 DUONG ABC, QUAN 1, TP HO CHI MINH",
        "known_province": "DA NANG",
        "expected_count": 1,
        "expected_province": "da nang",
        "should_not_contain": "ho chi minh"
    },
    {
        "address": "456 NGUYEN TRAI, HA NOI, VIET NAM",
        "known_province": "BAC GIANG",
        "expected_count": 1,
        "expected_province": "bac giang",
        "should_not_contain": "ha noi"
    },
]

print("\n" + "=" * 100)
print("Running tests...")
print("=" * 100)

all_passed = True

for i, test_case in enumerate(test_cases, 1):
    print(f"\n{'─' * 100}")
    print(f"Test Case {i}:")
    print(f"  Address: {test_case['address']}")
    print(f"  Known Province: {test_case['known_province']}")
    print(f"{'─' * 100}")

    # Normalize and tokenize
    normalized_address = normalize_address(test_case['address'])
    tokens = normalized_address.split()
    normalized_known = normalize_address(test_case['known_province'])

    print(f"  Normalized: {normalized_address}")
    print(f"  Tokens: {tokens}")
    print(f"  Normalized Known: {normalized_known}")

    # Extract province candidates
    candidates = extract_province_candidates(
        tokens=tokens,
        province_known=normalized_known
    )

    print(f"\n  Candidates found: {len(candidates)}")
    for prov, score, source, has_collision in candidates:
        collision_marker = " [COLLISION]" if has_collision else ""
        print(f"    - {prov} (score={score:.2f}, source={source}){collision_marker}")

    # Verify expectations
    passed = True

    # Check count
    if len(candidates) != test_case['expected_count']:
        print(f"\n  ❌ FAIL: Expected {test_case['expected_count']} candidate(s), got {len(candidates)}")
        passed = False

    # Check expected province
    found_expected = any(prov == test_case['expected_province'] for prov, _, _, _ in candidates)
    if not found_expected:
        print(f"  ❌ FAIL: Expected province '{test_case['expected_province']}' not found")
        passed = False

    # Check should not contain
    found_unwanted = any(prov == test_case['should_not_contain'] for prov, _, _, _ in candidates)
    if found_unwanted:
        print(f"  ❌ FAIL: Should NOT contain province '{test_case['should_not_contain']}' but found it")
        passed = False

    if passed:
        print(f"\n  ✅ PASS")
    else:
        all_passed = False

print("\n" + "=" * 100)
if all_passed:
    print("✅ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED")
print("=" * 100)
