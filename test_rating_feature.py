"""
Test script for user rating feature
"""
from datetime import datetime
from src.utils.db_utils import save_user_rating, get_rating_stats

def test_save_rating():
    """Test saving a user rating"""
    print("="*60)
    print("Testing save_user_rating() function")
    print("="*60)

    # Test data
    rating_data = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': 'TEST_CIF_123',
        'original_address': 'NGO394 DOI CAN P.CONG VI BD HN',
        'known_province': 'ha noi',
        'known_district': None,
        'parsed_province': 'ha noi',
        'parsed_district': 'ba dinh',
        'parsed_ward': 'cong vi',
        'confidence_score': 0.95,
        'user_rating': 1,  # 1 = Good
        'processing_time_ms': 125.5,
        'match_type': 'exact'
    }

    print("\n1. Saving test rating...")
    print(f"   - Address: {rating_data['original_address']}")
    print(f"   - Rating: {rating_data['user_rating']} (1=Good)")
    print(f"   - Confidence: {rating_data['confidence_score']}")

    try:
        record_id = save_user_rating(rating_data)
        print(f"   ✅ SUCCESS! Saved with ID: {record_id}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    # Test getting stats
    print("\n2. Getting rating statistics...")
    try:
        stats = get_rating_stats()
        print(f"   - Total ratings: {stats['total_ratings']}")
        print(f"   - Distribution:")
        print(f"     * Good (1): {stats['rating_distribution'][1]}")
        print(f"     * Average (2): {stats['rating_distribution'][2]}")
        print(f"     * Poor (3): {stats['rating_distribution'][3]}")
        print(f"   ✅ SUCCESS!")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)
    return True

if __name__ == "__main__":
    test_save_rating()
