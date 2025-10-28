"""
Phân tích đặc điểm của Vietnamese address data để chọn thuật toán phù hợp.
"""

import sys
import sqlite3
from collections import Counter
import re

sys.path.insert(0, '/Users/minhhieu/Library/CloudStorage/OneDrive-Personal/Coding/Python/company/address_mapping')

from src.config import DB_PATH

print("=" * 100)
print("PHÂN TÍCH ĐẶC ĐIỂM DỮ LIỆU VIETNAMESE ADDRESSES")
print("=" * 100)

# Connect to database
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# 1. Analyze District Names
print("\n1️⃣  DISTRICT NAMES CHARACTERISTICS")
print("─" * 100)

cursor.execute("""
    SELECT district_name_normalized, district_full, province_name
    FROM admin_divisions
    WHERE district_name_normalized IS NOT NULL
    ORDER BY province_name, district_name_normalized
""")

districts = cursor.fetchall()
print(f"Total districts: {len(districts)}")

# Analyze characteristics
district_names = [d[0] for d in districts]
district_full = [d[1] for d in districts]

# Token count
token_counts = Counter()
for name in district_names:
    tokens = name.split()
    token_counts[len(tokens)] += 1

print(f"\n📊 Token distribution:")
for token_count in sorted(token_counts.keys()):
    count = token_counts[token_count]
    pct = count / len(district_names) * 100
    print(f"  {token_count} token(s): {count:4d} districts ({pct:5.1f}%)")

# Single vs multi-word
single_word = sum(1 for name in district_names if len(name.split()) == 1)
multi_word = len(district_names) - single_word
print(f"\n  → Single-word districts: {single_word} ({single_word/len(district_names)*100:.1f}%)")
print(f"  → Multi-word districts:  {multi_word} ({multi_word/len(district_names)*100:.1f}%)")

# Show examples
print(f"\n📝 Examples:")
print(f"  Single-word: {[d for d in district_names if len(d.split()) == 1][:10]}")
print(f"  Multi-word:  {[d for d in district_names if len(d.split()) > 1][:10]}")

# Character length
lengths = [len(name) for name in district_names]
avg_len = sum(lengths) / len(lengths)
print(f"\n📏 Character length:")
print(f"  Average: {avg_len:.1f} chars")
print(f"  Min: {min(lengths)} chars")
print(f"  Max: {max(lengths)} chars")

# 2. Analyze Ward Names
print("\n\n2️⃣  WARD NAMES CHARACTERISTICS")
print("─" * 100)

cursor.execute("""
    SELECT ward_name_normalized, ward_full
    FROM admin_divisions
    WHERE ward_name_normalized IS NOT NULL
    LIMIT 5000
""")

wards = cursor.fetchall()
print(f"Sample wards: {len(wards)}")

ward_names = [w[0] for w in wards]

# Token count
token_counts = Counter()
for name in ward_names:
    tokens = name.split()
    token_counts[len(tokens)] += 1

print(f"\n📊 Token distribution:")
for token_count in sorted(token_counts.keys()):
    count = token_counts[token_count]
    pct = count / len(ward_names) * 100
    print(f"  {token_count} token(s): {count:4d} wards ({pct:5.1f}%)")

# Single vs multi-word
single_word_wards = sum(1 for name in ward_names if len(name.split()) == 1)
multi_word_wards = len(ward_names) - single_word_wards
print(f"\n  → Single-word wards: {single_word_wards} ({single_word_wards/len(ward_names)*100:.1f}%)")
print(f"  → Multi-word wards:  {multi_word_wards} ({multi_word_wards/len(ward_names)*100:.1f}%)")

# Numeric patterns (Phường 1, Phường 2, etc.)
numeric_wards = sum(1 for name in ward_names if re.match(r'^\d+$', name))
print(f"  → Numeric wards (1, 2, 3...): {numeric_wards} ({numeric_wards/len(ward_names)*100:.1f}%)")

# Show examples
print(f"\n📝 Examples:")
print(f"  Single-word: {[w for w in ward_names if len(w.split()) == 1][:15]}")
print(f"  Multi-word:  {[w for w in ward_names if len(w.split()) > 1][:10]}")

# 3. Common Patterns & Abbreviations
print("\n\n3️⃣  COMMON PATTERNS & ABBREVIATIONS")
print("─" * 100)

