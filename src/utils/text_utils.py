"""
Text processing utilities for address normalization.
"""
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Tuple, Any


# Precompiled regex patterns for performance
SPECIAL_CHAR_PATTERN = re.compile(r'[^\w\s]')
WHITESPACE_PATTERN = re.compile(r'\s+')
NUMBER_PATTERN = re.compile(r'\d+')

# Common abbreviation patterns (hardcoded for basic expansion)
# Only expand when followed by number or at word boundary
# NOTE: Province abbreviations (hn, hcm, dn) are handled via database lookup in extraction phase
COMMON_ABBREVIATION_PATTERNS = [
    (re.compile(r'\bf\s*\.?\s*(?=\d)', re.IGNORECASE), 'phuong '),
    (re.compile(r'\bp\s*\.?\s*(?=\d)', re.IGNORECASE), 'phuong '),
    (re.compile(r'\bq\s*\.?\s*(?=\d)', re.IGNORECASE), 'quan '),
    (re.compile(r'\btp\.?\s+', re.IGNORECASE), 'thanh pho '),
    (re.compile(r'\bt\.?p\.?\s+', re.IGNORECASE), 'thanh pho '),
    # Removed: (re.compile(r'\bhn\b', re.IGNORECASE), 'ha noi'),
    # Removed: (re.compile(r'\bhcm\b', re.IGNORECASE), 'ho chi minh'),
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


def _load_db_abbreviations(
    province_context: str = None,
    district_context: str = None
) -> Dict[str, str]:
    """
    Load abbreviations from database with optional province and district context.

    Note: This function is NOT cached at module level anymore, since it depends on contexts.
    Caching is handled by the load_abbreviations() function itself.

    Args:
        province_context: Province name (normalized) for context-specific abbreviations
        district_context: District name (normalized) for ward-level abbreviations

    Returns:
        Dict mapping abbreviation key to full word
    """
    try:
        from .db_utils import load_abbreviations
        return load_abbreviations(province_context, district_context)
    except Exception as e:
        # Fallback to empty dict if database not available
        print(f"Warning: Could not load abbreviations from database: {e}")
        return {}


@lru_cache(maxsize=10000)
def expand_abbreviations(
    text: str,
    use_db: bool = True,
    province_context: str = None,
    district_context: str = None
) -> str:
    """
    Expand common Vietnamese address abbreviations.

    Priority order:
    1. Hardcoded patterns (P., Q., TP.)
    2. abbreviations table with full context (province + district > province > global)

    Args:
        text: Input text with abbreviations
        use_db: Whether to load abbreviations from database (default: True)
        province_context: Province name (normalized) for context-specific abbreviations (optional)
        district_context: District name (normalized) for ward-level abbreviations (optional)

    Returns:
        Text with expanded abbreviations

    Example:
        >>> expand_abbreviations("P. 1, Q. 2, TP. HCM")
        'phuong 1, quan 2, thanh pho ho chi minh'
        >>> expand_abbreviations("TX", province_context="ha noi")
        'thanh xuan'
        >>> expand_abbreviations("DB", province_context="ha noi", district_context="ba dinh")
        'dien bien'
    """
    if not text:
        return text

    result = text.lower()

    # Step 1: Apply common hardcoded patterns (P., Q., etc.)
    for pattern, replacement in COMMON_ABBREVIATION_PATTERNS:
        result = pattern.sub(replacement, result)

    # Step 2: Apply database abbreviations with context priority
    if use_db:
        # Load abbreviations with full context (handles priority internally)
        db_abbr = _load_db_abbreviations(province_context, district_context)

        # First, handle multi-word abbreviations (2-3 words)
        # Sort by length descending to match longer phrases first
        multi_word_abbr = {k: v for k, v in db_abbr.items() if ' ' in k}
        single_word_abbr = {k: v for k, v in db_abbr.items() if ' ' not in k}

        # Apply multi-word abbreviations first
        for abbr, expansion in sorted(multi_word_abbr.items(), key=lambda x: -len(x[0])):
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(abbr) + r'\b'
            result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)

        # Then apply single-word abbreviations
        words = result.split()
        expanded_words = []

        for word in words:
            # Clean word (remove punctuation)
            clean_word = word.strip('.,;:!?')

            # Check if abbreviation exists in loaded dict
            if clean_word in single_word_abbr:
                expanded_words.append(single_word_abbr[clean_word])
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
def finalize_normalization(text: str, keep_separators: bool = False) -> str:
    """
    Final normalization step: remove special chars, lowercase, and normalize whitespace.

    This function is designed to be used after text has already been processed through
    unicode normalization, abbreviation expansion, and accent removal.

    Args:
        text: Text that has already been normalized (unicode, abbr expanded, accents removed)
        keep_separators: If True, still replace commas with spaces (legacy parameter kept for compatibility)

    Returns:
        Finalized normalized text

    Example:
        >>> finalize_normalization("phuong dien bien, quan ba dinh")
        'phuong dien bien quan ba dinh'
        >>> finalize_normalization("55 BE VAN DAN,P14,Q TAN BINH", keep_separators=True)
        '55 be van dan p14 q tan binh'
    """
    if not text or not isinstance(text, str):
        return ""

    result = text

    # Remove special characters
    if keep_separators:
        # Replace commas and hyphens with spaces to avoid parsing issues
        # Cases like "55,P14,Q" should become "55 P14 Q" for proper tokenization
        result = re.sub(r'[,\-_]', ' ', result)  # Replace commas, hyphens, and underscores with spaces
        result = re.sub(r'[^\w\s]', '', result)  # Remove all other special chars
    else:
        result = remove_special_chars(result, keep_spaces=True)

    # Lowercase and normalize whitespace
    result = result.lower().strip()
    result = WHITESPACE_PATTERN.sub(' ', result)

    return result


