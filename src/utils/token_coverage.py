"""
Token Coverage Scoring Module

This module calculates token coverage scores to differentiate candidate quality
based on how much of the raw input text is utilized in the match.

Token coverage considers:
1. Coverage Ratio: Percentage of meaningful tokens used
2. Continuity Score: How continuous/compact the matched tokens are
3. Weighted Coverage: Token importance based on match type (explicit pattern > keyword > normal)
"""

from typing import List, Set, Tuple, Dict
from ..config import (
    TOKEN_COVERAGE_ENABLED,
    TOKEN_COVERAGE_WEIGHTS,
    TOKEN_IMPORTANCE_WEIGHTS,
    TOKEN_COVERAGE_MULTIPLIERS,
    DEBUG_EXTRACTION
)

# Administrative noise words (imported from extraction_utils to avoid circular import)
# These are defined in extraction_utils.py
ADMIN_NOISE_WORDS = {
    'ubnd', 'phong', 'ban', 'cong ty', 'chi nhanh',
    'van phong', 'so', 'khach san', 'nha hang',
    'truong', 'benh vien', 'trung tam', 'dai hoc',
    'to', 'khu', 'cong', 'ty', 'tnhh'
}


def calculate_meaningful_tokens(all_tokens: List[str], noise_words: Set[str] = None) -> List[int]:
    """
    Filter out noise words and return indices of meaningful tokens.

    Args:
        all_tokens: List of all tokens from input text
        noise_words: Set of noise words to filter (defaults to ADMIN_NOISE_WORDS)

    Returns:
        List of indices of meaningful tokens

    Example:
        all_tokens = ['cong', 'ty', 'phuong', '3', 'quang', 'tri']
        noise_words = {'cong ty'}
        → Returns [2, 3, 4, 5] (indices of 'phuong', '3', 'quang', 'tri')
    """
    if noise_words is None:
        noise_words = ADMIN_NOISE_WORDS

    meaningful_indices = []

    for i, token in enumerate(all_tokens):
        token_lower = token.lower()

        # Check if token itself is noise
        if token_lower in noise_words:
            continue

        # Check if token is part of a multi-word noise phrase
        # (e.g., "cong" in "cong ty")
        is_noise = False
        for noise_phrase in noise_words:
            if ' ' in noise_phrase:  # Multi-word noise
                noise_tokens = noise_phrase.split()
                # Check if current position starts a noise phrase
                if i + len(noise_tokens) <= len(all_tokens):
                    potential_phrase = ' '.join(all_tokens[i:i+len(noise_tokens)]).lower()
                    if potential_phrase == noise_phrase:
                        is_noise = True
                        break

        if not is_noise:
            meaningful_indices.append(i)

    return meaningful_indices


def get_token_union(token_ranges: List[Tuple[int, int]]) -> Set[int]:
    """
    Get union of all token indices from multiple ranges.
    Handles overlap by counting each token only once.

    Args:
        token_ranges: List of (start, end) tuples representing token ranges

    Returns:
        Set of unique token indices

    Example:
        token_ranges = [(0, 2), (1, 3), (5, 7)]
        → Returns {0, 1, 2, 5, 6} (note: 1 only counted once)
    """
    token_union = set()
    for start, end in token_ranges:
        for i in range(start, end):
            token_union.add(i)
    return token_union


def calculate_coverage_ratio(used_tokens: Set[int], meaningful_tokens: List[int]) -> float:
    """
    Calculate what percentage of meaningful tokens were used in the match.

    Args:
        used_tokens: Set of token indices that were matched
        meaningful_tokens: List of indices of meaningful tokens

    Returns:
        Coverage ratio between 0.0 and 1.0

    Example:
        meaningful_tokens = [0, 1, 2, 3, 4, 5]  # 6 tokens
        used_tokens = {1, 2, 3, 4}  # 4 tokens used
        → Returns 4/6 = 0.667
    """
    if not meaningful_tokens:
        return 0.0

    meaningful_set = set(meaningful_tokens)
    used_meaningful = used_tokens.intersection(meaningful_set)

    return len(used_meaningful) / len(meaningful_tokens)


def calculate_continuity_score(used_tokens: Set[int]) -> float:
    """
    Calculate how continuous/compact the matched tokens are.
    More continuous = better (fewer gaps).

    Args:
        used_tokens: Set of token indices that were matched

    Returns:
        Continuity score between 0.0 and 1.0
        1.0 = all tokens are consecutive (one continuous group)
        Lower = more fragmented

    Example:
        used_tokens = {0, 1, 2, 3, 4}  # One continuous group
        → Returns 1.0

        used_tokens = {0, 1, 4, 5}  # Two groups: [0,1] and [4,5]
        → Returns 1/2 = 0.5
    """
    if not used_tokens:
        return 0.0

    sorted_tokens = sorted(used_tokens)

    # Count number of continuous groups
    num_groups = 1
    for i in range(1, len(sorted_tokens)):
        if sorted_tokens[i] != sorted_tokens[i-1] + 1:
            num_groups += 1

    return 1.0 / num_groups


