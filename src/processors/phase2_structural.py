"""
Phase 2: Structural Parsing using Separators & Keywords
========================================================

This layer sits between Phase 1 (preprocessing) and Phase 3 (entity extraction).
It leverages structural hints like commas, dashes, and administrative keywords
to parse addresses with high confidence before falling back to n-gram matching.

Parsing Tiers:
- Tier 1: Comma/Dash + Keywords → Confidence 0.85-0.95
- Tier 2: Keywords only → Confidence 0.70-0.85
- Tier 3: No structure → Confidence 0, fallback to n-gram

Example:
    >>> structural_parse("xa yen ho, duc tho", province_known="ha tinh")
    {
        'method': 'comma_keyword',
        'ward': 'yen ho',
        'district': 'duc tho',
        'province': 'ha tinh',
        'confidence': 0.95
    }
"""

from typing import Dict, Any, List, Tuple, Optional
import re
import time


# ============================================================================
# KEYWORD PATTERNS
# ============================================================================

# Compiled regex patterns for performance
WARD_KEYWORDS = re.compile(r'\b(xa|phuong|p\.|p(?=\s|$)|f\.|f(?=\s|$))\b', re.IGNORECASE)
# Note: "tp" (thanh pho) can be district-level OR province-level depending on context
# We include it in both patterns and rely on context resolution during parsing
DISTRICT_KEYWORDS = re.compile(r'\b(quan|huyen|q\.|q(?=\s|$)|h\.|h(?=\s|$)|tx|thi\s*xa|thanh\s*pho|tp|t\.?p\.?)\b', re.IGNORECASE)
PROVINCE_KEYWORDS = re.compile(r'\b(tinh|thanh\s*pho|tp|t\.?p\.?)\b', re.IGNORECASE)

