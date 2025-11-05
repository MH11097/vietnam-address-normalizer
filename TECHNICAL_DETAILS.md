# Technical Details: Letter-Number Spacing Normalization

## Current Text Processing Pipeline

### Phase 1: Preprocessing (`phase1_preprocessing.py`)
```
Raw Input: "co nhue1" or similar
    ↓
1. Unicode Normalization (NFC)
    → No change for ASCII-compatible input
    ↓
2. Abbreviation Expansion
    → Expands "P.", "Q.", "TP." to full words
    → "co nhue1" → "co nhue1" (no change)
    ↓
3. Accent Removal
    → Removes Vietnamese diacritics
    → "co nhue1" → "co nhue1" (already ASCII)
    ↓
4. Finalize Normalization ← MISSING STEP IS HERE
    → Removes special chars: [^\w\s]
    → Lowercases: "CO NHUE1" → "co nhue1"
    → Collapses whitespace: "a  b" → "a b"
    → [MISSING] Normalize letter-number spacing: "nhue1" → "nhue 1"
    ↓
Output: "co nhue1" (PROBLEM: missing space!)
```

### Phase 4: Fuzzy Matching (`matching_utils.py`)
```
String 1: "co nhue1"
String 2: "co nhue 1"
    ↓
ensemble_fuzzy_score(s1, s2)
    ↓
Token Sort Ratio:
  Tokens s1: ["co", "nhue1"]
  Tokens s2: ["co", "nhue", "1"]
  → 0.8235 (penalized for different token structure)
    ↓
Levenshtein Normalized:
  Edit distance: 1 (insert space)
  1 - (1/9) = 0.8889
    ↓
Ensemble: (0.8235 × 0.65) + (0.8889 × 0.35) = 0.8464
    ↓
Compare to threshold 0.88
Result: 0.8464 < 0.88 → FAIL
```

## Proposed Fix: Implementation Details

### Location in Code
File: `/src/utils/text_utils.py`
Function: `finalize_normalization()`
Lines: ~232-270

### Current Function Structure
```python
def finalize_normalization(text: str, keep_separators: bool = False) -> str:
    """
    Final normalization step: remove special chars, lowercase, and normalize whitespace.
    """
    if not text or not isinstance(text, str):
        return ""

    result = text

    # Remove special characters
    if keep_separators:
        result = re.sub(r'[,\-_]', ' ', result)      # Replace separators
        result = re.sub(r'[^\w\s]', ' ', result)     # Remove other special chars
    else:
        result = remove_special_chars(result, keep_spaces=True)

    # Lowercase and normalize whitespace
    result = result.lower().strip()
    result = WHITESPACE_PATTERN.sub(' ', result)

    return result
```

### Proposed Modification
```python
def finalize_normalization(text: str, keep_separators: bool = False) -> str:
    """
    Final normalization step: remove special chars, lowercase, and normalize whitespace.
    """
    if not text or not isinstance(text, str):
        return ""

    result = text

    # Remove special characters
    if keep_separators:
        result = re.sub(r'[,\-_]', ' ', result)      # Replace separators
        result = re.sub(r'[^\w\s]', ' ', result)     # Remove other special chars
    else:
        result = remove_special_chars(result, keep_spaces=True)

    # Lowercase and normalize whitespace
    result = result.lower().strip()
    result = WHITESPACE_PATTERN.sub(' ', result)

    # NEW: Normalize spaces between letters and numbers (Vietnamese ward patterns)
    # Handles cases like "nhue1" → "nhue 1", "12ba" → "12 ba"
    result = re.sub(r'([a-z])(\d)', r'\1 \2', result)  # letter+digit
    result = re.sub(r'(\d)([a-z])', r'\1 \2', result)  # digit+letter

    return result
```

## Regex Pattern Explanation

### Pattern 1: `r'([a-z])(\d)'` → `r'\1 \2'`
```
Description: Add space between lowercase letter and digit
Examples:
  nhue1    → nhue 1
  phuong3  → phuong 3
  xa2      → xa 2
  co1      → co 1

Pattern breakdown:
  ([a-z])  - Capture group 1: single lowercase letter a-z
  (\d)     - Capture group 2: single digit 0-9
  \1 \2    - Replace with: capture1 + space + capture2
```

### Pattern 2: `r'(\d)([a-z])'` → `r'\1 \2'`
```
Description: Add space between digit and lowercase letter
Examples:
  12ba     → 12 ba
  123abc   → 123 abc
  1p       → 1 p
  2q       → 2 q

Pattern breakdown:
  (\d)     - Capture group 1: one or more digits 0-9
  ([a-z])  - Capture group 2: single lowercase letter
  \1 \2    - Replace with: capture1 + space + capture2
```

## Why These Patterns Work

### Vietnamese Address Context
Vietnamese addresses use specific patterns:
1. Ward numbers follow text: "Phuong 3", "Xa 5", "Tho 1"
2. Street numbers with letters: "92a Nguyen Hue", "123b Le Loi"
3. Combined patterns: "District 1", "Ward 5A"

### Pattern Characteristics
- **Case-sensitive:** Only handles lowercase (acceptable after normalization)
- **Minimal overlap:** Each pattern handles one direction (letter→digit or digit→letter)
- **Non-destructive:** Only adds spaces, doesn't remove characters
- **Idempotent:** Running twice gives same result as running once

