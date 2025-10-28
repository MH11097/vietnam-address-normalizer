"""
Test script to analyze fuzzy matching scores for spacing issues.
Demonstrates why "P LEIKU" vs "PLEIKU" gets low score.
"""

import sys
sys.path.insert(0, '/Users/minhhieu/Library/CloudStorage/OneDrive-Personal/Coding/Python/company/address_mapping')

from src.utils.matching_utils import (
    token_sort_ratio,
    levenshtein_normalized,
    jaccard_similarity,
    ensemble_fuzzy_score
)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ = True
except ImportError:
    from fuzzywuzzy import fuzz
    RAPIDFUZZ = False

print("=" * 100)
print(f"PHÂN TÍCH CHI TIẾT: Tại sao 'P LEIKU' vs 'PLEIKU' chỉ được {0.642:.3f}?")
print(f"Using: {'rapidfuzz' if RAPIDFUZZ else 'fuzzywuzzy'}")
print("=" * 100)

# Test cases
test_cases = [
    # Main case
    ("p leiku", "pleiku", "Case chính: P và LEIKU tách rời"),

    # Similar spacing issues
    ("p lei ku", "pleiku", "Nhiều dấu cách hơn"),
    ("pleiku", "pleiku", "Perfect match (baseline)"),
    ("p leik", "pleiku", "Thiếu ký tự + dấu cách"),

    # Other district patterns
    ("tx binh minh", "binh minh", "TX prefix"),
    ("q 1", "1", "Quận số"),
    ("h long bien", "long bien", "Huyện prefix"),

    # Token variations
    ("ba dinh", "ba din", "1 ký tự khác - NO space issue"),
    ("ba dinh", "badinh", "Thiếu dấu cách - reverse"),
    ("thanh pho p leiku", "pleiku", "Full form: 'thanh pho p leiku'"),
]

def analyze_case(s1: str, s2: str, description: str):
    """Phân tích chi tiết 1 test case"""
    print(f"\n{'─' * 100}")
    print(f"TEST: {description}")
    print(f"  Input 1: '{s1}'")
    print(f"  Input 2: '{s2}'")
    print(f"{'─' * 100}")

    # Calculate individual metrics
    token_score = token_sort_ratio(s1, s2)
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)
    ensemble_score = ensemble_fuzzy_score(s1, s2, log=False)

    # Token analysis
    tokens1 = set(s1.lower().strip().split())
    tokens2 = set(s2.lower().strip().split())
    token_intersection = tokens1 & tokens2
    token_union = tokens1 | tokens2

    # Character analysis
    chars1 = s1.replace(" ", "")
    chars2 = s2.replace(" ", "")

    print(f"\n1️⃣  TOKEN SORT RATIO: {token_score:.3f} (weight: 50%)")
    print(f"    Tokens 1: {sorted(tokens1)}")
    print(f"    Tokens 2: {sorted(tokens2)}")
    print(f"    Intersection: {token_intersection} → {len(token_intersection)} common")
    print(f"    Union: {token_union} → {len(token_union)} total")

    # Show what token_sort_ratio actually does
    sorted_s1 = ' '.join(sorted(s1.lower().strip().split()))
    sorted_s2 = ' '.join(sorted(s2.lower().strip().split()))
    print(f"    After sorting: '{sorted_s1}' vs '{sorted_s2}'")
    print(f"    → Uses Levenshtein on sorted tokens: {token_score:.3f}")

    print(f"\n2️⃣  LEVENSHTEIN NORMALIZED: {lev_score:.3f} (weight: 30%)")
    print(f"    String 1: '{s1}' (length: {len(s1)})")
    print(f"    String 2: '{s2}' (length: {len(s2)})")

    # Calculate edit distance manually
    from Levenshtein import distance as lev_dist
    dist = lev_dist(s1.lower().strip(), s2.lower().strip())
    max_len = max(len(s1.lower().strip()), len(s2.lower().strip()))
    print(f"    Edit distance: {dist} operations")
    print(f"    Max length: {max_len}")
    print(f"    Score: 1 - ({dist}/{max_len}) = {lev_score:.3f}")

    # Without spaces
    chars_dist = lev_dist(chars1.lower(), chars2.lower())
    print(f"    📌 Nếu BỎ dấu cách: '{chars1}' vs '{chars2}'")
    print(f"       Edit distance: {chars_dist}, Score: {1 - chars_dist/max(len(chars1), len(chars2)):.3f}")

    print(f"\n3️⃣  JACCARD SIMILARITY: {jac_score:.3f} (weight: 20%)")
    print(f"    |A ∩ B| = {len(token_intersection)}")
    print(f"    |A ∪ B| = {len(token_union)}")
    print(f"    Jaccard = {len(token_intersection)}/{len(token_union)} = {jac_score:.3f}")

    if jac_score == 0.0:
        print(f"    ⚠️  JACCARD = 0 vì KHÔNG có token chung!")

    print(f"\n{'═' * 100}")
    print(f"📊 ENSEMBLE SCORE (Weighted Average):")
    print(f"    = {token_score:.3f} × 0.5 + {lev_score:.3f} × 0.3 + {jac_score:.3f} × 0.2")
    print(f"    = {token_score * 0.5:.3f} + {lev_score * 0.3:.3f} + {jac_score * 0.2:.3f}")
    print(f"    = {ensemble_score:.3f}")

    # Threshold check
    threshold = 0.90
    status = "✅ PASS" if ensemble_score >= threshold else "❌ FAIL"
    print(f"\n🎯 Threshold: {threshold:.2f} → {status}")

    if ensemble_score < threshold:
        print(f"    Gap: {threshold - ensemble_score:.3f} (cần thêm {(threshold - ensemble_score):.1%})")

    return ensemble_score


