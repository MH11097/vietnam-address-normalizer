"""Test multiple exact matches logic."""
import sys
sys.path.insert(0, 'src')

from utils.extraction_utils import match_in_set
from utils.db_utils import get_province_set

# Test 1: Single exact match
print("=" * 60)
print("TEST 1: Single exact match")
print("=" * 60)
province_set = get_province_set()
results = match_in_set('ha noi', province_set, level='province')
print(f"Query: 'ha noi'")
print(f"Results: {results}")
print(f"Count: {len(results)}")
print()

# Test 2: Check if can find multiple provinces with same name (hypothetical)
# In real DB, province names are unique, but let's test the logic
print("=" * 60)
print("TEST 2: Fuzzy matches with same score")
print("=" * 60)
# This might not produce multiple matches in real scenario
results = match_in_set('hai', province_set, level='province', threshold=0.5)
print(f"Query: 'hai'")
print(f"Results (top 5): {results[:5]}")
print(f"Count: {len(results)}")
print()

# Check if scores are equal
if len(results) > 1:
    scores = [score for _, score in results]
    if len(set(scores)) == 1:
        print("✅ All matches have the same score - logic is working!")
    else:
        print(f"⚠️  Different scores found: {set(scores)}")
else:
    print("Only one match found")

print()
print("=" * 60)
print("TEST COMPLETED")
print("=" * 60)
