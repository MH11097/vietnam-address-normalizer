"""
Iterative Preprocessing - Fix Abbreviation Expansion Logic

PROBLEM:
- Phase 1 expands abbreviations WITH province context
- Phase 2 extracts province AFTER expansion
- → Circular dependency: need province to expand, but get province after expansion

SOLUTION: Iterative approach
1. Phase 1a: Expand WITHOUT province context (basic expansion)
2. Phase 2: Extract province/district/ward
3. Phase 1b: Re-expand WITH province context (if province found)
4. Phase 2 again: Re-extract with better normalized text

This ensures abbreviations like "HBT" are correctly expanded based on discovered province.

Example:
    Input: "HBT, HN"

    Round 1:
    - Phase 1a: "HBT, HN" → "hbt, ha noi" (HN expanded, HBT not)
    - Phase 2: Extract province="ha noi"

    Round 2:
    - Phase 1b: "HBT, HN" → "hai ba trung, ha noi" (with province="ha noi" context)
    - Phase 2: Extract ward="hai ba trung", province="ha noi" ✓

Speedup: Only re-run if province_context changes (cached)
"""
from typing import Dict, Any, Optional
import time
from functools import lru_cache
from .text_utils import normalize_address, expand_abbreviations


def iterative_preprocess(
    raw_address: str,
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    max_iterations: int = 2
) -> Dict[str, Any]:
    """
    Iterative preprocessing with province context discovery.

    Strategy:
    1. First pass: Expand without province context
    2. Extract province from normalized text
    3. Second pass: Re-expand WITH province context (if province found)
    4. Return best result

    Args:
        raw_address: Raw input address
        province_known: Known province (if available)
        district_known: Known district (if available)
        max_iterations: Maximum iterations (default: 2)

    Returns:
        Dictionary with preprocessing results from best iteration

    Example:
        >>> iterative_preprocess("HBT, HN")
        {
            'normalized': 'hai ba trung ha noi',
            'province_context': 'ha noi',
            'iterations': 2,
            'improved': True,
            ...
        }
    """
    start_time = time.time()

    from .text_utils import normalize_hint

    # Normalize known values
    province_context = normalize_hint(province_known) if province_known else None
    district_context = normalize_hint(district_known) if district_known else None

    # Track results from each iteration
    iterations_data = []

    current_province = province_context
    current_district = district_context

    for iteration in range(1, max_iterations + 1):
        # === ITERATION N: Preprocess with current context ===
        iter_result = _preprocess_single_pass(
            raw_address,
            current_province,
            current_district
        )

        # Store iteration data
        iter_result['iteration'] = iteration
        iter_result['province_context'] = current_province
        iter_result['district_context'] = current_district
        iterations_data.append(iter_result)

        # === Try to extract province/district from this iteration ===
        # Quick extraction using simple regex (faster than full Phase 2)
        extracted = _quick_extract_context(iter_result['normalized'])

        # Check if we discovered new province/district
        new_province = extracted.get('province')
        new_district = extracted.get('district')

        # Update context for next iteration
        province_improved = False
        district_improved = False

        if new_province and new_province != current_province:
            current_province = new_province
            province_improved = True

        if new_district and new_district != current_district:
            current_district = new_district
            district_improved = True

        # Early stopping: If no improvement in context, stop
        if not province_improved and not district_improved:
            # No new information discovered, no need for another iteration
            break

        # If this is the last allowed iteration, stop
        if iteration >= max_iterations:
            break

    # === Select best result ===
    # Prefer later iterations (more context) if they improved
    best_result = iterations_data[-1]  # Last iteration is usually best

    # Add metadata
    best_result['total_iterations'] = len(iterations_data)
    best_result['improved'] = len(iterations_data) > 1  # True if we did multiple passes
    best_result['all_iterations'] = iterations_data
    best_result['processing_time_ms'] = round((time.time() - start_time) * 1000, 3)

    return best_result