# Run all test cases
print("\n\n")
scores = []
for s1, s2, desc in test_cases:
    score = analyze_case(s1, s2, desc)
    scores.append((s1, s2, score, desc))


# Summary
print("\n\n")
print("=" * 100)
print("📋 SUMMARY: Tất cả test cases")
print("=" * 100)
print(f"{'Input 1':<25} {'Input 2':<15} {'Score':<10} {'Status':<10} Description")
print("─" * 100)

for s1, s2, score, desc in scores:
    status = "✅ PASS" if score >= 0.90 else "❌ FAIL"
    print(f"{s1:<25} {s2:<15} {score:.3f}      {status:<10} {desc}")

# Root cause analysis
print("\n\n")
print("=" * 100)
print("🔍 ROOT CAUSE ANALYSIS")
print("=" * 100)

print("""
VẤN ĐỀ CHÍNH: Current ensemble algorithm DỰA VÀO TOKENS

1. TOKEN SORT RATIO (50% weight) - VẤN ĐỀ LỚN NHẤT:
   • "p leiku" → tokens: ["p", "leiku"]
   • "pleiku"  → tokens: ["pleiku"]
   • Token overlap = 0 (KHÔNG có token chung!)
   • Score thấp vì so sánh "leiku p" vs "pleiku"

2. LEVENSHTEIN (30% weight) - OK nhưng bị ảnh hưởng bởi SPACE:
   • "p leiku" (7 chars) vs "pleiku" (6 chars)
   • Edit distance = 2 (xóa "p " - 1 space + 1 char)
   • Score: 1 - 2/7 = 0.714
   • ✅ Nếu BỎ spaces: "pleiku" vs "pleiku" → 1.000

3. JACCARD (20% weight) - FAIL hoàn toàn:
   • Set overlap = 0 (no common tokens)
   • Score = 0.0
   • Không đóng góp gì vào ensemble score

➡️  ENSEMBLE = 0.5 × (token_sort) + 0.3 × (lev) + 0.2 × (0.0)
   ≈ 0.5 × 0.70 + 0.3 × 0.71 + 0.0
   ≈ 0.35 + 0.21 + 0.0
   ≈ 0.56 - 0.70 (tùy implementation chi tiết)

VÌ SAO THẤP?
• Token-based metrics (70% weight) FAIL với spacing issues
• "p" và "leiku" được coi là 2 tokens riêng biệt
• So sánh với "pleiku" (1 token) → overlap = 0

CHỈ CÓ Levenshtein (30% weight) làm việc được, nhưng:
• Vẫn bị penalty vì thêm 1 space
• Không đủ weight để đưa score lên >0.90
""")

print("\n" + "=" * 100)
print("💡 GIẢI PHÁP ĐỀ XUẤT")
print("=" * 100)
print("""
OPTION 1: Thêm CHARACTER-LEVEL matching (Không dùng tokens)
   • Thêm metric: compare strings SAU KHI bỏ spaces
   • "p leiku" → "pleiku", "pleiku" → "pleiku" → 100% match!
   • Weight: 30% (giảm token_sort xuống 40%)

OPTION 2: Thêm PARTIAL_RATIO / TOKEN_SET_RATIO
   • fuzz.partial_ratio() - substring matching
   • fuzz.token_set_ratio() - handles extra tokens better
   • Có thể cho score cao hơn cho "p leiku" vs "pleiku"

OPTION 3: Pre-processing: Bỏ single-character tokens
   • "p leiku" → strip "p" → "leiku" vs "pleiku"
   • Tăng token overlap
   • Risk: mất info từ single-char tokens hợp lệ

OPTION 4: Adaptive weights dựa trên token count
   • Nếu 1 string có 1 token, 1 string có nhiều tokens
   • Tăng weight cho Levenshtein, giảm weight cho Jaccard
   • Intelligent scoring based on input characteristics
""")

print("\n" + "=" * 100)
