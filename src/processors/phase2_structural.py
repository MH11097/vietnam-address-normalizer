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
DISTRICT_KEYWORDS = re.compile(r'\b(quan|huyen|q\.|q(?=\s|$)|h\.|h(?=\s|$)|tx|thi\s*xa)\b', re.IGNORECASE)
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
    district_known: Optional[str] = None
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

    Returns:
        {
            'method': 'comma_keyword' | 'keyword_only' | 'none',
            'ward': str or None,
            'district': str or None,
            'province': str or None,
            'confidence': float (0-1),
            'segments': List[Dict] (for debugging),
            'processing_time_ms': float
        }

    Example:
        >>> structural_parse("xa yen ho, duc tho", province_known="ha tinh")
        {
            'method': 'comma_keyword',
            'ward': 'yen ho',
            'district': 'duc tho',
            'province': 'ha tinh',
            'confidence': 0.95,
            'segments': [...]
        }
    """
    start_time = time.time()

    if not normalized_address:
        return _empty_result(0)

    # Skip structural parsing if address contains organizational noise
    # These addresses are better handled by n-gram extraction
    if NOISE_PATTERNS.search(normalized_address):
        return _empty_result((time.time() - start_time) * 1000)

    # Tier 1: Comma-separated parsing (highest confidence)
    if ',' in normalized_address:
        result = parse_comma_separated(normalized_address, province_known, district_known)
        if result['confidence'] > 0:
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            return result

    # Tier 1b: Dash-separated parsing (treat like comma)
    if ' - ' in normalized_address or '-' in normalized_address:
        # Replace dash with comma and reuse comma parser
        normalized_dash = normalized_address.replace(' - ', ',').replace('-', ',')
        result = parse_comma_separated(normalized_dash, province_known, district_known)
        if result['confidence'] > 0:
            result['method'] = 'dash_keyword'
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            return result

    # Tier 2: Keyword-only parsing (medium confidence)
    if has_keywords(normalized_address):
        result = parse_keyword_only(normalized_address, province_known, district_known)
        if result['confidence'] > 0:
            result['processing_time_ms'] = (time.time() - start_time) * 1000
            return result

    # No structure found - return confidence=0 to trigger n-gram fallback
    return _empty_result((time.time() - start_time) * 1000)


def _empty_result(processing_time_ms: float) -> Dict[str, Any]:
    """Return empty result indicating no structural parsing possible."""
    return {
        'method': 'none',
        'ward': None,
        'district': None,
        'province': None,
        'confidence': 0,
        'segments': [],
        'processing_time_ms': round(processing_time_ms, 3)
    }


def has_keywords(address: str) -> bool:
    """Check if address contains any administrative keywords."""
    return bool(
        WARD_KEYWORDS.search(address) or
        DISTRICT_KEYWORDS.search(address) or
        PROVINCE_KEYWORDS.search(address)
    )


# ============================================================================
# TIER 1: COMMA-SEPARATED PARSER
# ============================================================================

def parse_comma_separated(
    address: str,
    province_known: Optional[str],
    district_known: Optional[str]
) -> Dict[str, Any]:
    """
    Parse comma-separated address.

    Strategy:
    1. Split by comma into segments
    2. Extract keyword + name from each segment
    3. Label segments (ward/district/province/unknown)
    4. Resolve unknown segments using position heuristics
    5. Calculate confidence based on completeness

    Example:
        "xa yen ho, duc tho" →
        segments = [
            {'level': 'ward', 'name': 'yen ho', 'keyword': 'xa'},
            {'level': 'unknown', 'name': 'duc tho', 'keyword': None}
        ]
        → resolve → district='duc tho'

    Args:
        address: Normalized address text
        province_known: Known province (optional)
        district_known: Known district (optional)

    Returns:
        Parsed components with confidence score
    """

    # Split by comma and clean
    segments = [s.strip() for s in address.split(',') if s.strip()]

    if not segments:
        return {'method': 'none', 'confidence': 0}

    # Parse each segment to extract level, name, keyword
    parsed_segments = []
    for seg in segments:
        level, name, keyword = extract_segment_info(seg)
        parsed_segments.append({
            'original': seg,
            'level': level,      # 'ward' | 'district' | 'province' | 'unknown'
            'name': name,
            'keyword': keyword
        })

    # Resolve hierarchy (infer unknown segments from context)
    components = resolve_hierarchy(
        parsed_segments,
        province_known,
        district_known
    )

    # Calculate confidence based on completeness and structure quality
    confidence = calculate_confidence(parsed_segments, components, province_known, district_known)

    return {
        'method': 'comma_keyword',
        'ward': components.get('ward'),
        'district': components.get('district'),
        'province': components.get('province'),
        'confidence': confidence,
        'segments': parsed_segments
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
    - Stop at next keyword or end of tokens

    Args:
        tokens: List of tokens in segment
        keyword: The matched keyword (e.g., 'xa', 'huyen')

    Returns:
        Extracted name (e.g., 'yen ho', 'duc tho')

    Example:
        tokens = ['xa', 'yen', 'ho', 'huyen']
        keyword = 'xa'
        → returns 'yen ho' (stops at 'huyen')
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

    # Extract next 1-3 tokens after keyword
    name_tokens = []
    for i in range(kw_idx + 1, min(kw_idx + 4, len(tokens))):
        tok = tokens[i]

        # Stop at next keyword
        if (WARD_KEYWORDS.match(tok) or
            DISTRICT_KEYWORDS.match(tok) or
            PROVINCE_KEYWORDS.match(tok)):
            break

        name_tokens.append(tok)

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
# TIER 2: KEYWORD-ONLY PARSER
# ============================================================================

def parse_keyword_only(
    address: str,
    province_known: Optional[str],
    district_known: Optional[str]
) -> Dict[str, Any]:
    """
    Parse address with keywords but no separators.

    Strategy:
    - Scan tokens for keywords
    - Check if keyword is standalone (not part of compound name)
    - Extract 1-3 tokens after each keyword
    - Stop at next keyword

    IMPORTANT: Handle ambiguous cases like "phuc xa ba dinh"
    - "phuc xa" is a ward name (not "phuc" + keyword "xa")
    - Need to check if keyword appears at position > 0 without preceding uppercase/special context

    Example:
        "xa yen ho huyen duc tho" → ward='yen ho', district='duc tho'
        "phuc xa ba dinh" → ward='phuc xa', district='ba dinh' (NOT ward='ba dinh')

    Args:
        address: Normalized address
        province_known: Known province
        district_known: Known district

    Returns:
        Parsed components with confidence
    """

    tokens = address.lower().split()
    components = {}
    used_indices = set()  # Track which token indices have been consumed

    i = 0
    while i < len(tokens):
        if i in used_indices:
            i += 1
            continue

        tok = tokens[i]

        # Check if current token is a standalone keyword
        # HEURISTIC: If keyword appears after another token AND next token exists,
        # check if this is compound name (e.g., "phuc xa") vs keyword
        is_standalone_keyword = False

        if WARD_KEYWORDS.match(tok) or DISTRICT_KEYWORDS.match(tok) or PROVINCE_KEYWORDS.match(tok):
            # Check context: is this a standalone keyword or part of name?
            if i == 0:
                # First token → likely standalone keyword
                is_standalone_keyword = True
            elif i > 0 and i < len(tokens) - 1:
                # Middle position → check if forms compound name
                # Heuristic: If previous token + current tok exists in DB, it's a name
                # For now: use simpler rule - keyword at position 1-2 in short address
                # is likely part of name if followed by known admin term
                prev_tok = tokens[i-1]
                next_tok = tokens[i+1] if i+1 < len(tokens) else ''

                # Check if next token is a known district/province name
                from ..utils.db_utils import get_district_set, get_province_set
                dist_set = get_district_set()
                prov_set = get_province_set()

                if next_tok in dist_set or next_tok in prov_set or (i+2 < len(tokens) and f"{next_tok} {tokens[i+2]}" in dist_set):
                    # Next token is admin name → current 'xa'/'phuong' might be part of compound
                    # Check: "phuc xa" where "xa" is suffix of ward name
                    # If previous token exists, treat "prev + xa" as compound name
                    if i == 1 and len(tokens) <= 4:  # Short address, keyword at position 1
                        # Likely compound: "phuc xa" not "phuc" + keyword "xa"
                        is_standalone_keyword = False
                    else:
                        is_standalone_keyword = True
                else:
                    # Standard case
                    is_standalone_keyword = True
            else:
                is_standalone_keyword = True

        if not is_standalone_keyword:
            i += 1
            continue

        # Process standalone keyword
        if WARD_KEYWORDS.match(tok):
            name = extract_name_from_tokens(tokens[i+1:])
            if name:
                components['ward'] = name
                # Mark tokens as used
                used_indices.add(i)
                for j in range(i+1, i+1+len(name.split())):
                    used_indices.add(j)
                i += len(name.split()) + 1
            else:
                i += 1

        elif DISTRICT_KEYWORDS.match(tok):
            name = extract_name_from_tokens(tokens[i+1:])
            if name:
                components['district'] = name
                used_indices.add(i)
                for j in range(i+1, i+1+len(name.split())):
                    used_indices.add(j)
                i += len(name.split()) + 1
            else:
                i += 1

        elif PROVINCE_KEYWORDS.match(tok):
            name = extract_name_from_tokens(tokens[i+1:])
            if name:
                components['province'] = name
                used_indices.add(i)
                for j in range(i+1, i+1+len(name.split())):
                    used_indices.add(j)
                i += len(name.split()) + 1
            else:
                i += 1

        else:
            i += 1

    # Fallback: If nothing extracted, try n-gram approach
    # For "phuc xa ba dinh" → check if "phuc xa" + "ba dinh" both exist in DB
    if not components.get('ward') and not components.get('district'):
        # Try to parse as "name1 name2" without keywords
        components = _parse_no_keywords_fallback(tokens, province_known, district_known)

    # Use known values if extracted values are missing
    if province_known and not components.get('province'):
        components['province'] = province_known
    if district_known and not components.get('district'):
        components['district'] = district_known

    # Calculate confidence (lower than comma-separated)
    confidence = 0.65  # Base
    if components.get('ward'):
        confidence += 0.1
    if components.get('district'):
        confidence += 0.1
    if components.get('province'):
        confidence += 0.05
    if province_known or district_known:
        confidence += 0.05

    return {
        'method': 'keyword_only',
        'confidence': min(confidence, 0.85),  # Max 0.85 for keyword-only
        'ward': components.get('ward'),
        'district': components.get('district'),
        'province': components.get('province'),
        'segments': []  # No segments for keyword-only
    }


def _parse_no_keywords_fallback(
    tokens: List[str],
    province_known: Optional[str],
    district_known: Optional[str]
) -> Dict[str, str]:
    """
    Fallback parser for addresses with embedded keywords in names.

    Example: "phuc xa ba dinh" where "phuc xa" is ward, "ba dinh" is district

    Strategy:
    - Try 2-word + 2-word split
    - Try 2-word + 1-word split
    - Validate against DB
    """
    from ..utils.db_utils import get_ward_set, get_district_set

    ward_set = get_ward_set()
    dist_set = get_district_set()

    components = {}

    # Try split: first 2 words = ward, last 2 words = district
    if len(tokens) == 4:
        candidate_ward = f"{tokens[0]} {tokens[1]}"
        candidate_dist = f"{tokens[2]} {tokens[3]}"

        if candidate_ward in ward_set and candidate_dist in dist_set:
            components['ward'] = candidate_ward
            components['district'] = candidate_dist
            return components

    # Try split: first 2 words = ward, last 1 word = district
    if len(tokens) >= 3:
        candidate_ward = f"{tokens[0]} {tokens[1]}"
        candidate_dist = tokens[2]

        if candidate_ward in ward_set and candidate_dist in dist_set:
            components['ward'] = candidate_ward
            components['district'] = candidate_dist
            return components

    return components


def extract_name_from_tokens(tokens: List[str]) -> str:
    """
    Extract place name from tokens until next keyword (max 3 tokens).

    IMPORTANT: Skip first token if it contains keyword as suffix
    (e.g., "phuc xa" where "xa" is part of name, not keyword)

    Args:
        tokens: Remaining tokens after keyword

    Returns:
        Extracted name (1-3 words)
    """
    name_tokens = []
    for i, tok in enumerate(tokens[:3]):  # Max 3 words (covers 84% of real names)
        # Stop at next keyword (but only if it's a standalone keyword at token start)
        # This prevents "xa" in "phuc xa" from being treated as keyword
        if i > 0 and (  # Only check after first token
            WARD_KEYWORDS.match(tok) or
            DISTRICT_KEYWORDS.match(tok) or
            PROVINCE_KEYWORDS.match(tok)):
            break
        name_tokens.append(tok)

    return ' '.join(name_tokens)


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
