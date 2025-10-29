"""
Test to understand why 'my hiep,' gets low score
"""
from src.utils.text_utils import normalize_address
from src.utils.matching_utils import ensemble_fuzzy_score

# Input from address
input_text = "my hiep,"
normalized_input = normalize_address(input_text)

# All wards in Phu My district that start with "my"
wards = [
    "my an",
    "my cat",
    "my chanh",
    "my chanh tay",
    "my chau",
    "my duc",
    "my hiep",  # This should be the match
    "my hoa",
    "my loc",
    "my loi",
    "my phong",
    "my quang",
    "my tai",
    "my thang",
    "my thanh",
    "my tho",
    "my trinh",
]

print("=" * 60)
print(f"Testing: '{input_text}' → normalized: '{normalized_input}'")
print("=" * 60)

results = []
for ward in wards:
    score = ensemble_fuzzy_score(normalized_input, ward)
    results.append((ward, score))

# Sort by score descending
results.sort(key=lambda x: x[1], reverse=True)

print("\nTop matches:")
for ward, score in results[:10]:
    marker = " ← EXPECTED MATCH" if ward == "my hiep" else ""
    print(f"  {ward:20s}: {score:.3f}{marker}")

print("\n" + "=" * 60)
print("Analysis:")
print("=" * 60)
print(f"Expected 'my hiep' score: {[s for w, s in results if w == 'my hiep'][0]:.3f}")
print(f"Best score: {results[0][1]:.3f} ({results[0][0]})")

# Additional test: what if we test the RAW token without normalization?
print("\n" + "=" * 60)
print("Testing WITHOUT full normalization:")
print("=" * 60)
raw_test = "my hiep,"
for test in ["my hiep,", "my hiep"]:
    print(f"\nTesting '{test}':")
    for ward in ["my hiep", "my an", "my chanh"]:
        score = ensemble_fuzzy_score(test.strip(',').lower(), ward)
        print(f"  vs '{ward}': {score:.3f}")
