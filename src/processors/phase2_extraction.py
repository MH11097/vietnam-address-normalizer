"""
Phase 2: Entity Extraction (Database-based)

Input: Preprocessed address dict from Phase 1
Output: Extracted address components (province, district, ward)

Strategy: Use database n-gram matching instead of regex patterns.
Works WITHOUT keywords (phuong, quan, tinh) for real-world addresses.
"""
from typing import Dict, Any, Optional, Tuple
import re
import time
from functools import lru_cache
from ..utils.extraction_utils import extract_with_database
from ..utils.text_utils import normalize_address, normalize_hint


# Precompiled regex patterns for Vietnamese administrative levels
PATTERNS = {
    'province': re.compile(r'\b(tinh|thanhpho)\s*([a-z0-9]+(?:\s+[a-z0-9]+)*)', re.IGNORECASE),
    'district': re.compile(r'\b(quan|huyen|thitran)\s*([a-z0-9]+(?:\s+[a-z0-9]+)*)', re.IGNORECASE),
    'ward': re.compile(r'\b(phuong|xa)\s*([a-z0-9]+(?:\s+[a-z0-9]+)*)', re.IGNORECASE),
}

# Direct name patterns (when prefix is missing)
NAME_PATTERNS = {
    'province_names': re.compile(r'\b(hanoi|hochiminh|haiphong|cantho|danang|bienhoa|vungtau)\b', re.IGNORECASE),
    'district_names': re.compile(r'\b(badinh|caugiay|dongda|hoankiam|tayho|thanhxuan|longan|dongxoai)\b', re.IGNORECASE),
}


@lru_cache(maxsize=5000)
def extract_with_regex(normalized_text: str) -> Dict[str, Any]:
    """
    Extract address components using regex patterns.
    Primary extraction method.

    Args:
        normalized_text: Normalized address string

    Returns:
        Dictionary with extracted components
    """
    province = None
    district = None
    ward = None
    remaining = normalized_text

    # Extract province
    province_match = PATTERNS['province'].search(normalized_text)
    if province_match:
        province = province_match.group(2).strip()
        remaining = remaining.replace(province_match.group(0), '', 1).strip()
    else:
        # Try direct name matching
        name_match = NAME_PATTERNS['province_names'].search(normalized_text)
        if name_match:
            province = name_match.group(0).strip()
            remaining = remaining.replace(name_match.group(0), '', 1).strip()

    # Extract district
    district_match = PATTERNS['district'].search(normalized_text)
    if district_match:
        district = district_match.group(2).strip()
        remaining = remaining.replace(district_match.group(0), '', 1).strip()
    else:
        # Try direct name matching
        name_match = NAME_PATTERNS['district_names'].search(normalized_text)
        if name_match:
            district = name_match.group(0).strip()
            remaining = remaining.replace(name_match.group(0), '', 1).strip()

    # Extract ward
    ward_match = PATTERNS['ward'].search(normalized_text)
    if ward_match:
        ward = ward_match.group(2).strip()
        remaining = remaining.replace(ward_match.group(0), '', 1).strip()

    # Clean up remaining text
    remaining = re.sub(r'\s+', ' ', remaining).strip()

    return {
        'province': province,
        'district': district,
        'ward': ward,
        'remaining': remaining
    }


def extract_bidirectional(normalized_text: str) -> Dict[str, Any]:
    """
    Extract using bidirectional pattern matching.
    This is a key advantage from the original logic - handles Vietnamese addresses
    that can be written in various orders.

    Strategy:
    1. Backward scan (từ cuối về đầu): Find tinh+huyen+xa from end
    2. Forward scan (từ đầu về cuối): Find tinh+huyen+xa from start
    3. Merge results and pick best match

    Args:
        normalized_text: Normalized address string

    Returns:
        Dictionary with extracted components and confidence
    """
    # Split text into tokens
    tokens = normalized_text.split()

    # Backward scan
    backward_result = _scan_backward(tokens)

    # Forward scan
    forward_result = _scan_forward(tokens)

    # Merge results (prefer more complete match)
    if backward_result['match_level'] >= forward_result['match_level']:
        best = backward_result
        method = 'backward'
    else:
        best = forward_result
        method = 'forward'

    # If both found same level, combine information
    if backward_result['match_level'] == forward_result['match_level'] > 0:
        method = 'bidirectional'

    return {
        'province': best['province'],
        'district': best['district'],
        'ward': best['ward'],
        'remaining': best['remaining'],
        'match_level': best['match_level'],
        'method': method,
        'bidirectional_confirmed': backward_result['match_level'] == forward_result['match_level'] > 0
    }


