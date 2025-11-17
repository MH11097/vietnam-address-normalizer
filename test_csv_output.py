"""
Test CSV output with migration mappings (multiple rows)
"""
from src.pipeline import AddressPipeline
from src.main import save_results_to_csv
from pathlib import Path

print("=" * 80)
print("TEST CSV OUTPUT WITH MIGRATION MAPPINGS")
print("=" * 80)

pipeline = AddressPipeline()

test_addresses = [
    "Phường Trúc Bạch, Quận Ba Đình, Hà Nội",  # 1 mapping
    "Quận Ba Đình, Hà Nội",                    # 24 mappings
    "Phường Điện Biên, Ba Đình, Hà Nội",       # Current address (no mapping)
]

results = []
for address in test_addresses:
    print(f"\nProcessing: {address}")
    result = pipeline.process(address)

    output = result['final_output']
    new_addresses = output.get('new_addresses', [])

    print(f"  Old: {output.get('ward', 'N/A')} / {output.get('district', 'N/A')} / {output.get('province', 'N/A')}")
    if new_addresses:
        print(f"  New: {len(new_addresses)} mapping(s)")
        for i, addr in enumerate(new_addresses[:3]):
            if 'new_ward' in addr:
                print(f"    {i+1}. {addr['new_province']} / {addr['new_ward']} ({addr['note']})")
            else:
                print(f"    {i+1}. {addr['new_province']} ({addr['note']})")
        if len(new_addresses) > 3:
            print(f"    ... and {len(new_addresses) - 3} more")
    else:
        print(f"  New: No migration (current address)")

    results.append(result)

# Save to CSV
output_path = Path("test_migration_output.csv")
save_results_to_csv(results, output_path)

print(f"\n\nCSV saved to: {output_path}")
print("-" * 80)

# Display CSV content
import csv
with open(output_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

    print(f"Total CSV rows: {len(rows)}")
    print("\nFirst 10 rows:")
    print()

    for i, row in enumerate(rows[:10]):
        print(f"Row {i+1}:")
        print(f"  Input: {row['raw_input']}")
        print(f"  Old: {row['ward']} / {row['district']} / {row['province']}")
        print(f"  New: {row['new_ward']} / {row['new_province']}")
        print(f"  Note: {row['migration_note']}")
        print()

print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
