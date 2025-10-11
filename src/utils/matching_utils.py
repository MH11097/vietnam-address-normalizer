"""
Matching utilities for address component matching.
Includes exact match, fuzzy match, and advanced string similarity algorithms.
"""
from typing import List, Tuple, Optional, Set, Dict, Any
from functools import lru_cache
import Levenshtein
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    from fuzzywuzzy import fuzz, process
    RAPIDFUZZ_AVAILABLE = False


# Match thresholds (configurable)
PROVINCE_FUZZY_THRESHOLD = 90
DISTRICT_FUZZY_THRESHOLD = 85
WARD_FUZZY_THRESHOLD = 80


# === Advanced String Similarity Algorithms ===

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
def char_levenshtein_normalized(s1: str, s2: str) -> float:
    """
    Calculate character-level Levenshtein similarity (ignore spaces).
    Good for corrupted text like 'mnh tha nh' vs 'minh thanh'.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Normalized similarity score (0.0-1.0)

    Example:
        >>> char_levenshtein_normalized("mnh tha nh", "minh thanh")
        0.80  # 'mnhthanh' vs 'minhthanh' - 2 chars diff out of 10
    """
    if not s1 or not s2:
        return 0.0

    # Remove spaces for character comparison
    s1_chars = s1.lower().replace(' ', '').strip()
    s2_chars = s2.lower().replace(' ', '').strip()

    if s1_chars == s2_chars:
        return 1.0

    if not s1_chars or not s2_chars:
        return 0.0

    distance = Levenshtein.distance(s1_chars, s2_chars)
    max_len = max(len(s1_chars), len(s2_chars))

    return 1.0 - (distance / max_len) if max_len > 0 else 0.0


@lru_cache(maxsize=10000)
def dice_coefficient(s1: str, s2: str) -> float:
    """
    Calculate Dice coefficient (similar to Jaccard but different formula).
    More lenient than Jaccard for partial matches.

    Formula: 2 * |A ∩ B| / (|A| + |B|)

    Args:
        s1: First string
        s2: Second string

    Returns:
        Dice coefficient (0.0-1.0)

    Example:
        >>> dice_coefficient("phuong dien bien", "dien bien")
        0.80  # 2 * 2 / (3 + 2) = 0.80 (higher than Jaccard's 0.67)
    """
    if not s1 or not s2:
        return 0.0

    tokens_a = set(s1.lower().strip().split())
    tokens_b = set(s2.lower().strip().split())

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = len(tokens_a & tokens_b)
    total = len(tokens_a) + len(tokens_b)

    return (2.0 * intersection) / total if total > 0 else 0.0


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


def ensemble_fuzzy_score(s1: str, s2: str, weights: Optional[Dict[str, float]] = None) -> float:
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
    if not s1 or not s2:
        return 0.0

    if weights is None:
        weights = {
            'token_sort': 0.5,
            'levenshtein': 0.3,
            'jaccard': 0.2
        }

    # Calculate individual scores
    token_score = token_sort_ratio(s1, s2)
    lev_score = levenshtein_normalized(s1, s2)
    jac_score = jaccard_similarity(s1, s2)

    # Weighted average
    final_score = (
        token_score * weights.get('token_sort', 0.5) +
        lev_score * weights.get('levenshtein', 0.3) +
        jac_score * weights.get('jaccard', 0.2)
    )

    return final_score


@lru_cache(maxsize=5000)
def longest_common_subsequence(s1: str, s2: str) -> str:
    """
    Find longest common subsequence (LCS) between two strings.
    Used for matching incomplete addresses with noise.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Longest common subsequence string

    Example:
        >>> longest_common_subsequence("ha noi ba dinh", "thanh pho ha noi quan ba dinh")
        'ha noi ba dinh'
    """
    if not s1 or not s2:
        return ""

    s1 = s1.lower().strip()
    s2 = s2.lower().strip()

    # Split into tokens for word-level LCS
    tokens1 = s1.split()
    tokens2 = s2.split()

    m, n = len(tokens1), len(tokens2)

    # DP table
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Fill DP table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if tokens1[i-1] == tokens2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    # Backtrack to find LCS
    lcs_tokens = []
    i, j = m, n
    while i > 0 and j > 0:
        if tokens1[i-1] == tokens2[j-1]:
            lcs_tokens.append(tokens1[i-1])
            i -= 1
            j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            i -= 1
        else:
            j -= 1

    return ' '.join(reversed(lcs_tokens))