@lru_cache(maxsize=10000)
def normalize_address(
    text: str,
    province_context: str = None,
    district_context: str = None,
    keep_separators: bool = False
) -> str:
    """
    Full normalization pipeline for address text.

    Steps:
    1. Unicode normalization (NFC)
    2. Expand abbreviations (with province and district context if provided)
    3. Remove accents
    4. Remove special chars (optionally keep commas/dashes for structural parsing)
    5. Lowercase and trim

    Args:
        text: Raw address text
        province_context: Province name (normalized) for context-specific abbreviations (optional)
        district_context: District name (normalized) for ward-level abbreviations (optional)
        keep_separators: If True, preserve commas and dashes for structural parsing

    Returns:
        Normalized address text

    Example:
        >>> normalize_address("P. Điện Biên, Q. Ba Đình, HN")
        'phuong dien bien quan ba dinh hanoi'
        >>> normalize_address("DB", province_context="ha noi", district_context="ba dinh")
        'dien bien'
    """
    if not text or not isinstance(text, str):
        return ""

    # Step 1: Unicode normalization
    result = normalize_unicode(text)

    # Step 2: Expand abbreviations (with province and district context)
    result = expand_abbreviations(result, province_context=province_context, district_context=district_context)

    # Step 3: Remove accents
    result = remove_vietnamese_accents(result)

    # Step 4: Finalize normalization (remove special chars, lowercase, trim)
    result = finalize_normalization(result, keep_separators=keep_separators)

    return result


def clear_cache():
    """Clear all LRU caches to free memory."""
    remove_vietnamese_accents.cache_clear()
    normalize_unicode.cache_clear()
    expand_abbreviations.cache_clear()
    remove_special_chars.cache_clear()
    finalize_normalization.cache_clear()
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
        'finalize': finalize_normalization.cache_info()._asdict(),
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
def normalize_admin_number(text: str) -> str:
    """
    Normalize administrative unit numbers by removing leading zeros.

    This ensures consistency with database records which have leading zeros stripped.
    Only normalizes pure numeric strings (1-2 digits), preserves text-based names.

    Args:
        text: Administrative unit name (e.g., "06", "08", "dien bien")

    Returns:
        Normalized name with leading zeros removed (e.g., "6", "8", "dien bien")

    Example:
        >>> normalize_admin_number("06")
        '6'
        >>> normalize_admin_number("08")
        '8'
        >>> normalize_admin_number("10")
        '10'
        >>> normalize_admin_number("dien bien")
        'dien bien'
        >>> normalize_admin_number(None)
        None
    """
    if not text or not isinstance(text, str):
        return text

    # Only normalize if it's a pure numeric string with 1-2 digits
    # This preserves text-based ward/district names
    if text.isdigit() and 1 <= len(text) <= 2:
        return str(int(text))  # Convert "06" -> 6 -> "6"

    return text


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


