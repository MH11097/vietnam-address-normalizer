"""
Phase 1: Preprocessing & Normalization

Input: Raw address string
Output: Normalized and preprocessed address dict
"""
from typing import Dict, Any
import time
import logging
from ..utils.text_utils import (
    normalize_address,
    normalize_unicode,
    expand_abbreviations,
    remove_vietnamese_accents,
    remove_special_chars,
    finalize_normalization,
    tokenize_with_delimiter_info
)

logger = logging.getLogger(__name__)


def preprocess(raw_address: str, province_known: str = None) -> Dict[str, Any]:
    """
    Preprocess raw address through normalization pipeline.

    Pipeline steps:
    1. Unicode normalization (NFC)
    2. Abbreviation expansion (with province context if provided)
    3. Accent removal
    4. Finalize normalization (remove special chars, lowercase, trim)

    Each step builds on the previous one (no duplicate processing).

    Args:
        raw_address: Raw input address string
        province_known: Known province from raw data (optional, for context-aware abbreviation expansion)

    Returns:
        Dictionary containing:
        - original: Original input
        - unicode_normalized: After unicode normalization
        - expanded: After abbreviation expansion
        - no_accent: After accent removal
        - normalized: Fully normalized text (with separators for structural parsing)
        - processing_time_ms: Processing time in milliseconds

    Example:
        >>> preprocess("P. Điện Biên, Q. Ba Đình, HN")
        {
            'original': 'P. Điện Biên, Q. Ba Đình, HN',
            'unicode_normalized': 'P. Điện Biên, Q. Ba Đình, HN',
            'expanded': 'phuong điện biên, quan ba đình, hanoi',
            'no_accent': 'phuong dien bien, quan ba dinh, hanoi',
            'normalized': 'phuong dien bien, quan ba dinh, hanoi',
            'processing_time_ms': 0.15
        }
    """
    start_time = time.time()

    logger.debug("=" * 80)
    logger.debug("[PHASE 1] TIỀN XỬ LÝ - BẮT ĐẦU")
    logger.debug("  📥 Input:")
    logger.debug(f"      - Raw address: '{raw_address}'")
    logger.debug(f"      - Province known: {province_known or 'None'}")
    logger.debug("  🔧 Tác vụ: Chuẩn hóa văn bản qua 4 bước (không duplicate processing)")

    if not raw_address or not isinstance(raw_address, str):
        logger.debug("  ❌ ERROR: Invalid input")
        logger.debug("=" * 80)
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
    logger.debug("\n[PHASE 1.1] UNICODE NORMALIZATION")
    logger.debug(f"  📥 Input: '{raw_address}'")
    logger.debug("  🔧 Tác vụ: Chuẩn hóa unicode (NFC form)")
    unicode_normalized = normalize_unicode(raw_address)
    logger.debug(f"  📤 Output: '{unicode_normalized}'")
    if unicode_normalized != raw_address:
        changed_chars = sum(1 for a, b in zip(raw_address, unicode_normalized) if a != b)
        logger.debug(f"  📝 Notes: Đã sửa {changed_chars} ký tự unicode")

    # Step 2: Abbreviation expansion (with province context)
    logger.debug("\n[PHASE 1.2] ABBREVIATION EXPANSION")
    logger.debug(f"  📥 Input: '{unicode_normalized}'")
    logger.debug(f"  🔧 Tác vụ: Mở rộng viết tắt (context: {province_normalized or 'None'})")
    expanded = expand_abbreviations(unicode_normalized, province_context=province_normalized)
    logger.debug(f"  📤 Output: '{expanded}'")
    if expanded != unicode_normalized.lower():
        logger.debug(f"  📝 Notes: Đã mở rộng viết tắt (text đã thay đổi)")

    # Step 3: Accent removal
    logger.debug("\n[PHASE 1.3] ACCENT REMOVAL")
    logger.debug(f"  📥 Input: '{expanded}'")
    logger.debug("  🔧 Tác vụ: Loại bỏ dấu tiếng Việt")
    no_accent = remove_vietnamese_accents(expanded)
    logger.debug(f"  📤 Output: '{no_accent}'")
    if no_accent != expanded:
        logger.debug(f"  📝 Notes: Đã loại bỏ dấu cho matching")

    # Step 4: Extract delimiter information (before removing delimiters)
    logger.debug("\n[PHASE 1.4] DELIMITER EXTRACTION")
    logger.debug(f"  📥 Input: '{no_accent}'")
    logger.debug("  🔧 Tác vụ: Trích xuất thông tin delimiter (commas, hyphens, underscores, slashes)")
    delimiter_info = tokenize_with_delimiter_info(no_accent)
    if delimiter_info['has_delimiters']:
        logger.debug(f"  📤 Output: Found {len(delimiter_info['delimiter_positions'])} delimiters")
        logger.debug(f"      - Segments: {len(delimiter_info['segments'])}")
        logger.debug(f"      - Number tokens: {delimiter_info['number_tokens']}")
    else:
        logger.debug("  📤 Output: No delimiters found")

    # Step 5: Finalize normalization (remove special chars, lowercase, trim)
    logger.debug("\n[PHASE 1.5] FINALIZE NORMALIZATION")
    logger.debug(f"  📥 Input: '{no_accent}'")
    logger.debug("  🔧 Tác vụ: Loại bỏ ký tự đặc biệt, lowercase, normalize whitespace")
    normalized = finalize_normalization(no_accent, keep_separators=True)
    logger.debug(f"  📤 Output: '{normalized}'")
    logger.debug(f"  📝 Notes: Văn bản cuối cùng cho Phase 2 (giữ commas cho structural parsing)")

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000  # ms

    logger.debug(f"\n[PHASE 1] HOÀN THÀNH - Thời gian: {processing_time:.3f}ms")
    logger.debug("=" * 80)

    return {
        'original': raw_address,
        'unicode_normalized': unicode_normalized,
        'expanded': expanded,
        'no_accent': no_accent,
        'normalized': normalized,
        'delimiter_info': delimiter_info,
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
