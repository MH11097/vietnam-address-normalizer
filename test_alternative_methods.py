"""
Test alternative fuzzy matching methods to improve spacing issue handling.
"""

import sys
sys.path.insert(0, '/Users/minhhieu/Library/CloudStorage/OneDrive-Personal/Coding/Python/company/address_mapping')

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ = True
except ImportError:
    from fuzzywuzzy import fuzz
    RAPIDFUZZ = False

print("=" * 100)
print(f"TEST: Alternative Fuzzy Matching Methods")
print(f"Using: {'rapidfuzz' if RAPIDFUZZ else 'fuzzywuzzy'}")
print("=" * 100)

# Main test case
s1 = "p leiku"
s2 = "pleiku"

print(f"\nMain case: '{s1}' vs '{s2}'")
print("─" * 100)

# All available fuzz methods
methods = {
    'ratio': fuzz.ratio,
    'partial_ratio': fuzz.partial_ratio,
    'token_sort_ratio': fuzz.token_sort_ratio,
    'token_set_ratio': fuzz.token_set_ratio,
}

print("\n📊 ALL FUZZ METHODS (0-100 scale):")
print("─" * 100)

results = {}
for name, method in methods.items():
    score_100 = method(s1, s2)
    score_01 = score_100 / 100.0
    results[name] = score_01
    status = "✅ PASS" if score_01 >= 0.90 else "❌ FAIL"
    print(f"  {name:25} : {score_100:6.1f}/100 = {score_01:.3f}  {status}")

# Test character-level matching (remove spaces)
s1_no_space = s1.replace(" ", "")
s2_no_space = s2.replace(" ", "")

print(f"\n📌 CHARACTER-LEVEL (no spaces): '{s1_no_space}' vs '{s2_no_space}'")
print("─" * 100)

for name, method in methods.items():
    score_100 = method(s1_no_space, s2_no_space)
    score_01 = score_100 / 100.0
    status = "✅ PASS" if score_01 >= 0.90 else "❌ FAIL"
    print(f"  {name:25} : {score_100:6.1f}/100 = {score_01:.3f}  {status}")

# Test all spacing issue cases
print("\n\n" + "=" * 100)
print("📋 COMPARISON: All methods on all test cases")
print("=" * 100)

test_cases = [
    ("p leiku", "pleiku"),
    ("tx binh minh", "binh minh"),
    ("q 1", "1"),
    ("h long bien", "long bien"),
    ("ba dinh", "badinh"),
]

print(f"\n{'Test Case':<30} {'ratio':<8} {'partial':<8} {'token_sort':<12} {'token_set':<10} {'char-level':<12}")
print("─" * 100)

for s1, s2 in test_cases:
    ratio = fuzz.ratio(s1, s2) / 100.0
    partial = fuzz.partial_ratio(s1, s2) / 100.0
    token_sort = fuzz.token_sort_ratio(s1, s2) / 100.0
    token_set = fuzz.token_set_ratio(s1, s2) / 100.0

    # Char-level
    char_level = fuzz.ratio(s1.replace(" ", ""), s2.replace(" ", "")) / 100.0

    case_str = f"'{s1}' vs '{s2}'"
    print(f"{case_str:<30} {ratio:.3f}    {partial:.3f}    {token_sort:.3f}      {token_set:.3f}    {char_level:.3f}")

# Proposed new ensemble
print("\n\n" + "=" * 100)
print("💡 PROPOSED NEW ENSEMBLE FORMULAS")
print("=" * 100)

def current_ensemble(s1, s2):
    """Current implementation"""
    from src.utils.matching_utils import ensemble_fuzzy_score
    return ensemble_fuzzy_score(s1, s2, log=False)

def proposed_ensemble_v1(s1, s2):
    """
    V1: Add character-level matching
    Weights: token_sort(40%) + levenshtein(25%) + jaccard(10%) + char_level(25%)
    """
    from src.utils.matching_utils import token_sort_ratio, levenshtein_normalized, jaccard_similarity

    token_score = token_sort_ratio(s1, s2)
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    # NEW: Character-level matching (no spaces)
    s1_chars = s1.replace(" ", "")
    s2_chars = s2.replace(" ", "")
    char_score = levenshtein_normalized(s1_chars, s2_chars)

    ensemble = (
        token_score * 0.40 +
        lev_score * 0.25 +
        jac_score * 0.10 +
        char_score * 0.25
    )
    return ensemble

def proposed_ensemble_v2(s1, s2):
    """
    V2: Use token_set_ratio instead of token_sort_ratio
    Weights: token_set(50%) + levenshtein(30%) + jaccard(20%)
    """
    from src.utils.matching_utils import levenshtein_normalized, jaccard_similarity

    token_set_score = fuzz.token_set_ratio(s1, s2) / 100.0
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    ensemble = (
        token_set_score * 0.50 +
        lev_score * 0.30 +
        jac_score * 0.20
    )
    return ensemble