@lru_cache(maxsize=5000)
def lcs_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity based on LCS length.

    Formula: (2 * LCS_length) / (len(s1) + len(s2))

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity score (0.0-1.0)

    Example:
        >>> lcs_similarity("ha noi", "ha noi ba dinh")
        0.67  # 2*2 / (2+3)
    """
    if not s1 or not s2:
        return 0.0

    tokens1 = s1.lower().strip().split()
    tokens2 = s2.lower().strip().split()

    lcs = longest_common_subsequence(s1, s2)
    lcs_len = len(lcs.split())

    if lcs_len == 0:
        return 0.0

    return (2.0 * lcs_len) / (len(tokens1) + len(tokens2))


@lru_cache(maxsize=10000)
def ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """
    Calculate character n-gram overlap (default: bigrams).
    Good for typos, transpositions, and corrupted text.

    Args:
        s1: First string
        s2: Second string
        n: N-gram size (default: 2 for bigrams)

    Returns:
        Similarity score (0.0-1.0)

    Example:
        >>> ngram_similarity("minh thanh", "mnh tha nh", n=2)
        0.50  # Character bigram overlap
    """
    if not s1 or not s2:
        return 0.0

    # Remove spaces for character n-grams
    s1_chars = s1.lower().replace(' ', '').strip()
    s2_chars = s2.lower().replace(' ', '').strip()

    if not s1_chars or not s2_chars:
        return 0.0

    if s1_chars == s2_chars:
        return 1.0

    # Generate n-grams
    def get_ngrams(text: str, size: int) -> set:
        """Get character n-grams."""
        if len(text) < size:
            return {text}
        return set(text[i:i+size] for i in range(len(text) - size + 1))

    ngrams_a = get_ngrams(s1_chars, n)
    ngrams_b = get_ngrams(s2_chars, n)

    if not ngrams_a or not ngrams_b:
        return 0.0

    intersection = len(ngrams_a & ngrams_b)
    union = len(ngrams_a | ngrams_b)

    return intersection / union if union > 0 else 0.0


@lru_cache(maxsize=10000)
def prefix_suffix_score(s1: str, s2: str, prefix_weight: float = 0.6) -> float:
    """
    Weighted scoring favoring prefix matches.
    Useful for administrative units with prefixes.

    Args:
        s1: First string
        s2: Second string
        prefix_weight: Weight for prefix match (default: 0.6)

    Returns:
        Similarity score (0.0-1.0)

    Example:
        >>> prefix_suffix_score("ba dinh", "ba din")
        0.60  # Prefix matches "ba "
    """
    if not s1 or not s2:
        return 0.0

    s1 = s1.lower().strip()
    s2 = s2.lower().strip()

    if s1 == s2:
        return 1.0

    # Check prefix match (first 50% of shorter string, min 3 chars)
    min_len = min(len(s1), len(s2))
    prefix_len = max(3, min_len // 2)

    prefix_match = s1[:prefix_len] == s2[:prefix_len]
    suffix_match = s1[-prefix_len:] == s2[-prefix_len:]

    # Calculate score
    score = 0.0
    if prefix_match:
        score += prefix_weight
    if suffix_match:
        score += (1.0 - prefix_weight)

    # Both match = bonus
    if prefix_match and suffix_match:
        score = min(score * 1.2, 1.0)

    return score


# Vietnamese Phonetic Mapping for soundex-like matching
VIETNAMESE_PHONETIC_MAP = {
    # Consonants with similar sounds (longer patterns first)
    'ngh': '7', 'ng': '6', 'nh': '6',
    'tr': '3', 'ch': '3',
    'gi': '1', 'd': '1', 'r': '1',
    's': '2', 'x': '2',
    'c': '5', 'k': '5', 'q': '5',
    'n': '4', 'l': '4',
    'ph': '8', 'f': '8',
    'th': '9', 't': '9',
    # Vowels - keep simplified (tones already removed by normalize)
    'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u', 'y': 'i',
}


@lru_cache(maxsize=10000)
def vietnamese_soundex(text: str) -> str:
    """
    Generate Vietnamese phonetic code.
    Similar sounds get same code (e.g., d/gi/r all become '1').

    Args:
        text: Input text (should be normalized, no diacritics)

    Returns:
        Phonetic code string

    Example:
        >>> vietnamese_soundex("dau tieng")
        '1au 9ie4'
        >>> vietnamese_soundex("gau chieng")
        '1au 3ie4'  # Different but phonetically similar
    """
    if not text:
        return ""

    text = text.lower().strip()

    # Split into tokens
    tokens = text.split()
    soundex_tokens = []

    for token in tokens:
        code = token

        # Replace consonant groups (order matters - longer first)
        for sound in sorted(VIETNAMESE_PHONETIC_MAP.keys(), key=lambda x: -len(x)):
            phonetic = VIETNAMESE_PHONETIC_MAP[sound]
            code = code.replace(sound, phonetic)

        soundex_tokens.append(code)

    return ' '.join(soundex_tokens)


@lru_cache(maxsize=10000)
def phonetic_similarity(s1: str, s2: str) -> float:
    """
    Compare phonetic similarity using Vietnamese soundex.
    Returns 1.0 if phonetic codes match exactly, else use Levenshtein on codes.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Phonetic similarity score (0.0-1.0)

    Example:
        >>> phonetic_similarity("dau tieng", "gau chieng")
        0.85  # Phonetically similar
        >>> phonetic_similarity("minh thanh", "mnh tha nh")
        0.95  # Very similar phonetically
    """
    if not s1 or not s2:
        return 0.0

    # Generate phonetic codes
    code1 = vietnamese_soundex(s1)
    code2 = vietnamese_soundex(s2)

    if code1 == code2:
        return 1.0

    # If not exact match, use Levenshtein on phonetic codes
    return levenshtein_normalized(code1, code2)


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


def fuzzy_match(
    text: str,
    candidates: List[str],
    threshold: int = 80,
    limit: int = 3
) -> List[Tuple[str, float]]:
    """
    Perform fuzzy matching using rapidfuzz (or fuzzywuzzy fallback).

    Args:
        text: Text to match
        candidates: List of candidate strings
        threshold: Minimum similarity score (0-100)
        limit: Maximum number of matches to return

    Returns:
        List of (matched_string, score) tuples sorted by score

    Example:
        >>> fuzzy_match("hanoi", ["ha noi", "hai phong"], threshold=80)
        [('ha noi', 95.0)]
    """
    if not text or not candidates:
        return []

    text_normalized = text.lower().strip()

    # Use rapidfuzz or fuzzywuzzy
    matches = process.extract(
        text_normalized,
        candidates,
        scorer=fuzz.ratio,
        limit=limit
    )

    # Filter by threshold
    result = [(match[0], match[1]) for match in matches if match[1] >= threshold]

    return result


@lru_cache(maxsize=5000)
def fuzzy_match_single(
    text: str,
    candidate: str,
) -> float:
    """
    Calculate fuzzy match score between two strings.
    Cached for performance.

    Args:
        text: First string
        candidate: Second string

    Returns:
        Similarity score (0-100)

    Example:
        >>> fuzzy_match_single("hanoi", "ha noi")
        95.0
    """
    if not text or not candidate:
        return 0.0

    text_normalized = text.lower().strip()
    candidate_normalized = candidate.lower().strip()

    score = fuzz.ratio(text_normalized, candidate_normalized)

    return float(score)


def multi_level_match(
    province: Optional[str],
    district: Optional[str],
    ward: Optional[str],
    province_set: Set[str],
    district_set: Set[str],
    ward_set: Set[str]
) -> Tuple[Optional[str], Optional[str], Optional[str], int]:
    """
    Perform multi-level exact matching for province, district, ward.

    Args:
        province: Province text to match
        district: District text to match
        ward: Ward text to match
        province_set: Set of valid provinces
        district_set: Set of valid districts
        ward_set: Set of valid wards

    Returns:
        Tuple of (matched_province, matched_district, matched_ward, match_level)
        match_level: 3=all matched, 2=province+district, 1=province only, 0=none

    Example:
        >>> multi_level_match("hanoi", "badinh", "dienbien", {...}, {...}, {...})
        ('hanoi', 'badinh', 'dienbien', 3)
    """
    matched_province = exact_match(province, province_set) if province else None
    matched_district = exact_match(district, district_set) if district else None
    matched_ward = exact_match(ward, ward_set) if ward else None

    # Determine match level
    if matched_ward:
        match_level = 3  # Full match (province + district + ward)
    elif matched_district:
        match_level = 2  # Partial match (province + district)
    elif matched_province:
        match_level = 1  # Minimal match (province only)
    else:
        match_level = 0  # No match

    return matched_province, matched_district, matched_ward, match_level


def get_best_fuzzy_match(
    text: str,
    candidates: List[str],
    threshold: int = 80
) -> Optional[Tuple[str, float]]:
    """
    Get the single best fuzzy match.

    Args:
        text: Text to match
        candidates: List of candidate strings
        threshold: Minimum similarity score

    Returns:
        (best_match, score) tuple or None if no match above threshold

    Example:
        >>> get_best_fuzzy_match("hanoi", ["ha noi", "hai phong"])
        ('ha noi', 95.0)
    """
    if not text or not candidates:
        return None

    matches = fuzzy_match(text, candidates, threshold=threshold, limit=1)

    if matches:
        return matches[0]

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


def _calculate_consensus_bonus(votes: int, total: int) -> float:
    """
    Calculate consensus bonus based on voting agreement.

    Args:
        votes: Number of algorithms that passed threshold
        total: Total number of algorithms

    Returns:
        Bonus score (can be negative for penalty)
    """
    if total == 0:
        return 0.0

    ratio = votes / total

    if ratio >= 1.0:
        return 0.15  # All algorithms agree - unanimous
    elif ratio >= 0.83:  # 5/6
        return 0.10  # Strong consensus
    elif ratio >= 0.67:  # 4/6
        return 0.05  # Moderate consensus
    elif ratio >= 0.50:  # 3/6
        return 0.00  # Weak consensus - no bonus
    else:
        return -0.05  # Low confidence - penalty


def multi_tier_match(
    ngram: str,
    candidate: str,
    tier: int = 2,  # 1=strict, 2=moderate, 3=lenient
    algorithm_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Multi-tier matching with algorithm selection based on tier.
    Runs multiple algorithms and computes consensus-based score.

    Args:
        ngram: N-gram text to match
        candidate: Candidate string from database
        tier: Matching tier (1=strict/precision, 2=moderate/balanced, 3=lenient/recall)
        algorithm_config: Optional custom algorithm configuration

    Returns:
        Dictionary with:
        - tier: Tier used
        - algorithms_run: List of algorithm names
        - scores: Dict of individual algorithm scores
        - votes: Number of algorithms that passed threshold
        - consensus_ratio: Ratio of passing algorithms
        - consensus_bonus: Bonus/penalty from consensus
        - final_score: Final weighted score with consensus bonus
        - passed: Whether final score meets tier threshold
        - confidence_tier: Confidence level label

    Example:
        >>> result = multi_tier_match("minh thanh", "mnh tha nh", tier=3)
        >>> result['passed']
        True
        >>> result['votes']
        4  # Char-lev, N-gram, Phonetic, Prefix/Suffix passed
    """
    if not ngram or not candidate:
        return {
            'tier': tier,
            'algorithms_run': [],
            'scores': {},
            'votes': 0,
            'total_algorithms': 0,
            'consensus_ratio': 0.0,
            'consensus_bonus': 0.0,
            'final_score': 0.0,
            'passed': False,
            'confidence_tier': 'no_match'
        }

    # Define algorithm configurations for each tier
    if tier == 1:  # STRICT - High Precision
        algorithms = {
            'token_sort': (token_sort_ratio, 0.90, 0.30),
            'levenshtein': (levenshtein_normalized, 0.85, 0.30),
            'dice': (dice_coefficient, 0.85, 0.25),
            'jaccard': (jaccard_similarity, 0.85, 0.15),
        }
        final_threshold = 0.90
        confidence_label = 'strict_match'

    elif tier == 2:  # MODERATE - Balanced
        algorithms = {
            'token_sort': (token_sort_ratio, 0.80, 0.20),
            'levenshtein': (levenshtein_normalized, 0.75, 0.20),
            'jaccard': (jaccard_similarity, 0.70, 0.15),
            'lcs': (lcs_similarity, 0.75, 0.15),
            'char_lev': (char_levenshtein_normalized, 0.70, 0.15),
            'ngram': (ngram_similarity, 0.60, 0.15),
        }
        final_threshold = 0.75
        confidence_label = 'moderate_match'

    else:  # tier == 3, LENIENT - High Recall
        # Substring returns boolean, convert to float
        def substring_score(s1: str, s2: str) -> float:
            return 1.0 if is_substring_match(s1, s2) else 0.0

        algorithms = {
            'substring': (substring_score, 0.01, 0.05),  # Very low threshold, reduced weight
            'char_lev': (char_levenshtein_normalized, 0.70, 0.35),  # High weight for char-level
            'ngram': (ngram_similarity, 0.50, 0.25),  # Increased weight
            'phonetic': (phonetic_similarity, 0.65, 0.25),  # Lowered threshold
            'prefix_suffix': (prefix_suffix_score, 0.50, 0.10),  # Lowered threshold & weight
        }
        final_threshold = 0.55  # Lowered from 0.60 for corrupted text
        confidence_label = 'lenient_match'

    # Override with custom config if provided
    if algorithm_config:
        algorithms = algorithm_config.get('algorithms', algorithms)
        final_threshold = algorithm_config.get('threshold', final_threshold)

    # Run all algorithms
    scores = {}
    votes = 0
    total_algorithms = len(algorithms)

    for name, (func, threshold, weight) in algorithms.items():
        try:
            score = func(ngram, candidate)
            scores[name] = score

            if score >= threshold:
                votes += 1
        except Exception as e:
            # If algorithm fails, score as 0
            scores[name] = 0.0

    # Calculate weighted average
    total_weight = sum(weight for _, _, weight in algorithms.values())
    weighted_score = sum(
        scores[name] * weight
        for name, (_, _, weight) in algorithms.items()
    ) / total_weight if total_weight > 0 else 0.0

    # Calculate consensus bonus
    consensus_ratio = votes / total_algorithms if total_algorithms > 0 else 0.0
    consensus_bonus = _calculate_consensus_bonus(votes, total_algorithms)

    # Final score = weighted average + consensus bonus (capped at 1.0)
    final_score = min(weighted_score + consensus_bonus, 1.0)

    # Check if passed
    passed = final_score >= final_threshold

    return {
        'tier': tier,
        'algorithms_run': list(algorithms.keys()),
        'scores': scores,
        'votes': votes,
        'total_algorithms': total_algorithms,
        'consensus_ratio': consensus_ratio,
        'consensus_bonus': consensus_bonus,
        'final_score': final_score,
        'passed': passed,
        'confidence_tier': confidence_label if passed else 'no_match'
    }