def tokenize_with_delimiter_info(
    text: str,
    delimiter_chars: List[str] = None,
    slash_number_pattern: str = None
) -> Dict[str, Any]:
    """
    Tokenize text while preserving delimiter boundary information.

    This function is designed for delimiter-aware matching. When users include
    delimiters in their input, they have clear intent about segment boundaries.

    Args:
        text: Input text (after basic normalization but before removing delimiters)
        delimiter_chars: List of delimiter characters to detect (default from config)
        slash_number_pattern: Regex pattern for address numbers with slash (default from config)

    Returns:
        Dictionary containing:
        - 'tokens': List of token strings
        - 'normalized_text': Text with delimiters replaced by spaces
        - 'delimiter_positions': List of (char_index, delimiter_char) tuples
        - 'segments': List of dicts with 'start_token', 'end_token' for each segment
        - 'number_tokens': Set of token indices containing number/slash patterns
        - 'has_delimiters': Boolean indicating if any delimiters were found

    Example:
        >>> result = tokenize_with_delimiter_info("P3, Q5, HCM")
        >>> result['tokens']
        ['p3', 'q5', 'hcm']
        >>> result['segments']
        [{'start_token': 0, 'end_token': 1}, {'start_token': 1, 'end_token': 2}, {'start_token': 2, 'end_token': 3}]

        >>> result = tokenize_with_delimiter_info("55/2 Nguyen Trai")
        >>> result['tokens']
        ['55/2', 'nguyen', 'trai']
        >>> result['number_tokens']
        {0}
    """
    # Import config defaults
    from ..config import (
        DELIMITER_CHARS, SLASH_NUMBER_PATTERN, USE_DELIMITER_HINTS
    )

    if delimiter_chars is None:
        delimiter_chars = DELIMITER_CHARS
    if slash_number_pattern is None:
        slash_number_pattern = SLASH_NUMBER_PATTERN

    if not text or not isinstance(text, str):
        return {
            'tokens': [],
            'normalized_text': '',
            'delimiter_positions': [],
            'segments': [],
            'number_tokens': set(),
            'has_delimiters': False
        }

    # Lowercase for consistency
    text = text.lower().strip()

    # Step 1: Find all number/slash patterns (e.g., "55/2") and protect them
    number_slash_regex = re.compile(slash_number_pattern)
    protected_tokens = {}  # placeholder -> original
    placeholder_counter = [0]

    def protect_number_slash(match):
        placeholder = f"__NUM_SLASH_{placeholder_counter[0]}__"
        protected_tokens[placeholder] = match.group(0)
        placeholder_counter[0] += 1
        return placeholder

    # Protect number/slash patterns before processing delimiters
    protected_text = number_slash_regex.sub(protect_number_slash, text)

    # Step 2: Find delimiter positions in original text
    delimiter_positions = []
    for i, char in enumerate(text):
        if char in delimiter_chars:
            # Skip if this is part of a protected number/slash pattern
            is_protected = False
            for orig in protected_tokens.values():
                if '/' in orig:
                    # Check if this position falls within the original pattern
                    orig_start = text.find(orig)
                    if orig_start <= i < orig_start + len(orig):
                        is_protected = True
                        break

            if not is_protected:
                delimiter_positions.append((i, char))

    has_delimiters = len(delimiter_positions) > 0

    # Step 3: Replace delimiters with spaces (except protected patterns)
    normalized_text = protected_text
    for delim in delimiter_chars:
        normalized_text = normalized_text.replace(delim, ' ')

    # Normalize whitespace
    normalized_text = WHITESPACE_PATTERN.sub(' ', normalized_text).strip()

    # Step 4: Tokenize
    tokens = normalized_text.split()

    # Step 5: Restore protected number/slash patterns and track their token indices
    number_tokens = set()
    final_tokens = []
    for i, token in enumerate(tokens):
        if token in protected_tokens:
            final_tokens.append(protected_tokens[token])
            number_tokens.add(i)
        else:
            final_tokens.append(token)

    # Rebuild normalized text with restored tokens
    normalized_text = ' '.join(final_tokens)

    # Step 6: Build segment information from delimiter positions
    segments = []
    if has_delimiters and final_tokens:
        # Map delimiter positions to token boundaries
        # We need to figure out which tokens are in which segment

        # Rebuild text with spaces to map character positions to tokens
        char_to_token = []  # For each char position, which token index?
        token_idx = 0
        char_idx = 0

        for token in final_tokens:
            for _ in token:
                char_to_token.append(token_idx)
                char_idx += 1
            # Space after token (except last)
            if token_idx < len(final_tokens) - 1:
                char_to_token.append(-1)  # Space, no token
                char_idx += 1
            token_idx += 1

        # Find which delimiters fall between which tokens
        # Sort delimiter positions
        sorted_delims = sorted(delimiter_positions, key=lambda x: x[0])

        # Build segments based on delimiter positions
        # Simple approach: split based on delimiter positions in original text
        current_segment_start = 0

        for delim_pos, _ in sorted_delims:
            # Find the token that ends before this delimiter
            # Use cumulative character count approach
            cumulative_len = 0
            end_token = 0

            for idx, token in enumerate(final_tokens):
                cumulative_len += len(token)
                if cumulative_len >= delim_pos:
                    end_token = idx + 1
                    break
                cumulative_len += 1  # Space

            if end_token > current_segment_start:
                segments.append({
                    'start_token': current_segment_start,
                    'end_token': end_token
                })
                current_segment_start = end_token

        # Add final segment
        if current_segment_start < len(final_tokens):
            segments.append({
                'start_token': current_segment_start,
                'end_token': len(final_tokens)
            })
    else:
        # No delimiters - entire text is one segment
        if final_tokens:
            segments.append({
                'start_token': 0,
                'end_token': len(final_tokens)
            })

    return {
        'tokens': final_tokens,
        'normalized_text': normalized_text,
        'delimiter_positions': delimiter_positions,
        'segments': segments,
        'number_tokens': number_tokens,
        'has_delimiters': has_delimiters
    }


