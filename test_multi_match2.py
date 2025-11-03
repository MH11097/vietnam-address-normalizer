"""Test multiple exact matches via pipeline."""
from src.pipeline import parse_address

# Test with a simple address
test_address = "22 NGO 629 GIAI PHONG HA NOI"
result = parse_address(
    raw_input=test_address,
    province_known="HA NOI"
)

print("=" * 60)
print("TEST: Multi-match logic via pipeline")
print("=" * 60)
print(f"Input: {test_address}")
print(f"Province known: HA NOI")
print()
print("Result:")
print(f"  Province: {result['province']}")
print(f"  District: {result['district']}")
print(f"  Ward: {result['ward']}")
print(f"  Confidence: {result.get('confidence', 'N/A')}")
print()

# Check if extraction phase generated multiple candidates
if 'metadata' in result and 'extraction_result' in result['metadata']:
    extraction = result['metadata']['extraction_result']
    print("Extraction metadata:")
    print(f"  Potential provinces: {len(extraction.get('potential_provinces', []))}")
    print(f"  Potential districts: {len(extraction.get('potential_districts', []))}")
    print(f"  Potential wards: {len(extraction.get('potential_wards', []))}")
    
    if 'candidates' in result['metadata']:
        print(f"\nTotal candidates generated: {len(result['metadata']['candidates'])}")

print("=" * 60)
print("✅ TEST COMPLETED - No errors!")
print("=" * 60)
