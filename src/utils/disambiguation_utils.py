"""
Disambiguation utilities for ambiguous ward/district names.
Handles cases where a name appears at multiple administrative levels.
"""
from typing import Dict, List, Set, Tuple
import logging
from .db_utils import query_all, validate_hierarchy, infer_district_from_ward

logger = logging.getLogger(__name__)


def get_ambiguous_admin_names() -> Dict[str, Set[str]]:
    """
    Tìm các tên xuất hiện ở cả ward VÀ district level.

    Returns:
        Dict: {name_normalized: {'ward', 'district'}}

    Example:
        {
            'thanh tri': {'ward', 'district'},
            'dong da': {'ward', 'district'}
        }
    """
    query = """
    SELECT name_normalized, admin_level
    FROM (
        SELECT DISTINCT district_name_normalized as name_normalized, 'district' as admin_level
        FROM admin_divisions
        WHERE district_name_normalized IS NOT NULL

        UNION ALL

        SELECT DISTINCT ward_name_normalized as name_normalized, 'ward' as admin_level
        FROM admin_divisions
        WHERE ward_name_normalized IS NOT NULL
    )
    """

    results = query_all(query)

    # Group by name
    name_levels = {}
    for row in results:
        name = row['name_normalized']
        level = row['admin_level']

        if name not in name_levels:
            name_levels[name] = set()
        name_levels[name].add(level)

    # Return only ambiguous (appears at multiple levels)
    ambiguous = {name: levels for name, levels in name_levels.items() if len(levels) > 1}

    logger.info(f"Found {len(ambiguous)} ambiguous admin names")

    return ambiguous


def create_disambiguation_candidates(extraction_result: Dict) -> List[Dict]:
    """
    Tạo NHIỀU candidates cho mỗi tên ambiguous.
    Mỗi candidate = 1 cách hiểu khác nhau.

    Args:
        extraction_result: Kết quả từ Phase 2

    Returns:
        List of disambiguation candidates

    Example:
        Input: Phase 2 extracted "Thanh Trì" as district
        Output: [
            {province: 'ha noi', district: 'thanh tri', ward: None, interpretation: 'as_district'},
            {province: 'ha noi', district: 'hoang mai', ward: 'thanh tri', interpretation: 'as_ward'}
        ]
    """
    ambiguous_names = get_ambiguous_admin_names()

    if not ambiguous_names:
        logger.warning("No ambiguous names found in database")
        return []

    potential_provinces = extraction_result.get('potential_provinces', [])
    potential_districts = extraction_result.get('potential_districts', [])
    potential_wards = extraction_result.get('potential_wards', [])

    candidates = []

    # Check districts for ambiguity
    for dist_name, dist_score, dist_ngram in potential_districts[:3]:  # Top 3
        if dist_name not in ambiguous_names:
            continue

        levels = ambiguous_names[dist_name]
        logger.info(f"Processing ambiguous name '{dist_name}' (levels: {levels})")

        # Generate candidates for each province context
        for prov_name, prov_score, _ in potential_provinces[:2]:  # Top 2 provinces

            # Interpretation 1: Use as DISTRICT
            if 'district' in levels:
                if validate_hierarchy(prov_name, dist_name, None):
                    candidates.append({
                        'province': prov_name,
                        'district': dist_name,
                        'ward': None,
                        'province_score': prov_score,
                        'district_score': dist_score,
                        'ward_score': 0,
                        'match_type': 'disambiguation',
                        'source': 'disambiguation_as_district',
                        'at_rule': 2,
                        'confidence': (prov_score + dist_score) / 2,
                        'interpretation': f'{dist_name}_as_district'
                    })
                    logger.debug(f"Added disambiguation candidate: {dist_name} as district")

            # Interpretation 2: Use as WARD (infer district)
            if 'ward' in levels:
                inferred_dist = infer_district_from_ward(prov_name, dist_name)
                if inferred_dist and validate_hierarchy(prov_name, inferred_dist, dist_name):
                    candidates.append({
                        'province': prov_name,
                        'district': inferred_dist,
                        'ward': dist_name,
                        'province_score': prov_score,
                        'district_score': 1.0,  # DB-inferred, high confidence
                        'ward_score': dist_score,
                        'match_type': 'disambiguation',
                        'source': 'disambiguation_as_ward',
                        'at_rule': 3,
                        'confidence': (prov_score + dist_score) / 2,
                        'interpretation': f'{dist_name}_as_ward'
                    })
                    logger.debug(f"Added disambiguation candidate: {dist_name} as ward in {inferred_dist}")

    # Check wards for ambiguity (less common)
    for ward_name, ward_score, ward_ngram in potential_wards[:3]:
        if ward_name not in ambiguous_names:
            continue

        levels = ambiguous_names[ward_name]

        # If ward could also be district
        if 'district' in levels:
            for prov_name, prov_score, _ in potential_provinces[:2]:
                if validate_hierarchy(prov_name, ward_name, None):
                    candidates.append({
                        'province': prov_name,
                        'district': ward_name,  # Use as district
                        'ward': None,
                        'province_score': prov_score,
                        'district_score': ward_score,
                        'ward_score': 0,
                        'match_type': 'disambiguation',
                        'source': 'disambiguation_ward_as_district',
                        'at_rule': 2,
                        'confidence': (prov_score + ward_score) / 2 * 0.9,  # Slight penalty
                        'interpretation': f'{ward_name}_reinterpreted_as_district'
                    })
                    logger.debug(f"Added disambiguation candidate: {ward_name} reinterpreted as district")

    logger.info(f"Generated {len(candidates)} disambiguation candidates")

    return candidates


if __name__ == "__main__":
    # Test
    print("=" * 80)
    print("DISAMBIGUATION UTILITIES TEST")
    print("=" * 80)

    # Get ambiguous names
    ambiguous = get_ambiguous_admin_names()

    print(f"\nFound {len(ambiguous)} ambiguous names:")
    for name, levels in sorted(ambiguous.items())[:10]:  # Show first 10
        print(f"  {name}: {levels}")

    # Test with mock extraction result
    mock_extraction = {
        'potential_provinces': [('ha noi', 1.0, (0, 2))],
        'potential_districts': [('thanh tri', 0.95, (2, 4))],
        'potential_wards': []
    }

    print("\n" + "=" * 80)
    print("TEST: create_disambiguation_candidates()")
    print("=" * 80)

    candidates = create_disambiguation_candidates(mock_extraction)

    print(f"\nGenerated {len(candidates)} candidates:")
    for i, candidate in enumerate(candidates, 1):
        print(f"\n{i}. {candidate.get('interpretation', 'N/A')}")
        print(f"   Province: {candidate.get('province')}")
        print(f"   District: {candidate.get('district')}")
        print(f"   Ward: {candidate.get('ward')}")
        print(f"   Confidence: {candidate.get('confidence', 0):.2f}")
        print(f"   Source: {candidate.get('source')}")
