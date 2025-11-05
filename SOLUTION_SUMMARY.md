# Quick Solution Summary: "co nhue1" vs "co nhue 1" Issue

## The Problem
```
Input:    "co nhue1" vs "co nhue 1"
Score:    0.8464 (FAIL - below 0.88 threshold)
Gap:      -0.0336 points (3.36% below threshold)
```

## Root Cause
No normalization step adds spaces between letters and numbers in Vietnamese addresses.

## Why Score is 0.8464

```
Token Sort Ratio:    0.8235 × 0.65 = 0.5353
Levenshtein:         0.8889 × 0.35 = 0.3111
                                     ------
Ensemble Score:                      0.8464  ← Below 0.88 threshold
```

## Affected Cases (5 patterns with short ward names)
```
tho1 vs tho 1           → 0.7133 [FAIL]
xa2 vs xa 2             → 0.6339 [FAIL]
phuong3 vs phuong 3     → 0.8262 [FAIL]
co nhue1 vs co nhue 1   → 0.8464 [FAIL]
12ba vs 12 ba           → 0.8578 [FAIL]
```

## The Fix (Recommended Option)

Add 2 lines to `finalize_normalization()` in `/src/utils/text_utils.py` (line ~268):

```python
# Normalize spaces between letters and numbers
text = re.sub(r'([a-z])(\d)', r'\1 \2', text)  # "nhue1" → "nhue 1"
text = re.sub(r'(\d)([a-z])', r'\1 \2', text)  # "12ba" → "12 ba"
```

## Results After Fix
```
tho1 vs tho 1           → 1.0000 [PASS] ✓
xa2 vs xa 2             → 1.0000 [PASS] ✓
phuong3 vs phuong 3     → 1.0000 [PASS] ✓
co nhue1 vs co nhue 1   → 1.0000 [PASS] ✓
12ba vs 12 ba           → 1.0000 [PASS] ✓
```

## Implementation Details

| Aspect | Details |
|--------|---------|
| **File** | `/src/utils/text_utils.py` |
| **Function** | `finalize_normalization()` |
| **Location** | Line 268 (before final whitespace normalization) |
| **Code Change** | 2 regex lines |
| **Complexity** | Low |
| **Risk** | Very Low |
| **Performance** | Negligible impact |
| **Database Changes** | None required |
| **Testing Needed** | Unit test + regression test |

## Why This Solution

1. ✓ Fixes the root cause
2. ✓ Minimal code change
3. ✓ Applied universally to all addresses
4. ✓ No database migration needed
5. ✓ Safe for Vietnamese context
6. ✓ Can be implemented in 5 minutes

## Why NOT Other Options

- **Lower threshold to 0.84:** Accepts more false positives
- **Adjust weights:** Only masks the problem
- **Normalize at match time:** Too late, breaks consistency
- **Pre-normalize database:** Requires risky migration

## Quick Implementation Checklist

- [ ] Add regex patterns to `finalize_normalization()`
- [ ] Test with "co nhue1" vs "co nhue 1" (expect 1.0)
- [ ] Run unit tests on text_utils.py
- [ ] Run fuzzy matching regression tests
- [ ] Test with sample Vietnamese addresses
- [ ] Check performance (should be negligible)
- [ ] Commit with message: "Add letter-number spacing normalization"

## Code Location in Current Pipeline

```
Phase 1: normalize_address()
  ├─ Unicode normalization
  ├─ Abbreviation expansion
  ├─ Accent removal
  └─ finalize_normalization() ← ADD FIX HERE
       └─ Special char removal
       └─ Lowercase
       └─ Whitespace normalization
```

## Files to Review
- `/src/utils/text_utils.py` (main fix location)
- `/src/config.py` (threshold = 0.88, no change needed)
- `/test_matching_improvements.py` (existing tests)

---

For detailed analysis, see: `ANALYSIS_COHUE_SPACING_ISSUE.md`
