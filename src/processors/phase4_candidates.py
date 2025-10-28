"""
Phase 4: Candidate Enrichment (Simplified Pass-through)

REFACTORED: Phase 3 now generates candidates directly with proximity scoring.
Phase 4 is now a lightweight pass-through that returns candidates from Phase 3.

Previous responsibilities (now moved to Phase 3):
- ❌ Generate local candidates → MOVED to Phase 3 extract_components()
- ❌ Fuzzy matching → DONE in Phase 3 extraction_utils.py
- ❌ Token index optimization → REMOVED (premature optimization)
- ❌ Multi-tier matching → SIMPLIFIED to exact + ensemble fuzzy

Remaining responsibilities (minimal):
- ✅ Pass through candidates from Phase 3
- ✅ Return metadata for Phase 5

Input: Output from Phase 3 (contains candidates list)
Output: Same structure with minimal processing
"""
from typing import Dict, Any
import time
import logging

logger = logging.getLogger(__name__)


def generate_candidates(components: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pass-through enrichment for candidates from Phase 2.

    Phase 2 now does the heavy lifting:
    - N-gram matching
    - Candidate generation with generate_candidate_combinations()
    - Proximity scoring
    - Hierarchy validation

    Phase 3 is now just a compatibility layer that passes through results.

    Args:
        components: Output from Phase 2, containing:
            - candidates: List of candidates with proximity scores
            - normalized_text: For Phase 4
            - processing_time_ms: Phase 2 timing
            - geographic_known_used: Whether hints were used

    Returns:
        Dictionary containing:
        - candidates: Candidates from Phase 2 (unchanged)
        - total_candidates: Count
        - sources_used: ['local'] (since only local DB used now)
        - processing_time_ms: Minimal processing time

    Example:
        >>> phase2_output = extract_components({'normalized': 'dien bien ba dinh ha noi'})
        >>> phase3_output = generate_candidates(phase2_output)
        >>> len(phase3_output['candidates'])
        3
    """
    start_time = time.time()

    logger.debug("[🔍 DEBUG] " + "═" * 76)
    logger.debug("[🔍 DEBUG] [PHASE 4] CANDIDATES ENRICHMENT (Pass-through)")

    # Get candidates from Phase 2
    candidates = components.get('candidates', [])
    logger.debug(f"[🔍 DEBUG]   📥 Input: {len(candidates)} candidates from Phase 2")
    logger.debug(f"[🔍 DEBUG]   🔧 Tác vụ: Pass-through (no enrichment needed)")

    # Calculate processing time (should be minimal)
    processing_time = (time.time() - start_time) * 1000

    logger.debug(f"[🔍 DEBUG]   📤 Output: {len(candidates)} candidates")
    logger.debug(f"[🔍 DEBUG]   ⏱ Time: {processing_time:.3f}ms")
    logger.debug("[🔍 DEBUG] " + "═" * 76 + "\n")

    # Pass through with minimal processing
    return {
        'candidates': candidates,
        'total_candidates': len(candidates),
        'num_candidates': len(candidates),  # Backward compatibility
        'sources_used': ['local'],  # Only local DB used now
        'processing_time_ms': round(processing_time, 3),
        # Pass through metadata from Phase 2 for Phase 4
        'normalized_text': components.get('normalized_text', ''),
        'local_candidates_count': len(candidates),
        'candidates_processed': len(candidates),
        'osm_candidates_count': 0,  # OSM disabled
    }


if __name__ == "__main__":
    # Simple test
    print("=" * 80)
    print("PHASE 3: CANDIDATE ENRICHMENT (SIMPLIFIED)")
    print("=" * 80)

    test_input = {
        'candidates': [
            {
                'province': 'ha noi',
                'district': 'ba dinh',
                'ward': 'dien bien',
                'province_score': 1.0,
                'district_score': 1.0,
                'ward_score': 1.0,
                'combined_score': 0.95,
                'proximity_score': 1.0,
                'match_level': 3,
                'confidence': 0.95
            }
        ],
        'normalized_text': 'dien bien ba dinh ha noi',
        'processing_time_ms': 2.5
    }

    result = generate_candidates(test_input)

    print(f"\nInput candidates: {len(test_input['candidates'])}")
    print(f"Output candidates: {result['total_candidates']}")
    print(f"Processing time: {result['processing_time_ms']}ms")
    print(f"\nPhase 3 is now a pass-through - all logic moved to Phase 2!")
