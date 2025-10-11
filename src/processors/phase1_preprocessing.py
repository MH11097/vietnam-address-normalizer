"""
Phase 1: Preprocessing & Normalization

Input: Raw address string
Output: Normalized and preprocessed address dict
"""
from typing import Dict, Any
import time
from ..utils.text_utils import (
    normalize_address,
    normalize_unicode,
    expand_abbreviations,
    remove_vietnamese_accents,
    remove_special_chars
)


def preprocess(raw_address: str, province_known: str = None) -> Dict[str, Any]:
    """
    Preprocess raw address through normalization pipeline.

    Pipeline steps:
    1. Unicode normalization (NFC)
    2. Abbreviation expansion (with province context if provided)
    3. Accent removal
    4. Special character removal
    5. Full normalization

    Args:
        raw_address: Raw input address string
        province_known: Known province from raw data (optional, for context-aware abbreviation expansion)

    Returns:
        Dictionary containing:
        - original: Original input
        - unicode_normalized: After unicode normalization
        - expanded: After abbreviation expansion
        - no_accent: After accent removal
        - normalized: Fully normalized text
        - processing_time_ms: Processing time in milliseconds

    Example:
        >>> preprocess("P. Điện Biên, Q. Ba Đình, HN")
        {
            'original': 'P. Điện Biên, Q. Ba Đình, HN',
            'unicode_normalized': 'P. Điện Biên, Q. Ba Đình, HN',
            'expanded': 'phuong điện biên, quan ba đình, hanoi',
            'no_accent': 'phuong dien bien, quan ba dinh, hanoi',
            'normalized': 'phuong dien bien quan ba dinh hanoi',
            'processing_time_ms': 0.15
        }
    """
    start_time = time.time()

    if not raw_address or not isinstance(raw_address, str):
        return {
            'original': raw_address or '',
            'unicode_normalized': '',
            'expanded': '',
            'no_accent': '',
            'normalized': '',
            'processing_time_ms': 0.0,
            'error': 'Invalid input'
        }

    # Normalize province_known if provided (for abbreviation context)
    from ..utils.text_utils import normalize_hint
    province_normalized = normalize_hint(province_known) if province_known else None

    # Step 1: Unicode normalization
    unicode_normalized = normalize_unicode(raw_address)

    # Step 2: Abbreviation expansion (with province context)
    expanded = expand_abbreviations(unicode_normalized, province_context=province_normalized)

    # Step 3: Accent removal
    no_accent = remove_vietnamese_accents(expanded)

    # Step 4: Full normalization (includes special char removal)
    normalized = normalize_address(raw_address, province_context=province_normalized)

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000  # ms

    return {
        'original': raw_address,
        'unicode_normalized': unicode_normalized,
        'expanded': expanded,
        'no_accent': no_accent,
        'normalized': normalized,
        'processing_time_ms': round(processing_time, 3)
    }


def preprocess_batch(addresses: list) -> list:
    """
    Preprocess multiple addresses.

    Args:
        addresses: List of raw address strings

    Returns:
        List of preprocessed dictionaries
    """
    return [preprocess(addr) for addr in addresses]


if __name__ == "__main__":
    # Test examples
    test_cases = [
        "P. Điện Biên, Q. Ba Đình, HN",
        "19 Hoàng Diệu, Phường Điện Biên, Quận Ba Đình, Hà Nội",
        "Q. 1, TP. HCM",
        "123 Lê Lợi, Phường Bến Thành, Quận 1, Hồ Chí Minh"
    ]

    print("=" * 80)
    print("PHASE 1: PREPROCESSING TEST")
    print("=" * 80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. Input: {test}")
        result = preprocess(test)
        print(f"   Original:    {result['original']}")
        print(f"   Unicode:     {result['unicode_normalized']}")
        print(f"   Expanded:    {result['expanded']}")
        print(f"   No accent:   {result['no_accent']}")
        print(f"   Normalized:  {result['normalized']}")
        print(f"   Time:        {result['processing_time_ms']}ms")