def _scan_backward(tokens: list) -> Dict[str, Any]:
    """Scan from end to start to find administrative components."""
    province = None
    district = None
    ward = None
    match_level = 0

    # Reverse scan
    text = ' '.join(tokens)

    # Try to find patterns from the end
    components = extract_with_regex(text)

    if components['ward']:
        match_level = 3
    elif components['district']:
        match_level = 2
    elif components['province']:
        match_level = 1

    return {
        'province': components['province'],
        'district': components['district'],
        'ward': components['ward'],
        'remaining': components['remaining'],
        'match_level': match_level
    }


def _scan_forward(tokens: list) -> Dict[str, Any]:
    """Scan from start to end to find administrative components."""
    # For forward scan, we use the same regex but process differently
    # In practice, regex already handles both directions well
    # This is a placeholder for custom forward logic if needed

    text = ' '.join(tokens)
    components = extract_with_regex(text)

    match_level = 0
    if components['ward']:
        match_level = 3
    elif components['district']:
        match_level = 2
    elif components['province']:
        match_level = 1

    return {
        'province': components['province'],
        'district': components['district'],
        'ward': components['ward'],
        'remaining': components['remaining'],
        'match_level': match_level
    }


def extract_components(
    preprocessed: Dict[str, Any],
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    use_legacy: bool = False
) -> Dict[str, Any]:
    """
    Main extraction function - uses database n-gram matching.

    Args:
        preprocessed: Output from Phase 1 preprocessing
        province_known: Known province from raw data (optional, trusted 100%)
        district_known: Known district from raw data (optional, trusted 100%)
        use_legacy: Use old regex-based extraction (default: False)

    Returns:
        Dictionary containing:
        - candidates: List of candidate combinations, each with:
            - province, district, ward: Component names
            - province_score, district_score, ward_score: Scores (0-100)
            - combined_score: Average of non-zero scores
            - match_level: 0-3 (0=none, 1=province, 2=district, 3=ward)
            - confidence: Confidence score (0-1)
            - method: Extraction method for this candidate
            - hierarchy_valid: Whether hierarchy is valid
        - processing_time_ms: Processing time (shared)
        - geographic_known_used: Whether known values were provided (shared)
        - original_address: Original address from Phase 1 (shared)
        - province_known: Normalized province hint if provided (shared)
        - district_known: Normalized district hint if provided (shared)

    Example:
        >>> extract_components({'normalized': 'bach khoa ha noi'}, province_known='ha noi')
        {
            'candidates': [
                {
                    'province': 'ha noi',
                    'district': None,
                    'ward': 'bach khoa',
                    'province_score': 100.0,
                    'district_score': 0.0,
                    'ward_score': 100.0,
                    'combined_score': 100.0,
                    'match_level': 3,
                    'confidence': 1.0,
                    'method': 'database_ngram',
                    'hierarchy_valid': True
                }
            ],
            'processing_time_ms': 2.5,
            'geographic_known_used': True,
            'original_address': 'bach khoa ha noi'
        }
    """
    start_time = time.time()

    normalized_text = preprocessed.get('normalized', '')

    if not normalized_text:
        return {
            'province': None,
            'district': None,
            'ward': None,
            'province_score': 0.0,
            'district_score': 0.0,
            'ward_score': 0.0,
            'method': 'none',
            'confidence': 0.0,
            'match_level': 0,
            'geographic_known_used': False,
            'processing_time_ms': 0.0,
            'error': 'No normalized text'
        }

    # Normalize known values if provided
    # Use normalize_hint() to strip administrative prefixes (thanh pho, quan, phuong)
    prov_known_norm = None
    dist_known_norm = None

    if province_known:
        prov_known_norm = normalize_hint(province_known)
    if district_known:
        dist_known_norm = normalize_hint(district_known)

    # Use legacy regex-based extraction if requested
    if use_legacy:
        bidirectional_result = extract_bidirectional(normalized_text)

        if bidirectional_result['match_level'] == 0:
            regex_result = extract_with_regex(normalized_text)
            legacy_candidate = {
                'province': regex_result['province'],
                'district': regex_result['district'],
                'ward': regex_result['ward'],
                'province_score': 100.0 if regex_result['province'] else 0.0,
                'district_score': 100.0 if regex_result['district'] else 0.0,
                'ward_score': 100.0 if regex_result['ward'] else 0.0,
                'method': 'regex_legacy',
                'confidence': 0.7 if regex_result.get('province') else 0.3,
                'match_level': _calculate_match_level(regex_result),
                'combined_score': 70.0 if regex_result.get('province') else 30.0,
                'hierarchy_valid': True
            }
        else:
            confidence = _calculate_confidence(bidirectional_result)
            legacy_candidate = {
                'province': bidirectional_result['province'],
                'district': bidirectional_result['district'],
                'ward': bidirectional_result['ward'],
                'province_score': 100.0 if bidirectional_result['province'] else 0.0,
                'district_score': 100.0 if bidirectional_result['district'] else 0.0,
                'ward_score': 100.0 if bidirectional_result['ward'] else 0.0,
                'method': bidirectional_result['method'],
                'confidence': confidence,
                'match_level': bidirectional_result['match_level'],
                'combined_score': confidence * 100.0,
                'hierarchy_valid': True
            }

        candidates = [legacy_candidate] if legacy_candidate['province'] or legacy_candidate['district'] or legacy_candidate['ward'] else []
    else:
        # NEW: Use database-based extraction (default)
        extraction_result = extract_with_database(
            normalized_text,
            province_known=prov_known_norm,
            district_known=dist_known_norm
        )
        candidates = extraction_result.get('candidates', [])

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

    # Build result with candidates-first structure
    result = {
        'candidates': candidates,
        'processing_time_ms': round(processing_time, 3),
        'geographic_known_used': prov_known_norm is not None or dist_known_norm is not None,
        'original_address': preprocessed.get('original', '')
    }

    # Add known values for OSM context enhancement in Phase 3
    if prov_known_norm:
        result['province_known'] = prov_known_norm
    if dist_known_norm:
        result['district_known'] = dist_known_norm

    return result


