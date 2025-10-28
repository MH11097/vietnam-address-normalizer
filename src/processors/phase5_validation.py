"""
Phase 5: Validation & Ranking

Input: Candidates from Phase 4
Output: Validated and ranked results with best match
"""
from typing import Dict, Any, List
import time
import logging
from ..utils.db_utils import validate_hierarchy as db_validate_hierarchy

logger = logging.getLogger(__name__)


def _get_source_multiplier(source: str) -> float:
    """
    Get reliability multiplier for different sources.

    Args:
        source: Source identifier string

    Returns:
        Multiplier (0.5-1.0)
    """
    source_multipliers = {
        # Database sources (highest reliability)
        'db_exact_match': 1.0,
        'multi_candidate_full': 1.0,

        # Disambiguation sources
        'disambiguation_as_ward': 0.95,
        'disambiguation_as_district': 0.9,

        # OSM sources
        'osm_nominatim_bbox': 0.9,
        'osm_nominatim_query': 0.85,

        # Street-based (lower reliability)
        'street_based': 0.7,

        # Fallback sources
        'province_only_no_db': 0.5,
    }

    return source_multipliers.get(source, 0.8)  # Default: 0.8


def calculate_confidence_score(candidate: Dict[str, Any], normalized_text: str = None) -> float:
    """
    Simplified confidence scoring using proximity-based approach.

    Formula components (4 components):
    1. Base Fuzzy Scores (40%) - Average of province/district/ward scores
    2. Proximity Score (30%) - Token distance between components
    3. Completeness (20%) - Full address > partial address
    4. Hierarchy Validation (10%) - Valid geographic hierarchy

    Then apply:
    5. Order Bonus (×1.1) - If components in correct geographic order
    6. Source Reliability (optional adjustment for non-DB sources)

    NOTE: If candidate already has 'combined_score' from Phase 2, use it directly
    (Phase 2 already calculates this formula during candidate generation).

    Args:
        candidate: Candidate dict with match details (province_score/district_score/ward_score should be 0-1)
        normalized_text: Normalized address text (optional, unused in simplified version)

    Returns:
        Normalized final confidence score (0.0-1.0)
    """
    # If Phase 2 already calculated combined_score with proximity, use it
    # (This is the case for db_exact_match candidates from generate_candidate_combinations)
    if 'combined_score' in candidate and 'proximity_score' in candidate:
        # Phase 2 already did the calculation
        base_confidence = candidate['combined_score']

        # Apply source reliability adjustment for non-DB sources (OSM, disambiguation, etc.)
        source = candidate.get('source', 'db_exact_match')
        source_multiplier = _get_source_multiplier(source)

        # CHANGED: No cap - preserve full position-based scoring information
        # Scores can be > 1.0 (e.g., 1.26, 1.5, 2.0) - this is weighted confidence, not probability
        # Higher scores indicate better matches with position bonuses applied
        return base_confidence * source_multiplier

    # Legacy path: Calculate from scratch (for candidates not from Phase 2)
    # This handles OSM/Goong/disambiguation candidates added in Phase 3
    # Use simplified formula with 4 components

    # Component 1: Base fuzzy scores (40%)
    prov_score = candidate.get('province_score', 0)
    dist_score = candidate.get('district_score', 0)
    ward_score = candidate.get('ward_score', 0)

    scores = [s for s in [prov_score, dist_score, ward_score] if s > 0]
    base_fuzzy = sum(scores) / len(scores) if scores else 0.5

    # Component 2: Proximity score (30%)
    # For OSM/disambiguation candidates, we don't have token positions
    # Use a heuristic: if all 3 levels present, assume good proximity
    at_rule = candidate.get('at_rule', 0)
    if at_rule == 3:
        proximity = 0.9  # Assume good proximity for full addresses
    elif at_rule == 2:
        proximity = 0.7  # Medium proximity for partial
    else:
        proximity = 0.5  # Neutral for province-only

    # Component 3: Completeness (20%)
    if at_rule == 3:
        completeness = 1.0
    elif at_rule == 2:
        completeness = 0.7
    else:
        completeness = 0.4

    # Component 4: Hierarchy validation (10%)
    hierarchy_valid = candidate.get('hierarchy_valid', False)
    hierarchy = 1.0 if hierarchy_valid else 0.0

    # Combined score
    combined = (
        base_fuzzy * 0.4 +
        proximity * 0.3 +
        completeness * 0.2 +
        hierarchy * 0.1
    )

    # Apply source multiplier
    source = candidate.get('source', '')
    source_multiplier = _get_source_multiplier(source)

    # Special handling for OSM importance
    if 'osm' in source:
        osm_importance = candidate.get('osm_importance', 0.5)
        source_multiplier *= (0.5 + osm_importance * 0.5)  # Scale 0.5-1.0

    # District mismatch penalty
    district_mismatch = candidate.get('district_mismatch', False)
    if district_mismatch:
        combined *= 0.3  # -70% penalty

    final_confidence = min(combined * source_multiplier, 1.0)

    return round(final_confidence, 3)


