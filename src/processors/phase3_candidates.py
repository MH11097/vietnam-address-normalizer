"""
Phase 3: Candidate Generation (Hybrid Approach)

Input: Extracted components from Phase 2
Output: List of candidate matches with scores
"""
from typing import Dict, Any, List, Set, Optional, Tuple
import time
import os
from functools import lru_cache
from ..utils.matching_utils import (
    exact_match,
    fuzzy_match,
    get_best_fuzzy_match,
    ensemble_fuzzy_score,
    lcs_similarity
)
from ..utils.db_utils import (
    get_province_set,
    get_district_set,
    get_ward_set,
    find_exact_match,
    validate_hierarchy
)


# Source weighting for ranking candidates
SOURCE_WEIGHTS = {
    'db_exact_match': 1.0,              # Highest trust - exact DB match
    'osm_nominatim_full': 0.95,         # Very good for real addresses
    'multi_candidate_full': 0.90,       # Good combination match
    'fuzzy_match': 0.85,                # Good for typos
    'osm_nominatim_bbox': 0.80,         # OSM with province context
    'osm_nominatim_query': 0.75,        # OSM without strict context
    'disambiguation': 0.70,             # Context-dependent
    'multi_candidate_inferred_district': 0.65,  # Inferred district
    'hierarchical_fallback': 0.60,      # Last resort
    'lcs_ward_fallback': 0.55,          # LCS matching
    'set_exact_match': 0.90,            # Set-based exact match
}


