"""Test THANH CHUONG case"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set debug mode
os.environ['DEBUG_EXTRACTION'] = '1'

from utils.extraction_utils import extract_district_scoped
from utils.db_utils import get_districts_by_province

# Test input
tokens = ['thanh', 'hung', 'thanh', 'chuong', 'cty', 'tnhh', 'matrix', 'vinh']
province_context = 'nghe an'
province_tokens_used = (-1, -1)  # Known but not in text

print("=" * 80)
print("TEST: THANH CHUONG vs VINH")
print("=" * 80)
print(f"Tokens: {tokens}")
print(f"Province: {province_context}")
print()

# Get all districts in NGHE AN
districts = get_districts_by_province(province_context)
print(f"Districts in NGHE AN: {len(districts)}")
print("Sample districts:", [d['district_name_normalized'] for d in districts[:10]])
print()

# Check if both VINH and THANH CHUONG are in the set
district_names = [d['district_name_normalized'] for d in districts]
print(f"'vinh' in districts: {'vinh' in district_names}")
print(f"'thanh chuong' in districts: {'thanh chuong' in district_names}")
print()

# Run extraction
print("Running extract_district_scoped...")
print("-" * 80)
candidates = extract_district_scoped(
    tokens,
    province_context=province_context,
    province_tokens_used=province_tokens_used,
    district_known=None,
    fuzzy_threshold=0.90
)

print("-" * 80)
print()
print("RESULTS:")
print(f"Total candidates found: {len(candidates)}")
for i, cand in enumerate(candidates, 1):
    if len(cand) == 5:
        name, score, source, pos, metadata = cand
        print(f"{i}. {name} | score: {score:.3f} | source: {source} | pos: {pos}")
        if metadata:
            print(f"   └─ ward: {metadata['ward_name']}")
    else:
        name, score, source, pos = cand
        print(f"{i}. {name} | score: {score:.3f} | source: {source} | pos: {pos}")

print("=" * 80)