def calculate_weighted_coverage(
    token_importance: Dict[int, str],
    used_tokens: Set[int],
    all_tokens_count: int
) -> float:
    """
    Calculate weighted coverage based on token importance.
    Tokens from explicit patterns get higher weight than normal tokens.

    Args:
        token_importance: Dict mapping token index to importance type
                         ('explicit_pattern', 'keyword', 'normal')
        used_tokens: Set of token indices that were matched
        all_tokens_count: Total number of tokens in input

    Returns:
        Weighted coverage between 0.0 and 1.0

    Example:
        token_importance = {1: 'explicit_pattern', 2: 'normal', 3: 'normal'}
        used_tokens = {1, 2, 3}
        weights = {'explicit_pattern': 2.0, 'normal': 1.0}
        → used_weight = 2.0 + 1.0 + 1.0 = 4.0
        → total_possible = 2.0 + 1.0 + 1.0 + 1.0*remaining = ...
    """
    if all_tokens_count == 0:
        return 0.0

    # Calculate weight of used tokens
    used_weight = 0.0
    for token_idx in used_tokens:
        importance_type = token_importance.get(token_idx, 'normal')
        used_weight += TOKEN_IMPORTANCE_WEIGHTS.get(importance_type, 1.0)

    # Calculate total possible weight (all tokens)
    total_weight = 0.0
    for i in range(all_tokens_count):
        importance_type = token_importance.get(i, 'normal')
        total_weight += TOKEN_IMPORTANCE_WEIGHTS.get(importance_type, 1.0)

    if total_weight == 0:
        return 0.0

    return used_weight / total_weight


def calculate_token_coverage_score(
    coverage_ratio: float,
    continuity_score: float,
    weighted_coverage: float
) -> float:
    """
    Combine the three coverage metrics into a single score.

    Args:
        coverage_ratio: Percentage of meaningful tokens used (0-1)
        continuity_score: How continuous the tokens are (0-1)
        weighted_coverage: Weighted coverage by importance (0-1)

    Returns:
        Combined token coverage score (0-1)

    Formula:
        score = coverage_ratio * 0.4 + continuity_score * 0.3 + weighted_coverage * 0.3
    """
    weights = TOKEN_COVERAGE_WEIGHTS

    score = (
        coverage_ratio * weights['coverage_ratio'] +
        continuity_score * weights['continuity'] +
        weighted_coverage * weights['weighted']
    )

    return min(1.0, max(0.0, score))


def get_coverage_multiplier(token_coverage_score: float) -> float:
    """
    Convert token coverage score to a bonus/penalty multiplier.

    Args:
        token_coverage_score: Score from 0.0 to 1.0

    Returns:
        Multiplier to apply to combined_score

    Thresholds (from config):
        >= 0.8: 1.20 (+20% bonus)
        >= 0.6: 1.10 (+10% bonus)
        >= 0.4: 1.00 (neutral)
        >= 0.2: 0.90 (-10% penalty)
        <  0.2: 0.80 (-20% penalty)
    """
    if not TOKEN_COVERAGE_ENABLED:
        return 1.0

    # Sort thresholds in descending order
    sorted_thresholds = sorted(TOKEN_COVERAGE_MULTIPLIERS.items(), reverse=True)

    for threshold, multiplier in sorted_thresholds:
        if token_coverage_score >= threshold:
            return multiplier

    # Fallback to lowest multiplier
    return sorted_thresholds[-1][1]


