"""
Test UPDATE with real data from database
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.db_utils import save_user_rating, get_db_connection

def test_real_update():
    """Test UPDATE with a real existing record"""

    print("="*60)
    print("Testing UPDATE with Real Database Record")
    print("="*60 + "\n")

    # Get a real record from database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, original_address, known_province, known_district,
                   parsed_province, parsed_district, user_rating, confidence_score
            FROM user_quality_ratings
            LIMIT 1
        """)
        existing_record = cursor.fetchone()

    if not existing_record:
        print("❌ No records found in database to test")
        return

    record_id, orig_addr, known_prov, known_dist, parsed_prov, parsed_dist, old_rating, old_conf = existing_record

    print(f"Found existing record:")
    print(f"  ID: {record_id}")
    print(f"  Address: {orig_addr}")
    print(f"  Known Province: '{known_prov}'")
    print(f"  Known District: '{known_dist}'")
    print(f"  Parsed Province: {parsed_prov}")
    print(f"  Parsed District: {parsed_dist}")
    print(f"  Old Rating: {old_rating}")
    print(f"  Old Confidence: {old_conf}")
    print()

    # Try to update this record with new values
    rating_data = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': 'TEST_CIF_UPDATE',
        'original_address': orig_addr,
        'known_province': known_prov,
        'known_district': known_dist,
        'parsed_province': 'TEST_UPDATED_PROVINCE',
        'parsed_district': 'TEST_UPDATED_DISTRICT',
        'parsed_ward': 'TEST_UPDATED_WARD',
        'user_rating': 3,
        'confidence_score': 0.99,
        'processing_time_ms': 999.99,
        'match_type': 'test_update'
    }

    print("Attempting UPDATE with new values...")
    try:
        returned_id = save_user_rating(rating_data)
        print(f"✅ save_user_rating() successful, returned ID: {returned_id}")

        if returned_id == record_id:
            print(f"✅ PASS: Same ID returned (UPDATE occurred)")
        else:
            print(f"❌ FAIL: Different ID returned ({returned_id} vs {record_id})")

        # Verify the record was updated
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM user_quality_ratings
                WHERE original_address = ? AND COALESCE(known_province, '') = ? AND COALESCE(known_district, '') = ?
            """, (orig_addr, known_prov or '', known_dist or ''))
            count = cursor.fetchone()[0]

            if count == 1:
                print(f"✅ PASS: Still only 1 record (no duplicate created)")
            else:
                print(f"❌ FAIL: {count} records found (duplicate created!)")

            # Check updated values
            cursor.execute("""
                SELECT cif_no, parsed_province, parsed_district, parsed_ward, user_rating, confidence_score, match_type
                FROM user_quality_ratings
                WHERE id = ?
            """, (record_id,))
            updated = cursor.fetchone()

            print(f"\nUpdated record values:")
            print(f"  CIF: {updated[0]} (expected: TEST_CIF_UPDATE)")
            print(f"  Parsed Province: {updated[1]} (expected: TEST_UPDATED_PROVINCE)")
            print(f"  Parsed District: {updated[2]} (expected: TEST_UPDATED_DISTRICT)")
            print(f"  Parsed Ward: {updated[3]} (expected: TEST_UPDATED_WARD)")
            print(f"  Rating: {updated[4]} (expected: 3)")
            print(f"  Confidence: {updated[5]} (expected: 0.99)")
            print(f"  Match Type: {updated[6]} (expected: test_update)")

            if (updated[0] == 'TEST_CIF_UPDATE' and
                updated[1] == 'TEST_UPDATED_PROVINCE' and
                updated[4] == 3 and
                updated[5] == 0.99):
                print(f"\n✅ PASS: Record successfully updated with new values")
            else:
                print(f"\n❌ FAIL: Record was not updated correctly")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)

    # Restore original values
    print("\nRestoring original values...")
    restore_data = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': None,
        'original_address': orig_addr,
        'known_province': known_prov,
        'known_district': known_dist,
        'parsed_province': parsed_prov,
        'parsed_district': parsed_dist,
        'parsed_ward': None,
        'user_rating': old_rating,
        'confidence_score': old_conf,
        'processing_time_ms': None,
        'match_type': None
    }
    save_user_rating(restore_data)
    print("✅ Original values restored")

if __name__ == "__main__":
    test_real_update()
