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
    fuzzy_match,
    fuzzy_match_single,
    multi_level_match,
    get_best_fuzzy_match,
    is_substring_match,
)

__all__ = [
    # Text utilities
    'normalize_address',
    'remove_vietnamese_accents',
    'expand_abbreviations',
    'normalize_unicode',
    'remove_special_chars',
    # Matching utilities
    'exact_match',
    'fuzzy_match',
    'fuzzy_match_single',
    'multi_level_match',
    'get_best_fuzzy_match',
    'is_substring_match',
]