class CandidateGenerator:
    """
    Generate address candidates using tiered matching strategy.

    Matching tiers (in order):
    1. Exact Match (O(1) lookup) - Fastest, highest priority
    2. Fuzzy Match - Medium speed, good for typos
    3. Hierarchical Fallback - Slowest, for incomplete addresses
    """

    def __init__(self, province_set=None, district_set=None, ward_set=None):
        """
        Initialize with address sets from database.

        Args:
            province_set: Set of valid province names (optional, will load from DB)
            district_set: Set of valid district names (optional, will load from DB)
            ward_set: Set of valid ward names (optional, will load from DB)
        """
        # Load from database if not provided
        self.province_set = province_set or get_province_set()
        self.district_set = district_set or get_district_set()
        self.ward_set = ward_set or get_ward_set()

        # Convert to lists for fuzzy matching
        self.province_list = sorted(list(self.province_set))
        self.district_list = sorted(list(self.district_set))
        self.ward_list = sorted(list(self.ward_set))

    def tier1_exact_match(self, components: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Tier 1: Exact match using database lookup with O(1) index.
        Fastest and most accurate method.

        Args:
            components: Extracted components from Phase 2

        Returns:
            Matched candidate or None
        """
        province = components.get('province')
        district = components.get('district')
        ward = components.get('ward')

        # IMPORTANT: Do NOT query database if only province is available
        # This prevents returning random districts/wards
        if province and not district and not ward:
            # Get province full name from database (just for display)
            from ..utils.db_utils import query_one
            db_result = query_one(
                "SELECT province_full FROM admin_divisions WHERE province_name_normalized = ? LIMIT 1",
                (province,)
            )
            province_full = db_result.get('province_full') if db_result else ''

            # Return province-only candidate without querying DB for district/ward
            return {
                'province': province,
                'district': None,
                'ward': None,
                'province_full': province_full,
                'district_full': '',
                'ward_full': '',
                'match_type': 'exact',
                'at_rule': 1,
                'confidence': 0.5,  # Low confidence for province only
                'source': 'province_only_no_db'
            }

        # Try exact match in database (requires at least district or ward)
        exact_result = find_exact_match(province, district, ward)

        if exact_result:
            # Found exact match in database
            # Determine at_rule based on matched components FROM INPUT (not DB result)
            if ward:
                at_rule = 3
            elif district:
                at_rule = 2
            elif province:
                at_rule = 1
            else:
                at_rule = 0

            # IMPORTANT: Only use DB values for components that exist in INPUT
            # Don't use random ward from DB when ward was None in input
            return {
                'province': exact_result.get('province_name_normalized', province) if province else None,
                'district': exact_result.get('district_name_normalized', district) if district else None,
                'ward': exact_result.get('ward_name_normalized') if ward else None,
                'province_full': exact_result.get('province_full') if province else '',
                'district_full': exact_result.get('district_full') if district else '',
                'ward_full': exact_result.get('ward_full') if ward else '',
                'match_type': 'exact',
                'at_rule': at_rule,
                'confidence': 1.0,
                'source': 'db_exact_match'
            }

        # Fallback: Check in sets (less accurate but faster than fuzzy)
        matched_province = exact_match(province, self.province_set) if province else None
        matched_district = exact_match(district, self.district_set) if district else None
        matched_ward = exact_match(ward, self.ward_set) if ward else None

        # Only return if at least province matched
        if not matched_province:
            return None

        # Determine at_rule
        if matched_ward:
            at_rule = 3
        elif matched_district:
            at_rule = 2
        else:
            at_rule = 1

        return {
            'province': matched_province,
            'district': matched_district,
            'ward': matched_ward,
            'match_type': 'exact',
            'at_rule': at_rule,
            'confidence': 0.95,  # Slightly lower than DB match
            'source': 'set_exact_match'
        }

    def tier2_fuzzy_match(self, components: Dict[str, Any], use_token_index: bool = True) -> List[Dict[str, Any]]:
        """
        Tier 2: Fuzzy match using ensemble scoring for handling typos.
        NOW OPTIMIZED with token index pre-filtering (50-100x speedup).

        Args:
            components: Extracted components from Phase 2
            use_token_index: Use token index for pre-filtering (default: True)

        Returns:
            List of fuzzy matched candidates with validated hierarchy

        Performance:
            - Without token index: ~50-100ms (loop 9,991 records)
            - With token index: ~0.5-2ms (filter to 10-50 candidates)
            - Speedup: 50-100x
        """
        candidates = []

        province = components.get('province')
        district = components.get('district')
        ward = components.get('ward')

        # === PROVINCE MATCHING with Token Index ===
        if province:
            province_matches = []

            if use_token_index:
                # NEW: Use token index to pre-filter candidates
                from ..utils.token_index import get_token_index
                token_idx = get_token_index()
                province_candidates_filtered = token_idx.get_province_candidates(province, min_token_overlap=1)

                # Fuzzy match ONLY on filtered candidates (10-50 instead of 63)
                for cand_dict in province_candidates_filtered:
                    candidate_prov = cand_dict['name']
                    score = ensemble_fuzzy_score(province, candidate_prov)
                    if score >= 0.85:
                        province_matches.append((candidate_prov, score))
            else:
                # OLD: Loop through ALL provinces (slow)
                for candidate_prov in self.province_list:
                    score = ensemble_fuzzy_score(province, candidate_prov)
                    if score >= 0.85:  # 85% threshold
                        province_matches.append((candidate_prov, score))

            # Sort by score descending, take top 3
            province_matches = sorted(province_matches, key=lambda x: x[1], reverse=True)[:3]

            for prov_match, prov_score in province_matches:
                # === DISTRICT MATCHING with Token Index ===
                district_match = None
                district_score = 0.0

                if district:
                    district_matches = []

                    if use_token_index:
                        # NEW: Use token index with province filter
                        from ..utils.token_index import get_token_index
                        token_idx = get_token_index()
                        district_candidates_filtered = token_idx.get_district_candidates(
                            district,
                            province_filter=prov_match,
                            min_token_overlap=1
                        )

                        # Fuzzy match ONLY on filtered candidates (5-30 instead of 700)
                        for cand_dict in district_candidates_filtered:
                            candidate_dist = cand_dict['name']
                            score = ensemble_fuzzy_score(district, candidate_dist)
                            if score >= 0.80:
                                district_matches.append((candidate_dist, score))
                    else:
                        # OLD: Loop through ALL districts (slow)
                        for candidate_dist in self.district_list:
                            score = ensemble_fuzzy_score(district, candidate_dist)
                            if score >= 0.80:  # 80% threshold
                                district_matches.append((candidate_dist, score))

                    if district_matches:
                        district_match, district_score = max(district_matches, key=lambda x: x[1])

                # === WARD MATCHING with Token Index ===
                ward_match = None
                ward_score = 0.0

                if ward:
                    ward_candidates = []

                    if use_token_index:
                        # NEW: Use token index with province/district filter
                        from ..utils.token_index import get_token_index
                        token_idx = get_token_index()
                        ward_candidates_filtered = token_idx.get_ward_candidates(
                            ward,
                            province_filter=prov_match,
                            district_filter=district_match,
                            min_token_overlap=1
                        )

                        # Fuzzy match ONLY on filtered candidates (3-20 instead of 9,000)
                        for cand_dict in ward_candidates_filtered:
                            candidate_ward = cand_dict['name']
                            score = ensemble_fuzzy_score(ward, candidate_ward)
                            if score >= 0.75:  # 75% threshold for ward
                                # Hierarchy already validated by token index filter
                                ward_candidates.append((candidate_ward, score))
                    else:
                        # OLD: Loop through ALL wards (very slow)
                        for candidate_ward in self.ward_list:
                            score = ensemble_fuzzy_score(ward, candidate_ward)
                            if score >= 0.75:  # 75% threshold for ward
                                # Validate hierarchy if we have district
                                if district_match:
                                    if validate_hierarchy(prov_match, district_match, candidate_ward):
                                        ward_candidates.append((candidate_ward, score))
                                else:
                                    ward_candidates.append((candidate_ward, score))

                    if ward_candidates:
                        ward_match, ward_score = max(ward_candidates, key=lambda x: x[1])

                # Determine at_rule
                if ward_match:
                    at_rule = 3
                elif district_match:
                    at_rule = 2
                else:
                    at_rule = 1

                # Calculate weighted confidence
                scores = [(prov_score, 0.4)]  # Province weight
                if district_score > 0:
                    scores.append((district_score, 0.3))  # District weight
                if ward_score > 0:
                    scores.append((ward_score, 0.3))  # Ward weight

                # Weighted average
                total_weight = sum(w for _, w in scores)
                avg_confidence = sum(s * w for s, w in scores) / total_weight if total_weight > 0 else 0

                # Hierarchy bonus
                hierarchy_valid = False
                if ward_match and district_match:
                    hierarchy_valid = validate_hierarchy(prov_match, district_match, ward_match)
                    if hierarchy_valid:
                        avg_confidence = min(avg_confidence * 1.1, 1.0)  # +10% bonus

                # Get full names from database
                from ..utils.db_utils import query_one
                province_full = ''
                district_full = ''
                ward_full = ''

                if at_rule == 1 and prov_match:
                    # Province only - get province_full
                    db_result = query_one(
                        "SELECT province_full FROM admin_divisions WHERE province_name_normalized = ? LIMIT 1",
                        (prov_match,)
                    )
                    province_full = db_result.get('province_full') if db_result else ''
                elif at_rule >= 2:
                    # Has district or ward - use find_exact_match
                    db_result = find_exact_match(prov_match, district_match, ward_match)
                    if db_result:
                        province_full = db_result.get('province_full', '')
                        district_full = db_result.get('district_full', '')
                        ward_full = db_result.get('ward_full', '')

                candidates.append({
                    'province': prov_match,
                    'district': district_match,
                    'ward': ward_match,
                    'province_full': province_full,
                    'district_full': district_full,
                    'ward_full': ward_full,
                    'province_score': prov_score,
                    'district_score': district_score,
                    'ward_score': ward_score,
                    'match_type': 'fuzzy',
                    'at_rule': at_rule,
                    'confidence': round(avg_confidence, 3),
                    'hierarchy_valid': hierarchy_valid,
                    'source': 'ensemble_fuzzy_match'
                })

        return candidates

    def generate_from_potentials(
        self,
        potential_provinces: List[Tuple[str, float, Tuple[int, int]]],
        potential_districts: List[Tuple[str, float, Tuple[int, int]]],
        potential_wards: List[Tuple[str, float, Tuple[int, int]]],
        components: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple candidates from potential matches.
        Validate hierarchy before creating candidate.

        Args:
            potential_provinces: List of (name, score, ngram_key) tuples
            potential_districts: List of (name, score, ngram_key) tuples
            potential_wards: List of (name, score, ngram_key) tuples
            components: Original components from Phase 2

        Returns:
            List of validated candidate dictionaries
        """
        candidates = []

        # Take top candidates from each level
        # PRIORITY: Use selected values from Phase 2 first, then alternatives from potentials
        selected_province = components.get('province')
        selected_district = components.get('district')
        selected_ward = components.get('ward')

        # For province: Use selected first, then alternatives
        if selected_province:
            top_provinces = [(selected_province, components.get('province_score', 1.0), None)]
            # Add alternatives only if score is low
            if components.get('province_score', 1.0) < 0.9 and potential_provinces:
                for prov in potential_provinces[:1]:
                    if prov[0] != selected_province:
                        top_provinces.append(prov)
        else:
            top_provinces = potential_provinces[:2] if potential_provinces else []

        # For district: Use selected first, then alternatives
        if selected_district:
            top_districts = [(selected_district, components.get('district_score', 1.0), None)]
            # Add alternatives only if score is low
            if components.get('district_score', 1.0) < 0.9 and potential_districts:
                for dist in potential_districts[:1]:
                    if dist[0] != selected_district:
                        top_districts.append(dist)
        else:
            top_districts = potential_districts[:2] if potential_districts else []

        # For ward: Use selected first, then alternatives
        if selected_ward:
            top_wards = [(selected_ward, components.get('ward_score', 1.0), None)]
            # Add alternatives only if score is low
            if components.get('ward_score', 1.0) < 0.9 and potential_wards:
                for ward in potential_wards[:2]:
                    if ward[0] != selected_ward:
                        top_wards.append(ward)
        else:
            top_wards = potential_wards[:3] if potential_wards else []

        # Strategy 1: Full address (province + district + ward)
        if top_provinces and top_districts and top_wards:
            for prov_name, prov_score, _ in top_provinces:
                if not prov_name:
                    continue
                for dist_name, dist_score, _ in top_districts:
                    if not dist_name:
                        continue
                    for ward_name, ward_score, _ in top_wards:
                        if not ward_name:
                            continue
                        # Validate hierarchy BEFORE creating candidate
                        if validate_hierarchy(prov_name, dist_name, ward_name):
                            avg_score = (prov_score + dist_score + ward_score) / 3
                            candidates.append({
                                'province': prov_name,
                                'district': dist_name,
                                'ward': ward_name,
                                'province_score': prov_score,
                                'district_score': dist_score,
                                'ward_score': ward_score,
                                'match_type': 'exact',
                                'at_rule': 3,
                                'confidence': round(avg_score, 3),
                                'hierarchy_valid': True,
                                'source': 'multi_candidate_full'
                            })

        # Strategy 2: Province + Ward (infer district)
        # IMPORTANT: Ưu tiên district đã biết từ Phase 2
        if top_provinces and top_wards and not candidates:
            for prov_name, prov_score, _ in top_provinces:
                if not prov_name:
                    continue
                for ward_name, ward_score, _ in top_wards:
                    if not ward_name:
                        continue

                    # Try to infer district from ward
                    from ..utils.db_utils import infer_district_from_ward, find_exact_match
                    inferred_district = infer_district_from_ward(prov_name, ward_name)

                    if not inferred_district:
                        continue

                    # Check if inferred district matches selected district from Phase 2
                    district_mismatch = False
                    if selected_district and inferred_district != selected_district:
                        # Ward belongs to a DIFFERENT district than what Phase 2 found
                        district_mismatch = True

                    # Get full names from database
                    db_result = find_exact_match(prov_name, inferred_district, ward_name)
                    avg_score = (prov_score + ward_score) / 2

                    # Penalty if district mismatch
                    if district_mismatch:
                        avg_score *= 0.3  # 70% penalty for district mismatch
                        source_name = 'multi_candidate_inferred_district_mismatch'
                    else:
                        source_name = 'multi_candidate_inferred_district'

                    candidates.append({
                        'province': prov_name,
                        'district': inferred_district,
                        'ward': ward_name,
                        'province_full': db_result.get('province_full') if db_result else '',
                        'district_full': db_result.get('district_full') if db_result else '',
                        'ward_full': db_result.get('ward_full') if db_result else '',
                        'province_score': prov_score,
                        'district_score': 1.0 if not district_mismatch else 0.5,
                        'ward_score': ward_score,
                        'match_type': 'exact',
                        'at_rule': 3,
                        'confidence': round(avg_score, 3),
                        'hierarchy_valid': True,
                        'source': source_name,
                        'district_mismatch': district_mismatch
                    })

        # Strategy 3: Province + District (no ward)
        if top_provinces and top_districts and not top_wards:
            for prov_name, prov_score, _ in top_provinces:
                if not prov_name:
                    continue
                for dist_name, dist_score, _ in top_districts:
                    if not dist_name:
                        continue
                    # Validate hierarchy
                    if validate_hierarchy(prov_name, dist_name, None):
                        avg_score = (prov_score + dist_score) / 2
                        candidates.append({
                            'province': prov_name,
                            'district': dist_name,
                            'ward': None,
                            'province_score': prov_score,
                            'district_score': dist_score,
                            'ward_score': 0,
                            'match_type': 'exact',
                            'at_rule': 2,
                            'confidence': round(avg_score * 0.8, 3),  # Lower confidence for partial
                            'hierarchy_valid': True,
                            'source': 'multi_candidate_partial'
                        })

        # Strategy 4: Province only (DO NOT call find_exact_match to avoid random results)
        if top_provinces and not top_districts and not top_wards:
            for prov_name, prov_score, _ in top_provinces:
                if not prov_name:
                    continue
                # Get province full name from database (just for display, not for matching)
                from ..utils.db_utils import query_one
                db_result = query_one(
                    "SELECT province_full FROM admin_divisions WHERE province_name_normalized = ? LIMIT 1",
                    (prov_name,)
                )
                province_full = db_result.get('province_full') if db_result else ''

                # IMPORTANT: Only return province, do NOT fabricate district/ward
                candidates.append({
                    'province': prov_name,
                    'district': None,
                    'ward': None,
                    'province_full': province_full,
                    'district_full': '',
                    'ward_full': '',
                    'province_score': prov_score,
                    'district_score': 0,
                    'ward_score': 0,
                    'match_type': 'exact',
                    'at_rule': 1,
                    'confidence': round(prov_score * 0.5, 3),  # Very low confidence for province only
                    'hierarchy_valid': True,
                    'source': 'multi_candidate_province_only'
                })

        return candidates

    @lru_cache(maxsize=1000)
    def tier3_hierarchical_fallback(self, normalized_address: str) -> Optional[Dict[str, Any]]:
        """
        Tier 3: Hierarchical fallback with LCS algorithm.
        For incomplete addresses with noise.

        Strategy:
        1. Try ward level with LCS similarity
        2. Try district level with LCS similarity
        3. Try province level with LCS similarity

        Args:
            normalized_address: Normalized address string

        Returns:
            Best hierarchical match or None
        """
        best_match = None
        best_score = 0.0

        # Try ward level first (most specific)
        for ward in self.ward_list:
            # Use LCS similarity for partial matching
            lcs_score = lcs_similarity(ward, normalized_address)

            # Also check simple substring
            substring_match = ward in normalized_address

            if substring_match or lcs_score > 0.6:
                score = max(lcs_score, 0.7 if substring_match else 0)
                if score > best_score:
                    best_score = score
                    best_match = {
                        'province': None,  # To be inferred
                        'district': None,  # To be inferred
                        'ward': ward,
                        'match_type': 'hierarchical_fallback',
                        'at_rule': 3,
                        'confidence': round(score * 0.7, 3),  # Lower confidence for fallback
                        'lcs_score': lcs_score,
                        'source': 'lcs_ward_fallback'
                    }

        if best_match:
            return best_match

        # Try district level
        for district in self.district_list:
            lcs_score = lcs_similarity(district, normalized_address)
            substring_match = district in normalized_address

            if substring_match or lcs_score > 0.6:
                score = max(lcs_score, 0.7 if substring_match else 0)
                if score > best_score:
                    best_score = score
                    best_match = {
                        'province': None,
                        'district': district,
                        'ward': None,
                        'match_type': 'hierarchical_fallback',
                        'at_rule': 2,
                        'confidence': round(score * 0.6, 3),
                        'lcs_score': lcs_score,
                        'source': 'lcs_district_fallback'
                    }

        if best_match:
            return best_match

        # Try province level (least specific)
        for province in self.province_list:
            lcs_score = lcs_similarity(province, normalized_address)
            substring_match = province in normalized_address

            if substring_match or lcs_score > 0.5:
                score = max(lcs_score, 0.7 if substring_match else 0)
                if score > best_score:
                    best_score = score
                    best_match = {
                        'province': province,
                        'district': None,
                        'ward': None,
                        'match_type': 'hierarchical_fallback',
                        'at_rule': 1,
                        'confidence': round(score * 0.5, 3),
                        'lcs_score': lcs_score,
                        'source': 'lcs_province_fallback'
                    }

        return best_match


def generate_candidates(components: Dict[str, Any]) -> Dict[str, Any]:
    """
    NEW: Generate ALL candidates from Phase 2 potentials + multi-source enrichment.

    Strategy:
    1. Generate local DB candidates from Phase 2 potentials using generate_candidate_combinations()
    2. Generate disambiguation candidates (if needed)
    3. Generate street-based candidates (from Phase 2 potential_streets)
    4. Generate OSM/Goong candidates (CONDITIONAL - only if local confidence < 0.7)
    5. Populate full names for ALL candidates
    6. Deduplicate & sort

    Args:
        components: Output from Phase 2, containing:
            - potential_provinces/districts/wards/streets: Potential matches
            - province/district/ward: Best single match (backward compat)
            - original_address: For OSM geocoding
            - geographic_known_used: Whether known province/district hints were used
            - province_known, district_known: Normalized hints (optional)

    Returns:
        Dictionary containing:
        - candidates: List of all enriched candidates with full names populated
        - total_candidates: Total number of candidates
        - sources_used: List of sources used
        - processing_time_ms: Total processing time

    Example:
        >>> phase2_output = extract_with_database("dien bien ba dinh ha noi")
        >>> phase3_output = generate_candidates(phase2_output)
        >>> len(phase3_output['candidates'])
        5
    """
    import logging
    logger = logging.getLogger(__name__)

    start_time = time.time()

    # STEP 1: Generate local candidates from potentials
    # This replaces the old logic that expected 'candidates' from Phase 2
    from ..utils.extraction_utils import generate_candidate_combinations

    local_candidates = generate_candidate_combinations(components, max_candidates=5)

    logger.info(f"Generated {len(local_candidates)} local candidates from potentials")

    # Fallback: If no local candidates, return empty result
    if not local_candidates:
        logger.warning("No local candidates generated, returning empty result")
        return {
            'candidates': [],
            'total_candidates': 0,
            'sources_used': [],
            'local_candidates_count': 0,
            'candidates_processed': 0,
            'osm_candidates_count': 0,
            'processing_time_ms': 0.0
        }

    # STEP 1: Already generated local candidates (line 691)
    all_candidates = list(local_candidates)  # Copy to mutable list
    sources_used = set(['local'])

    logger.info(f"Starting with {len(local_candidates)} local candidates")

    # STEP 2: Add disambiguation candidates (if needed)
    if local_candidates:
        logger.info("Generating disambiguation candidates...")
        from ..utils.disambiguation_utils import create_disambiguation_candidates
        try:
            disambiguation_candidates = create_disambiguation_candidates(components)
            if disambiguation_candidates:
                all_candidates.extend(disambiguation_candidates)
                sources_used.add('disambiguation')
                logger.info(f"  → Disambiguation: {len(disambiguation_candidates)} candidates")
        except Exception as e:
            logger.warning(f"  ⚠️ Disambiguation failed: {e}")

    # STEP 3: Conditional API calls (ONLY if local confidence < 0.7)
    # Check if we need external API enrichment
    best_local = local_candidates[0] if local_candidates else None
    should_call_api = (
        not best_local or
        best_local.get('confidence', 0) < 0.7 or
        best_local.get('at_rule', 0) < 3
    )

    logger.info(f"API call decision: should_call={'YES' if should_call_api else 'NO'} "
                f"(best_local_conf={best_local.get('confidence', 0) if best_local else 0:.2f}, "
                f"at_rule={best_local.get('at_rule', 0) if best_local else 0})")

    original_address = components.get('original_address', '')
    use_goong = os.getenv('USE_GOONG_API', 'false').lower() == 'true'

    # === 3A. GOONG API CANDIDATES (PREFERRED for Vietnam) ===
    if should_call_api and original_address and use_goong:
        logger.info("Generating Goong candidates for top candidate...")
        from ..utils.goong_geocoding import geocode_with_goong, parse_goong_to_candidates

        try:
            # Use best local candidate for context
            known_province = best_local.get('province') if best_local else components.get('province')

            # Build enhanced query
            enhanced_address = original_address
            if known_province and known_province.lower() not in original_address.lower():
                enhanced_address = f"{original_address}, {known_province}"

            # Call Goong API
            goong_result = geocode_with_goong(enhanced_address, limit=3)

            if goong_result:
                goong_candidates = parse_goong_to_candidates(goong_result)
                all_candidates.extend(goong_candidates)
                sources_used.add('goong')
                logger.info(f"  → Goong: {len(goong_candidates)} candidates")
        except Exception as e:
            logger.warning(f"  ⚠️ Goong API failed: {e}")

    # === 3B. OSM CANDIDATES (FALLBACK) ===
    # Only use OSM if Goong is not enabled AND conditions met
    elif should_call_api and original_address and not use_goong:
        logger.info(f"Generating OSM candidates for top candidate (fallback)...")
        from ..utils.geocoding_utils import geocode_address, parse_osm_to_candidates

        # Use best local candidate for context
        known_province = best_local.get('province') if best_local else components.get('province')
        known_district = best_local.get('district') if best_local else components.get('district')

        # Enhance with district (if available and not in address)
        enhanced_address = original_address
        if known_district and known_district.lower() not in original_address.lower():
            enhanced_address = f"{enhanced_address}, {known_district}"

        # === STRATEGY 1: Province-specific bbox (no province in query) ===
        if known_province:
            logger.info(f"  OSM Strategy 1: Using province bbox for '{known_province}'")
            try:
                osm_result_bbox = geocode_address(enhanced_address, known_province=known_province)
                if osm_result_bbox:
                    osm_candidates_bbox = parse_osm_to_candidates(osm_result_bbox)
                    for osm_cand in osm_candidates_bbox:
                        osm_cand['source'] = 'osm_nominatim_bbox'
                        osm_cand['osm_strategy'] = 'province_bbox'
                    all_candidates.extend(osm_candidates_bbox)
                    logger.info(f"    → OSM Strategy 1: {len(osm_candidates_bbox)} candidates")
            except Exception as e:
                logger.warning(f"    ⚠️ OSM Strategy 1 failed: {e}")

        # === STRATEGY 2: Province in query (Vietnam-wide bbox) ===
        # Add province to query if not already present
        query_with_province = enhanced_address
        if known_province and known_province.lower() not in enhanced_address.lower():
            query_with_province = f"{enhanced_address}, {known_province}"

        logger.info(f"  OSM Strategy 2: Province in query (Vietnam-wide bbox)")
        try:
            osm_result_query = geocode_address(query_with_province, known_province=None)
            if osm_result_query:
                osm_candidates_query = parse_osm_to_candidates(osm_result_query)
                for osm_cand in osm_candidates_query:
                    osm_cand['source'] = 'osm_nominatim_query'
                    osm_cand['osm_strategy'] = 'province_in_query'
                all_candidates.extend(osm_candidates_query)
                logger.info(f"    → OSM Strategy 2: {len(osm_candidates_query)} candidates")
        except Exception as e:
            logger.warning(f"    ⚠️ OSM Strategy 2 failed: {e}")

        # Mark OSM as used if at least one strategy succeeded
        osm_candidate_count = len([c for c in all_candidates if 'osm' in c.get('source', '')])
        if osm_candidate_count > 0:
            sources_used.add('osm')
            logger.info(f"  → OSM total: {osm_candidate_count} candidates")
    else:
        if not should_call_api:
            logger.info("Skipping API calls - local confidence sufficient")
        else:
            logger.warning("No original address for API calls")

    # STEP 4: Populate full names for ALL candidates (prevents Phase 5 DB lookups)
    logger.info(f"Populating full names for {len(all_candidates)} candidates...")
    all_candidates_with_names = _populate_full_names(all_candidates)
    logger.info(f"  → Full names populated")

    # STEP 5: Deduplicate
    unique_candidates = _deduplicate_candidates(all_candidates_with_names)
    logger.info(f"After deduplication: {len(unique_candidates)} unique candidates")

    # STEP 6: Sort by confidence
    unique_candidates.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    # Calculate processing time
    processing_time = (time.time() - start_time) * 1000

    return {
        'candidates': unique_candidates,
        'total_candidates': len(unique_candidates),
        'num_candidates': len(unique_candidates),  # Keep for backward compatibility
        'sources_used': list(sources_used),
        'processing_time_ms': round(processing_time, 3),
        # Metadata
        'local_candidates_count': len(local_candidates),
        'osm_candidates_count': len([c for c in all_candidates if 'osm' in c.get('source', '')])
    }


# REMOVED: _generate_local_candidates() function
# This function was duplicate logic - candidate generation now happens in extraction_utils.py
# via generate_candidate_combinations() which is called in generate_candidates() at line 691


def _deduplicate_candidates(candidates: List[Dict]) -> List[Dict]:
    """
    Remove duplicates based on (province, district, ward).
    Keep highest WEIGHTED score for each unique key.

    NEW: Uses source weighting to prefer higher-quality sources.
    Score = confidence × source_weight

    Args:
        candidates: List of all candidates

    Returns:
        List of unique candidates
    """
    seen = {}

    for candidate in candidates:
        key = (
            candidate.get('province'),
            candidate.get('district'),
            candidate.get('ward')
        )

        # Calculate weighted score
        source = candidate.get('source', 'unknown')
        source_weight = SOURCE_WEIGHTS.get(source, 0.5)  # Default 0.5 for unknown sources
        confidence = candidate.get('confidence', 0)
        weighted_score = confidence * source_weight

        if key not in seen:
            seen[key] = candidate
        else:
            # Keep higher WEIGHTED score
            existing_source = seen[key].get('source', 'unknown')
            existing_weight = SOURCE_WEIGHTS.get(existing_source, 0.5)
            existing_conf = seen[key].get('confidence', 0)
            existing_weighted = existing_conf * existing_weight

            if weighted_score > existing_weighted:
                seen[key] = candidate

    return list(seen.values())


def _populate_full_names(candidates: List[Dict]) -> List[Dict]:
    """
    Populate full names (with diacritics) for all candidates.
    Prevents redundant DB lookups in Phase 5.

    Args:
        candidates: List of candidates with province/district/ward

    Returns:
        Same list with full names populated
    """
    from ..utils.db_utils import find_exact_match, query_one

    for candidate in candidates:
        province = candidate.get('province')
        district = candidate.get('district')
        ward = candidate.get('ward')

        # Skip if already fully populated
        if (candidate.get('province_full') and
            candidate.get('district_full') and
            candidate.get('ward_full')):
            continue

        # IMPORTANT: Lookup separately for each level to avoid random results

        # Lookup province full name
        if province and not candidate.get('province_full'):
            prov_result = query_one(
                "SELECT province_full FROM admin_divisions WHERE province_name_normalized = ? LIMIT 1",
                (province,)
            )
            candidate['province_full'] = prov_result.get('province_full', '') if prov_result else ''

        # Lookup district full name
        if district and not candidate.get('district_full'):
            dist_result = query_one(
                "SELECT district_full FROM admin_divisions WHERE province_name_normalized = ? AND district_name_normalized = ? LIMIT 1",
                (province, district)
            )
            candidate['district_full'] = dist_result.get('district_full', '') if dist_result else ''

        # Lookup ward full name (only if ward exists)
        if ward and not candidate.get('ward_full'):
            ward_result = find_exact_match(province, district, ward)
            candidate['ward_full'] = ward_result.get('ward_full', '') if ward_result else ''

    return candidates


if __name__ == "__main__":
    # Test examples
    test_cases = [
        {
            'province': 'hanoi',
            'district': 'badinh',
            'ward': 'dienbien',
            'description': 'Exact match case'
        },
        {
            'province': 'ha noi',  # Typo
            'district': 'ba dinh',
            'ward': 'dien bien',
            'description': 'Fuzzy match case'
        },
        {
            'province': None,
            'district': 'badinh',
            'ward': None,
            'description': 'Partial - district only'
        },
        {
            'province': 'unknown_province',
            'district': None,
            'ward': None,
            'description': 'No match case'
        }
    ]

    print("=" * 80)
    print("PHASE 3: CANDIDATE GENERATION TEST")
    print("=" * 80)

    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Input: province={test.get('province')}, district={test.get('district')}, ward={test.get('ward')}")

        result = generate_candidates(test)

        print(f"   Candidates found: {result['num_candidates']}")
        print(f"   Tier used: {result['tier_used']}")

        if result['best_candidate']:
            best = result['best_candidate']
            print(f"   Best match:")
            print(f"     Province:  {best['province']}")
            print(f"     District:  {best['district']}")
            print(f"     Ward:      {best['ward']}")
            print(f"     Type:      {best['match_type']}")
            print(f"     At rule:   {best['at_rule']}")
            print(f"     Confidence: {best['confidence']:.2f}")
        else:
            print(f"   No candidates found")

        print(f"   Time:      {result['processing_time_ms']}ms")
