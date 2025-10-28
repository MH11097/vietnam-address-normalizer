"""
Utility modules for address parsing.
"""
from .text_utils import (
    normalize_address,
    remove_vietnamese_accents,
    expand_abbreviations,
    normalize_unicode,
    remove_special_chars,
)

from .matching_utils import (
    exact_match,
    is_substring_match,
    ensemble_fuzzy_score,
    levenshtein_normalized,
    jaccard_similarity,
    token_sort_ratio,
)

__all__ = [
    # Text utilities
    'normalize_address',
    'remove_vietnamese_accents',
    'expand_abbreviations',
    'normalize_unicode',
    'remove_special_chars',
    # Matching utilities (simplified)
    'exact_match',
    'is_substring_match',
    'ensemble_fuzzy_score',
    'levenshtein_normalized',
    'jaccard_similarity',
    'token_sort_ratio',
]