# Noise patterns (organizations, contacts) that indicate non-parsable address
NOISE_PATTERNS = re.compile(
    r'\b(cong\s*ty|cty|chi\s*nhanh|van\s*phong|benh\s*vien|truong|'
    r'ngan\s*hang|ubnd|kho\s*bac|so\s+y\s*te|dt:|dd:|tel:|phone:|\d{10,})\b',
    re.IGNORECASE
)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def structural_parse(
    normalized_address: str,
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    delimiter_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main structural parsing function.

    Strategy:
    1. Detect if address has structural hints (separators/keywords)
    2. Parse using appropriate tier
    3. Return components with confidence score
    4. Return confidence=0 if no structure → triggers fallback to n-gram

    Args:
        normalized_address: Normalized text from Phase 1 (lowercase, no accents)
        province_known: Known province from raw data (optional, trusted)
        district_known: Known district from raw data (optional, trusted)
        delimiter_info: Delimiter information from Phase 1 (optional, for Phase 3 scoring)

    Returns:
        {
            'method': 'comma_keyword' | 'dash_keyword' | 'none',
            'confidence': float (always 0 to trigger Phase 3),
            'segments': List[Dict] with boost scores,
            'has_structure': bool,
            'delimiter_info': Dict from Phase 1 (passed through for Phase 3),
            'processing_time_ms': float
        }

    Example:
        >>> structural_parse("xa yen ho, duc tho", province_known="ha tinh")
        {
            'method': 'comma_keyword',
            'confidence': 0,
            'segments': [
                {'text': 'yen ho', 'keyword': 'xa', 'boost': 0.4},
                {'text': 'duc tho', 'keyword': None, 'boost': 0.2}
            ],
            'has_structure': True
        }
    """
    start_time = time.time()

    if not normalized_address:
        return _empty_result(0, delimiter_info)

    # Skip structural parsing if address contains organizational noise
    # These addresses are better handled by n-gram extraction
    if NOISE_PATTERNS.search(normalized_address):
        return _empty_result((time.time() - start_time) * 1000, delimiter_info)

    # Tier 1: Comma-separated parsing (highest confidence)
    if ',' in normalized_address:
        result = parse_comma_separated(normalized_address, province_known, district_known)
        # Always return result if has_structure (even if confidence=0)
        # Phase 3 will use segment_boundaries for scoring
        if result.get('has_structure'):
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            result['delimiter_info'] = delimiter_info
            return result

    # Tier 1b: Dash-separated parsing (treat like comma)
    if ' - ' in normalized_address or '-' in normalized_address:
        # Replace dash with comma and reuse comma parser
        normalized_dash = normalized_address.replace(' - ', ',').replace('-', ',')
        result = parse_comma_separated(normalized_dash, province_known, district_known)
        if result.get('has_structure'):
            result['method'] = 'dash_keyword'
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            result['delimiter_info'] = delimiter_info
            # Recalculate boundaries with dash as delimiter
            result['segment_boundaries'] = calculate_segment_boundaries(
                normalized_address, delimiter_chars=['-', ' - ']
            )
            return result

    # Tier 1c: Underscore-separated parsing (treat like comma)
    if '_' in normalized_address:
        # Replace underscore with comma and reuse comma parser
        normalized_underscore = normalized_address.replace('_', ',')
        result = parse_comma_separated(normalized_underscore, province_known, district_known)
        if result.get('has_structure'):
            result['method'] = 'underscore_keyword'
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            result['delimiter_info'] = delimiter_info
            # Recalculate boundaries with underscore as delimiter
            result['segment_boundaries'] = calculate_segment_boundaries(
                normalized_address, delimiter_chars=['_']
            )
            return result

    # No delimiter found - return confidence=0 to trigger n-gram fallback (Phase 3)
    # Phase 3 will handle keyword-based extraction
    return _empty_result((time.time() - start_time) * 1000, delimiter_info)


def _empty_result(processing_time_ms: float, delimiter_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return empty result indicating no structural parsing possible."""
    return {
        'method': 'none',
        'confidence': 0,
        'segments': [],
        'segment_boundaries': [],  # NEW: Empty boundaries when no structure
        'has_structure': False,
        'delimiter_info': delimiter_info,
        'processing_time_ms': round(processing_time_ms, 3)
    }


# ============================================================================
# TIER 1: COMMA-SEPARATED PARSER
# ============================================================================

def calculate_segment_boundaries(
    normalized_address: str,
    delimiter_chars: List[str] = None
) -> List[Tuple[int, int]]:
    """
    Calculate token index boundaries for each segment.
    
    Args:
        normalized_address: Full normalized text (e.g., "xa yen ho, duc tho, ha tinh")
        delimiter_chars: List of delimiter characters to split on
    
    Returns:
        List of (start_idx, end_idx) tuples for each segment
    
    Example:
        Input: "xa yen ho, duc tho, ha tinh"
        Output: [(0, 3), (3, 5), (5, 7)]
               segment 0: tokens[0:3] = "xa yen ho"
               segment 1: tokens[3:5] = "duc tho"  
               segment 2: tokens[5:7] = "ha tinh"
    """
    if delimiter_chars is None:
        delimiter_chars = [',', '-', '_']
    
    # Check if any delimiter exists
    has_delimiter = any(d in normalized_address for d in delimiter_chars)
    
    if not has_delimiter:
        # No delimiters → single segment covering all tokens
        tokens = normalized_address.split()
        return [(0, len(tokens))]
    
    # Split by all delimiters using regex
    pattern = '|'.join(re.escape(d) for d in delimiter_chars)
    segments = re.split(pattern, normalized_address)
    segments = [s.strip() for s in segments if s.strip()]
    
    boundaries = []
    current_pos = 0
    
    for seg in segments:
        seg_tokens = seg.split()
        seg_len = len(seg_tokens)
        if seg_len > 0:  # Only add non-empty segments
            boundaries.append((current_pos, current_pos + seg_len))
            current_pos += seg_len
    
    return boundaries


def parse_comma_separated(
    address: str,
    province_known: Optional[str],
    district_known: Optional[str]
) -> Dict[str, Any]:
    """
    Parse comma-separated address into scored segments.

    NEW Strategy (Scoring, not Decision):
    1. Split by comma into segments
    2. Extract keyword + name from each segment
    3. Calculate boost score based on:
       - Has keyword: +0.3
       - Position (later segments = higher boost)
       - Delimiter presence (comma/dash): +0.15 base
    4. Return segments with scores for Phase 3 to validate with DB
    5. NEW: Return segment_boundaries for n-gram containment scoring

    Example:
        "xa yen ho, duc tho" →
        segments = [
            {'text': 'yen ho', 'keyword': 'xa', 'position': 0, 'boost': 0.3},
            {'text': 'duc tho', 'keyword': None, 'position': 1, 'boost': 0.15}
        ]
        segment_boundaries = [(0, 3), (3, 5)]
        → Phase 3 validates with DB and picks valid matches

    Args:
        address: Normalized address text
        province_known: Known province (optional)
        district_known: Known district (optional)

    Returns:
        Segments with boost scores and segment_boundaries for containment scoring
    """

    # Split by comma and clean
    segments = [s.strip() for s in address.split(',') if s.strip()]

    if not segments:
        return {'method': 'none', 'confidence': 0, 'segments': [], 'segment_boundaries': []}

    # Calculate segment boundaries for n-gram containment scoring
    segment_boundaries = calculate_segment_boundaries(address, delimiter_chars=[','])

    # Parse each segment to extract keyword and calculate boost
    scored_segments = []
    for idx, seg in enumerate(segments):
        level, name, keyword = extract_segment_info(seg)

        # Skip empty or numeric-only segments
        if not name or name.isdigit():
            continue

        # Calculate boost score
        boost = 0.1  # Base delimiter bonus

        # Keyword bonus
        if keyword:
            boost += 0.3

        # Position bonus (later = higher, follows hierarchy)
        position_bonus = (idx / max(len(segments) - 1, 1)) * 0.1
        boost += position_bonus

        scored_segments.append({
            'text': name,
            'keyword': keyword,
            'keyword_level': level if level != 'unknown' else None,
            'position': idx,
            'boost': round(boost, 2)
        })

    return {
        'method': 'comma_keyword',
        'confidence': 0,  # Always 0 → Always run Phase 3 for DB validation
        'segments': scored_segments,
        'segment_boundaries': segment_boundaries,  # NEW: For n-gram containment scoring
        'has_structure': True
    }


def extract_segment_info(segment: str) -> Tuple[str, str, Optional[str]]:
    """
    Extract administrative level, name, and keyword from a segment.

    Args:
        segment: Single segment (e.g., "xa yen ho" or "duc tho")

    Returns:
        (level, name, keyword)
        - level: 'ward' | 'district' | 'province' | 'unknown'
        - name: Extracted place name
        - keyword: Matched keyword or None

    Example:
        "xa yen ho" → ('ward', 'yen ho', 'xa')
        "duc tho"   → ('unknown', 'duc tho', None)
        "huyen duc tho" → ('district', 'duc tho', 'huyen')
    """

    seg_lower = segment.lower().strip()
    tokens = seg_lower.split()

    if not tokens:
        return ('unknown', '', None)

    # Check for keywords (in order of specificity)
    ward_match = WARD_KEYWORDS.search(seg_lower)
    district_match = DISTRICT_KEYWORDS.search(seg_lower)
    province_match = PROVINCE_KEYWORDS.search(seg_lower)

    if ward_match:
        keyword = ward_match.group()
        name = extract_name_after_keyword(tokens, keyword)
        return ('ward', name, keyword)

    elif district_match:
        keyword = district_match.group()
        name = extract_name_after_keyword(tokens, keyword)
        return ('district', name, keyword)

    elif province_match:
        keyword = province_match.group()
        name = extract_name_after_keyword(tokens, keyword)
        return ('province', name, keyword)

    else:
        # No keyword found - return whole segment as unknown
        # (will be inferred later using position heuristics)
        return ('unknown', seg_lower, None)


def extract_name_after_keyword(tokens: List[str], keyword: str) -> str:
    """
    Extract place name after keyword.

    Strategy:
    - Find keyword position in tokens
    - Take next 1-3 tokens (84% of real names are 1-2 words)
    - IMPORTANT: For abbreviated keywords (p, p., q, q., h, h., f, f.), limit to 2 tokens max
    - Stop at next keyword or end of tokens
    - Validate against DB to prevent over-extraction

    Args:
        tokens: List of tokens in segment
        keyword: The matched keyword (e.g., 'xa', 'huyen', 'p', 'p.')

    Returns:
        Extracted name (e.g., 'yen ho', 'duc tho', 'nam ngan')

    Example:
        tokens = ['xa', 'yen', 'ho', 'huyen']
        keyword = 'xa'
        → returns 'yen ho' (stops at 'huyen')

        tokens = ['p', 'nam', 'ngan', 'thanh', 'hoa']
        keyword = 'p'
        → returns 'nam ngan' (2 tokens max for abbreviated keyword, validated via DB)
    """

    kw_lower = keyword.lower()

    # Find keyword position
    try:
        # Handle multi-word keywords like "thanh pho"
        if ' ' in kw_lower:
            kw_tokens = kw_lower.split()
            for i in range(len(tokens) - len(kw_tokens) + 1):
                if tokens[i:i+len(kw_tokens)] == kw_tokens:
                    kw_idx = i + len(kw_tokens) - 1
                    break
            else:
                return ''
        else:
            kw_idx = tokens.index(kw_lower)
    except ValueError:
        # Keyword not found (shouldn't happen)
        return ''

    # Determine max tokens based on keyword type
    # Abbreviated keywords (p, p., q, q., h, h., f, f.) → max 2 tokens
    # Full keywords (xa, phuong, quan, huyen) → max 3 tokens
    abbreviated_keywords = {'p', 'p.', 'q', 'q.', 'h', 'h.', 'f', 'f.', 'tx', 't.p', 't.p.', 'tp'}
    max_tokens = 2 if kw_lower in abbreviated_keywords else 3

    # Extract next 1-max_tokens after keyword
    name_tokens = []
    for i in range(kw_idx + 1, min(kw_idx + max_tokens + 1, len(tokens))):
        tok = tokens[i]

        # Stop at next keyword
        if (WARD_KEYWORDS.match(tok) or
            DISTRICT_KEYWORDS.match(tok) or
            PROVINCE_KEYWORDS.match(tok)):
            break

        name_tokens.append(tok)

    # Try to validate and refine using DB
    # Try from longest to shortest to find best match
    if len(name_tokens) > 1:
        from ..utils.db_utils import get_ward_set, get_district_set

        # Determine which set to check based on keyword type
        if WARD_KEYWORDS.match(kw_lower):
            valid_set = get_ward_set()
        elif DISTRICT_KEYWORDS.match(kw_lower):
            valid_set = get_district_set()
        else:
            valid_set = None

        if valid_set:
            # Try longest match first, then progressively shorter
            for length in range(len(name_tokens), 0, -1):
                candidate = ' '.join(name_tokens[:length])
                if candidate in valid_set:
                    return candidate

    return ' '.join(name_tokens)


# ============================================================================
# HIERARCHY RESOLUTION
# ============================================================================

def resolve_hierarchy(
    parsed_segments: List[Dict],
    province_known: Optional[str],
    district_known: Optional[str]
) -> Dict[str, str]:
    """
    Resolve unknown segments using context and position heuristics.

    Heuristics (from 100-sample analysis):
    1. Use known values (province/district) if provided (trusted 100%)
    2. Last unknown segment often = province (if not labeled)
    3. Unknown segment after ward = district
    4. First unknown segment (if short) = possible street/landmark (skip)

    Args:
        parsed_segments: List of parsed segments with levels
        province_known: Known province (trusted)
        district_known: Known district (trusted)

    Returns:
        Dict with resolved ward/district/province

    Example:
        segments = [
            {'level': 'ward', 'name': 'yen ho'},
            {'level': 'unknown', 'name': 'duc tho'}
        ]
        → infers unknown as district
        → returns {'ward': 'yen ho', 'district': 'duc tho'}
    """

    components = {}

    # Use known values first (trusted 100%)
    if province_known:
        components['province'] = province_known
    if district_known:
        components['district'] = district_known

    # Extract explicitly labeled segments
    for seg in parsed_segments:
        if seg['level'] in ['ward', 'district', 'province']:
            components[seg['level']] = seg['name']

    # Infer unknown segments using position heuristics
    unknown_segments = [(i, s) for i, s in enumerate(parsed_segments) if s['level'] == 'unknown']

    if unknown_segments:
        # Heuristic 1: Last unknown segment = province (if not already known)
        if not components.get('province') and len(parsed_segments) > 1:
            last_idx, last_seg = unknown_segments[-1]
            if last_idx == len(parsed_segments) - 1:  # Is last segment
                # Validate against province DB
                from ..utils.db_utils import get_province_set
                prov_set = get_province_set()
                if last_seg['name'] in prov_set:
                    components['province'] = last_seg['name']
                    unknown_segments = unknown_segments[:-1]  # Remove from unknowns

        # Heuristic 2: Unknown after ward = district
        if not components.get('district'):
            for i, (seg_idx, seg) in enumerate(unknown_segments):
                if seg_idx > 0:
                    prev_seg = parsed_segments[seg_idx - 1]
                    if prev_seg['level'] == 'ward':
                        # This unknown is likely district
                        components['district'] = seg['name']
                        break

        # Heuristic 3: If only one unknown and we have ward but no district
        if (not components.get('district') and
            components.get('ward') and
            len(unknown_segments) == 1):
            # Likely the unknown is district
            components['district'] = unknown_segments[0][1]['name']

    return components


def calculate_confidence(
    parsed_segments: List[Dict],
    components: Dict[str, str],
    province_known: Optional[str],
    district_known: Optional[str]
) -> float:
    """
    Calculate confidence score based on parsing quality.

    Factors:
    - Has keywords: +0.3 per level
    - Has known province: +0.1
    - Has known district: +0.1
    - Complete hierarchy: +0.1
    - Unknown segments inferred: -0.05 per unknown

    Args:
        parsed_segments: Parsed segments with levels
        components: Resolved components
        province_known: Known province
        district_known: Known district

    Returns:
        Confidence score (0-1)
    """

    confidence = 0.5  # Base score

    # Bonus for explicit keywords
    for seg in parsed_segments:
        if seg['level'] in ['ward', 'district', 'province']:
            confidence += 0.15

    # Bonus for known values
    if province_known:
        confidence += 0.1
    if district_known:
        confidence += 0.1

    # Bonus for complete hierarchy
    if components.get('ward') and components.get('district') and components.get('province'):
        confidence += 0.1

    # Penalty for inferred unknowns
    unknown_count = sum(1 for seg in parsed_segments if seg['level'] == 'unknown')
    confidence -= unknown_count * 0.05

    # Cap at 0.95 (never 100% confident without validation)
    return min(max(confidence, 0.0), 0.95)


# ============================================================================
# MAIN TEST
# ============================================================================

if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("xa yen ho, duc tho", "ha tinh", None),
        ("phuong dien bien, quan ba dinh", "ha noi", None),
        ("xa bac son huyen trang bom", None, None),
        ("hoan kiem ha noi", None, None),
    ]

    print("=" * 80)
    print("PHASE 2 STRUCTURAL PARSER - TEST")
    print("=" * 80)

    for i, (address, prov, dist) in enumerate(test_cases, 1):
        print(f"\n{i}. Address: {address}")
        if prov:
            print(f"   Province known: {prov}")

        result = structural_parse(address, prov, dist)

        print(f"   Method: {result['method']}")
        print(f"   Ward: {result['ward']}")
        print(f"   District: {result['district']}")
        print(f"   Province: {result['province']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Time: {result['processing_time_ms']:.2f}ms")
