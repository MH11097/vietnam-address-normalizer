# Analysis Report: "co nhue1" vs "co nhue 1" Scoring Issue

## Executive Summary
The strings "co nhue1" and "co nhue 1" score **0.8464 (below threshold 0.88)** because of a missing space between the letter 'e' and the number '1'. This is a common Vietnamese address pattern where ward numbers follow text without proper spacing. The current normalization pipeline does not add spaces between letters and numbers, causing the score to fall short by **0.0336 points (3.36%)**.

---

## 1. Current Normalization Logic

### Text Processing Pipeline (Phase 1)
Location: `/src/processors/phase1_preprocessing.py` and `/src/utils/text_utils.py`

**Four-step normalization pipeline:**

1. **Unicode Normalization (NFC)**
   - Standardizes unicode representation
   - No structural changes

2. **Abbreviation Expansion**
   - Expands "P.", "Q.", "TP." to "phuong", "quan", "thanh pho"
   - Uses database context (province/district-aware)
   - Does NOT add spaces between letters and numbers

3. **Accent Removal**
   - Removes Vietnamese diacritical marks (á, ă, â, ộ, etc.)
   - No impact on spacing

4. **Finalize Normalization** (`finalize_normalization()`)
   ```python
   # Current implementation in text_utils.py (lines 232-270):
   - Remove special characters (except spaces)
   - Lowercase text
   - Collapse multiple spaces to single space
   - NO step to add spaces between letters/numbers
   ```

### Current finalize_normalization() Function
```python
def finalize_normalization(text: str, keep_separators: bool = False) -> str:
    # Removes special characters but doesn't normalize letter-number spacing
    result = re.sub(r'[,\-_]', ' ', result)      # Replace separators with spaces
    result = re.sub(r'[^\w\s]', ' ', result)     # Remove special chars
    result = result.lower().strip()
    result = WHITESPACE_PATTERN.sub(' ', result)  # Normalize whitespace
    return result
```

**Key finding:** The pipeline does NOT normalize spaces between letters and numbers.

---

## 2. Why the Score is 0.8464

### Calculation Breakdown

**Input strings:**
- String 1: `"co nhue1"` (length: 8)
- String 2: `"co nhue 1"` (length: 9)

**Character-by-character comparison:**
```
Position:  0 1 2 3 4 5 6 7 (8)
String 1:  c o   n h u e 1
String 2:  c o   n h u e   1
```

**Individual scores (current weights):**

| Metric | Score | Weight | Contribution |
|--------|-------|--------|---------------|
| Token Sort Ratio | 0.8235 | 65% | 0.5353 |
| Levenshtein Normalized | 0.8889 | 35% | 0.3111 |
| **Ensemble Score** | - | - | **0.8464** |

**Score formula:**
```
Ensemble = (Token_Sort × 0.65) + (Levenshtein × 0.35)
Ensemble = (0.8235 × 0.65) + (0.8889 × 0.35)
Ensemble = 0.5353 + 0.3111
Ensemble = 0.8464
```

**Threshold:** 0.88 (88%)
**Result:** 0.8464 < 0.88 → **FAIL**
**Gap:** -0.0336 points (3.36% below threshold)

### Why Scores Are Lower

1. **Token Sort Ratio = 0.8235**
   - Tokenizes: `["co", "nhue1"]` vs `["co", "nhue", "1"]`
   - Doesn't recognize "nhue1" and "nhue 1" as related
   - Different token structure penalizes score

2. **Levenshtein Normalized = 0.8889**
   - Edit distance between strings: 1 (insert space)
   - Formula: 1 - (edit_distance / max_length) = 1 - (1/9) = 0.8889
   - Better than token sort, but still below acceptable threshold

---

## 3. Similar Cases Affected (Vietnamese Ward/District Numbers)

### Cases Below Threshold (ALL FAIL)
```
'tho1'      vs 'tho 1'         → 0.7133 [FAIL]  ← Extreme issue
'xa2'       vs 'xa 2'          → 0.6339 [FAIL]  ← Extreme issue
'phuong3'   vs 'phuong 3'      → 0.8262 [FAIL]
'co nhue1'  vs 'co nhue 1'     → 0.8464 [FAIL]
'12ba'      vs '12 ba'         → 0.8578 [FAIL]
```

### Cases That Pass (Longer strings)
```
'92a nguyen hue' vs '92 a nguyen hue' → 0.9543 [PASS]
```

**Pattern observed:** Longer strings pass because proportional differences are smaller. Short ward names fail.

---

## 4. Impact of Adding Space Normalization

### Proposed Function
```python
def normalize_spaces_between_letters_and_numbers(text: str) -> str:
    """
    Add spaces between letters and numbers when missing.
    Examples:
      - "co nhue1" → "co nhue 1"
      - "phuong3" → "phuong 3"
      - "12ba" → "12 ba"
    """
    # Add space between letter and digit
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    # Add space between digit and letter  
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
    return text
```

### Results After Normalization
```
'tho1'      vs 'tho 1'         → 1.0000 [PASS] ✓ (+0.2867)
'xa2'       vs 'xa 2'          → 1.0000 [PASS] ✓ (+0.3661)
'phuong3'   vs 'phuong 3'      → 1.0000 [PASS] ✓ (+0.1738)
'co nhue1'  vs 'co nhue 1'     → 1.0000 [PASS] ✓ (+0.1536)
'12ba'      vs '12 ba'         → 1.0000 [PASS] ✓ (+0.1422)
'92a nguyen hue' vs '92 a...'  → 1.0000 [PASS] ✓ (already passing)
```