def clear_cache():
    """Clear all LRU caches to free memory."""
    fuzzy_match_single.cache_clear()
    levenshtein_distance.cache_clear()
    levenshtein_normalized.cache_clear()
    jaccard_similarity.cache_clear()
    token_sort_ratio.cache_clear()
    strip_prefix.cache_clear()
    # New algorithms
    char_levenshtein_normalized.cache_clear()
    dice_coefficient.cache_clear()
    ngram_similarity.cache_clear()
    prefix_suffix_score.cache_clear()
    vietnamese_soundex.cache_clear()
    phonetic_similarity.cache_clear()
    longest_common_subsequence.cache_clear()
    lcs_similarity.cache_clear()


def get_cache_stats() -> dict:
    """
    Get statistics about cache usage.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'fuzzy_match_single': fuzzy_match_single.cache_info()._asdict(),
        'levenshtein_distance': levenshtein_distance.cache_info()._asdict(),
        'levenshtein_normalized': levenshtein_normalized.cache_info()._asdict(),
        'jaccard_similarity': jaccard_similarity.cache_info()._asdict(),
        'token_sort_ratio': token_sort_ratio.cache_info()._asdict(),
        'strip_prefix': strip_prefix.cache_info()._asdict(),
        # New algorithms
        'char_levenshtein_normalized': char_levenshtein_normalized.cache_info()._asdict(),
        'dice_coefficient': dice_coefficient.cache_info()._asdict(),
        'ngram_similarity': ngram_similarity.cache_info()._asdict(),
        'prefix_suffix_score': prefix_suffix_score.cache_info()._asdict(),
        'vietnamese_soundex': vietnamese_soundex.cache_info()._asdict(),
        'phonetic_similarity': phonetic_similarity.cache_info()._asdict(),
        'longest_common_subsequence': longest_common_subsequence.cache_info()._asdict(),
        'lcs_similarity': lcs_similarity.cache_info()._asdict(),
    }


if __name__ == "__main__":
    # Test string similarity algorithms
    print("=" * 80)
    print("STRING MATCHING ALGORITHMS TEST")
    print("=" * 80)

    test_pairs = [
        ("ba dinh", "ba din"),  # 1 char difference
        ("ha noi", "hanoi"),  # No space
        ("phuong dien bien", "dien bien"),  # Prefix
        ("ba dinh ha noi", "ha noi ba dinh"),  # Order changed
        ("quan 1", "quan mot"),  # Different representation
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
        "tinh ho chi minh",
        "xa tan lap",
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
