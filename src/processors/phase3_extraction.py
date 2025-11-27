"""
Phase 3: Entity Extraction (Database-based)

Input: Preprocessed address dict from Phase 1
Output: Extracted address components (province, district, ward)

Strategy: Use database n-gram matching instead of regex patterns.
Works WITHOUT keywords (phuong, quan, tinh) for real-world addresses.
"""
from typing import Dict, Any, Optional
import time
import logging
from ..utils.extraction_utils import extract_with_database, generate_candidate_combinations
from ..utils.text_utils import normalize_hint

logger = logging.getLogger(__name__)


def extract_components(
    preprocessed: Dict[str, Any],
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    phase2_segments: list = None
) -> Dict[str, Any]:
    """
    Extract components and generate LOCAL candidates from database.

    Phase 3 Responsibilities:
    1. Extract potentials from normalized text via n-gram matching
    2. Apply boost scores from Phase 2 (delimiter/keyword bonuses)
    3. Generate all valid candidate combinations from potentials
    4. Validate hierarchy for each candidate
    5. Return ranked candidates ready for Phase 4

    Args:
        preprocessed: Output from Phase 1 preprocessing
        province_known: Known province from raw data (optional, trusted 100%)
        district_known: Known district from raw data (optional, trusted 100%)
        phase2_segments: Segments with boost scores from Phase 2 (optional)

    Returns:
        Dictionary containing:
        - candidates: List of candidate combinations ready for Phase 3, each with:
            - province, district, ward: Component names
            - province_score, district_score, ward_score: Scores (0-1)
            - combined_score: Average of non-zero scores
            - match_level: 0-3 (0=none, 1=province, 2=district, 3=ward)
            - confidence: Confidence score (0-1)
            - source: 'db_exact_match' | 'street_based'
            - hierarchy_valid: Whether hierarchy is valid
        - processing_time_ms: Processing time
        - geographic_known_used: Whether known values were provided
        - normalized_text: Normalized address text (for Phase 4 coverage scoring)
        - potential_*: All potential matches (for debugging)

    Example:
        >>> extract_components({'normalized': 'bach khoa ha noi'}, province_known='ha noi')
        {
            'candidates': [
                {
                    'province': 'ha noi',
                    'district': None,
                    'ward': 'bach khoa',
                    'province_score': 1.0,
                    'district_score': 0.0,
                    'ward_score': 1.0,
                    'combined_score': 100.0,
                    'match_level': 3,
                    'confidence': 1.0,
                    'source': 'db_exact_match',
                    'hierarchy_valid': True
                }
            ],
            'processing_time_ms': 1.1,
            'geographic_known_used': True,
            'normalized_text': 'bach khoa ha noi'
        }
    """
    start_time = time.time()

    normalized_text = preprocessed.get('normalized', '')

    # Log entry with token count
    tokens = normalized_text.split() if normalized_text else []
    logger.debug(f"[PHASE 3] Starting extraction with {len(tokens)} tokens: {tokens}")

    if not normalized_text:
        logger.debug("[PHASE 3] No normalized text to extract")
        return {
            'candidates': [],
            'processing_time_ms': 0.0,
            'geographic_known_used': False,
            'normalized_text': '',
            'potential_provinces': [],
            'potential_districts': [],
            'potential_wards': [],
            'potential_streets': [],
            'error': 'No normalized text'
        }

    # Normalize known values if provided
    # Use normalize_hint() to strip administrative prefixes (thanh pho, quan, phuong)
    prov_known_norm = None
    dist_known_norm = None

    if province_known:
        prov_known_norm = normalize_hint(province_known)
        logger.debug(f"[PHASE 3] Known province: '{province_known}' -> normalized: '{prov_known_norm}'")
    if district_known:
        dist_known_norm = normalize_hint(district_known)
        logger.debug(f"[PHASE 3] Known district: '{district_known}' -> normalized: '{dist_known_norm}'")

    # Step 1: Extract potentials from database
    logger.debug(f"[PHASE 3] Step 1: Extracting potentials from database")
    # Pass original text (before abbreviation expansion) for direct match bonus
    original_text_for_matching = preprocessed.get('no_accent', preprocessed.get('unicode_normalized'))
    # Get delimiter info from preprocessing (if available)
    delimiter_info = preprocessed.get('delimiter_info')
    extraction_result = extract_with_database(
        normalized_text,
        province_known=prov_known_norm,
        district_known=dist_known_norm,
        original_text_for_matching=original_text_for_matching,
        phase2_segments=phase2_segments or [],
        delimiter_info=delimiter_info
    )
    
    # Log extraction results
    prov_count = len(extraction_result.get('potential_provinces', []))
    dist_count = len(extraction_result.get('potential_districts', []))
    ward_count = len(extraction_result.get('potential_wards', []))
    logger.debug(f"[PHASE 3] Extracted: {prov_count} provinces, {dist_count} districts, {ward_count} wards")

    # Step 2: Use candidates from extraction (already includes token positions)
    # Candidates from build_search_tree() already have normalized_tokens and token positions
    candidates = extraction_result.get('candidates', [])
    if not candidates:
        # Fallback: Generate candidates from potentials (old method)
        logger.debug(f"[PHASE 3] Step 2: No candidates from extraction, generating from potentials")
        candidates = generate_candidate_combinations(
            extraction_result,
            max_candidates=5
        )
    else:
        logger.debug(f"[PHASE 3] Step 2: Using {len(candidates)} candidates from extraction (with token positions)")

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

    # Log exit summary
    logger.debug(f"[PHASE 3] Generated {len(candidates)} candidates in {processing_time:.2f}ms")
    if candidates:
        best = candidates[0]
        logger.debug(f"[PHASE 3] Best candidate: {best.get('ward') or 'None'} | {best.get('district') or 'None'} | {best.get('province')} (score: {best.get('combined_score', 0):.3f})")

    # Build result with candidates-first structure
    result = {
        'candidates': candidates,
        'processing_time_ms': round(processing_time, 3),
        'geographic_known_used': prov_known_norm is not None or dist_known_norm is not None,
        'original_address': preprocessed.get('original', ''),
        # Pass through potentials from extraction_result
        'potential_provinces': extraction_result.get('potential_provinces', []),
        'potential_districts': extraction_result.get('potential_districts', []),
        'potential_wards': extraction_result.get('potential_wards', []),
        'potential_streets': extraction_result.get('potential_streets', []),
        # Pass through best match values for Phase 3 (needed by generate_candidate_combinations)
        'province': extraction_result.get('province'),
        'district': extraction_result.get('district'),
        'ward': extraction_result.get('ward'),
        'province_score': extraction_result.get('province_score', 0),
        'district_score': extraction_result.get('district_score', 0),
        'ward_score': extraction_result.get('ward_score', 0),
        # Pass through normalized text from Phase 1 for Phase 4 coverage scoring
        'normalized_text': preprocessed.get('normalized', '')
    }

    # Add known values for OSM context enhancement in Phase 3
    if prov_known_norm:
        result['province_known'] = prov_known_norm
    if dist_known_norm:
        result['district_known'] = dist_known_norm

    
    return result


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
    print("PHASE 2: EXTRACTION & CANDIDATE GENERATION TEST")
    print("=" * 80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Input: {test['normalized']}")

        preprocessed = {'normalized': test['normalized']}
        result = extract_components(preprocessed)

        print(f"   Candidates generated: {len(result.get('candidates', []))}")
        if result.get('candidates'):
            best = result['candidates'][0]
            print(f"   Best candidate:")
            print(f"     Province:  {best.get('province')}")
            print(f"     District:  {best.get('district')}")
            print(f"     Ward:      {best.get('ward')}")
            print(f"     Confidence: {best.get('confidence', 0):.2f}")
            print(f"     Source:    {best.get('source')}")
        print(f"   Time:      {result['processing_time_ms']}ms")
