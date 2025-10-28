"""
Phase 6: Post-processing & Enrichment

Input: Validated best match from Phase 5
Output: Final formatted output with STATE/COUNTY codes
"""
from typing import Dict, Any, List
import time
import unicodedata
import logging
from ..utils.db_utils import find_exact_match

logger = logging.getLogger(__name__)


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
    logger.debug("[🔍 DEBUG] " + "═" * 76)
    logger.debug("[🔍 DEBUG] [PHASE 5] POST-PROCESSING")

    if not best_match:
        logger.debug(f"[🔍 DEBUG]   ⚠ No best match to format")
        logger.debug("[🔍 DEBUG] " + "═" * 76 + "\n")
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
    # Ensure None values are converted to empty strings to avoid type errors
    province = best_match.get('province') or ''
    district = best_match.get('district') or ''
    ward = best_match.get('ward') or ''

    logger.debug(f"[🔍 DEBUG]   📥 Best match: {ward or 'None'} | {district or 'None'} | {province or 'None'}")
    logger.debug(f"[🔍 DEBUG]   🔧 Tác vụ: Format + STATE/COUNTY codes + Extract remaining")
    # Get full names (ALWAYS populated by Phase 3)
    # Phase 3 now populates full names for ALL candidates to prevent redundant DB lookups
    # Ensure None values are converted to empty strings
    province_full = best_match.get('province_full') or ''
    district_full = best_match.get('district_full') or ''
    ward_full = best_match.get('ward_full') or ''

    # No DB lookups needed - Phase 3 already populated full names
    # If _full fields are empty, it means the component itself is None/empty (no match found)
    
    # Lookup STATE/COUNTY codes from database (only if components exist)
    state_code, county_code = _get_state_county_codes(province, district, ward)
    
    # Extract remaining address (street, house number, etc.) using token positions
    normalized_tokens = best_match.get('normalized_tokens', [])

    if normalized_tokens and best_match:
        # Get token positions from best_match
        token_positions = {
            'province': best_match.get('province_tokens', (-1, -1)),
            'district': best_match.get('district_tokens', (-1, -1)),
            'ward': best_match.get('ward_tokens', (-1, -1))
        }
        remaining = extract_remaining_address(normalized_tokens, token_positions)
    else:
        # Fallback: no tokens available
        logger.debug("[REMAINING] No normalized_tokens in best_match, remaining address will be empty")
        remaining = ''

    remaining_parts = _split_remaining(remaining)

    # Use capitalized full names if available, otherwise capitalize normalized names
    # If both _full and normalized are empty/None, return empty string (no unnecessary queries)
    province_formatted = _capitalize_full_name(province_full) if province_full else (_capitalize(province) if province else '')
    district_formatted = _capitalize_full_name(district_full) if district_full else (_capitalize(district) if district else '')
    ward_formatted = _capitalize_full_name(ward_full) if ward_full else (_capitalize(ward) if ward else '')

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


def _capitalize_full_name(full_name: str) -> str:
    """
    Capitalize full administrative name with prefix.
    E.g., "THÀNH PHỐ HÀ NỘI" -> "Thành phố Hà Nội"
         "QUẬN BA ĐÌNH" -> "Quận Ba Đình"
         "PHƯỜNG ĐIỆN BIÊN" -> "Phường Điện Biên"
    """
    if not full_name:
        return ''

    # Split into words and capitalize each word
    # Vietnamese capitalization: first letter of each word is capitalized
    words = full_name.split()
    capitalized_words = []

    for word in words:
        if word:
            # Capitalize first letter, lowercase the rest
            capitalized_words.append(word[0].upper() + word[1:].lower())

    return ' '.join(capitalized_words)


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


def extract_remaining_address(
    normalized_tokens: List[str],
    token_positions: Dict[str, tuple]
) -> str:
    """
    Extract remaining address by removing matched province/district/ward tokens.

    Uses token positions from extraction phase for accurate removal.

    Args:
        normalized_tokens: List of normalized tokens from Phase 1
        token_positions: Dict with token positions for province/district/ward
                        e.g., {'province': (8, 10), 'district': (6, 8), 'ward': (4, 6)}

    Returns:
        Remaining address text (normalized, space-separated tokens)

    Example:
        >>> tokens = ['19', 'hoang', 'dieu', 'p', 'dien', 'bien', 'ba', 'dinh', 'ha', 'noi']
        >>> positions = {'province': (8, 10), 'district': (6, 8), 'ward': (4, 6)}
        >>> extract_remaining_address(tokens, positions)
        '19 hoang dieu p'
    """
    if not normalized_tokens:
        logger.debug("[REMAINING] No tokens to process")
        return ''

    logger.debug(f"[REMAINING] Input tokens ({len(normalized_tokens)}): {normalized_tokens}")
    logger.debug(f"[REMAINING] Token positions to remove: {token_positions}")

    # Create a mask for tokens to keep (True = keep, False = remove)
    mask = [True] * len(normalized_tokens)

    # Mark matched tokens for removal
    removed_ranges = []
    for component in ['province', 'district', 'ward']:
        pos = token_positions.get(component)
        if pos and pos != (-1, -1):
            start, end = pos
            # Mark tokens in this range as removed
            for i in range(start, end):
                if i < len(mask):
                    mask[i] = False
            removed_ranges.append((component, start, end, normalized_tokens[start:end]))
            logger.debug(f"[REMAINING] Removing {component} at [{start}:{end}]: {normalized_tokens[start:end]}")

    # Keep only unmatched tokens
    remaining_tokens = [t for i, t in enumerate(normalized_tokens) if mask[i]]
    remaining = ' '.join(remaining_tokens)

    # Log the result
    total_removed = sum(1 for m in mask if not m)
    logger.debug(f"[REMAINING] Removed {total_removed} tokens, {len(remaining_tokens)} tokens remain")
    logger.debug(f"[REMAINING] Remaining tokens: {remaining_tokens}")
    logger.debug(f"[REMAINING] Remaining address text: '{remaining}'")

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