def validate_hierarchy(candidate: Dict[str, Any]) -> bool:
    """
    Validate that province-district-ward hierarchy is correct using database.

    Checks:
    - Ward belongs to district
    - District belongs to province
    - Geographic hierarchy is valid in admin_divisions table

    Args:
        candidate: Candidate dict with province/district/ward

    Returns:
        True if hierarchy is valid, False otherwise

    Note:
        OSM candidates are always considered valid (skip DB validation)
        because they come from external geocoding service
    """
    # Skip validation for OSM candidates (external source, may not be in DB)
    source = candidate.get('source', '')
    if 'osm' in source:
        return True

    province = candidate.get('province')
    district = candidate.get('district')
    ward = candidate.get('ward')
    at_rule = candidate.get('at_rule', 0)

    # Basic validation - check components exist at expected levels
    if at_rule >= 3 and not (province and district and ward):
        return False

    if at_rule >= 2 and not (province and district):
        return False

    if at_rule >= 1 and not province:
        return False

    # Database validation using real DB lookup
    if at_rule >= 1:
        # Validate against database
        is_valid = db_validate_hierarchy(province, district, ward)
        return is_valid

    return True


def rank_candidates(candidates: List[Dict[str, Any]], normalized_text: str = None) -> List[Dict[str, Any]]:
    """
    Rank candidates by multiple criteria.

    Sorting order:
    1. Confidence score (descending)
    2. Match type (exact > fuzzy > fallback)
    3. At rule level (3 > 2 > 1 > 0)

    Args:
        candidates: List of candidate dicts
        normalized_text: Normalized address text for coverage calculation (optional)

    Returns:
        Sorted list of candidates
    """
    # Calculate confidence for each candidate
    for candidate in candidates:
        candidate['final_confidence'] = calculate_confidence_score(candidate, normalized_text)
        candidate['hierarchy_valid'] = validate_hierarchy(candidate)

    # Sort by confidence, match type, and at_rule
    match_type_priority = {'exact': 3, 'fuzzy': 2, 'hierarchical_fallback': 1}

    sorted_candidates = sorted(
        candidates,
        key=lambda x: (
            x.get('final_confidence', 0),
            match_type_priority.get(x.get('match_type', ''), 0),
            x.get('at_rule', 0)
        ),
        reverse=True
    )

    return sorted_candidates


