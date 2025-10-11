"""
Phase 5: Post-processing & Enrichment

Input: Validated best match from Phase 4
Output: Final formatted output with STATE/COUNTY codes
"""
from typing import Dict, Any
import time
import re
import unicodedata
from ..utils.db_utils import find_exact_match


def format_output(best_match: Dict[str, Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Format final output with all required fields.

    In production, this would:
    - Add STATE/COUNTY codes from database
    - Format remaining address
    - Add ACN cross-validation
    - Split remaining into 3 columns (40 chars each)

    Args:
        best_match: Best match from Phase 4
        metadata: Additional metadata (original input, etc.)

    Returns:
        Formatted output dictionary

    Example:
        >>> format_output({...})
        {
            'province': 'Hà Nội',
            'district': 'Ba Đình',
            'ward': 'Điện Biên',
            'state_code': '01',
            'county_code': '001',
            'remaining_1': '...',
            'remaining_2': '',
            'remaining_3': '',
            ...
        }
    """
    if not best_match:
        return {
            'province': None,
            'district': None,
            'ward': None,
            'state_code': None,
            'county_code': None,
            'remaining_1': '',
            'remaining_2': '',
            'remaining_3': '',
            'error': 'No match to format'
        }

    # Get components (normalized names)
    province = best_match.get('province', '')
    district = best_match.get('district', '')
    ward = best_match.get('ward', '')

    # Get full names (ALWAYS populated by Phase 3)
    # Phase 3 now populates full names for ALL candidates to prevent redundant DB lookups
    province_full = best_match.get('province_full', '')
    district_full = best_match.get('district_full', '')
    ward_full = best_match.get('ward_full', '')

    # No DB lookups needed - Phase 3 already populated full names

    # Lookup STATE/COUNTY codes from database
    state_code, county_code = _get_state_county_codes(province, district, ward)

    # Extract remaining address (street, house number, etc.)
    original_address = metadata.get('original_address', '') if metadata else ''

    if original_address and best_match:
        # Extract parts that are not province/district/ward
        matched_components = {
            'province': province,
            'district': district,
            'ward': ward
        }
        remaining = extract_remaining_address(original_address, matched_components)
    else:
        remaining = ''

    remaining_parts = _split_remaining(remaining)

    # Use full names if available, otherwise capitalize normalized names
    province_formatted = _extract_name_from_full(province_full) if province_full else _capitalize(province)
    district_formatted = _extract_name_from_full(district_full) if district_full else _capitalize(district)
    ward_formatted = _extract_name_from_full(ward_full) if ward_full else _capitalize(ward)

    return {
        'province': province_formatted,
        'district': district_formatted,
        'ward': ward_formatted,
        'state_code': state_code,
        'county_code': county_code,
        'remaining_1': remaining_parts[0],
        'remaining_2': remaining_parts[1],
        'remaining_3': remaining_parts[2],
        'at_rule': best_match.get('at_rule', 0),
        'confidence': best_match.get('final_confidence', 0),
        'match_type': best_match.get('match_type', ''),
    }


def _get_state_county_codes(province: str, district: str, ward: str) -> tuple:
    """
    Get STATE and COUNTY codes from database.

    Args:
        province: Normalized province name
        district: Normalized district name
        ward: Normalized ward name

    Returns:
        Tuple of (state_code, county_code)
    """
    if not province:
        return ('', '')

    # Query database for exact match to get codes
    db_result = find_exact_match(province, district, ward)

    if db_result:
        # admin_divisions table should have these fields
        # Check if STATE/COUNTY columns exist in result
        state_code = db_result.get('STATE', '') or db_result.get('state_code', '')
        county_code = db_result.get('COUNTY', '') or db_result.get('county_code', '')

        return (str(state_code) if state_code else '', str(county_code) if county_code else '')

    return ('', '')


def remove_diacritics_and_uppercase(text: str) -> str:
    """
    Remove Vietnamese diacritics and convert to uppercase.
    From ref/extract_location.py

    Args:
        text: Input text with diacritics

    Returns:
        Text without diacritics in uppercase
    """
    if not text:
        return ''

    # Normalize to NFD form and remove diacritics
    text_normalized = unicodedata.normalize('NFD', str(text))
    text_without_diacritics = ''.join([
        char for char in text_normalized
        if unicodedata.category(char) != 'Mn'
    ])

    return text_without_diacritics.upper()


def _extract_name_from_full(full_name: str) -> str:
    """
    Extract name from full administrative name.
    E.g., "THÀNH PHỐ HÀ NỘI" -> "Hà Nội"
         "QUẬN BA ĐÌNH" -> "Ba Đình"
         "PHƯỜNG ĐIỆN BIÊN" -> "Điện Biên"
    """
    if not full_name:
        return ''

    # Remove administrative prefixes
    prefixes = [
        'THÀNH PHỐ ', 'TỈNH ',
        'QUẬN ', 'HUYỆN ', 'THỊ XÃ ', 'THÀNH PHỐ ',
        'PHƯỜNG ', 'XÃ ', 'THỊ TRẤN '
    ]

    name = full_name
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Capitalize properly (title case)
    return ' '.join(word.capitalize() for word in name.split())


def _capitalize(text: str) -> str:
    """Capitalize Vietnamese name properly."""
    if not text:
        return ''

    # Simple capitalization - in production, use proper Vietnamese rules
    words = text.split()
    return ' '.join(word.capitalize() for word in words)


def extract_remaining_address(original_address: str, matched_components: Dict[str, str]) -> str:
    """
    Extract remaining address by removing matched province/district/ward.

    Args:
        original_address: Original raw address
        matched_components: Dict with province, district, ward

    Returns:
        Remaining address text
    """
    if not original_address:
        return ''

    # Normalize to lowercase for matching
    from ..utils.text_utils import normalize_address
    address_normalized = normalize_address(original_address)

    province = matched_components.get('province', '')
    district = matched_components.get('district', '')
    ward = matched_components.get('ward', '')

    # Load abbreviations from database (context-aware based on province)
    from ..utils.db_utils import load_abbreviations
    abbreviations = load_abbreviations(province)

    # Remove matched components using word boundary regex
    remaining = address_normalized

    # STEP 1: Remove abbreviations first (before full names)
    # This handles cases where "BD" was matched to "ba dinh"

    for abbr, full_name in abbreviations.items():
        # If the matched component matches the full name, also remove the abbreviation
        if ward and ward == full_name:
            pattern = r'\b' + re.escape(abbr) + r'\b'
            remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
        if district and district == full_name:
            pattern = r'\b' + re.escape(abbr) + r'\b'
            remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
        if province and province == full_name:
            pattern = r'\b' + re.escape(abbr) + r'\b'
            remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)

    # STEP 2: Remove full names with prefixes

    # Remove ward if matched (with word boundary)
    if ward:
        # Try with administrative prefixes first
        pattern = r'\b(phuong|xa|thi\s+tran|p|x)\s+' + re.escape(ward) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
        # Then try without prefix
        pattern = r'\b' + re.escape(ward) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)

    # Remove district if matched (with word boundary)
    if district:
        # Try with administrative prefixes first
        pattern = r'\b(quan|huyen|thi\s+xa|thanh\s+pho|q|h)\s+' + re.escape(district) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
        # Then try without prefix
        pattern = r'\b' + re.escape(district) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)

    # Remove province if matched (with word boundary)
    if province:
        # Try with administrative prefixes first
        pattern = r'\b(tinh|thanh\s+pho|tp)\s+' + re.escape(province) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)
        # Then try without prefix
        pattern = r'\b' + re.escape(province) + r'\b'
        remaining = re.sub(pattern, ' ', remaining, flags=re.IGNORECASE)

    # Clean up: remove extra spaces
    remaining = re.sub(r'\s+', ' ', remaining).strip()

    return remaining


def _split_remaining(remaining: str) -> tuple:
    """
    Split remaining address into 3 parts (40 chars each).
    Apply Vietnamese text formatting.

    Args:
        remaining: Remaining address text

    Returns:
        Tuple of (part1, part2, part3)
    """
    if not remaining:
        return ('', '', '')

    # Clean up and format remaining text
    cleaned = remove_diacritics_and_uppercase(remaining)

    # Split into 40-char chunks
    part1 = cleaned[:40] if len(cleaned) > 0 else ''
    part2 = cleaned[40:80] if len(cleaned) > 40 else ''
    part3 = cleaned[80:120] if len(cleaned) > 80 else ''

    return (part1, part2, part3)


def postprocess(validation_result: Dict[str, Any], extraction_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Main post-processing function.

    Args:
        validation_result: Output from Phase 4
        extraction_result: Optional output from Phase 2 (for remaining address)

    Returns:
        Dictionary containing:
        - formatted_output: Final formatted result
        - quality_flag: Quality indicator (high/medium/low/failed)
        - processing_time_ms: Processing time

    Example:
        >>> postprocess({'best_match': {...}})
        {
            'formatted_output': {...},
            'quality_flag': 'high_confidence',
            'processing_time_ms': 0.1
        }
    """
    start_time = time.time()

    best_match = validation_result.get('best_match')

    # Prepare metadata
    metadata = {}
    if extraction_result:
        metadata['remaining'] = extraction_result.get('remaining', '')
        metadata['original_address'] = extraction_result.get('original_address', '')

    # Format output
    formatted = format_output(best_match, metadata)

    # Determine quality flag
    quality_flag = _determine_quality(formatted)

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

    return {
        'formatted_output': formatted,
        'quality_flag': quality_flag,
        'processing_time_ms': round(processing_time, 3)
    }


def _determine_quality(formatted: Dict[str, Any]) -> str:
    """
    Determine quality flag based on completeness and confidence.

    Returns:
        'full_address' | 'partial_address' | 'province_only' | 'failed'
    """
    at_rule = formatted.get('at_rule', 0)
    confidence = formatted.get('confidence', 0)

    if at_rule == 3 and confidence >= 0.8:
        return 'full_address'
    elif at_rule == 2 and confidence >= 0.6:
        return 'partial_address'
    elif at_rule == 1 and confidence >= 0.6:
        return 'province_only'
    else:
        return 'failed'


if __name__ == "__main__":
    # Test example
    test_validation_result = {
        'best_match': {
            'province': 'hanoi',
            'district': 'badinh',
            'ward': 'dienbien',
            'match_type': 'exact',
            'at_rule': 3,
            'confidence': 1.0,
            'final_confidence': 0.95
        }
    }

    test_extraction_result = {
        'remaining': 'so 1 nguyen thai hoc'
    }

    print("=" * 80)
    print("PHASE 5: POST-PROCESSING TEST")
    print("=" * 80)

    result = postprocess(test_validation_result, test_extraction_result)

    print("\nFormatted output:")
    output = result['formatted_output']
    for key, value in output.items():
        print(f"  {key:15} = {value}")

    print(f"\nQuality flag: {result['quality_flag']}")
    print(f"Processing time: {result['processing_time_ms']}ms")
