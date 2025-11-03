"""
Final verification test - Simulate user workflow
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.db_utils import save_user_rating, get_db_connection

def test_user_workflow():
    """Simulate real user workflow: parse same address multiple times"""

    print("="*60)
    print("FINAL VERIFICATION TEST")
    print("Simulating User Workflow: Processing Same Address 3 Times")
    print("="*60 + "\n")

    test_address = "123 NGUYEN TRAI, THANH XUAN, HA NOI"

    print(f"Test Address: {test_address}")
    print(f"Known Province: ha noi")
    print(f"Known District: None (NULL)\n")

    # Simulate 3 processing attempts with different results
    attempts = [
        {
            'desc': '1st Attempt (Low confidence)',
            'parsed_province': 'ha noi',
            'parsed_district': 'thanh xuan',
            'parsed_ward': 'khuong trung',
            'confidence': 0.75,
            'rating': 2
        },
        {
            'desc': '2nd Attempt (Medium confidence)',
            'parsed_province': 'ha noi',
            'parsed_district': 'thanh xuan',
            'parsed_ward': 'thanh xuan trung',
            'confidence': 0.85,
            'rating': 1
        },
        {
            'desc': '3rd Attempt (High confidence)',
            'parsed_province': 'ha noi',
            'parsed_district': 'thanh xuan',
            'parsed_ward': 'khuong mai',
            'confidence': 0.95,
            'rating': 1
        }
    ]

    returned_ids = []

    for i, attempt in enumerate(attempts, 1):
        print(f"\n{'-'*60}")
        print(f"Attempt {i}: {attempt['desc']}")
        print(f"{'-'*60}")

        rating_data = {
            'timestamp': datetime.now().isoformat(),
            'cif_no': f'CIF{i:03d}',
            'original_address': test_address,
            'known_province': 'ha noi',
            'known_district': None,  # This is the key test case!
            'parsed_province': attempt['parsed_province'],
            'parsed_district': attempt['parsed_district'],
            'parsed_ward': attempt['parsed_ward'],
            'user_rating': attempt['rating'],
            'confidence_score': attempt['confidence'],
            'processing_time_ms': 100.0 * i,
            'match_type': 'test'
        }

        try:
            record_id = save_user_rating(rating_data)
            returned_ids.append(record_id)
            print(f"✅ Saved successfully, ID: {record_id}")
            print(f"   Parsed: {attempt['parsed_district']} / {attempt['parsed_ward']}")
            print(f"   Confidence: {attempt['confidence']}")
            print(f"   Rating: {attempt['rating']}")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Verify results
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}\n")

    # Check all IDs are the same (UPDATE happened)
    all_same = len(set(returned_ids)) == 1
    print(f"Returned IDs: {returned_ids}")

    if all_same:
        print(f"✅ PASS: All IDs are the same ({returned_ids[0]}) - UPDATE worked!")
    else:
        print(f"❌ FAIL: Different IDs returned - duplicates created!")
        return False

    # Check only one record exists in database
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM user_quality_ratings
            WHERE original_address = ?
                AND COALESCE(known_province, '') = ?
                AND COALESCE(known_district, '') = ?
        """, (test_address, 'ha noi', ''))

        count = cursor.fetchone()[0]

        if count == 1:
            print(f"✅ PASS: Only 1 record in database (expected)")
        else:
            print(f"❌ FAIL: {count} records in database (expected 1)")
            return False

        # Check final values (should be from 3rd attempt)
        cursor.execute("""
            SELECT cif_no, parsed_district, parsed_ward, confidence_score, user_rating
            FROM user_quality_ratings
            WHERE original_address = ?
                AND COALESCE(known_province, '') = ?
                AND COALESCE(known_district, '') = ?
        """, (test_address, 'ha noi', ''))

        row = cursor.fetchone()
        final_cif, final_dist, final_ward, final_conf, final_rating = row

        print(f"\nFinal record values (should be from 3rd attempt):")
        print(f"  CIF: {final_cif} (expected: CIF003)")
        print(f"  District: {final_dist} (expected: thanh xuan)")
        print(f"  Ward: {final_ward} (expected: khuong mai)")
        print(f"  Confidence: {final_conf} (expected: 0.95)")
        print(f"  Rating: {final_rating} (expected: 1)")

        if (final_cif == 'CIF003' and
            final_ward == 'khuong mai' and
            final_conf == 0.95 and
            final_rating == 1):
            print(f"\n✅ PASS: Final values are correct (3rd attempt data)")
        else:
            print(f"\n❌ FAIL: Final values don't match 3rd attempt")
            return False

    # Clean up test data
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM user_quality_ratings
            WHERE original_address = ?
        """, (test_address,))
        print(f"\n✅ Test data cleaned up ({cursor.rowcount} record deleted)")

    return True


def main():
    print("\n")
    success = test_user_workflow()

    print("\n" + "="*60)
    if success:
        print("🎉 FINAL VERIFICATION: ALL TESTS PASSED!")
        print("="*60)
        print("\n✅ System is working correctly:")
        print("   - No duplicates created")
        print("   - UPDATE works with NULL values")
        print("   - Latest data always overwrites previous data")
        print("\n✅ demo.py and app.py will now UPDATE instead of INSERT")
        print("   when processing the same address multiple times!")
    else:
        print("❌ FINAL VERIFICATION FAILED!")
        print("="*60)

    print()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