def _preprocess_single_pass(
    raw_address: str,
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Single preprocessing pass with given context.

    Args:
        raw_address: Raw address string
        province_context: Province context for abbreviation expansion
        district_context: District context (for future use)

    Returns:
        Preprocessing result dict
    """
    from .text_utils import normalize_unicode, remove_vietnamese_accents

    # Unicode normalization
    unicode_normalized = normalize_unicode(raw_address)

    # Abbreviation expansion with context
    expanded = expand_abbreviations(unicode_normalized, province_context=province_context)

    # Accent removal
    no_accent = remove_vietnamese_accents(expanded)

    # Full normalization
    normalized = normalize_address(raw_address, province_context=province_context)

    return {
        'original': raw_address,
        'unicode_normalized': unicode_normalized,
        'expanded': expanded,
        'no_accent': no_accent,
        'normalized': normalized
    }


@lru_cache(maxsize=5000)
def _quick_extract_context(normalized_text: str) -> Dict[str, Optional[str]]:
    """
    Quick context extraction using simple pattern matching.
    This is faster than running full Phase 2.

    Args:
        normalized_text: Normalized address text

    Returns:
        Dict with extracted province/district (or None)

    Example:
        >>> _quick_extract_context("hai ba trung ha noi")
        {'province': 'ha noi', 'district': None}
    """
    import re

    result = {
        'province': None,
        'district': None
    }

    # Common province patterns
    province_patterns = [
        r'\b(ha\s*noi|hanoi)\b',
        r'\b(ho\s*chi\s*minh|hochiminh|sai\s*gon|saigon)\b',
        r'\b(da\s*nang|danang)\b',
        r'\b(hai\s*phong|haiphong)\b',
        r'\b(can\s*tho|cantho)\b',
        r'\b(ba\s*ria\s*vung\s*tau|baria\s*vungtau|brvt)\b',
        r'\b(dong\s*nai|dongnai)\b',
        r'\b(binh\s*duong|binhduong)\b',
    ]

    # Try to match province
    for pattern in province_patterns:
        match = re.search(pattern, normalized_text, re.IGNORECASE)
        if match:
            # Normalize the match
            matched_text = match.group(0).replace(' ', '')

            # Map to standard form
            province_map = {
                'hanoi': 'ha noi',
                'hochiminh': 'ho chi minh',
                'saigon': 'ho chi minh',
                'danang': 'da nang',
                'haiphong': 'hai phong',
                'cantho': 'can tho',
                'brvt': 'ba ria vung tau',
                'bariavungtau': 'ba ria vung tau',
                'dongnai': 'dong nai',
                'binhduong': 'binh duong'
            }

            result['province'] = province_map.get(matched_text, match.group(1).replace(r'\s*', ' '))
            break

    # Common district patterns (only if province found)
    if result['province']:
        district_patterns = [
            r'\b(ba\s*dinh|badinh)\b',
            r'\b(cau\s*giay|caugiay)\b',
            r'\b(dong\s*da|dongda)\b',
            r'\b(hoan\s*kiem|hoankiem)\b',
            r'\b(quan\s*(\d+))\b',  # Quan 1, Quan 2, etc.
        ]

        for pattern in district_patterns:
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if match:
                matched_text = match.group(0).replace(' ', '')
                result['district'] = match.group(1).replace(r'\s*', ' ')
                break

    return result


def should_use_iterative(raw_address: str, province_known: Optional[str] = None) -> bool:
    """
    Determine if iterative preprocessing is needed.

    Use iterative if:
    1. No province_known is provided (need to discover)
    2. Address contains abbreviations that need province context

    Args:
        raw_address: Raw address string
        province_known: Known province (optional)

    Returns:
        True if iterative preprocessing should be used

    Example:
        >>> should_use_iterative("HBT, HN", province_known=None)
        True  # Need to discover province

        >>> should_use_iterative("HBT, HN", province_known="ha noi")
        False  # Already have province context
    """
    # If province is already known, single pass is sufficient
    if province_known:
        return False

    # Check if address likely contains abbreviations
    # Common abbreviations: HBT, DBP, BTL, etc. (2-3 uppercase letters)
    import re
    has_abbreviations = bool(re.search(r'\b[A-Z]{2,4}\b', raw_address))

    return has_abbreviations


if __name__ == "__main__":
    # Test iterative preprocessing
    print("=" * 80)
    print("ITERATIVE PREPROCESSING TEST")
    print("=" * 80)

    test_cases = [
        ("HBT, HN", None, "Abbreviation needing province context"),
        ("DBP, Q. Ba Dinh, HN", None, "Ward abbreviation with province"),
        ("P. Điện Biên, Q. Ba Đình, HN", None, "No abbreviations (should stop early)"),
        ("HBT, HN", "ha noi", "With known province (single pass)"),
    ]

    for raw_addr, prov_known, description in test_cases:
        print(f"\n{description}")
        print(f"Input: {raw_addr}")
        if prov_known:
            print(f"Known province: {prov_known}")

        # Check if iterative is needed
        use_iter = should_use_iterative(raw_addr, prov_known)
        print(f"Use iterative: {use_iter}")

        # Process
        result = iterative_preprocess(raw_addr, prov_known)

        print(f"\nResults:")
        print(f"  Iterations: {result['total_iterations']}")
        print(f"  Improved: {result['improved']}")
        print(f"  Final normalized: {result['normalized']}")
        print(f"  Province context discovered: {result.get('province_context', 'N/A')}")
        print(f"  Time: {result['processing_time_ms']:.2f}ms")

        # Show all iterations
        if result['total_iterations'] > 1:
            print(f"\n  Iteration details:")
            for iter_data in result['all_iterations']:
                print(f"    Iteration {iter_data['iteration']}: {iter_data['normalized']}")
                print(f"      Context: province={iter_data.get('province_context', 'None')}")

    print("\n" + "=" * 80)
