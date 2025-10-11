"""
Extraction utilities using database-based matching.
Alternative to regex-based extraction for addresses without keywords.
"""
from typing import List, Dict, Optional, Tuple, Set
from functools import lru_cache
from .db_utils import (
    get_province_set,
    get_district_set,
    get_ward_set,
    get_street_set,
    get_candidates_scoped,
    get_wards_by_district,
    get_streets_by_province,
    validate_hierarchy,
    load_admin_divisions_all,
    infer_district_from_ward
)
from .matching_utils import ensemble_fuzzy_score, multi_tier_match


def generate_ngrams(tokens: List[str], max_n: int = 4) -> List[Tuple[str, Tuple[int, int]]]:
    """
    Generate n-grams from tokens (1-gram to max_n-gram).
    Returns list of (ngram_text, (start_idx, end_idx))

    Args:
        tokens: List of word tokens
        max_n: Maximum n-gram size (default: 4)

    Returns:
        List of (ngram_string, (start_index, end_index)) tuples
        Sorted by n descending (longer phrases first)

    Example:
        >>> generate_ngrams(['ha', 'noi', 'ba', 'dinh'], max_n=2)
        [('ha noi ba dinh', (0, 4)),   # 4-gram
         ('ha noi ba', (0, 3)),         # 3-gram
         ('noi ba dinh', (1, 4)),       # 3-gram
         ('ha noi', (0, 2)),            # 2-gram
         ('noi ba', (1, 3)),            # 2-gram
         ('ba dinh', (2, 4)),           # 2-gram
         ('ha', (0, 1)),                # 1-gram
         ('noi', (1, 2)),               # 1-gram
         ...]
    """
    if not tokens:
        return []

    ngrams = []

    # Generate n-grams from max_n down to 1
    for n in range(min(max_n, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            ngram_tokens = tokens[i:i+n]
            ngram_text = ' '.join(ngram_tokens)
            ngrams.append((ngram_text, (i, i+n)))

    return ngrams


def match_in_set(
    ngram: str,
    candidates: Set[str],
    threshold: float = 0.85,
    use_multi_tier: bool = True,
    use_token_index: bool = False,
    token_index_type: Optional[str] = None,
    province_filter: Optional[str] = None,
    district_filter: Optional[str] = None
) -> Optional[Tuple[str, float]]:
    """
    Match n-gram against candidate set with exact/fuzzy matching.
    Now supports token index pre-filtering for 50-100x speedup.

    Args:
        ngram: N-gram text to match
        candidates: Set of candidate strings (used if token index disabled)
        threshold: Fuzzy match threshold (default: 0.85)
        use_multi_tier: Whether to use multi-tier matching (default: True)
        use_token_index: Use token index for pre-filtering (default: False for backward compat)
        token_index_type: Type of index ('province'|'district'|'ward') - required if use_token_index=True
        province_filter: Filter by province (for district/ward queries)
        district_filter: Filter by district (for ward queries)

    Returns:
        (matched_string, score) or None

    Performance:
        - Without token index: ~50-100ms (loop 9,991 records)
        - With token index: ~0.5-2ms (filter to 10-50 candidates)
        - Speedup: 50-100x

    Example:
        >>> # Legacy (slow)
        >>> match_in_set('ha noi', get_province_set())
        ('ha noi', 1.0)

        >>> # New (fast with token index)
        >>> match_in_set('ha noi', None, use_token_index=True, token_index_type='province')
        ('ha noi', 1.0)
    """
    # Exact match first (fastest) - only if candidates provided
    if candidates and ngram in candidates:
        return (ngram, 1.0)

    # NEW: Token index pre-filtering (50-100x speedup)
    if use_token_index and token_index_type:
        from .token_index import get_token_index
        token_idx = get_token_index()

        # Get filtered candidates from token index
        if token_index_type == 'province':
            filtered_candidates = token_idx.get_province_candidates(ngram, min_token_overlap=1)
            # Convert to list of names
            candidate_names = [c['name'] for c in filtered_candidates]
        elif token_index_type == 'district':
            filtered_candidates = token_idx.get_district_candidates(
                ngram,
                province_filter=province_filter,
                min_token_overlap=1
            )
            candidate_names = [c['name'] for c in filtered_candidates]
        elif token_index_type == 'ward':
            filtered_candidates = token_idx.get_ward_candidates(
                ngram,
                province_filter=province_filter,
                district_filter=district_filter,
                min_token_overlap=1
            )
            candidate_names = [c['name'] for c in filtered_candidates]
        else:
            # Fallback to full set if invalid type
            candidate_names = list(candidates) if candidates else []
    else:
        # Legacy: Use full candidate set (slow for large sets)
        candidate_names = list(candidates) if candidates else []

    # No candidates to match
    if not candidate_names:
        return None

    # Choose matching strategy
    if use_multi_tier:
        # Multi-tier matching - try all 3 tiers
        best_match = None
        best_score = 0
        best_tier = None

        for candidate in candidate_names:
            # Try tiers in order: strict → moderate → lenient
            for tier in [1, 2, 3]:
                result = multi_tier_match(ngram, candidate, tier=tier)

                if result['passed']:
                    score = result['final_score']
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                        best_tier = tier
                    break  # Found match in this tier, no need to try lower tiers

        if best_match and best_score >= threshold:
            return (best_match, best_score)

    else:
        # Legacy: Single ensemble fuzzy score
        best_match = None
        best_score = 0

        for candidate in candidate_names:
            score = ensemble_fuzzy_score(ngram, candidate)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = candidate

        if best_match:
            return (best_match, best_score)

    return None


def extract_with_database(
    normalized_text: str,
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    use_fuzzy: bool = True
) -> Dict:
    """
    Extract province/district/ward using database matching.
    Works WITHOUT keywords (phuong, quan, tinh).

    Strategy:
    1. Trust known values 100% (if provided)
    2. Expand abbreviations based on province context
    3. Generate n-grams from text (4-gram → 1-gram)
    4. Match against database sets (province, district, ward)
    5. Use geographic known values to scope search if available
    6. Validate hierarchy
    7. Return best match

    Args:
        normalized_text: Normalized address text
        province_known: Known province from raw data (optional, trusted 100%)
        district_known: Known district from raw data (optional, trusted 100%)
        use_fuzzy: Whether to use fuzzy matching (default: True)

    Returns:
        Dictionary with extracted components and metadata

    Example:
        >>> extract_with_database("dien bien ba dinh ha noi")
        {
            'province': 'ha noi',
            'district': 'ba dinh',
            'ward': 'dien bien',
            'method': 'database_ngram',
            'match_level': 3,
            'confidence': 0.95
        }
    """
    if not normalized_text:
        return _empty_result()

    # Note: Abbreviation expansion is now done in Phase 1 with province context
    # No need to do it again here

    # Tokenize the normalized text
    tokens = normalized_text.split()

    if not tokens:
        return _empty_result()

    # Generate n-grams (prioritize longer phrases)
    ngrams = generate_ngrams(tokens, max_n=4)

    # STEP 0: Trust known values 100% (NEW LOGIC)
    province_match = None
    district_match = None
    ward_match = None

    province_score = 0
    district_score = 0
    ward_score = 0

    # If province is known, use it directly (don't search)
    if province_known:
        province_match = province_known
        province_score = 100

    # If district is known, use it directly (don't search)
    if district_known:
        district_match = district_known
        district_score = 100

    # Load candidate sets
    province_candidates = get_province_set()
    district_candidates = get_district_set()
    ward_candidates = get_ward_set()
    street_candidates = get_street_set()

    # If known values provided, scope the search space
    scoped_records = None
    if province_known or district_known:
        scoped_records = get_candidates_scoped(province_known, district_known)

        # Extract names from scoped records
        if scoped_records:
            if province_known and not district_known:
                # Scope districts and wards to this province
                district_candidates = {r['district_name_normalized'] for r in scoped_records if r['district_name_normalized']}
                ward_candidates = {r['ward_name_normalized'] for r in scoped_records if r['ward_name_normalized']}
            elif province_known and district_known:
                # Scope wards to this district
                ward_candidates = {r['ward_name_normalized'] for r in scoped_records if r['ward_name_normalized']}

    # Lowered threshold to support tier 3 lenient matching (min score ~0.55)
    fuzzy_threshold = 0.55 if use_fuzzy else 1.0

    # Track matched ngrams to avoid using same text for multiple levels
    matched_ngrams = set()

    # Collect ALL potential matches first (for hierarchy validation)
    potential_wards = []
    potential_districts = []
    potential_provinces = []
    potential_streets = []

    # Decide whether to use token index (only if NOT using scoped search)
    # Token index is most beneficial when searching full 9,991 records
    # When scoped (province/district known), set is already small (10-500 records)
    use_token_idx = not (province_known or district_known)

    for ngram, (start_idx, end_idx) in ngrams:
        ngram_key = (start_idx, end_idx)

        # Collect potential wards (always search, as ward is rarely known)
        if not ward_match:
            match_result = match_in_set(
                ngram,
                ward_candidates,
                fuzzy_threshold,
                use_token_index=use_token_idx,
                token_index_type='ward' if use_token_idx else None,
                province_filter=province_match or province_known,
                district_filter=district_match or district_known
            )
            if match_result:
                potential_wards.append((match_result[0], match_result[1], ngram_key))

        # Collect potential districts
        # Always collect, even if district_known exists (for conflict detection & validation)
        match_result = match_in_set(
            ngram,
            district_candidates,
            fuzzy_threshold,
            use_token_index=use_token_idx,
            token_index_type='district' if use_token_idx else None,
            province_filter=province_match or province_known
        )
        if match_result:
            potential_districts.append((match_result[0], match_result[1], ngram_key))

        # Collect potential provinces (skip if already known)
        if not province_match:
            match_result = match_in_set(
                ngram,
                province_candidates,
                fuzzy_threshold,
                use_token_index=use_token_idx,
                token_index_type='province' if use_token_idx else None
            )
            if match_result:
                potential_provinces.append((match_result[0], match_result[1], ngram_key))

        # NEW: Collect potential streets
        # Only if province is known (streets need province context for district lookup)
        if province_match:
            # Streets don't have token index yet, use set matching
            match_result = match_in_set(ngram, street_candidates, fuzzy_threshold)
            if match_result:
                potential_streets.append((match_result[0], match_result[1], ngram_key))

    # DISABLED: Early selection logic - now handled by generate_candidate_combinations()
    # All potential matches are passed to generate_candidate_combinations() which will:
    # 1. Create all valid combinations from potentials
    # 2. Validate hierarchy for each combination
    # 3. Rank by comprehensive scoring
    #
    # This allows multiple candidates (e.g., both "nam dinh" district AND "y yen" district)
    # to be generated and validated, instead of picking one too early.

    # Step 1: Select best province (ONLY for backward compatibility with result dict)
    if not province_match and potential_provinces:
        province_match = potential_provinces[0][0]
        province_score = potential_provinces[0][1] * 100
        # Note: We don't track matched_ngrams anymore since we want all potentials

    # Step 2 & 3: REMOVED - District and Ward selection now handled by generate_candidate_combinations()
    # This prevents early filtering and allows all alternatives to be considered

    # STEP 3.5: Ward-to-District Inference
    # If ward found but district missing, infer district from database
    if ward_match and province_match and not district_match:
        inferred_district = infer_district_from_ward(province_match, ward_match)
        if inferred_district:
            district_match = inferred_district
            district_score = 100  # High confidence since it's from DB
            # Note: We don't add to matched_ngrams since this is inferred, not extracted

    # Store all potential matches for Phase 3 to use
    # This allows Phase 3 to generate multiple candidate combinations

    # Calculate match level
    match_level = 0
    if ward_match:
        match_level = 3
    elif district_match:
        match_level = 2
    elif province_match:
        match_level = 1

    # Calculate confidence
    confidence = _calculate_extraction_confidence(
        province_score,
        district_score,
        ward_score,
        match_level,
        province_known is not None or district_known is not None
    )

    result = {
        'province': province_match,
        'district': district_match,
        'ward': ward_match,
        'province_score': province_score,
        'district_score': district_score,
        'ward_score': ward_score,
        'method': 'database_ngram',
        'match_level': match_level,
        'confidence': confidence,
        'geographic_known_used': province_known is not None or district_known is not None,
        # NEW: Add all potential matches for Phase 3 to generate combinations
        'potential_provinces': potential_provinces,  # [(name, score, ngram_key), ...]
        'potential_districts': potential_districts,
        'potential_wards': potential_wards,
        'potential_streets': potential_streets  # [(name, score, ngram_key), ...] - NEW for street-based candidates
    }

    # REMOVED: Candidate generation moved to Phase 3
    # This prevents duplicate work between Phase 2 and Phase 3
    # Phase 2 now only extracts potentials, Phase 3 generates all candidates

    return result


def _empty_result() -> Dict:
    """Return empty extraction result."""
    return {
        'province': None,
        'district': None,
        'ward': None,
        'province_score': 0,
        'district_score': 0,
        'ward_score': 0,
        'method': 'none',
        'match_level': 0,
        'confidence': 0.0,
        'geographic_known_used': False,
        'potential_provinces': [],
        'potential_districts': [],
        'potential_wards': [],
        'potential_streets': []
    }


def generate_candidate_combinations(
    extraction_result: Dict,
    max_candidates: int = 5
) -> List[Dict]:
    """
    Generate all valid combinations from potential matches.

    Strategy:
    1. If known values exist (score=100), use them as fixed
    2. For non-known values, generate combinations from potential matches
    3. Validate hierarchy for each combination
    4. Limit to top N candidates based on combined scores

    Args:
        extraction_result: Output from extract_with_database()
        max_candidates: Maximum number of candidates to return (default: 5)

    Returns:
        List of candidate dictionaries, each with:
        - province, district, ward
        - province_score, district_score, ward_score
        - combined_score (for ranking)
        - match_level, confidence

    Example:
        >>> result = extract_with_database("hong hai ha long", province_known="quang ninh")
        >>> candidates = generate_candidate_combinations(result, max_candidates=3)
        >>> len(candidates)
        3
        >>> candidates[0]
        {'province': 'quang ninh', 'district': 'ha long', 'ward': 'hong hai', ...}
    """
    # Get best match (used as fallback)
    best_match = {
        'province': extraction_result.get('province'),
        'district': extraction_result.get('district'),
        'ward': extraction_result.get('ward'),
        'province_score': extraction_result.get('province_score', 0),
        'district_score': extraction_result.get('district_score', 0),
        'ward_score': extraction_result.get('ward_score', 0),
        'match_level': extraction_result.get('match_level', 0),
        'confidence': extraction_result.get('confidence', 0),
        'geographic_known_used': extraction_result.get('geographic_known_used', False),
        'method': extraction_result.get('method', 'unknown')
    }

    # Get potential matches
    potential_provinces = extraction_result.get('potential_provinces', [])
    potential_districts = extraction_result.get('potential_districts', [])
    potential_wards = extraction_result.get('potential_wards', [])
    potential_streets = extraction_result.get('potential_streets', [])

    # If province is known (score=100), use it as fixed
    province_fixed = best_match['province_score'] == 100
    district_fixed = best_match['district_score'] == 100

    # Prepare province candidates
    if province_fixed:
        province_candidates = [(best_match['province'], best_match['province_score'])]
    elif potential_provinces:
        province_candidates = [(name, score * 100) for name, score, _ in potential_provinces[:3]]
    elif best_match['province']:
        province_candidates = [(best_match['province'], best_match['province_score'])]
    else:
        province_candidates = [(None, 0)]

    # Prepare district candidates
    if district_fixed:
        district_candidates = [(best_match['district'], best_match['district_score'])]
    elif potential_districts:
        # INCREASED LIMIT: Keep top 5 instead of 3 to handle ambiguous names (e.g., "nam dinh" + "y yen")
        district_candidates = [(name, score * 100) for name, score, _ in potential_districts[:5]]
    elif best_match['district']:
        district_candidates = [(best_match['district'], best_match['district_score'])]
    else:
        district_candidates = [(None, 0)]

    # Prepare ward candidates
    # Always include potential wards if available (even if best_match ward is None)
    if potential_wards:
        ward_candidates = [(name, score * 100) for name, score, _ in potential_wards[:3]]
        # Also include None as fallback
        if not best_match['ward']:
            ward_candidates.append((None, 0))
    elif best_match['ward']:
        ward_candidates = [(best_match['ward'], best_match['ward_score'])]
    else:
        ward_candidates = [(None, 0)]

    # Generate all combinations
    from itertools import product
    combinations = []

    for (prov, prov_score), (dist, dist_score), (ward, ward_score) in product(
        province_candidates, district_candidates, ward_candidates
    ):
        # Calculate combined score (average of non-zero scores)
        scores = [s for s in [prov_score, dist_score, ward_score] if s > 0]
        combined_score = sum(scores) / len(scores) if scores else 0

        # Calculate match level
        match_level = 0
        if ward:
            match_level = 3
        elif dist:
            match_level = 2
        elif prov:
            match_level = 1

        # Validate hierarchy if we have province and ward/district
        hierarchy_valid = True
        if prov and (dist or ward):
            hierarchy_valid = validate_hierarchy(prov, dist, ward)

        # Only include valid combinations
        if hierarchy_valid:
            combinations.append({
                'province': prov,
                'district': dist,
                'ward': ward,
                'province_score': prov_score,
                'district_score': dist_score,
                'ward_score': ward_score,
                'combined_score': combined_score,
                'match_level': match_level,
                'confidence': combined_score / 100,  # Normalize to 0-1
                'geographic_known_used': best_match['geographic_known_used'],
                'method': best_match['method'],
                'hierarchy_valid': hierarchy_valid
            })

    # NEW: Generate street-based candidates
    # When we have province + street matches but no clear district/ward
    # Use admin_streets table to lookup district for each street
    if potential_streets and best_match['province']:
        for street_name, street_score, ngram_key in potential_streets[:3]:  # Limit to top 3 streets
            # Query admin_streets to get all districts for this street in the province
            street_districts = get_streets_by_province(
                province=best_match['province'],
                street=street_name
            )

            for street_record in street_districts:
                dist_from_street = street_record.get('district_name_normalized')

                # Skip if this district is already in our regular candidates
                # (to avoid duplicates with higher scores)
                if any(c['district'] == dist_from_street and c['ward'] is None
                       for c in combinations):
                    continue

                # Create street-based candidate
                # Score: Lower than ward matches but higher than province-only
                # Formula: (province_score + street_match_score) / 2 * 0.75 (25% penalty for being street-based)
                # Rationale: Phase 4 will further differentiate via source_weight (street_based=8 < db_exact_match=15)
                prov_score = best_match['province_score']
                street_match_score = street_score * 100
                combined_score = ((prov_score + street_match_score) / 2) * 0.75  # 25% penalty

                # Validate hierarchy
                hierarchy_valid = validate_hierarchy(
                    best_match['province'],
                    dist_from_street,
                    None
                )

                if hierarchy_valid:
                    combinations.append({
                        'province': best_match['province'],
                        'district': dist_from_street,
                        'ward': None,
                        'province_score': prov_score,
                        'district_score': street_match_score,
                        'ward_score': 0,
                        'combined_score': combined_score,
                        'match_level': 2,  # Province + District
                        'confidence': combined_score / 100,
                        'geographic_known_used': best_match['geographic_known_used'],
                        'source': 'street_based',  # Changed from 'method' to 'source' for Phase 4 recognition
                        'match_type': 'hierarchical_fallback',  # Lower priority than exact/fuzzy matches
                        'at_rule': 2,  # Province + District (no ward)
                        'hierarchy_valid': hierarchy_valid,
                        'street_name': street_name  # Keep street info for debugging
                    })

    # Sort by combined_score descending, then by match_level descending
    combinations.sort(key=lambda x: (x['combined_score'], x['match_level']), reverse=True)

    # Limit to top N
    return combinations[:max_candidates]


def _calculate_extraction_confidence(
    province_score: float,
    district_score: float,
    ward_score: float,
    match_level: int,
    has_known: bool
) -> float:
    """
    Calculate confidence based on match scores and level.

    Formula:
    - Base: Average of match scores
    - Bonus: +0.1 for match_level 3, +0.05 for level 2
    - Bonus: +0.1 if geographic known values were used
    """
    scores = []
    if province_score > 0:
        scores.append(province_score)
    if district_score > 0:
        scores.append(district_score)
    if ward_score > 0:
        scores.append(ward_score)

    if not scores:
        return 0.0

    # Base confidence (average of scores)
    base = sum(scores) / len(scores)

    # Match level bonus
    if match_level == 3:
        base += 0.1
    elif match_level == 2:
        base += 0.05

    # Geographic known bonus
    if has_known:
        base += 0.1

    return min(base, 1.0)


if __name__ == "__main__":
    # Test
    print("=" * 80)
    print("DATABASE EXTRACTION TEST")
    print("=" * 80)

    test_cases = [
        ("dien bien ba dinh ha noi", None, None),
        ("ha noi ba dinh dien bien", None, None),  # Reversed
        ("ba dinh ha noi", None, None),  # No ward
        ("ha noi", None, None),  # Province only
        ("22 ngo 629 giai phong ha noi", "ha noi", None),  # With known
        ("bach khoa ha noi", "ha noi", None),  # With known
    ]

    for text, prov_known, dist_known in test_cases:
        print(f"\nInput: '{text}'")
        if prov_known:
            print(f"Known: province={prov_known}")

        result = extract_with_database(text, prov_known, dist_known)

        print(f"  Province: {result['province']} (score: {result['province_score']:.2f})")
        print(f"  District: {result['district']} (score: {result['district_score']:.2f})")
        print(f"  Ward:     {result['ward']} (score: {result['ward_score']:.2f})")
        print(f"  Level:    {result['match_level']}")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Method:   {result['method']}")

    print("\n" + "=" * 80)
