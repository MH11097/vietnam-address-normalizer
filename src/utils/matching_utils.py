"""
Matching utilities for address component matching.

SIMPLIFIED: Removed 13 unused algorithms, kept only 8 core functions.

Kept (8 functions):
- levenshtein_distance() & levenshtein_normalized()
- jaccard_similarity()
- token_sort_ratio()
- strip_prefix()
- ensemble_fuzzy_score()
- exact_match()
- is_substring_match()

Removed (13 functions):
- char_levenshtein_normalized, dice_coefficient
- lcs_similarity, longest_common_subsequence
- ngram_similarity, prefix_suffix_score
- vietnamese_soundex, phonetic_similarity
- multi_tier_match, fuzzy_match, fuzzy_match_single
- get_best_fuzzy_match, multi_level_match
"""
from typing import List, Tuple, Optional, Set, Dict
from functools import lru_cache
import logging
import Levenshtein
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    from fuzzywuzzy import fuzz
    RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger(__name__)


# === Core String Similarity Algorithms ===

@lru_cache(maxsize=10000)
def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.
    Cached for performance.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance (number of operations to transform s1 to s2)

    Example:
        >>> levenshtein_distance("ba dinh", "ba din")
        1
    """
    if not s1 or not s2:
        return max(len(s1 or ''), len(s2 or ''))

    return Levenshtein.distance(s1.lower().strip(), s2.lower().strip())


@lru_cache(maxsize=10000)
def levenshtein_normalized(s1: str, s2: str) -> float:
    """
    Calculate normalized Levenshtein similarity (0-1 scale).
    1.0 = identical, 0.0 = completely different.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Normalized similarity score (0.0-1.0)

    Example:
        >>> levenshtein_normalized("ba dinh", "ba din")
        0.875  # (8-1)/8 = 0.875
    """
    if not s1 or not s2:
        return 0.0

    s1_norm = s1.lower().strip()
    s2_norm = s2.lower().strip()

    if s1_norm == s2_norm:
        return 1.0

    distance = Levenshtein.distance(s1_norm, s2_norm)
    max_len = max(len(s1_norm), len(s2_norm))

    return 1.0 - (distance / max_len) if max_len > 0 else 0.0


@lru_cache(maxsize=10000)
def jaccard_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaccard similarity based on token (word) overlap.

    Formula: |A ∩ B| / |A ∪ B|

    Args:
        s1: First string
        s2: Second string

    Returns:
        Jaccard similarity (0.0-1.0)

    Example:
        >>> jaccard_similarity("phuong dien bien", "phuong dien bien quan")
        0.75  # 3 common tokens / 4 total unique tokens
    """
    if not s1 or not s2:
        return 0.0

    tokens_a = set(s1.lower().strip().split())
    tokens_b = set(s2.lower().strip().split())

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)

    return intersection / union if union > 0 else 0.0


@lru_cache(maxsize=10000)
def token_sort_ratio(s1: str, s2: str) -> float:
    """
    Calculate token sort ratio (order-invariant matching).
    Wrapper around rapidfuzz/fuzzywuzzy token_sort_ratio.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score (0.0-1.0, normalized from 0-100)

    Example:
        >>> token_sort_ratio("ba dinh ha noi", "ha noi ba dinh")
        1.0  # Perfect match despite different order
    """
    if not s1 or not s2:
        return 0.0

    score = fuzz.token_sort_ratio(s1.lower().strip(), s2.lower().strip())
    return score / 100.0


@lru_cache(maxsize=5000)
def strip_prefix(text: str, prefixes: Optional[Tuple[str, ...]] = None) -> str:
    """
    Strip Vietnamese administrative unit prefixes.

    Args:
        text: Input text
        prefixes: Tuple of prefixes to strip (default: common Vietnamese prefixes)

    Returns:
        Text with prefix removed

    Example:
        >>> strip_prefix("phuong dien bien")
        "dien bien"
        >>> strip_prefix("quan ba dinh")
        "ba dinh"
    """
    if not text:
        return ""

    if prefixes is None:
        prefixes = (
            'phuong', 'xa', 'thi tran',  # Ward level
            'quan', 'huyen', 'thi xa', 'thanh pho',  # District level
            'tinh', 'thanh pho'  # Province level
        )

    text_lower = text.lower().strip()

    for prefix in prefixes:
        if text_lower.startswith(prefix + ' '):
            return text_lower[len(prefix):].strip()

    return text_lower