def proposed_ensemble_v3(s1, s2):
    """
    V3: Hybrid - use max of token_sort and token_set
    Weights: max(token_sort, token_set)(50%) + levenshtein(30%) + jaccard(20%)
    """
    from src.utils.matching_utils import token_sort_ratio, levenshtein_normalized, jaccard_similarity

    token_sort_score = token_sort_ratio(s1, s2)
    token_set_score = fuzz.token_set_ratio(s1, s2) / 100.0
    token_best = max(token_sort_score, token_set_score)

    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    ensemble = (
        token_best * 0.50 +
        lev_score * 0.30 +
        jac_score * 0.20
    )
    return ensemble

def proposed_ensemble_v4(s1, s2):
    """
    V4: Multi-metric with char-level and partial_ratio
    Weights: token_sort(30%) + partial(20%) + lev(20%) + char_level(20%) + jaccard(10%)
    """
    from src.utils.matching_utils import token_sort_ratio, levenshtein_normalized, jaccard_similarity

    token_score = token_sort_ratio(s1, s2)
    partial_score = fuzz.partial_ratio(s1, s2) / 100.0
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    # Character-level
    s1_chars = s1.replace(" ", "")
    s2_chars = s2.replace(" ", "")
    char_score = levenshtein_normalized(s1_chars, s2_chars)

    ensemble = (
        token_score * 0.30 +
        partial_score * 0.20 +
        lev_score * 0.20 +
        char_score * 0.20 +
        jac_score * 0.10
    )
    return ensemble


# Test all versions
print(f"\n{'Test Case':<30} {'Current':<10} {'V1-Char':<10} {'V2-TokSet':<12} {'V3-Hybrid':<10} {'V4-Multi':<10}")
print("─" * 100)

for s1, s2 in test_cases:
    curr = current_ensemble(s1, s2)
    v1 = proposed_ensemble_v1(s1, s2)
    v2 = proposed_ensemble_v2(s1, s2)
    v3 = proposed_ensemble_v3(s1, s2)
    v4 = proposed_ensemble_v4(s1, s2)

    case_str = f"'{s1}' vs '{s2}'"

    # Color code: green if >= 0.90
    def fmt(score):
        status = "✅" if score >= 0.90 else "  "
        return f"{score:.3f}{status}"

    print(f"{case_str:<30} {fmt(curr):<10} {fmt(v1):<10} {fmt(v2):<12} {fmt(v3):<10} {fmt(v4):<10}")

# Summary
print("\n\n" + "=" * 100)
print("📊 SUMMARY")
print("=" * 100)

all_scores = {
    'Current': [],
    'V1 (Char-level)': [],
    'V2 (Token Set)': [],
    'V3 (Hybrid)': [],
    'V4 (Multi-metric)': []
}

for s1, s2 in test_cases:
    all_scores['Current'].append(current_ensemble(s1, s2))
    all_scores['V1 (Char-level)'].append(proposed_ensemble_v1(s1, s2))
    all_scores['V2 (Token Set)'].append(proposed_ensemble_v2(s1, s2))
    all_scores['V3 (Hybrid)'].append(proposed_ensemble_v3(s1, s2))
    all_scores['V4 (Multi-metric)'].append(proposed_ensemble_v4(s1, s2))

print(f"\n{'Version':<25} {'Avg Score':<12} {'Pass Rate':<12} {'Min Score':<12}")
print("─" * 100)

for version, scores in all_scores.items():
    avg_score = sum(scores) / len(scores)
    pass_rate = sum(1 for s in scores if s >= 0.90) / len(scores)
    min_score = min(scores)

    print(f"{version:<25} {avg_score:.3f}        {pass_rate:.1%}         {min_score:.3f}")

print("\n" + "=" * 100)
print("🎯 RECOMMENDATION")
print("=" * 100)

print("""
Dựa trên kết quả test:

1. CURRENT: Average ~0.6-0.7, Pass rate 0% - FAIL với tất cả spacing cases

2. V1 (Character-level 25%): Thêm char-level matching
   • Tốt cho "p leiku" vs "pleiku" (perfect sau khi bỏ space)
   • Simple, easy to implement
   • RECOMMENDED nếu muốn fix nhanh

3. V2 (Token Set Ratio): Thay token_sort bằng token_set
   • token_set_ratio xử lý extra tokens tốt hơn
   • Tốt cho "tx binh minh" vs "binh minh"
   • Nhưng vẫn FAIL với "p leiku" vs "pleiku" (no common tokens)

4. V3 (Hybrid): Lấy max(token_sort, token_set)
   • Kết hợp ưu điểm của cả 2
   • Tốt hơn V2 một chút
   • Computational cost cao hơn

5. V4 (Multi-metric): Nhiều metrics, phân tán weights
   • Balanced, robust nhất
   • Sử dụng nhiều signals: token_sort, partial, lev, char, jaccard
   • RECOMMENDED nếu muốn solution robust

BEST CHOICE:
• Nếu chỉ fix spacing: V1 (Character-level)
• Nếu muốn robust cho nhiều cases: V4 (Multi-metric)
""")

print("\n" + "=" * 100)
