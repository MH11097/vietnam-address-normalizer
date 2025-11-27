"""
Test delimiter-aware address matching.

This script tests the new delimiter handling logic that respects user intent
when they include delimiters like commas, hyphens, underscores, or slashes.
"""
import sys
from src.pipeline import AddressPipeline

# Test cases covering different delimiter scenarios
test_cases = [
    {
        "name": "Comma delimiter - 3 admin units",
        "address": "P3, Q5, HCM",
        "expected": "Should separate P3, Q5, and HCM cleanly"
    },
    {
        "name": "Slash in address number",
        "address": "55/2 Nguyen Trai, Q1, HCM",
        "expected": "55/2 should stay together as address number"
    },
    {
        "name": "Hyphen delimiter",
        "address": "Phuong 3 - Quan 5 - TP HCM",
        "expected": "Should separate units by hyphens"
    },
    {
        "name": "No delimiters",
        "address": "Phuong 3 Quan 5 TP HCM",
        "expected": "Should work normally without delimiter bonuses"
    },
    {
        "name": "Underscore delimiter",
        "address": "Ward_3_District_5_HCM",
        "expected": "Should separate by underscores"
    },
    {
        "name": "Mixed address with slash number",
        "address": "123/45 Le Loi, P Ben Thanh, Q1, HCM",
        "expected": "123/45 stays together, segments separated by commas"
    }
]

def run_tests():
    """Run all test cases and display results."""
    print("=" * 80)
    print("DELIMITER-AWARE ADDRESS MATCHING - TEST SUITE")
    print("=" * 80)
    print()

    # Initialize pipeline
    pipeline = AddressPipeline()

    for i, test in enumerate(test_cases, 1):
        print(f"\nTest #{i}: {test['name']}")
        print(f"Input: {test['address']}")
        print(f"Expected: {test['expected']}")
        print("-" * 80)

        try:
            result = pipeline.process(test['address'])

            # Display results
            if result:
                print(f"✓ Success!")
                print(f"  Province: {result.get('PROVINCE', 'N/A')}")
                print(f"  District: {result.get('DISTRICT', 'N/A')}")
                print(f"  Ward: {result.get('WARD', 'N/A')}")
                confidence = result.get('CONFIDENCE', result.get('confidence', 0))
                print(f"  Confidence: {confidence if isinstance(confidence, (int, float)) else 0:.2f}")
                print(f"  @-Rule: {result.get('AT_RULE', result.get('@-rule', 'N/A'))}")

                # Show delimiter info if available
                phase_results = result.get('phase_results', result.get('_phase_results', {}))
                phase1 = phase_results.get('phase1', {})
                delimiter_info = phase1.get('delimiter_info')
                if delimiter_info and delimiter_info.get('has_delimiters'):
                    print(f"  Delimiters found: {len(delimiter_info['delimiter_positions'])}")
                    print(f"  Segments: {len(delimiter_info['segments'])}")
                    if delimiter_info['number_tokens']:
                        print(f"  Number tokens with slash: {delimiter_info['number_tokens']}")
            else:
                print(f"✗ Failed: No result returned")

        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            import traceback
            traceback.print_exc()

        print()

    print("=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