def validate_and_rank(candidates_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main validation and ranking function.

    Args:
        candidates_result: Output from Phase 3

    Returns:
        Dictionary containing:
        - validated_candidates: List of validated candidates
        - best_match: Top-ranked candidate
        - all_valid: Whether all candidates passed validation
        - processing_time_ms: Processing time

    Example:
        >>> validate_and_rank({'candidates': [...]})
        {
            'validated_candidates': [...],
            'best_match': {...},
            'all_valid': True,
            'processing_time_ms': 0.2
        }
    """
    start_time = time.time()

    logger.debug("[🔍 DEBUG] " + "═" * 76)
    logger.debug("[🔍 DEBUG] [PHASE 4] VALIDATION & RANKING")

    candidates = candidates_result.get('candidates', [])
    logger.debug(f"[🔍 DEBUG]   📥 Input: {len(candidates)} candidates")

    if not candidates:
        logger.debug(f"[🔍 DEBUG]   ⚠ No candidates to validate")
        logger.debug("[🔍 DEBUG] " + "═" * 76 + "\n")
        return {
            'validated_candidates': [],
            'best_match': None,
            'all_valid': True,
            'processing_time_ms': 0.0,
            'error': 'No candidates to validate'
        }

    # Get normalized text from Phase 1 (for text coverage calculation)
    # Phase 3 should pass this through from Phase 1
    normalized_text = candidates_result.get('normalized_text')

    logger.debug(f"[🔍 DEBUG]   🔧 Tác vụ: Validate hierarchy + Rank by confidence")

    # Rank candidates
    ranked_candidates = rank_candidates(candidates, normalized_text)

    logger.debug(f"[🔍 DEBUG]   📤 Ranked {len(ranked_candidates)} candidates:")
    for i, cand in enumerate(ranked_candidates[:5], 1):
        valid_icon = "✓" if cand.get('hierarchy_valid') else "✗"
        logger.debug(f"[🔍 DEBUG]      {i}. [{cand.get('final_confidence', 0):.3f}] {valid_icon} "
                    f"{cand.get('ward') or 'None'} | {cand.get('district') or 'None'} | {cand.get('province')}")

    # Select best match
    best_match = ranked_candidates[0] if ranked_candidates else None

    if best_match:
        logger.debug(f"\n[🔍 DEBUG]   🏆 BEST MATCH:")
        logger.debug(f"[🔍 DEBUG]      {best_match.get('ward') or 'None'} | "
                    f"{best_match.get('district') or 'None'} | {best_match.get('province')}")
        logger.debug(f"[🔍 DEBUG]      Confidence: {best_match.get('final_confidence', 0):.3f}")

    # Check if all valid
    all_valid = all(c.get('hierarchy_valid', False) for c in ranked_candidates)

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

    logger.debug(f"[🔍 DEBUG]   ⏱ Time: {processing_time:.3f}ms")
    logger.debug("[🔍 DEBUG] " + "═" * 76 + "\n")

    return {
        'validated_candidates': ranked_candidates,
        'best_match': best_match,
        'all_valid': all_valid,
        'num_validated': len(ranked_candidates),
        'processing_time_ms': round(processing_time, 3)
    }


if __name__ == "__main__":
    # Test examples
    test_candidates = {
        'candidates': [
            {
                'province': 'hanoi',
                'district': 'badinh',
                'ward': 'dienbien',
                'match_type': 'exact',
                'at_rule': 3,
                'confidence': 1.0
            },
            {
                'province': 'ha noi',
                'district': 'ba dinh',
                'ward': None,
                'match_type': 'fuzzy',
                'at_rule': 2,
                'confidence': 0.85
            },
            {
                'province': 'hanoi',
                'district': None,
                'ward': None,
                'match_type': 'hierarchical_fallback',
                'at_rule': 1,
                'confidence': 0.4
            }
        ]
    }

    print("=" * 80)
    print("PHASE 4: VALIDATION & RANKING TEST")
    print("=" * 80)

    result = validate_and_rank(test_candidates)

    print(f"\nCandidates validated: {result['num_validated']}")
    print(f"All valid: {result['all_valid']}")
    print(f"Processing time: {result['processing_time_ms']}ms")

    print("\nRanked candidates:")
    for i, candidate in enumerate(result['validated_candidates'], 1):
        print(f"\n{i}. Province: {candidate['province']}, District: {candidate['district']}, Ward: {candidate['ward']}")
        print(f"   Type: {candidate['match_type']}, At rule: {candidate['at_rule']}")
        print(f"   Original confidence: {candidate['confidence']:.2f}")
        print(f"   Final confidence: {candidate['final_confidence']:.3f}")
        print(f"   Hierarchy valid: {candidate['hierarchy_valid']}")

    if result['best_match']:
        print("\nBest match:")
        best = result['best_match']
        print(f"  {best['province']} / {best['district']} / {best['ward']}")
        print(f"  Confidence: {best['final_confidence']:.3f}")
