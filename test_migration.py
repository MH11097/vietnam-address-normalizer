"""
Test migration lookup functionality
"""
from src.utils.db_utils import (
    get_new_addresses_for_old_ward,
    get_new_addresses_for_old_district,
    get_new_addresses_for_old_province
)
from src.pipeline import AddressPipeline

print("=" * 80)
print("TEST MIGRATION LOOKUP")
print("=" * 80)

# Test 1: Ward level lookup
print("\n1. Ward Level Test: Phường Trúc Bạch, Quận Ba Đình, Thành phố Hà Nội")
print("-" * 80)
new_addresses = get_new_addresses_for_old_ward(
    "Thành phố Hà Nội",
    "Quận Ba Đình",
    "Phường Trúc Bạch"
)
print(f"Found {len(new_addresses)} mapping(s):")
for addr in new_addresses:
    print(f"  → {addr['new_province']} / {addr['new_ward']} ({addr['note']})")

# Test 2: District level lookup
print("\n2. District Level Test: Quận Ba Đình, Thành phố Hà Nội")
print("-" * 80)
new_addresses = get_new_addresses_for_old_district(
    "Thành phố Hà Nội",
    "Quận Ba Đình"
)
print(f"Found {len(new_addresses)} mapping(s):")
for i, addr in enumerate(new_addresses[:10]):  # Show first 10
    print(f"  {i+1}. {addr['new_province']} / {addr['new_ward']} ({addr['note']})")
if len(new_addresses) > 10:
    print(f"  ... and {len(new_addresses) - 10} more")

# Test 3: Province level lookup
print("\n3. Province Level Test: Tỉnh Hải Dương")
print("-" * 80)
new_addresses = get_new_addresses_for_old_province("Tỉnh Hải Dương")
print(f"Found {len(new_addresses)} mapping(s):")
for addr in new_addresses:
    print(f"  → {addr['new_province']} ({addr['note']})")

# Test 4: Full pipeline integration
print("\n4. Full Pipeline Test")
print("-" * 80)
pipeline = AddressPipeline()

test_addresses = [
    "Phường Trúc Bạch, Quận Ba Đình, Hà Nội",
    "Quận Ba Đình, Hà Nội",
]

for address in test_addresses:
    print(f"\nProcessing: {address}")
    result = pipeline.process(address)

    output = result['final_output']
    print(f"  Extracted: {output.get('ward', '')} / {output.get('district', '')} / {output.get('province', '')}")

    new_addresses = output.get('new_addresses', [])
    if new_addresses:
        print(f"  New addresses ({len(new_addresses)} mappings):")
        for i, addr in enumerate(new_addresses[:5]):  # Show first 5
            if 'new_ward' in addr:
                print(f"    {i+1}. {addr['new_province']} / {addr['new_ward']} ({addr['note']})")
            else:
                print(f"    {i+1}. {addr['new_province']} ({addr['note']})")
        if len(new_addresses) > 5:
            print(f"    ... and {len(new_addresses) - 5} more")
    else:
        print("  No migration mappings found (current address)")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
