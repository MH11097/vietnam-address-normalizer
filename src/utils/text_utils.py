"""
Text processing utilities for address normalization.
"""
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Tuple


# Precompiled regex patterns for performance
SPECIAL_CHAR_PATTERN = re.compile(r'[^\w\s]')
WHITESPACE_PATTERN = re.compile(r'\s+')
NUMBER_PATTERN = re.compile(r'\d+')

# Common abbreviation patterns (hardcoded for basic expansion)
# Only expand when followed by number or at word boundary
COMMON_ABBREVIATION_PATTERNS = [
    (re.compile(r'\bf\s*\.?\s*(?=\d)', re.IGNORECASE), 'phuong '),
    (re.compile(r'\bp\s*\.?\s*(?=\d)', re.IGNORECASE), 'phuong '),
    (re.compile(r'\bq\s*\.?\s*(?=\d)', re.IGNORECASE), 'quan '),
    (re.compile(r'\btp\.?\s+', re.IGNORECASE), 'thanh pho '),
    (re.compile(r'\bt\.?p\.?\s+', re.IGNORECASE), 'thanh pho '),
    (re.compile(r'\bhn\b', re.IGNORECASE), 'ha noi'),
    (re.compile(r'\bhcm\b', re.IGNORECASE), 'ho chi minh'),
]

# Database abbreviations (loaded lazily)
_DB_ABBREVIATIONS: Dict[str, str] = None

# Vietnamese character mapping for accent removal
VIETNAMESE_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
    'đ': 'd',
    'À': 'A', 'Á': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
    'Ă': 'A', 'Ằ': 'A', 'Ắ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
    'Â': 'A', 'Ầ': 'A', 'Ấ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
    'È': 'E', 'É': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
    'Ê': 'E', 'Ề': 'E', 'Ế': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
    'Ì': 'I', 'Í': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
    'Ò': 'O', 'Ó': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
    'Ô': 'O', 'Ồ': 'O', 'Ố': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
    'Ơ': 'O', 'Ờ': 'O', 'Ớ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
    'Ù': 'U', 'Ú': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
    'Ư': 'U', 'Ừ': 'U', 'Ứ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
    'Ỳ': 'Y', 'Ý': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y',
    'Đ': 'D',
}


@lru_cache(maxsize=10000)
def remove_vietnamese_accents(text: str) -> str:
    """
    Remove Vietnamese accents from text using fast character mapping.
    Uses LRU cache to avoid repeated processing.

    Args:
        text: Input text with Vietnamese accents

    Returns:
        Text without accents

    Example:
        >>> remove_vietnamese_accents("Điện Biên Phủ")
        'Dien Bien Phu'
    """
    if not text:
        return text

    # Fast character-by-character replacement
    result = []
    for char in text:
        result.append(VIETNAMESE_MAP.get(char, char))

    return ''.join(result)


@lru_cache(maxsize=10000)
def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode to NFC form.

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    if not text:
        return text

    return unicodedata.normalize('NFC', text)


def _load_db_abbreviations(province_context: str = None) -> Dict[str, str]:
    """
    Load abbreviations from database with optional province context.

    Note: This function is NOT cached at module level anymore, since it depends on province_context.
    Caching is handled by the load_abbreviations() function itself.

    Args:
        province_context: Province name (normalized) for context-specific abbreviations

    Returns:
        Dict mapping abbreviation key to full word
    """
    try:
        from .db_utils import load_abbreviations
        return load_abbreviations(province_context)
    except Exception as e:
        # Fallback to empty dict if database not available
        print(f"Warning: Could not load abbreviations from database: {e}")
        return {}


@lru_cache(maxsize=10000)
def expand_abbreviations(text: str, use_db: bool = True, province_context: str = None) -> str:
    """
    Expand common Vietnamese address abbreviations.
    Uses both hardcoded patterns and database abbreviations.

    Args:
        text: Input text with abbreviations
        use_db: Whether to load abbreviations from database (default: True)
        province_context: Province name (normalized) for context-specific abbreviations (optional)

    Returns:
        Text with expanded abbreviations

    Example:
        >>> expand_abbreviations("P. 1, Q. 2, TP. HCM")
        'phuong 1, quan 2, thanh pho ho chi minh'
        >>> expand_abbreviations("HBT")  # From DB
        'hai ba trung'
        >>> expand_abbreviations("TPHL", province_context="quang ninh")
        'ha long'
    """
    if not text:
        return text

    result = text.lower()

    # Step 1: Apply common hardcoded patterns (P., Q., etc.)
    for pattern, replacement in COMMON_ABBREVIATION_PATTERNS:
        result = pattern.sub(replacement, result)

    # Step 2: Apply database abbreviations (hbt→hai ba trung, etc.)
    if use_db:
        db_abbr = _load_db_abbreviations(province_context)

        # Replace each abbreviation found in database
        words = result.split()
        expanded_words = []

        for word in words:
            # Clean word (remove punctuation)
            clean_word = word.strip('.,;:!?')

            # Check if in database
            if clean_word in db_abbr:
                expanded_words.append(db_abbr[clean_word])
            else:
                expanded_words.append(word)

        result = ' '.join(expanded_words)

    return result


