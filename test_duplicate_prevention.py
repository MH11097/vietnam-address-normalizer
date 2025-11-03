"""
Test script to verify duplicate prevention with NULL values
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.db_utils import save_user_rating, get_db_connection

def test_duplicate_prevention():
    """Test that UPDATE happens instead of INSERT for duplicates with NULL values"""

    print("="*60)
    print("Testing Duplicate Prevention with NULL Values")
    print("="*60 + "\n")

    # Test Case 1: Same address with NULL district
    print("Test Case 1: Same address with NULL district")
    print("-" * 60)

    test_address = f"TEST_ADDRESS_{datetime.now().timestamp()}"

    # First insertion
    rating_data_1 = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': 'CIF001',
        'original_address': test_address,
        'known_province': 'ha noi',
        'known_district': None,  # NULL district
        'parsed_province': 'ha noi',
        'parsed_district': 'ba dinh',
        'parsed_ward': 'cong vi',
        'user_rating': 1,
        'confidence_score': 0.85,
        'processing_time_ms': 100.5,
        'match_type': 'exact'
    }

    print(f"First insert: address='{test_address}', province='ha noi', district=None")
    record_id_1 = save_user_rating(rating_data_1)
    print(f"✅ First insert successful, ID: {record_id_1}")

    # Second insertion with same address (should UPDATE, not INSERT)
    rating_data_2 = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': 'CIF002',
        'original_address': test_address,
        'known_province': 'ha noi',
        'known_district': None,  # NULL district (same as first)
        'parsed_province': 'ha noi',
        'parsed_district': 'hoan kiem',  # Different result
        'parsed_ward': 'hang bac',
        'user_rating': 2,
        'confidence_score': 0.92,  # Higher confidence
        'processing_time_ms': 150.3,
        'match_type': 'fuzzy'
    }

    print(f"\nSecond insert: address='{test_address}', province='ha noi', district=None")
    record_id_2 = save_user_rating(rating_data_2)
    print(f"✅ Second insert successful, ID: {record_id_2}")

    # Check if UPDATE happened (IDs should be same)
    if record_id_1 == record_id_2:
        print(f"\n✅ PASS: UPDATE occurred (same ID: {record_id_1})")
    else:
        print(f"\n❌ FAIL: INSERT occurred (different IDs: {record_id_1} vs {record_id_2})")

    # Verify only one record exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM user_quality_ratings
            WHERE original_address = ? AND known_province = ? AND known_district = ?
        """, (test_address, 'ha noi', ''))
        count = cursor.fetchone()[0]

        if count == 1:
            print(f"✅ PASS: Only 1 record exists (expected)")
        else:
            print(f"❌ FAIL: {count} records exist (expected 1)")

        # Check that the second values were saved
        cursor.execute("""
            SELECT cif_no, parsed_district, parsed_ward, confidence_score, user_rating
            FROM user_quality_ratings
            WHERE original_address = ? AND known_province = ? AND known_district = ?
        """, (test_address, 'ha noi', ''))
        row = cursor.fetchone()

        print(f"\nFinal record values:")
        print(f"  - CIF: {row[0]} (expected: CIF002)")
        print(f"  - Parsed district: {row[1]} (expected: hoan kiem)")
        print(f"  - Parsed ward: {row[2]} (expected: hang bac)")
        print(f"  - Confidence: {row[3]} (expected: 0.92)")
        print(f"  - Rating: {row[4]} (expected: 2)")

        if row[0] == 'CIF002' and row[1] == 'hoan kiem' and row[4] == 2:
            print("\n✅ PASS: Record was updated with second values")
        else:
            print("\n❌ FAIL: Record was not updated correctly")

    print("\n" + "="*60)

    # Test Case 2: Different addresses should create separate records
    print("\nTest Case 2: Different addresses should be separate")
    print("-" * 60)

    test_address_2 = f"TEST_ADDRESS_2_{datetime.now().timestamp()}"

    rating_data_3 = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': 'CIF003',
        'original_address': test_address_2,  # Different address
        'known_province': 'ha noi',
        'known_district': None,
        'parsed_province': 'ha noi',
        'parsed_district': 'dong da',
        'parsed_ward': 'khuong thuong',
        'user_rating': 3,
        'confidence_score': 0.75,
        'processing_time_ms': 200.0,
        'match_type': 'approximate'
    }

    print(f"Third insert: address='{test_address_2}', province='ha noi', district=None")
    record_id_3 = save_user_rating(rating_data_3)
    print(f"✅ Third insert successful, ID: {record_id_3}")

    if record_id_3 != record_id_2:
        print(f"✅ PASS: New record created (ID: {record_id_3})")
    else:
        print(f"❌ FAIL: Should have created new record")

    # Verify two records exist (one for each address)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM user_quality_ratings
            WHERE original_address IN (?, ?) AND known_province = ? AND known_district = ?
        """, (test_address, test_address_2, 'ha noi', ''))
        count = cursor.fetchone()[0]

        if count == 2:
            print(f"✅ PASS: 2 records exist for different addresses")
        else:
            print(f"❌ FAIL: {count} records exist (expected 2)")

    print("\n" + "="*60)
    print("Testing completed!")
    print("="*60)

if __name__ == "__main__":
    test_duplicate_prevention()