def check_ngram_crosses_delimiter(
    ngram_start: int,
    ngram_end: int,
    segments: List[Dict[str, int]]
) -> bool:
    """
    Check if an n-gram crosses delimiter boundaries.

    Args:
        ngram_start: Start token index (inclusive)
        ngram_end: End token index (exclusive)
        segments: List of segment dicts with 'start_token' and 'end_token'

    Returns:
        True if the n-gram spans multiple segments (crosses delimiter boundary)

    Example:
        >>> segments = [{'start_token': 0, 'end_token': 2}, {'start_token': 2, 'end_token': 4}]
        >>> check_ngram_crosses_delimiter(0, 2, segments)  # Within first segment
        False
        >>> check_ngram_crosses_delimiter(1, 3, segments)  # Crosses boundary
        True
    """
    if not segments or len(segments) <= 1:
        return False

    # Find which segment(s) this n-gram overlaps with
    overlapping_segments = 0

    for segment in segments:
        seg_start = segment['start_token']
        seg_end = segment['end_token']

        # Check if there's any overlap
        if ngram_start < seg_end and ngram_end > seg_start:
            overlapping_segments += 1

    # If it overlaps with more than one segment, it crosses a boundary
    return overlapping_segments > 1


def calculate_delimiter_score(
    ngram_start: int,
    ngram_end: int,
    delimiter_info: Dict[str, Any],
    cross_penalty: float = None,
    within_bonus: float = None
) -> float:
    """
    Calculate delimiter-aware score multiplier for an n-gram.

    Args:
        ngram_start: Start token index (inclusive)
        ngram_end: End token index (exclusive)
        delimiter_info: Dictionary from tokenize_with_delimiter_info()
        cross_penalty: Penalty multiplier when crossing boundaries (default from config)
        within_bonus: Bonus multiplier when fully within segment (default from config)

    Returns:
        Score multiplier (1.0 = neutral, <1.0 = penalty, >1.0 = bonus)

    Example:
        >>> delimiter_info = tokenize_with_delimiter_info("P3, Q5, HCM")
        >>> calculate_delimiter_score(0, 1, delimiter_info)  # P3 - within segment
        1.10  # bonus
        >>> calculate_delimiter_score(0, 2, delimiter_info)  # P3 Q5 - crosses boundary
        0.85  # penalty
    """
    from ..config import (
        USE_DELIMITER_HINTS, DELIMITER_CROSS_PENALTY, DELIMITER_WITHIN_BONUS
    )

    # If delimiter hints are disabled, return neutral score
    if not USE_DELIMITER_HINTS:
        return 1.0

    # Use defaults from config if not provided
    if cross_penalty is None:
        cross_penalty = DELIMITER_CROSS_PENALTY
    if within_bonus is None:
        within_bonus = DELIMITER_WITHIN_BONUS

    # If no delimiters in input, return neutral score
    if not delimiter_info.get('has_delimiters', False):
        return 1.0

    segments = delimiter_info.get('segments', [])

    # Check if n-gram crosses delimiter boundary
    if check_ngram_crosses_delimiter(ngram_start, ngram_end, segments):
        return cross_penalty
    else:
        # N-gram is fully within a segment - apply bonus
        return within_bonus
