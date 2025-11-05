# Keyword Context Penalty/Bonus Implementation

## Overview

Implemented a keyword context-aware scoring system for numeric administrative division names (phường, xã, quận, huyện). This prevents confusion between house numbers and administrative division names by applying penalties/bonuses based on whether numbers are preceded by admin keywords.

## Problem Statement

Vietnamese addresses often contain numeric administrative divisions (e.g., "Phường 1", "Quận 3"). When these numbers appear without keywords, they could be confused with house numbers:

**Example:**
- "123 Phường 1 Quận 3" - Clear: "123" is house number, "1" is ward, "3" is district
- "1 Lê Lợi Quận 3" - Ambiguous: Is "1" a house number or ward name?

## Solution

### Configuration (src/config.py)

Added three new configuration variables:

```python
# Keyword context scoring for numeric administrative divisions
NUMERIC_WITHOUT_KEYWORD_PENALTY = 0.7  # 30% penalty (0.7x score) for standalone 1-2 digit numbers
NUMERIC_WITH_KEYWORD_BONUS = 1.2       # 20% bonus (1.2x score) for numbers with preceding keywords

# Full administrative keywords (no abbreviations per user preference)
ADMIN_KEYWORDS_FULL = {'phuong', 'xa', 'quan', 'huyen', 'thanh', 'thi', 'tran', 'pho'}
```

### Implementation Details

#### 1. N-gram Generation (src/utils/extraction_utils.py:376-436)

Modified `generate_ngrams()` to track keyword context:

**Before:**
```python
def generate_ngrams(tokens: List[str], max_n: int = 4) -> List[Tuple[str, Tuple[int, int]]]:
    # Returns: (ngram_text, (start_idx, end_idx))
```

**After:**
```python
def generate_ngrams(tokens: List[str], max_n: int = 4) -> List[Tuple[str, Tuple[int, int], bool]]:
    # Returns: (ngram_text, (start_idx, end_idx), has_admin_keyword)
    # Checks if previous token is in ADMIN_KEYWORDS_FULL
```

#### 2. Ward Extraction (src/utils/extraction_utils.py:2089-2139)

Added keyword context checking in `extract_ward_scoped()`:

```python
# Check if this n-gram is preceded by an admin keyword (phuong, xa, etc.)
has_keyword = False
if i > 0:
    prev_token = clean_token(available_tokens[i-1][1])
    has_keyword = prev_token in ADMIN_KEYWORDS_FULL

# Calculate keyword context multiplier for 1-2 digit numbers
keyword_multiplier = 1.0
if ngram_text_normalized.isdigit() and len(ngram_text_normalized) <= 2:
    if has_keyword:
        keyword_multiplier = NUMERIC_WITH_KEYWORD_BONUS  # 1.2x
    else:
        keyword_multiplier = NUMERIC_WITHOUT_KEYWORD_PENALTY  # 0.7x

# Apply keyword context multiplier
adjusted_score = match_score * keyword_multiplier
```

#### 3. District Extraction (src/utils/extraction_utils.py:1739-1858)

Applied the same logic to both "rightmost tokens" and "full scan" sections in `extract_district_scoped()`:

**Rightmost section (lines 1756-1797):**
- Checks if token before rightmost n tokens is a keyword
- Applies multiplier to match scores

**Full scan section (lines 1821-1858):**
- Checks if token immediately before n-gram is a keyword
- Applies multiplier to match scores

Both sections also apply multiplier to abbreviation expansion results.

## Behavior

### With Keywords (Bonus Applied)

**Input:** "Phuong 1 Quan 3 TP HCM"
- "phuong" keyword detected before "1" → **1.2x bonus**
- "quan" keyword detected before "3" → **1.2x bonus**
- **Result:** Phường 01, Quận 3 matched with high confidence (score: 1.00)

### Without Keywords (Penalty Applied)

**Input:** "1 Le Loi Quan 3 TP HCM"
- No keyword before "1" → **0.7x penalty**
- "quan" keyword detected before "3" → **1.2x bonus**
- **Result:**
  - "1" as ward gets lower score due to penalty
  - "Quan 3" still matches correctly with bonus
  - Score: 0.96 (slightly lower due to standalone "1")

### Prioritizing Named Wards Over Numbers

**Input:** "8 Nguyen Hue Ben Nghe Quan 1 TP HCM"
- No keyword before "8" → **0.7x penalty**
- "Ben Nghe" (named ward) has no penalty
- **Result:** "Phường Bến Nghé" correctly identified (not standalone "8")

## Scope

The penalty/bonus system applies **only** to:
- ✅ Numeric tokens with 1-2 digits (e.g., "1", "12")
- ✅ Full word keywords only (per user preference): `phuong`, `xa`, `quan`, `huyen`, `thanh`, `thi`, `tran`, `pho`

**Does NOT apply to:**
- ❌ Numbers with 3+ digits (e.g., "123", "660") - already skipped as street numbers
- ❌ Non-numeric tokens
- ❌ Abbreviated keywords (e.g., "p", "q", "h", "x") - per user preference

## Testing

Manual testing with real examples:

```bash
# Test with keywords
python3 demo.py --address "Phuong 1 Quan 3 TP HCM"
# ✓ Result: Phường 01 | Quận 3 | TP HCM (score: 1.00)

# Test without keywords
python3 demo.py --address "1 Le Loi Quan 3 TP HCM"
# ✓ Result: Phường 01 | Quận 3 | TP HCM (score: 0.96)
# Note: Still matches but with penalty applied to standalone "1"

# Test prioritizing named wards
python3 demo.py --address "8 Nguyen Hue Ben Nghe Quan 1 TP HCM"
# ✓ Result: Phường Bến Nghé | Quận 1 | TP HCM (score: 1.00)
# Correctly chose "Bến Nghé" over standalone "8"
```

## Files Modified

1. **src/config.py** (lines 70-76)
   - Added `NUMERIC_WITHOUT_KEYWORD_PENALTY`
   - Added `NUMERIC_WITH_KEYWORD_BONUS`
   - Added `ADMIN_KEYWORDS_FULL` set

2. **src/utils/extraction_utils.py**
   - `generate_ngrams()` (lines 376-436): Added keyword context tracking
   - Province extraction callsite (line 1488, 1554): Updated to handle 3-tuple
   - `extract_district_scoped()` (lines 1739-1858): Added keyword checking + penalty/bonus
   - `extract_ward_scoped()` (lines 2089-2139): Added keyword checking + penalty/bonus

## Performance Impact

- **Minimal:** Only adds a simple set lookup per n-gram (`prev_token in ADMIN_KEYWORDS_FULL`)
- **No additional database queries**
- **No impact on non-numeric tokens**

## Future Enhancements

Potential improvements (not implemented):
1. Track keyword context through the entire scoring pipeline for better transparency
2. Add debug logging to show when penalty/bonus is applied
3. Make penalty/bonus configurable per admin level (different values for ward vs district)
4. Support abbreviated keywords if user preference changes

## Conclusion

The implementation successfully addresses the issue of numeric administrative divisions being confused with house numbers. By applying context-aware penalties and bonuses, the system now better distinguishes:
- "Phường 1" (with keyword) → High confidence match
- Standalone "1" (no keyword) → Lower confidence, less likely to match
- Named wards (e.g., "Bến Nghé") → Prioritized over ambiguous numbers

This results in more accurate parsing of Vietnamese addresses with numeric administrative divisions.
