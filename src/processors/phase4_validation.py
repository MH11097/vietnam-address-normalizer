"""
Phase 4: Validation & Ranking

Input: Candidates from Phase 3
Output: Validated and ranked results with best match
"""
from typing import Dict, Any, List
import time
from ..utils.db_utils import validate_hierarchy as db_validate_hierarchy


def calculate_confidence_score(candidate: Dict[str, Any]) -> float:
    """
    Enhanced confidence scoring với source reliability weighting.

    Formula components (total 110 points):
    1. Match Type Score (0-50 points)
    2. At Rule Score (0-30 points)
    3. String Similarity Score (0-15 points)
    4. Source Reliability Score (0-15 points) - NEW
    5. Geographic Context Bonus (+10%)
    6. Hierarchy Validation Penalty (-20%)

    Args:
        candidate: Candidate dict with match details

    Returns:
        Normalized final confidence score (0.0-1.0)
    """
    # Component 1: Match Type Score (0-50 points)
    match_type_weights = {
        'exact': 50,
        'fuzzy': 30,
        'hierarchical_fallback': 20,
        'db_exact_match': 50,
        'set_exact_match': 45,
        'ensemble_fuzzy_match': 30,
        'disambiguation': 40,  # NEW
        'osm': 35,  # NEW
        'lcs_ward_fallback': 20,
        'lcs_district_fallback': 18,
        'lcs_province_fallback': 15
    }

    match_type = candidate.get('match_type', '')
    match_type_score = match_type_weights.get(match_type, 25)

    # Component 2: At Rule Score (0-30 points)
    at_rule = candidate.get('at_rule', 0)
    at_rule_score = {
        3: 30,  # Full address (province + district + ward)
        2: 20,  # Partial (province + district)
        1: 10,  # Province only
        0: 0    # Failed
    }.get(at_rule, 0)

    # Component 3: String Similarity Score (0-15 points) - reduced from 20
    prov_score = candidate.get('province_score', 0)
    dist_score = candidate.get('district_score', 0)
    ward_score = candidate.get('ward_score', 0)

    if prov_score or dist_score or ward_score:
        # Weighted average of component scores
        similarity_scores = []
        if prov_score:
            similarity_scores.append((prov_score, 0.3))
        if dist_score:
            similarity_scores.append((dist_score, 0.3))
        if ward_score:
            similarity_scores.append((ward_score, 0.4))

        total_weight = sum(w for _, w in similarity_scores)
        avg_similarity = sum(s * w for s, w in similarity_scores) / total_weight if total_weight > 0 else 0.5
        string_similarity_score = avg_similarity * 15  # Max 15 points
    else:
        # Fallback to candidate's base confidence
        base_conf = candidate.get('confidence', 0.5)
        string_similarity_score = base_conf * 15

    # Component 4: Source Reliability Score (0-15 points) - NEW
    source = candidate.get('source', '')
    source_weights = {
        # Local database sources (highest trust)
        'db_exact_match': 15,
        'multi_candidate_full': 14,
        'set_exact_match': 13,
        'multi_candidate_inferred_district': 12,
        'ensemble_fuzzy_match': 10,

        # Disambiguation sources (high trust)
        'disambiguation_as_ward': 13,
        'disambiguation_as_district': 12,
        'disambiguation_ward_as_district': 11,

        # OSM sources (medium-high trust)
        'osm_nominatim_bbox': 10,  # Province-specific bbox (higher trust)
        'osm_nominatim_query': 9,  # Province in query (slightly lower trust)
        'osm_nominatim': 9,
        'osm_nominatim_alt': 7,

        # Street-based sources (low-medium trust - lower than ward matches)
        'street_based': 6,  # District inferred from street name (less reliable than direct ward match)

        # Fallback sources (lower trust)
        'lcs_ward_fallback': 5,
        'lcs_district_fallback': 4,
        'lcs_province_fallback': 3,
        'province_only_no_db': 2
    }
    source_score = source_weights.get(source, 7)  # Default: 7

    # If OSM: use importance as multiplier
    if 'osm' in source:
        osm_importance = candidate.get('osm_importance', 0.5)
        source_score *= osm_importance

    # Calculate base score (0-110)
    base_score = match_type_score + at_rule_score + string_similarity_score + source_score

    # Component 5: Geographic Context Bonus (+10%)
    geographic_hint_used = candidate.get('geographic_hint_used', False)
    hierarchy_valid = candidate.get('hierarchy_valid', False)

    # Don't apply hierarchy bonus for street-based candidates (inferred, not direct match)
    is_street_based = (source == 'street_based')

    if (hierarchy_valid or geographic_hint_used) and not is_street_based:
        base_score *= 1.1  # +10% bonus

    # Component 6: Hierarchy Validation Penalty (-20%)
    if at_rule >= 3 and not hierarchy_valid:
        base_score *= 0.8  # -20% penalty

    # Component 7: District Mismatch Penalty (-70%)
    # Khi ward thuộc district khác với district đã biết từ Phase 2
    district_mismatch = candidate.get('district_mismatch', False)
    if district_mismatch:
        base_score *= 0.3  # -70% penalty

    # Normalize to 0-1 range (base_score max is ~110 * 1.1 = 121)
    final_confidence = min(base_score / 110.0, 1.0)

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


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank candidates by multiple criteria.

    Sorting order:
    1. Confidence score (descending)
    2. Match type (exact > fuzzy > fallback)
    3. At rule level (3 > 2 > 1 > 0)

    Args:
        candidates: List of candidate dicts

    Returns:
        Sorted list of candidates
    """
    # Calculate confidence for each candidate
    for candidate in candidates:
        candidate['final_confidence'] = calculate_confidence_score(candidate)
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

    candidates = candidates_result.get('candidates', [])

    if not candidates:
        return {
            'validated_candidates': [],
            'best_match': None,
            'all_valid': True,
            'processing_time_ms': 0.0,
            'error': 'No candidates to validate'
        }

    # Rank candidates
    ranked_candidates = rank_candidates(candidates)

    # Select best match
    best_match = ranked_candidates[0] if ranked_candidates else None

    # Check if all valid
    all_valid = all(c.get('hierarchy_valid', False) for c in ranked_candidates)

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

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