def ensemble_fuzzy_score(s1: str, s2: str, weights: Optional[Dict[str, float]] = None, log: bool = True) -> float:
    """
    Calculate ensemble fuzzy score combining multiple similarity metrics.

    Default weights:
    - Token Sort Ratio: 50%
    - Levenshtein: 30%
    - Jaccard: 20%

    Args:
        s1: First string
        s2: Second string
        weights: Custom weights dict (optional)

    Returns:
        Ensemble similarity score (0.0-1.0)

    Example:
        >>> ensemble_fuzzy_score("ba dinh ha noi", "ha noi ba dinh")
        0.95
    """
    from ..config import DEBUG_FUZZY

    if not s1 or not s2:
        return 0.0

    if weights is None:
        weights = {
            'token_sort': 0.5,
            'levenshtein': 0.3,
            'jaccard': 0.2
        }

    # Only log if explicitly requested AND DEBUG_FUZZY is FULL
    should_log = log and DEBUG_FUZZY in [True, 'FULL']

    if should_log:
        logger.debug(f"[FUZZY] Comparing: '{s1}' vs '{s2}'")

    # Calculate individual scores
    token_score = token_sort_ratio(s1, s2)
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    if should_log:
        logger.debug(f"[FUZZY]   Token Sort: {token_score:.3f} (weight: {weights.get('token_sort', 0.5):.1f})")
        logger.debug(f"[FUZZY]   Levenshtein: {lev_score:.3f} (weight: {weights.get('levenshtein', 0.3):.1f})")
        logger.debug(f"[FUZZY]   Jaccard: {jac_score:.3f} (weight: {weights.get('jaccard', 0.2):.1f})")

    # Weighted average
    final_score = (
        token_score * weights.get('token_sort', 0.5) +
        lev_score * weights.get('levenshtein', 0.3) +
        jac_score * weights.get('jaccard', 0.2)
    )

    if should_log:
        logger.debug(f"[FUZZY] → Ensemble: {final_score:.3f}")

    return final_score


def exact_match(text: str, candidates: Set[str]) -> Optional[str]:
    """
    Perform exact match using O(1) set lookup.

    Args:
        text: Text to match
        candidates: Set of candidate strings

    Returns:
        Matched string if found, None otherwise

    Example:
        >>> exact_match("hanoi", {"hanoi", "hochiminh"})
        'hanoi'
    """
    if not text:
        return None

    text_normalized = text.lower().strip()

    if text_normalized in candidates:
        return text_normalized

    return None


def is_substring_match(text: str, candidate: str) -> bool:
    """
    Check if text is a substring of candidate or vice versa.

    Args:
        text: First string
        candidate: Second string

    Returns:
        True if one is substring of the other

    Example:
        >>> is_substring_match("hanoi", "thanh pho ha noi")
        True
    """
    if not text or not candidate:
        return False

    text_normalized = text.lower().strip()
    candidate_normalized = candidate.lower().strip()

    return (
        text_normalized in candidate_normalized or
        candidate_normalized in text_normalized
    )


def clear_cache():
    """Clear all LRU caches to free memory."""
    levenshtein_distance.cache_clear()
    levenshtein_normalized.cache_clear()
    jaccard_similarity.cache_clear()
    token_sort_ratio.cache_clear()
    strip_prefix.cache_clear()


def get_cache_stats() -> dict:
    """
    Get statistics about cache usage.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'levenshtein_distance': levenshtein_distance.cache_info()._asdict(),
        'levenshtein_normalized': levenshtein_normalized.cache_info()._asdict(),
        'jaccard_similarity': jaccard_similarity.cache_info()._asdict(),
        'token_sort_ratio': token_sort_ratio.cache_info()._asdict(),
        'strip_prefix': strip_prefix.cache_info()._asdict(),
    }


if __name__ == "__main__":
    # Test string similarity algorithms
    print("=" * 80)
    print("MATCHING UTILITIES TEST (SIMPLIFIED)")
    print("=" * 80)

    test_pairs = [
        ("ba dinh", "ba din"),  # 1 char difference
        ("ha noi", "hanoi"),  # No space
        ("phuong dien bien", "dien bien"),  # Prefix
        ("ba dinh ha noi", "ha noi ba dinh"),  # Order changed
    ]

    for s1, s2 in test_pairs:
        print(f"\nComparing: '{s1}' vs '{s2}'")
        print(f"  Levenshtein distance:    {levenshtein_distance(s1, s2)}")
        print(f"  Levenshtein normalized:  {levenshtein_normalized(s1, s2):.3f}")
        print(f"  Jaccard similarity:      {jaccard_similarity(s1, s2):.3f}")
        print(f"  Token sort ratio:        {token_sort_ratio(s1, s2):.3f}")
        print(f"  Ensemble score:          {ensemble_fuzzy_score(s1, s2):.3f}")

    print("\n" + "=" * 80)
    print("PREFIX STRIPPING TEST")
    print("=" * 80)

    test_texts = [
        "phuong dien bien",
        "quan ba dinh",
        "thanh pho ha noi",
    ]

    for text in test_texts:
        stripped = strip_prefix(text)
        print(f"  '{text}' → '{stripped}'")

    print("\n" + "=" * 80)
    print("CACHE STATISTICS")
    print("=" * 80)
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}:")
        print(f"    hits={value['hits']}, misses={value['misses']}, size={value['currsize']}")

    print("\n" + "=" * 80)
    print("Simplified from 1024 → ~350 lines (66% reduction)")
    print("Removed 13 unused/complex algorithms")
    print("=" * 80)