def calculate_token_coverage(
    all_tokens: List[str],
    ward_name: str = None,
    location_name: str = None,
    province_tokens: Tuple[int, int] = None,
    district_tokens: Tuple[int, int] = None,
    ward_tokens: Tuple[int, int] = None,
    token_importance: Dict[int, str] = None,
    debug: bool = False
) -> Tuple[float, Dict]:
    """
    Calculate token coverage based on how much of raw input is utilized.

    SIMPLIFIED LOGIC: Coverage = tokens used in final result / total input tokens
    - Higher coverage = better (more of input is utilized)
    - Candidate using 6/6 tokens > candidate using 5/6 tokens

    Args:
        all_tokens: List of all tokens from input text
        ward_name: Matched ward name (e.g., "Tịnh Ấn Đông")
        location_name: Matched location name (e.g., "THON TU DO")
        province_tokens: (start, end) tuple for province tokens
        district_tokens: (start, end) tuple for district tokens
        ward_tokens: (start, end) tuple for ward tokens
        token_importance: Dict mapping token index to importance type
        debug: If True, print debug information

    Returns:
        Tuple of (multiplier, details_dict)
        - multiplier: Bonus/penalty multiplier to apply
        - details_dict: Detailed breakdown for debugging

    Example:
        Input: ['thon', 'tu', 'do', 'tinh', 'an', 'dong']

        Candidate 1: Ward "Tịnh An" + Location "THON TU DO DONG"
        - Tokens used: {0,1,2,3,4,5} BUT 'dong'(5) doesn't match ward → 5/6 = 83%

        Candidate 2: Ward "Tịnh Ấn Đông" + Location "THON TU DO"
        - Tokens used: {0,1,2,3,4,5} ALL match → 6/6 = 100% ✅
    """
    if not TOKEN_COVERAGE_ENABLED:
        return 1.0, {}

    if token_importance is None:
        token_importance = {}

    # SIMPLIFIED: Count how many input tokens are actually used in the result
    # Prefer candidates that use more tokens in ward name (higher priority)
    used_tokens = set()
    ward_used_tokens = set()  # Track which tokens are used for ward
    location_used_tokens = set()  # Track which tokens are used for location

    # Normalize names for matching (remove accents for Vietnamese text matching)
    from ..utils.text_utils import remove_vietnamese_accents

    ward_normalized = remove_vietnamese_accents(ward_name.lower()) if ward_name else ''
    location_normalized = remove_vietnamese_accents(location_name.lower()) if location_name else ''

    # Tokenize ward and location (split into words)
    ward_tokens_normalized = set(ward_normalized.split())
    location_tokens_normalized = set(location_normalized.split())

    for idx, token in enumerate(all_tokens):
        token_lower = remove_vietnamese_accents(token.lower())

        # Priority: ward tokens > location tokens
        # If token appears in ward, mark as ward token (higher priority)
        if token_lower in ward_tokens_normalized:
            used_tokens.add(idx)
            ward_used_tokens.add(idx)
        elif token_lower in location_tokens_normalized:
            used_tokens.add(idx)
            location_used_tokens.add(idx)

    # Get meaningful tokens (filter noise)
    meaningful_indices = calculate_meaningful_tokens(all_tokens)
    meaningful_set = set(meaningful_indices)

    # Calculate coverage ratio (only count meaningful tokens)
    used_meaningful = used_tokens.intersection(meaningful_set)
    coverage_ratio = len(used_meaningful) / len(meaningful_indices) if meaningful_indices else 0.0

    # Continuity score
    continuity_score = calculate_continuity_score(used_tokens)

    # Weighted coverage: ward tokens get 2x weight, location tokens get 1x weight
    # This prefers candidates that match more tokens in ward name
    #
    # Formula: (ward_tokens * 2.0 + location_tokens * 1.0) / (total_tokens * 2.0)
    # Max possible score = all tokens used as ward = 2.0 * N / 2.0 * N = 1.0
    # Using ward tokens is better than location tokens
    ward_weight = 2.0
    location_weight = 1.0

    used_weighted = 0.0
    for idx in range(len(all_tokens)):
        if idx in ward_used_tokens:
            used_weighted += ward_weight
        elif idx in location_used_tokens:
            used_weighted += location_weight
        # else: unused tokens contribute 0

    # Total is always max weight (all tokens as ward)
    total_weighted = len(all_tokens) * ward_weight

    weighted_coverage = used_weighted / total_weighted if total_weighted > 0 else 0.0

    # Combine into final score
    token_coverage_score = calculate_token_coverage_score(
        coverage_ratio,
        continuity_score,
        weighted_coverage
    )

    # Get multiplier
    multiplier = get_coverage_multiplier(token_coverage_score)

    # Build details dict
    details = {
        'coverage_ratio': coverage_ratio,
        'continuity_score': continuity_score,
        'weighted_coverage': weighted_coverage,
        'token_coverage_score': token_coverage_score,
        'multiplier': multiplier,
        'used_tokens': sorted(used_tokens),
        'meaningful_tokens': meaningful_indices,
        'total_tokens': len(all_tokens),
        'used_count': len(used_meaningful),
        'meaningful_count': len(meaningful_indices)
    }

    if debug or (DEBUG_EXTRACTION and DEBUG_EXTRACTION != 'OFF'):
        print(f"\n[Token Coverage Debug - Simplified]")
        print(f"  All tokens: {all_tokens}")
        print(f"  Ward name: {ward_name}")
        print(f"  Location name: {location_name}")
        print(f"  Ward tokens: {sorted(ward_used_tokens)} ({len(ward_used_tokens)} tokens, weight=2.0x)")
        print(f"  Location tokens: {sorted(location_used_tokens)} ({len(location_used_tokens)} tokens, weight=1.0x)")
        print(f"  Total used: {sorted(used_tokens)} ({len(used_meaningful)}/{len(meaningful_indices)})")
        print(f"  Coverage ratio: {coverage_ratio:.3f} ({len(used_meaningful)}/{len(meaningful_indices)})")
        print(f"  Continuity: {continuity_score:.3f}")
        print(f"  Weighted coverage: {weighted_coverage:.3f} (ward tokens prioritized)")
        print(f"  Final score: {token_coverage_score:.3f}")
        print(f"  Multiplier: {multiplier:.2f}x")

    return multiplier, details