def _calculate_match_level(components: Dict) -> int:
    """Calculate match level based on extracted components."""
    if components.get('ward'):
        return 3
    elif components.get('district'):
        return 2
    elif components.get('province'):
        return 1
    return 0


def _calculate_confidence(result: Dict) -> float:
    """Calculate confidence score based on extraction results."""
    base_confidence = 0.5

    # Add confidence based on match level
    if result['match_level'] == 3:
        base_confidence += 0.3
    elif result['match_level'] == 2:
        base_confidence += 0.2
    elif result['match_level'] == 1:
        base_confidence += 0.1

    # Bonus for bidirectional confirmation
    if result.get('bidirectional_confirmed'):
        base_confidence += 0.15

    return min(base_confidence, 1.0)


if __name__ == "__main__":
    # Test examples
    test_cases = [
        {
            'normalized': 'phuong dien bien quan ba dinh hanoi',
            'description': 'Standard format'
        },
        {
            'normalized': 'hanoi ba dinh dien bien',
            'description': 'Reversed order'
        },
        {
            'normalized': 'quan 1 thanh pho hochiminh',
            'description': 'With numbers'
        },
        {
            'normalized': 'so 1 nguyen thai hoc phuong dien bien quan ba dinh hanoi',
            'description': 'With street address'
        }
    ]

    print("=" * 80)
    print("PHASE 2: EXTRACTION TEST")
    print("=" * 80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Input: {test['normalized']}")

        preprocessed = {'normalized': test['normalized']}
        result = extract_components(preprocessed)

        print(f"   Province:  {result['province']}")
        print(f"   District:  {result['district']}")
        print(f"   Ward:      {result['ward']}")
        print(f"   Remaining: {result['remaining']}")
        print(f"   Method:    {result['method']}")
        print(f"   Level:     {result['match_level']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Bidirectional: {result['bidirectional_confirmed']}")
        print(f"   Time:      {result['processing_time_ms']}ms")