**Key impact for "co nhue1" vs "co nhue 1":**
- Before: 0.8464 (FAIL)
- After: 1.0000 (PASS)
- **Improvement: +0.1536 (+18.1%)**

---

## 5. Implementation Options

### Option 1: Add to finalize_normalization() [RECOMMENDED]
**Pros:**
- Happens late in pipeline (after abbreviation expansion)
- Applied universally to all addresses
- Minimal code change (2 regex lines)
- Fixes the root cause
- Preserves intent of abbreviations

**Cons:**
- May change tokenization in edge cases
- Slightly increased processing time

**Implementation:**
```python
def finalize_normalization(text: str, keep_separators: bool = False) -> str:
    if not text or not isinstance(text, str):
        return ""
    
    result = text
    
    # NEW: Normalize spaces between letters and numbers
    result = re.sub(r'([a-z])(\d)', r'\1 \2', result)  # "nhue1" → "nhue 1"
    result = re.sub(r'(\d)([a-z])', r'\1 \2', result)  # "12ba" → "12 ba"
    
    # ... rest of finalize_normalization ...
```

### Option 2: Add to normalize_address() [ALTERNATIVE]
**Pros:**
- Happens during main normalization pipeline
- Clear semantic meaning

**Cons:**
- Happens before accent removal (redundant work)
- After abbreviation expansion (may miss some cases)

### Option 3: Add to ensemble_fuzzy_score() [NOT RECOMMENDED]
**Pros:**
- Normalizes only when matching

**Cons:**
- Happens at matching time (too late)
- Breaks consistency with database records
- Each match recalculates (performance issue)

### Option 4: Pre-normalize all database records [NOT RECOMMENDED]
**Pros:**
- Consistent source of truth

**Cons:**
- Requires database migration
- Affects all downstream queries
- High risk change

---

## 6. Risk Analysis

### Potential Issues with Letter-Number Spacing Normalization

1. **Vietnamese Addresses**
   ```
   "92a Nguyen Hue" (street) → "92 a Nguyen Hue"
   "lot 5" → "lot 5" (already has space)
   "P5" (Province 5) → "P 5" (may be abbreviation)
   ```
   - Generally harmless; Vietnamese addresses commonly have spaces

2. **Abbreviations Without Expansion**
   ```
   "P5" (phuong 5) → "P 5"
   "Q1" (quan 1) → "Q 1"
   ```
   - Safe because abbreviation expansion happens first
   - If P/Q not expanded, adding space still makes sense

3. **Edge Cases to Test**
   ```
   "3a1" → "3 a 1"   (triple pattern - rare)
   "p123" → "p 123"  (long number - uncommon in Vietnamese addresses)
   "a1b2" → "a 1 b 2" (alternating pattern - very rare)
   ```
   - Unlikely in Vietnamese context
   - Can test with actual database samples

---

## 7. Recommended Solution

### Primary Recommendation: **Option 1 - Add to finalize_normalization()**

**Rationale:**
1. Fixes root cause (missing spaces)
2. Minimal code change (2 regex lines)
3. Applied consistently before matching
4. No database changes needed
5. Handles the specific Vietnamese ward number pattern
6. Can be implemented in 5 minutes

**Implementation steps:**
1. Add two regex patterns to `finalize_normalization()` function
2. Add unit tests for letter-number spacing
3. Verify no regressions on existing test cases
4. Test with "co nhue1" vs "co nhue 1" (should score 1.0)

**Files to modify:**
- `/src/utils/text_utils.py` - Line ~268 (add before whitespace normalization)

**Testing strategy:**
- Unit test the new function behavior
- Run existing fuzzy matching tests
- Test with sample Vietnamese addresses from database
- Verify performance impact (negligible)

---

## 8. Alternative: Weight Adjustment (NOT RECOMMENDED)

Could lower threshold from 0.88 to 0.84, but this would:
- Accept more false positives
- Defeat the purpose of a threshold
- Only works for this specific case
- Affects all other matching types

Current score of 0.8464 is legitimate feedback that spacing is missing.

---

## 9. Summary Table

| Aspect | Current State | Proposed Fix |
|--------|---------------|--------------|
| **Score (co nhue1 vs co nhue 1)** | 0.8464 | 1.0000 |
| **Status** | FAIL | PASS |
| **Gap to Threshold** | -0.0336 | +0.12 |
| **Similar Cases Affected** | 4-5 patterns | All fixed |
| **Implementation Complexity** | N/A | Low (2 regex) |
| **Risk Level** | N/A | Very Low |
| **Performance Impact** | N/A | Negligible |
| **Database Changes** | N/A | None |

---

## 10. Code Locations

**Current normalization flow:**
1. `finalize_normalization()` - Line 232-270 in `text_utils.py`
2. `normalize_address()` - Line 274-320 in `text_utils.py`
3. `ensemble_fuzzy_score()` - Line 188-246 in `matching_utils.py`

**Threshold configuration:**
- `config.py` - Line 20-26 (FUZZY_THRESHOLDS = 0.88)

**Weights configuration:**
- `config.py` - Line 72-76 (ENSEMBLE_WEIGHTS)