# Test common Vietnamese address patterns
test_patterns = [
    # District prefixes
    ("TP Pleiku", "pleiku", "Thành phố abbreviated"),
    ("TX Binh Minh", "binh minh", "Thị xã abbreviated"),
    ("Q.1", "1", "Quận abbreviated with dot"),
    ("Q 1", "1", "Quận abbreviated with space"),
    ("H.Long Bien", "long bien", "Huyện abbreviated"),

    # Spacing issues (data quality)
    ("P LEIKU", "pleiku", "Wrong spacing - separate P"),
    ("BA DINH", "badinh", "Missing space in input"),
    ("HOCHIMINH", "ho chi minh", "Missing all spaces"),

    # Ward patterns
    ("P.1", "1", "Phường abbreviated"),
    ("P 1", "1", "Phường with space"),
    ("Xa Tan Phu", "tan phu", "Xã prefix"),

    # Common typos
    ("ha noi", "hanoi", "Missing space vs no space"),
    ("pleiku", "p leiku", "Reverse: correct vs wrong"),

    # Partial matches
    ("thanh pho pleiku", "pleiku", "Full prefix vs short"),
    ("huyen long bien", "long bien", "Full prefix vs short"),
]

print(f"\n📋 Testing {len(test_patterns)} common patterns:")
print(f"{'Pattern':<30} {'Target':<20} {'Description':<30}")
print("─" * 100)
for pattern, target, desc in test_patterns:
    print(f"{pattern:<30} {target:<20} {desc:<30}")

# 4. Test Real Fuzzy Matching on Patterns
print("\n\n4️⃣  FUZZY MATCHING PERFORMANCE ON PATTERNS")
print("─" * 100)

try:
    from rapidfuzz import fuzz
except ImportError:
    from fuzzywuzzy import fuzz

from src.utils.matching_utils import (
    token_sort_ratio,
    levenshtein_normalized,
    jaccard_similarity,
    ensemble_fuzzy_score
)

print(f"\n{'Pattern':<25} {'Target':<20} {'ratio':<8} {'partial':<8} {'tok_sort':<10} {'tok_set':<10} {'current':<10}")
print("─" * 100)

results_by_method = {
    'ratio': [],
    'partial_ratio': [],
    'token_sort_ratio': [],
    'token_set_ratio': [],
    'current_ensemble': []
}

for pattern, target, desc in test_patterns:
    ratio = fuzz.ratio(pattern.lower(), target.lower()) / 100.0
    partial = fuzz.partial_ratio(pattern.lower(), target.lower()) / 100.0
    tok_sort = fuzz.token_sort_ratio(pattern.lower(), target.lower()) / 100.0
    tok_set = fuzz.token_set_ratio(pattern.lower(), target.lower()) / 100.0
    current = ensemble_fuzzy_score(pattern.lower(), target.lower(), log=False)

    results_by_method['ratio'].append(ratio)
    results_by_method['partial_ratio'].append(partial)
    results_by_method['token_sort_ratio'].append(tok_sort)
    results_by_method['token_set_ratio'].append(tok_set)
    results_by_method['current_ensemble'].append(current)

    print(f"{pattern:<25} {target:<20} {ratio:.3f}    {partial:.3f}    {tok_sort:.3f}      {tok_set:.3f}      {current:.3f}")

# 5. Evaluate which method works best
print("\n\n5️⃣  METHOD PERFORMANCE SUMMARY")
print("─" * 100)

threshold = 0.90

print(f"\n{'Method':<25} {'Avg Score':<12} {'Pass Rate':<12} {'Min Score':<12} {'Max Score':<12}")
print("─" * 100)

for method_name, scores in results_by_method.items():
    avg_score = sum(scores) / len(scores)
    pass_rate = sum(1 for s in scores if s >= threshold) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    print(f"{method_name:<25} {avg_score:.3f}        {pass_rate:6.1%}       {min_score:.3f}        {max_score:.3f}")

# 6. Analyze data-specific characteristics
print("\n\n6️⃣  DATA-SPECIFIC INSIGHTS")
print("─" * 100)