### Example Flow
```
Input:    "co nhue1"
Step 1:   Pattern 1 matches "e1" → replace with "e 1"
Result:   "co nhue 1"
Step 2:   Pattern 2 finds no matches (no digit directly followed by letter)
Output:   "co nhue 1" ✓

Input:    "12ba hung vuong"
Step 1:   Pattern 1 finds no matches (digits don't directly follow letters)
Result:   "12ba hung vuong"
Step 2:   Pattern 2 matches "2b" → replace with "2 b"
Output:   "12 ba hung vuong" ✓
```

## Edge Cases Analyzed

### Case 1: Multiple Letter-Digit Patterns
```
Input:    "a1b2c3"
Expected: "a 1 b 2 c 3"
Step 1:   "a 1b2c3" (matches "a1")
Step 2:   "a 1 b 2 c 3" (matches "1b" and "2c")
Result:   ✓ Works correctly

Likelihood in Vietnamese addresses: Very low (rare street numbering)
```

### Case 2: Already Spaced Input
```
Input:    "co nhue 1"
Step 1:   No matches (space between "e" and "1")
Step 2:   No matches
Output:   "co nhue 1" ✓ (unchanged, idempotent)
```

### Case 3: Uppercase Letters (before lowercasing)
```
Input to finalize: "CO NHUE1" (already lowercased to "co nhue1")
Step 1:   Pattern uses [a-z], so no uppercase matches
Step 2:   Pattern added before lowercase in original flow, so works correctly
Output:   "co nhue 1" ✓
```

### Case 4: Only Numbers
```
Input:    "123 45"
Step 1:   No matches (digits don't match [a-z])
Step 2:   No matches (digits don't match [a-z])
Output:   "123 45" ✓ (unchanged)
```

### Case 5: Only Letters
```
Input:    "abc def"
Step 1:   No matches (no digits)
Step 2:   No matches (no digits)
Output:   "abc def" ✓ (unchanged)
```

## Performance Impact Analysis

### Regex Compilation
- Patterns are compiled once per execution
- Can be pre-compiled for better performance:
```python
LETTER_DIGIT_PATTERN = re.compile(r'([a-z])(\d)')
DIGIT_LETTER_PATTERN = re.compile(r'(\d)([a-z])')
```

### Execution Time
- 2 regex substitutions on ~50-100 character string: < 1 microsecond
- Memory overhead: Negligible (2 temporary strings max)
- Cache impact: Minimal (strings are transient)

### Frequency
- Called once per address during normalization
- Not called in matching loop (normalization happens once upfront)
- Total impact: Negligible for typical batch processing

## Integration Points

### Before Modification
```python
# text_utils.py
1. remove_vietnamese_accents()
2. remove_special_chars()
3. finalize_normalization()   ← Currently ends here
4. normalize_address()        ← Wrapper function
```

### After Modification
```python
# text_utils.py
1. remove_vietnamese_accents()
2. remove_special_chars()
3. finalize_normalization()   ← Now includes letter-number spacing
4. normalize_address()        ← Wrapper function
```

## Testing Strategy

### Unit Tests Needed
```python
def test_normalize_spacing_letter_to_digit():
    assert finalize_normalization("nhue1") == "nhue 1"
    assert finalize_normalization("phuong3") == "phuong 3"
    assert finalize_normalization("xa2") == "xa 2"

def test_normalize_spacing_digit_to_letter():
    assert finalize_normalization("12ba") == "12 ba"
    assert finalize_normalization("123abc") == "123 abc"

def test_normalize_spacing_idempotent():
    result1 = finalize_normalization("nhue1")
    result2 = finalize_normalization(result1)
    assert result1 == result2

def test_normalize_spacing_already_spaced():
    assert finalize_normalization("nhue 1") == "nhue 1"
    assert finalize_normalization("12 ba") == "12 ba"

def test_fuzzy_matching_with_spacing():
    score = ensemble_fuzzy_score("co nhue1", "co nhue 1")
    assert score >= 0.88  # Should pass threshold
```

### Regression Tests
- Run `test_matching_improvements.py` to verify no score regressions
- Test with sample Vietnamese addresses from database
- Verify all existing tests still pass

## Rollback Plan

If issues arise:
1. Remove 2 lines from `finalize_normalization()`
2. Revert to previous version
3. No database changes needed
4. No configuration changes needed
5. Immediate rollback possible (takes < 1 minute)

## Configuration Changes

**NO configuration changes needed:**
- Threshold stays at 0.88
- Weights stay at token_sort=0.65, levenshtein=0.35
- No database migration required
- No cache clearing required

## Validation Criteria

The fix is successful if:
1. ✓ "co nhue1" vs "co nhue 1" scores 1.0 (currently 0.8464)
2. ✓ "tho1" vs "tho 1" scores 1.0 (currently 0.7133)
3. ✓ "xa2" vs "xa 2" scores 1.0 (currently 0.6339)
4. ✓ All existing tests still pass
5. ✓ No performance degradation (negligible impact expected)
6. ✓ No false positives introduced (patterns are safe)

---

See `SOLUTION_SUMMARY.md` for quick overview and implementation checklist.
