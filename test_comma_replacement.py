"""
Test comma replacement in address normalization.
This test verifies that commas are replaced with spaces and whitespace is properly trimmed.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.text_utils import finalize_normalization


def test_comma_replacement():
    """Test that commas are replaced with spaces."""

    print("=" * 80)
    print("Testing Comma Replacement in Address Normalization")
    print("=" * 80)

    test_cases = [
        # (input, expected_output, description)
        (
            "55 BE VAN DAN,P14,Q TAN BINH,TP",
            "55 be van dan p14 q tan binh tp",
            "Original issue: commas without spaces"
        ),
        (
            "phuong dien bien, quan ba dinh, ha noi",
            "phuong dien bien quan ba dinh ha noi",
            "Commas with spaces"
        ),
        (
            "xa yen ho,duc tho,ha tinh",
            "xa yen ho duc tho ha tinh",
            "Multiple commas without spaces"
        ),
        (
            "  ,leading comma and spaces  ",
            "leading comma and spaces",
            "Leading comma and extra spaces"
        ),
        (
            "trailing comma,  ",
            "trailing comma",
            "Trailing comma and spaces"
        ),
        (
            "multiple,,,,commas",
            "multiple commas",
            "Multiple consecutive commas"
        ),
        (
            "combo-test,with-hyphens,and,commas",
            "combo test with hyphens and commas",
            "Both hyphens and commas"
        ),
        (
            "no,commas here",
            "no commas here",
            "Simple case"
        ),
    ]

    all_passed = True

    for i, (input_text, expected, description) in enumerate(test_cases, 1):
        # Test with keep_separators=True (the production mode)
        result = finalize_normalization(input_text, keep_separators=True)

        passed = result == expected
        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"\nTest {i}: {description}")
        print(f"  Input:    {repr(input_text)}")
        print(f"  Expected: {repr(expected)}")
        print(f"  Got:      {repr(result)}")
        print(f"  Status:   {status}")

        if not passed:
            all_passed = False
            print(f"  ERROR: Mismatch!")

    print("\n" + "=" * 80)

    if all_passed:
        print("✓ ALL TESTS PASSED")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = test_comma_replacement()
    sys.exit(exit_code)