@lru_cache(maxsize=10000)
def remove_special_chars(text: str, keep_spaces: bool = True) -> str:
    """
    Remove special characters from text.

    Args:
        text: Input text
        keep_spaces: Whether to keep whitespace

    Returns:
        Cleaned text
    """
    if not text:
        return text

    # Remove special characters
    result = SPECIAL_CHAR_PATTERN.sub(' ' if keep_spaces else '', text)

    # Normalize whitespace
    if keep_spaces:
        result = WHITESPACE_PATTERN.sub(' ', result)

    return result.strip()


@lru_cache(maxsize=10000)
def normalize_address(text: str, province_context: str = None) -> str:
    """
    Full normalization pipeline for address text.

    Steps:
    1. Unicode normalization (NFC)
    2. Expand abbreviations (with province context if provided)
    3. Remove accents
    4. Remove special chars
    5. Lowercase and trim

    Args:
        text: Raw address text
        province_context: Province name (normalized) for context-specific abbreviations (optional)

    Returns:
        Normalized address text

    Example:
        >>> normalize_address("P. Điện Biên, Q. Ba Đình, HN")
        'phuong dien bien quan ba dinh hanoi'
        >>> normalize_address("TPHL", province_context="quang ninh")
        'ha long'
    """
    if not text or not isinstance(text, str):
        return ""

    # Step 1: Unicode normalization
    result = normalize_unicode(text)

    # Step 2: Expand abbreviations (with province context)
    result = expand_abbreviations(result, province_context=province_context)

    # Step 3: Remove accents
    result = remove_vietnamese_accents(result)

    # Step 4: Remove special characters
    result = remove_special_chars(result, keep_spaces=True)

    # Step 5: Lowercase and normalize whitespace
    result = result.lower().strip()
    result = WHITESPACE_PATTERN.sub(' ', result)

    return result


def clear_cache():
    """Clear all LRU caches to free memory."""
    remove_vietnamese_accents.cache_clear()
    normalize_unicode.cache_clear()
    expand_abbreviations.cache_clear()
    remove_special_chars.cache_clear()
    normalize_address.cache_clear()


def get_cache_stats() -> dict:
    """
    Get statistics about cache usage.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'remove_accents': remove_vietnamese_accents.cache_info()._asdict(),
        'normalize_unicode': normalize_unicode.cache_info()._asdict(),
        'expand_abbr': expand_abbreviations.cache_info()._asdict(),
        'remove_special': remove_special_chars.cache_info()._asdict(),
        'normalize_full': normalize_address.cache_info()._asdict(),
    }


# Regex patterns for administrative prefixes
ADMIN_PREFIX_PATTERNS = [
    # Province prefixes (order matters - longer first)
    (re.compile(r'^thanh\s*pho\s+', re.IGNORECASE), ''),
    (re.compile(r'^tinh\s+', re.IGNORECASE), ''),

    # District prefixes
    (re.compile(r'^thi\s*xa\s+', re.IGNORECASE), ''),
    (re.compile(r'^thi\s*tran\s+', re.IGNORECASE), ''),
    (re.compile(r'^quan\s+', re.IGNORECASE), ''),
    (re.compile(r'^huyen\s+', re.IGNORECASE), ''),

    # Ward prefixes
    (re.compile(r'^phuong\s+', re.IGNORECASE), ''),
    (re.compile(r'^xa\s+', re.IGNORECASE), ''),
]


@lru_cache(maxsize=5000)
def strip_admin_prefixes(text: str) -> str:
    """
    Strip administrative prefixes from text.

    Removes common prefixes like:
    - Province: "thanh pho", "tinh"
    - District: "quan", "huyen", "thi xa", "thi tran"
    - Ward: "phuong", "xa"

    Args:
        text: Normalized text with potential admin prefixes

    Returns:
        Text with prefixes removed

    Example:
        >>> strip_admin_prefixes("thanh pho ha noi")
        'ha noi'
        >>> strip_admin_prefixes("quan ba dinh")
        'ba dinh'
        >>> strip_admin_prefixes("phuong dien bien")
        'dien bien'
    """
    if not text:
        return text

    result = text.strip()

    # Try each pattern
    for pattern, replacement in ADMIN_PREFIX_PATTERNS:
        result = pattern.sub(replacement, result)

    return result.strip()


@lru_cache(maxsize=5000)
def normalize_hint(text: str) -> str:
    """
    Normalize geographic hints (province/district from raw data).

    This is specifically for hints that may contain administrative prefixes
    like "THANH PHO Ha Noi" or "Quan Ba Dinh".

    Steps:
    1. Full normalization (expand abbr, remove accents, etc.)
    2. Strip administrative prefixes

    Args:
        text: Raw hint text (e.g., "THANH PHO Ha Noi")

    Returns:
        Normalized hint without prefixes (e.g., "ha noi")

    Example:
        >>> normalize_hint("THANH PHO Ha Noi")
        'ha noi'
        >>> normalize_hint("Quan Ba Dinh")
        'ba dinh'
        >>> normalize_hint("Phuong Dien Bien")
        'dien bien'
    """
    if not text or not isinstance(text, str):
        return ""

    # Step 1: Full normalization
    normalized = normalize_address(text)

    # Step 2: Strip admin prefixes
    result = strip_admin_prefixes(normalized)

    return result
