"""Simple test for THANH CHUONG case - using pipeline logic manually"""
import os
os.chdir('/Users/minhhieu/Library/CloudStorage/OneDrive-Personal/Coding/Python/company/address_mapping')

# Test manually with tokens
tokens = ['thanh', 'hung', 'thanh', 'chuong', 'cty', 'tnhh', 'matrix', 'vinh']
province_context = 'nghe an'

print("=" * 80)
print("TEST: THANH CHUONG extraction")
print("=" * 80)
print(f"Tokens: {tokens}")
print(f"Province: {province_context}")
print()
print("Expected: Both 'thanh chuong' and 'vinh' should be found as district candidates")
print()

# Count matches manually
thanh_chuong_found = False
vinh_found = False

# Check if "thanh chuong" can be constructed from tokens
for i in range(len(tokens)-1):
    if tokens[i:i+2] == ['thanh', 'chuong']:
        thanh_chuong_found = True
        print(f"✅ 'thanh chuong' can be constructed from tokens at position {i}:{i+2}")

# Check if "vinh" exists
for i, token in enumerate(tokens):
    if token == 'vinh':
        vinh_found = True
        print(f"✅ 'vinh' found at position {i}")

print()
print("=" * 80)
if thanh_chuong_found and vinh_found:
    print("✅ TEST PASSED: Both districts can be found in tokens")
    print("After fix, both should be extracted as candidates")
else:
    print("❌ TEST FAILED: Missing districts in tokens")
print("=" * 80)