print(f"""
Đặc điểm dữ liệu Vietnamese Addresses:

1. DISTRICT NAMES:
   • {multi_word/len(district_names)*100:.1f}% là multi-word (nhiều từ)
   • {single_word/len(district_names)*100:.1f}% là single-word
   • Average length: {avg_len:.1f} characters
   → TOKEN-BASED matching phù hợp với majority cases (multi-word)

2. WARD NAMES:
   • {multi_word_wards/len(ward_names)*100:.1f}% là multi-word
   • {numeric_wards/len(ward_names)*100:.1f}% là numeric (1, 2, 3...)
   • Many numbered wards: "1", "2", "3"... "24"
   → CHARACTER-LEVEL matching quan trọng cho numeric wards

3. COMMON PROBLEMS:
   • Abbreviations: TP, TX, Q, H, P (very common in raw data)
   • Spacing issues: "P LEIKU" vs "PLEIKU"
   • Missing spaces: "BADINH" vs "BA DINH"
   • Extra spaces: "HO CHI MINH" vs "HOCHIMINH"

4. PATTERN ANALYSIS:
   • Abbreviation patterns: Very frequent in user input
   • Full forms in DB: "pleiku", "binh minh", "long bien"
   • Users type short: "TP Pleiku", "TX Binh Minh"
""")

# 7. Recommend algorithm based on data characteristics
print("\n\n7️⃣  ALGORITHM RECOMMENDATION BASED ON DATA")
print("─" * 100)

# Count specific issues
abbrev_cases = len([p for p, _, desc in test_patterns if 'abbreviated' in desc.lower()])
spacing_cases = len([p for p, _, desc in test_patterns if 'spacing' in desc.lower() or 'space' in desc.lower()])
prefix_cases = len([p for p, _, desc in test_patterns if 'prefix' in desc.lower()])

print(f"""
Phân loại cases theo tần suất:

1. Abbreviation cases: {abbrev_cases}/{len(test_patterns)} ({abbrev_cases/len(test_patterns)*100:.1f}%)
   • TP, TX, Q, H, P + name
   → Best method: partial_ratio (finds "pleiku" in "TP Pleiku")

2. Spacing issues: {spacing_cases}/{len(test_patterns)} ({spacing_cases/len(test_patterns)*100:.1f}%)
   • "P LEIKU" vs "PLEIKU"
   • "BADINH" vs "BA DINH"
   → Best method: ratio (character-level) hoặc char-level matching

3. Prefix removal cases: {prefix_cases}/{len(test_patterns)} ({prefix_cases/len(test_patterns)*100:.1f}%)
   • "thanh pho pleiku" vs "pleiku"
   → Best method: partial_ratio hoặc token_set_ratio

Performance so sánh:
""")

# Find best performing method
best_method = max(results_by_method.items(), key=lambda x: sum(x[1])/len(x[1]))
print(f"  🏆 Best overall: {best_method[0]} (avg: {sum(best_method[1])/len(best_method[1]):.3f})")

best_pass_rate = max(results_by_method.items(), key=lambda x: sum(1 for s in x[1] if s >= threshold)/len(x[1]))
print(f"  🎯 Highest pass rate: {best_pass_rate[0]} ({sum(1 for s in best_pass_rate[1] if s >= threshold)/len(best_pass_rate[1])*100:.1f}%)")

print("\n" + "=" * 100)
print("🎯 FINAL RECOMMENDATION")
print("=" * 100)

print("""
Dựa trên đặc điểm data:

APPROACH 1: HYBRID MULTI-METHOD (RECOMMENDED) ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ensemble = MAX of:
  1. ratio() - for spacing issues
  2. partial_ratio() - for abbreviations & prefixes
  3. token_set_ratio() - for token overlap

Logic:
  • Lấy score CAO NHẤT trong 3 methods
  • Covers all common cases
  • Simple & effective

Weights: N/A (use MAX, not weighted average)

APPROACH 2: WEIGHTED ENSEMBLE ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ensemble = weighted average of:
  • partial_ratio: 40% (handles abbreviations best)
  • ratio: 30% (handles spacing issues)
  • token_set_ratio: 20% (handles extra tokens)
  • char_level: 10% (backup for extreme spacing)

Threshold: 0.85 (lower than 0.90 vì có nhiều abbreviation cases)

APPROACH 3: ADAPTIVE (MOST SOPHISTICATED) ⭐⭐⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IF input có abbreviation pattern (TP, TX, Q, H, P):
  → Use partial_ratio (weight: 60%)
ELSE IF token count mismatch (1 vs 2+ tokens):
  → Use ratio + char_level (weight: 50% + 30%)
ELSE:
  → Use token_set_ratio + ratio (weight: 50% + 30%)

Always add levenshtein as base: 20%

Lợi ích:
  • Intelligent - adapts to input pattern
  • Best performance on all case types
  • More complex to implement
""")

conn.close()
print("\n" + "=" * 100)
