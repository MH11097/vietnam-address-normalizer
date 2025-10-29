"""
Test script to check how commas affect token matching
"""
from src.utils.text_utils import normalize_address, finalize_normalization
from src.utils.matching_utils import ensemble_fuzzy_score

# Test case from user
test_texts = [
    "my hiep,",  # With comma
    "my hiep",   # Without comma
]

target = "my hiep"  # Database value (normalized)

print("=" * 60)
print("Testing comma impact on normalization and matching")
print("=" * 60)

print("\n1. Normalization test:")
print("-" * 60)
for text in test_texts:
    normalized = normalize_address(text)
    print(f"Input:      '{text}'")
    print(f"Normalized: '{normalized}'")
    print(f"Length:     {len(normalized)}")
    print()

print("\n2. Finalization with keep_separators:")
print("-" * 60)
for text in test_texts:
    # Test with keep_separators=True
    with_sep = finalize_normalization(text.lower(), keep_separators=True)
    without_sep = finalize_normalization(text.lower(), keep_separators=False)
    print(f"Input:              '{text}'")
    print(f"With separators:    '{with_sep}'")
    print(f"Without separators: '{without_sep}'")
    print()

print("\n3. Fuzzy matching scores:")
print("-" * 60)
for text in test_texts:
    normalized = normalize_address(text)
    score = ensemble_fuzzy_score(normalized, target)
    print(f"'{normalized}' vs '{target}': {score:.3f}")
print()

print("\n4. Character-by-character comparison:")
print("-" * 60)
text_with_comma = normalize_address("my hiep,")
text_without_comma = normalize_address("my hiep")
print(f"With comma:    '{text_with_comma}' -> bytes: {[ord(c) for c in text_with_comma]}")
print(f"Without comma: '{text_without_comma}' -> bytes: {[ord(c) for c in text_without_comma]}")
print(f"Are they equal? {text_with_comma == text_without_comma}")
