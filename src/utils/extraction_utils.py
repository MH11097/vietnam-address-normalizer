"""
Extraction utilities using database-based matching.
Alternative to regex-based extraction for addresses without keywords.
"""
from typing import List, Dict, Optional, Tuple, Set
from functools import lru_cache
import logging
from .db_utils import (
    get_province_set,
    get_district_set,
    get_ward_set,
    get_street_set,
    get_candidates_scoped,
    get_wards_by_district,
    get_streets_by_province,
    validate_hierarchy,
    load_admin_divisions_all,
    infer_district_from_ward,
    find_exact_match
)
from .matching_utils import ensemble_fuzzy_score
from .text_utils import normalize_admin_number

logger = logging.getLogger(__name__)

# Administrative noise words that should NOT be matched as place names
# These are typically organizational/institutional keywords
ADMIN_NOISE_WORDS = {
    'ubnd', 'phong', 'ban', 'cong ty', 'chi nhanh',
    'van phong', 'so', 'khach san', 'nha hang',
    'truong', 'benh vien', 'cong an', 'vien',
    'ngan hang', 'ngai hang', 'buu dien', 'bo',
    'to chuc', 'don vi', 'dai hoc', 'hoc vien',
    'toa nha', 'cua hang', 'sieu thi', 'trung tam'
}

# Administrative keywords that mark boundaries between place names
# Used to prevent greedy extraction (e.g., "quan 8 phuong 4" should be "8" and "4", not "8 phuong 4")
ADMIN_KEYWORDS = {
    'phuong', 'p', 'xa', 'x', 'thi', 'tran',
    'quan', 'q', 'huyen', 'h',
    'thanh', 'pho', 'tp', 'tx'
}


def lookup_full_names(
    province: Optional[str],
    district: Optional[str],
    ward: Optional[str]
) -> Tuple[str, str, str]:
    """
    Lookup full administrative names from database.

    Args:
        province: Normalized province name (e.g., 'ha noi')
        district: Normalized district name (e.g., 'ba dinh')
        ward: Normalized ward name (e.g., 'dien bien')

    Returns:
        Tuple of (province_full, district_full, ward_full)
        Empty strings if not found.

    Example:
        >>> lookup_full_names('ha noi', 'ba dinh', 'dien bien')
        ('THÀNH PHỐ HÀ NỘI', 'QUẬN BA ĐÌNH', 'PHƯỜNG ĐIỆN BIÊN')
        >>> lookup_full_names('ha noi', None, None)
        ('THÀNH PHỐ HÀ NỘI', '', '')  # Province-only lookup
    """
    # Try find_exact_match first (requires at least 2 components)
    result = find_exact_match(province, district, ward)
    if result:
        return (
            result.get('province_full', ''),
            result.get('district_full', '') if district else '',
            result.get('ward_full', '') if ward else ''
        )
    
    # If find_exact_match returns None (e.g., province-only), try province lookup
    if province and not district and not ward:
        # Query for province-only
        from .db_utils import query_one
        query = """
        SELECT DISTINCT province_full
        FROM admin_divisions
        WHERE province_name_normalized = ?
        LIMIT 1
        """
        prov_result = query_one(query, (province,))
        if prov_result:
            return (prov_result.get('province_full', ''), '', '')

    return ('', '', '')


def has_noise_word(ngram: str, tokens: List[str], start_idx: int, end_idx: int) -> bool:
    """
    Check if n-gram contains administrative noise words.

    Args:
        ngram: The n-gram text
        tokens: Original token list
        start_idx: Start index in tokens
        end_idx: End index in tokens

    Returns:
        True if n-gram contains noise words, False otherwise

    Example:
        >>> has_noise_word('ubnd huyen thanh tri', ['ubnd', 'huyen', 'thanh', 'tri'], 0, 4)
        True
        >>> has_noise_word('thanh tri', ['thanh', 'tri'], 0, 2)
        False
    """
    # Check if any token in this n-gram is a noise word
    ngram_tokens = tokens[start_idx:end_idx]
    return any(token in ADMIN_NOISE_WORDS for token in ngram_tokens)


def extract_explicit_patterns(tokens: List[str]) -> Dict[str, List[Tuple[str, int, int]]]:
    """
    Extract place names from explicit administrative patterns.

    Patterns:
    - "THANH PHO X" / "TP X" → X is district/city
    - "THI XA X" / "TX X" → X is district/town
    - "HUYEN X" / "H X" → X is district
    - "QUAN X" / "Q X" → X is district
    - "PHUONG X" / "P X" / "P.X" → X is ward
    - "XA X" / "X.X" → X is ward/commune

    Args:
        tokens: List of normalized tokens

    Returns:
        Dict with keys 'districts' and 'wards', each containing list of (name, start_idx, end_idx)

    Example:
        >>> extract_explicit_patterns(['tp', 'vung', 'tau'])
        {'districts': [('vung tau', 1, 3)], 'wards': []}
        >>> extract_explicit_patterns(['phuong', 'nghia', 'duc'])
        {'districts': [], 'wards': [('nghia duc', 1, 3)]}
    """
    districts = []
    wards = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Pattern 1: THANH PHO / TP (city/district)
        if token in ['thanh', 'tp']:
            if token == 'thanh' and i + 1 < len(tokens) and tokens[i + 1] == 'pho':
                # "THANH PHO X" → extract X
                start_idx = i + 2
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    districts.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 2
                continue
            elif token == 'tp':
                # "TP X" → extract X
                start_idx = i + 1
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    districts.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 1
                continue

        # Pattern 2: THI XA / TX (town/district)
        if token in ['thi', 'tx']:
            if token == 'thi' and i + 1 < len(tokens) and tokens[i + 1] == 'xa':
                # "THI XA X" → extract X
                start_idx = i + 2
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    districts.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 2
                continue
            elif token == 'tx':
                # "TX X" → extract X
                start_idx = i + 1
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    districts.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 1
                continue

        # Pattern 3: HUYEN / H (district)
        if token in ['huyen', 'h']:
            if token == 'huyen' or (token == 'h' and i + 1 < len(tokens)):
                # "HUYEN X" or "H X" → extract X
                start_idx = i + 1
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    # Special case: Filter out noise words after HUYEN
                    if not has_noise_word(name, tokens, start_idx, end_idx):
                        districts.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 1
                continue

        # Pattern 4: QUAN / Q (district)
        if token in ['quan', 'q']:
            # "QUAN X" or "Q X" → extract X
            start_idx = i + 1
            end_idx = start_idx

            # Expand until we hit another admin keyword or max 3 tokens
            while end_idx < len(tokens) and end_idx < start_idx + 3:
                if tokens[end_idx] in ADMIN_KEYWORDS:
                    break  # Stop at keyword boundary
                end_idx += 1

            if end_idx > start_idx:
                name = ' '.join(tokens[start_idx:end_idx])
                # Normalize leading zeros for numeric districts (08 → 8, 02 → 2)
                name = normalize_admin_number(name)
                districts.append((name, start_idx, end_idx))
            i = end_idx if end_idx > start_idx else i + 1
            continue

        # Pattern 5: PHUONG / P (ward)
        if token in ['phuong', 'p']:
            # "PHUONG X" or "P X" → extract X
            start_idx = i + 1
            end_idx = start_idx

            # Expand until we hit another admin keyword or max 3 tokens
            while end_idx < len(tokens) and end_idx < start_idx + 3:
                if tokens[end_idx] in ADMIN_KEYWORDS:
                    break  # Stop at keyword boundary
                end_idx += 1

            if end_idx > start_idx:
                name = ' '.join(tokens[start_idx:end_idx])
                # Normalize leading zeros for numeric wards (06 → 6, 08 → 8)
                name = normalize_admin_number(name)
                wards.append((name, start_idx, end_idx))
            i = end_idx if end_idx > start_idx else i + 1
            continue

        # Pattern 6: XA / X (commune/ward)
        if token in ['xa', 'x']:
            if token == 'xa' or (token == 'x' and i + 1 < len(tokens)):
                # "XA X" or "X X" → extract X
                start_idx = i + 1
                end_idx = start_idx

                # Expand until we hit another admin keyword or max 3 tokens
                while end_idx < len(tokens) and end_idx < start_idx + 3:
                    if tokens[end_idx] in ADMIN_KEYWORDS:
                        break
                    end_idx += 1

                if end_idx > start_idx:
                    name = ' '.join(tokens[start_idx:end_idx])
                    # Normalize leading zeros for numeric communes/wards (06 → 6)
                    name = normalize_admin_number(name)
                    wards.append((name, start_idx, end_idx))
                i = end_idx if end_idx > start_idx else i + 1
                continue

        i += 1

    return {
        'districts': districts,
        'wards': wards
    }


def clean_token(token: str) -> str:
    """
    Clean token by removing trailing punctuation.

    This fixes matching issues where tokens like "hiep," don't match "hiep" in database.

    Args:
        token: Raw token from text split

    Returns:
        Cleaned token without trailing punctuation

    Example:
        >>> clean_token("hiep,")
        'hiep'
        >>> clean_token("my")
        'my'
    """
    return token.strip('.,;:!?')


def expand_tokens_with_context(
    tokens: List[str],
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> List[str]:
    """
    Expand abbreviations trong token list với context.

    Sau khi xác định được province/district từ các branch, hàm này expand lại
    abbreviations với context đã biết để tìm district/ward chính xác hơn.

    Args:
        tokens: List of tokens cần expand
        province_context: Province context (normalized) để expand district abbreviations
        district_context: District context (normalized) để expand ward abbreviations

    Returns:
        List of expanded tokens

    Example:
        >>> expand_tokens_with_context(["dha", "phuong", "3"], province_context="quang tri")
        ['dong', 'ha', 'phuong', '3']  # DHA → dong ha với context

        >>> expand_tokens_with_context(["tx"], province_context="bac lieu")
        ['thanh', 'xuan']  # TX → thanh xuan với context
    """
    if not tokens:
        return tokens

    # Join tokens thành text
    text = ' '.join(tokens)

    # Expand với context
    from .text_utils import expand_abbreviations
    expanded = expand_abbreviations(
        text,
        use_db=True,
        province_context=province_context,
        district_context=district_context
    )

    # Split lại thành tokens
    return expanded.split()


def generate_ngrams(tokens: List[str], max_n: int = 4) -> List[Tuple[str, Tuple[int, int], bool]]:
    """
    Generate n-grams from tokens (1-gram to max_n-gram).
    Returns list of (ngram_text, (start_idx, end_idx), has_keyword)

    Args:
        tokens: List of word tokens
        max_n: Maximum n-gram size (default: 4)

    Returns:
        List of (ngram_string, (start_index, end_index), has_admin_keyword) tuples
        Sorted by n descending (longer phrases first)
        has_admin_keyword: True if the token immediately before this n-gram is an admin keyword

    Example:
        >>> generate_ngrams(['phuong', '1', 'quan', '3'], max_n=2)
        [('phuong 1 quan 3', (0, 4), False),  # 4-gram (no preceding keyword)
         ('phuong 1 quan', (0, 3), False),     # 3-gram
         ('1 quan 3', (1, 4), True),           # 3-gram (preceded by 'phuong')
         ('phuong 1', (0, 2), False),          # 2-gram
         ('1 quan', (1, 3), True),             # 2-gram (preceded by 'phuong')
         ('quan 3', (2, 4), False),            # 2-gram
         ('phuong', (0, 1), False),            # 1-gram
         ('1', (1, 2), True),                  # 1-gram (preceded by 'phuong')
         ('quan', (2, 3), False),              # 1-gram
         ('3', (3, 4), True)]                  # 1-gram (preceded by 'quan')
    """
    from ..config import DEBUG_NGRAMS, ADMIN_KEYWORDS_FULL

    if not tokens:
        return []

    ngrams = []

    # Generate n-grams from max_n down to 1
    for n in range(min(max_n, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            ngram_tokens = tokens[i:i+n]
            # Clean tokens to remove trailing punctuation (e.g., "hiep," → "hiep")
            ngram_tokens_cleaned = [clean_token(t) for t in ngram_tokens]
            ngram_text = ' '.join(ngram_tokens_cleaned)

            # Check if the token immediately before this n-gram is an admin keyword
            has_keyword = False
            if i > 0:
                prev_token = clean_token(tokens[i-1])
                has_keyword = prev_token in ADMIN_KEYWORDS_FULL

            ngrams.append((ngram_text, (i, i+n), has_keyword))

    if DEBUG_NGRAMS:
        logger.debug(f"[NGRAMS] Generated {len(ngrams)} n-grams from {len(tokens)} tokens (max_n={max_n})")
        # Show breakdown by n
        ngram_counts = {}
        for ngram, _, _ in ngrams:
            n = len(ngram.split())
            ngram_counts[n] = ngram_counts.get(n, 0) + 1
        breakdown = ', '.join([f"{n}-gram:{count}" for n, count in sorted(ngram_counts.items(), reverse=True)])
        logger.debug(f"[NGRAMS]   Breakdown: {breakdown}")

    return ngrams


def match_in_set(
    ngram: str,
    candidates: Set[str],
    threshold=0.85,
    province_filter: Optional[str] = None,
    district_filter: Optional[str] = None,
    level: str = 'ward'
) -> List[Tuple[str, float]]:
    """
    Match n-gram against candidate set with exact/fuzzy matching.

    OPTIMIZED: Uses Token Index for pre-filtering (50-100x speedup).
    Reduces search space from 300-9,991 to 5-10 candidates.

    NEW: Returns ALL best matches (multiple exact matches or multiple fuzzy matches with same top score)
    to create multiple candidate branches for Phase 4 scoring.

    Args:
        ngram: N-gram text to match
        candidates: Set of candidate strings (fallback if Token Index unavailable)
        threshold: Fuzzy match threshold (default: 0.85)
        province_filter: Filter by province (for district/ward queries)
        district_filter: Filter by district (for ward queries)
        level: Level type ('province', 'district', 'ward', 'street')

    Returns:
        List of (matched_string, score) tuples. Empty list if no matches.
        If multiple matches have the same best score, all are returned.

    Example:
        >>> match_in_set('dien bien', get_ward_set(), level='ward', province_filter='ha noi')
        [('dien bien', 1.0)]
        >>> match_in_set('bac lieu', get_province_set(), level='province')  # Multiple exact matches
        [('bac lieu', 1.0), ('bac lieu', 1.0)]  # If exists in both province and district
    """
    from ..config import DEBUG_EXTRACTION

    if DEBUG_EXTRACTION:
        filters = []
        if province_filter:
            filters.append(f"prov={province_filter}")
        if district_filter:
            filters.append(f"dist={district_filter}")
        filter_str = f" ({', '.join(filters)})" if filters else ""
        logger.debug(f"[MATCH] Testing '{ngram}' | level={level}, threshold={threshold:.2f}{filter_str}")

    # Exact match first (fastest - O(1))
    # NEW: Don't return immediately - continue to find ALL exact matches or fuzzy matches
    exact_matches = []
    if candidates and ngram in candidates:
        exact_matches.append((ngram, 1.0))
        if DEBUG_EXTRACTION:
            logger.debug(f"[MATCH] → Found exact match in fallback set!")

    # Use Token Index for pre-filtering (province/district/ward only)
    if level in ['province', 'district', 'ward']:
        try:
            from .token_index import get_token_index
            index = get_token_index()

            # Get pre-filtered candidates from Token Index (5-10 items)
            # Use adaptive min_token_overlap: 2 for multi-token queries, 1 for single-token
            query_tokens = ngram.split()
            min_overlap = 2 if len(query_tokens) >= 2 else 1

            if level == 'ward':
                token_candidates = index.get_ward_candidates(
                    ngram,
                    province_filter=province_filter,
                    district_filter=district_filter,
                    min_token_overlap=min_overlap
                )
            elif level == 'district':
                token_candidates = index.get_district_candidates(
                    ngram,
                    province_filter=province_filter,
                    min_token_overlap=min_overlap
                )
            else:  # province
                token_candidates = index.get_province_candidates(
                    ngram,
                    min_token_overlap=min_overlap
                )

            if DEBUG_EXTRACTION:
                logger.debug(f"[MATCH] Token Index: {len(token_candidates)} pre-filtered candidates")

            # NEW: Check for exact matches in Token Index candidates
            for candidate in token_candidates:
                candidate_name = candidate['name']
                if candidate_name == ngram:
                    exact_matches.append((candidate_name, 1.0))
                    if DEBUG_EXTRACTION:
                        logger.debug(f"[MATCH] → Found exact match: '{candidate_name}'")

            # If we have exact matches from Token Index, return them immediately
            if exact_matches:
                if DEBUG_EXTRACTION:
                    logger.debug(f"[MATCH] → Returning {len(exact_matches)} exact match(es)")
                return exact_matches

            # Fuzzy match on pre-filtered candidates (5-10 instead of 300-9,991)
            # NEW: Find ALL matches with the best score (not just first one)
            best_score = 0
            all_scores = []  # Collect for smart logging

            for candidate in token_candidates:
                candidate_name = candidate['name']
                # Don't log individual fuzzy scores here - collect and log smartly
                score = ensemble_fuzzy_score(ngram, candidate_name, log=False)
                all_scores.append((candidate_name, score))

                if score >= threshold and score > best_score:
                    best_score = score

            # Collect ALL candidates with the best score
            best_matches = []
            for candidate_name, score in all_scores:
                if score == best_score and score >= threshold:
                    best_matches.append((candidate_name, score))

            # Smart logging based on DEBUG_FUZZY mode - ONLY if enabled
            if DEBUG_EXTRACTION:
                from ..config import DEBUG_FUZZY

                if DEBUG_FUZZY and all_scores:
                    # Sort by score descending
                    all_scores.sort(key=lambda x: x[1], reverse=True)

                    if DEBUG_FUZZY == 'WINNERS' and best_matches:
                        # Log all winners
                        logger.debug(f"[MATCH]   WINNER(S): {len(best_matches)} match(es)")
                        for name, score in best_matches:
                            logger.debug(f"[MATCH]     '{name}' [{score:.3f}]")
                    elif DEBUG_FUZZY == 'TOP3':
                        # Log top 3
                        logger.debug(f"[MATCH]   Top 3 candidates:")
                        for name, score in all_scores[:3]:
                            marker = " ← WINNER" if (name, score) in best_matches else ""
                            logger.debug(f"[MATCH]     '{name}': {score:.3f}{marker}")
                    elif DEBUG_FUZZY in [True, 'FULL']:
                        # Log all (original behavior)
                        for name, score in all_scores:
                            logger.debug(f"[MATCH]   '{name}': {score:.3f}")

            if best_matches:
                if DEBUG_EXTRACTION and DEBUG_FUZZY not in ['WINNERS', 'TOP3', True, 'FULL']:
                    # If FUZZY logging is off but EXTRACTION is on, still log winners
                    logger.debug(f"[MATCH] → WINNER(S): {len(best_matches)} match(es) with score {best_score:.3f}")
                return best_matches

        except Exception as e:
            # Fallback to brute force if Token Index fails
            if DEBUG_EXTRACTION:
                logger.debug(f"[MATCH] Token Index failed: {e}, falling back to brute force")
            pass

    # Fallback: Brute force for streets or if Token Index unavailable
    # Return exact_matches if already found from fallback set
    if exact_matches:
        if DEBUG_EXTRACTION:
            logger.debug(f"[MATCH] → Returning {len(exact_matches)} exact match(es) from fallback set")
        return exact_matches

    candidate_names = list(candidates) if candidates else []

    if not candidate_names:
        if DEBUG_EXTRACTION:
            logger.debug(f"[MATCH] → No match (no candidates)")
        return []

    if DEBUG_EXTRACTION:
        logger.debug(f"[MATCH] Brute force: testing {len(candidate_names)} candidates")

    # NEW: Find ALL matches with the best score
    best_score = 0
    all_scores = []

    for candidate in candidate_names:
        score = ensemble_fuzzy_score(ngram, candidate, log=False)  # Don't log individual comparisons
        all_scores.append((candidate, score))
        if score >= threshold and score > best_score:
            best_score = score

    # Collect ALL candidates with the best score
    best_matches = []
    for candidate_name, score in all_scores:
        if score == best_score and score >= threshold:
            best_matches.append((candidate_name, score))

    # Smart logging - ONLY if DEBUG_FUZZY is enabled
    if DEBUG_EXTRACTION:
        from ..config import DEBUG_FUZZY

        if DEBUG_FUZZY and all_scores:
            all_scores.sort(key=lambda x: x[1], reverse=True)

            if DEBUG_FUZZY == 'WINNERS' and best_matches:
                logger.debug(f"[MATCH]   WINNER(S): {len(best_matches)} match(es)")
                for name, score in best_matches:
                    logger.debug(f"[MATCH]     '{name}' [{score:.3f}]")
            elif DEBUG_FUZZY == 'TOP3':
                logger.debug(f"[MATCH]   Top 3 candidates:")
                for name, score in all_scores[:3]:
                    marker = " ← WINNER" if (name, score) in best_matches else ""
                    logger.debug(f"[MATCH]     '{name}': {score:.3f}{marker}")
            elif DEBUG_FUZZY in [True, 'FULL']:
                for name, score in all_scores:
                    logger.debug(f"[MATCH]   '{name}': {score:.3f}")

    if best_matches:
        if DEBUG_EXTRACTION and DEBUG_FUZZY not in ['WINNERS', 'TOP3', True, 'FULL']:
            logger.debug(f"[MATCH] → WINNER(S): {len(best_matches)} match(es) with score {best_score:.3f}")
        return best_matches

    if DEBUG_EXTRACTION:
        logger.debug(f"[MATCH] → No match (best score: {best_score:.3f} < threshold {threshold:.2f})")

    return []


def extract_with_database(
    normalized_text: str,
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    original_text_for_matching: Optional[str] = None,
    phase2_segments: list = None
) -> Dict:
    """
    Extract province/district/ward using hierarchical scoped search.

    NEW STRATEGY (mimics human reading):
    1. Extract province (known > rightmost > full scan)
    2. For each province → Extract district (scoped, with abbreviation expansion)
    3. For each (province, district) → Extract ward (scoped, with patterns)
    4. Generate candidate branches and rank by confidence

    This replaces the old bidirectional n-gram matching with a more intuitive
    right-to-left hierarchical approach.

    Args:
        normalized_text: Normalized address text
        province_known: Known province from raw data (optional, trusted 100%)
        district_known: Known district from raw data (optional, trusted 100%)
        original_text_for_matching: Original text before abbreviation expansion (for direct match bonus)
        phase2_segments: Segments with boost scores from Phase 2 (optional)

    Returns:
        Dictionary with extracted components and metadata
        - Best match: province, district, ward with scores
        - potential_* fields: For backward compatibility with Phase 3
        - Candidates ready for generate_candidate_combinations()

    Example:
        >>> extract_with_database("phuong 3 dha quang tri", province_known="quang tri")
        {
            'province': 'quang tri',
            'district': 'dong ha',
            'ward': '3',
            'province_score': 1.0,
            'district_score': 0.67,
            'ward_score': 1.0,
            'method': 'hierarchical_search',
            'match_level': 3,
            'confidence': 0.89,
            'potential_provinces': [('quang tri', 1.0, ...)],
            'potential_districts': [('dong ha', 0.67, ...)],
            'potential_wards': [('3', 1.0, ...)]
        }
    """
    if not normalized_text:
        return _empty_result()

    # Tokenize the normalized text
    tokens = normalized_text.split()

    if not tokens:
        return _empty_result()

    # Use new hierarchical search tree algorithm
    candidates = build_search_tree(
        tokens,
        province_known=province_known,
        district_known=district_known,
        max_branches=5,
        phase2_segments=phase2_segments or []
    )

    if not candidates:
        return _empty_result()

    # Get best candidate
    best = candidates[0]
    
    # Extract potential matches for backward compatibility with Phase 3
    # (Phase 3 uses these to generate candidate combinations, but now we already have candidates)
    potential_provinces = []
    potential_districts = []
    potential_wards = []

    # Collect unique values from all candidates
    seen_provinces = set()
    seen_districts = set()
    seen_wards = set()

    for cand in candidates:
        prov = cand.get('province')
        dist = cand.get('district')
        ward = cand.get('ward')

        if prov and prov not in seen_provinces:
            potential_provinces.append((prov, cand.get('province_score', 1.0), (-1, -1)))
            seen_provinces.add(prov)

        if dist and dist not in seen_districts:
            potential_districts.append((dist, cand.get('district_score', 0.0), (-1, -1)))
            seen_districts.add(dist)

        if ward and ward not in seen_wards:
            potential_wards.append((ward, cand.get('ward_score', 0.0), (-1, -1)))
            seen_wards.add(ward)

    # Build result in expected format
    result = {
        'province': best.get('province'),
        'district': best.get('district'),
        'ward': best.get('ward'),
        'province_score': best.get('province_score', 0.0),
        'district_score': best.get('district_score', 0.0),
        'ward_score': best.get('ward_score', 0.0),
        'method': 'hierarchical_search',
        'match_level': best.get('match_level', 0),
        'confidence': best.get('confidence', 0.0),
        'geographic_known_used': province_known is not None or district_known is not None,
        # Add potential matches for Phase 3 compatibility
        'potential_provinces': potential_provinces,
        'potential_districts': potential_districts,
        'potential_wards': potential_wards,
        'potential_streets': [],  # Not used in new algorithm
        # Add candidates with token positions for Phase 6
        'candidates': candidates,  # Includes normalized_tokens and token positions
        # Add original text for direct match bonus scoring
        'original_text_for_matching': original_text_for_matching
    }

    return result


def _empty_result() -> Dict:
    """Return empty extraction result."""
    return {
        'province': None,
        'district': None,
        'ward': None,
        'province_score': 0,
        'district_score': 0,
        'ward_score': 0,
        'method': 'none',
        'match_level': 0,
        'confidence': 0.0,
        'geographic_known_used': False,
        'potential_provinces': [],
        'potential_districts': [],
        'potential_wards': [],
        'potential_streets': []
    }


def generate_candidate_combinations(
    extraction_result: Dict,
    max_candidates: int = 5
) -> List[Dict]:
    """
    Generate all valid combinations from potential matches.

    Strategy:
    1. If known values exist (score=100), use them as fixed
    2. For non-known values, generate combinations from potential matches
    3. Validate hierarchy for each combination
    4. Limit to top N candidates based on combined scores

    Args:
        extraction_result: Output from extract_with_database()
        max_candidates: Maximum number of candidates to return (default: 5)

    Returns:
        List of candidate dictionaries, each with:
        - province, district, ward
        - province_score, district_score, ward_score
        - combined_score (for ranking)
        - match_level, confidence

    Example:
        >>> result = extract_with_database("hong hai ha long", province_known="quang ninh")
        >>> candidates = generate_candidate_combinations(result, max_candidates=3)
        >>> len(candidates)
        3
        >>> candidates[0]
        {'province': 'quang ninh', 'district': 'ha long', 'ward': 'hong hai', ...}
    """
    # Get normalized text for validation
    normalized_text = extraction_result.get('normalized_text', '')
    # Get best match (used as fallback)
    best_match = {
        'province': extraction_result.get('province'),
        'district': extraction_result.get('district'),
        'ward': extraction_result.get('ward'),
        'province_score': extraction_result.get('province_score', 0),
        'district_score': extraction_result.get('district_score', 0),
        'ward_score': extraction_result.get('ward_score', 0),
        'match_level': extraction_result.get('match_level', 0),
        'confidence': extraction_result.get('confidence', 0),
        'geographic_known_used': extraction_result.get('geographic_known_used', False),
        'method': extraction_result.get('method', 'unknown')
    }

    # Get potential matches
    potential_provinces = extraction_result.get('potential_provinces', [])
    potential_districts = extraction_result.get('potential_districts', [])
    potential_wards = extraction_result.get('potential_wards', [])
    potential_streets = extraction_result.get('potential_streets', [])

    # If province is known (score=1.0), use it as fixed
    province_fixed = best_match['province_score'] == 1.0
    district_fixed = best_match['district_score'] == 1.0

    # Prepare province candidates
    if province_fixed:
        province_candidates = [(best_match['province'], best_match['province_score'])]
    elif potential_provinces:
        province_candidates = [(name, score) for name, score, _ in potential_provinces[:3]]
    elif best_match['province']:
        province_candidates = [(best_match['province'], best_match['province_score'])]
    else:
        province_candidates = [(None, 0)]

    # Prepare district candidates
    if district_fixed:
        district_candidates = [(best_match['district'], best_match['district_score'])]
    elif potential_districts:
        # INCREASED LIMIT: Keep top 5 instead of 3 to handle ambiguous names (e.g., "nam dinh" + "y yen")
        district_candidates = [(name, score) for name, score, _ in potential_districts[:5]]
    elif best_match['district']:
        district_candidates = [(best_match['district'], best_match['district_score'])]
    else:
        district_candidates = [(None, 0)]

    # Prepare ward candidates
    # Always include potential wards if available (even if best_match ward is None)
    # IMPROVED: Always add (None, 0) fallback to handle missing ward level (common in real addresses)
    if potential_wards:
        ward_candidates = [(name, score) for name, score, _ in potential_wards[:3]]
        # Always add None as fallback (ward might be street name, not ward)
        ward_candidates.append((None, 0))
    elif best_match['ward']:
        ward_candidates = [(best_match['ward'], best_match['ward_score']), (None, 0)]
    else:
        ward_candidates = [(None, 0)]

    # NEW: Infer districts for wards that don't have districts
    # This prevents invalid (province, None, ward) combinations
    # Each ward belongs to exactly ONE district - we should infer it from the database
    if ward_candidates and province_candidates:
        inferred_districts = []

        for ward_name, ward_score in ward_candidates:
            if ward_name:  # Skip None
                # Use first province candidate (most common case)
                # In multi-province scenarios, we'd need to iterate all provinces
                for prov_name, prov_score in province_candidates[:1]:
                    if prov_name:
                        # Infer district from ward using database lookup
                        district_inferred = infer_district_from_ward(prov_name, ward_name)
                        if district_inferred:
                            # Add if not already in district_candidates (avoid duplicates)
                            existing_districts = [d[0] for d in district_candidates if d[0]]
                            if district_inferred not in existing_districts:
                                inferred_districts.append((district_inferred, 1.0))  # High confidence (DB-sourced)

        # Merge inferred districts into district_candidates
        if inferred_districts:
            if district_candidates == [(None, 0)]:
                # Replace None with inferred districts + keep None for province-only fallback
                district_candidates = inferred_districts + [(None, 0)]
            elif not district_fixed:
                # Add to existing candidates (only if district not fixed/known)
                district_candidates.extend(inferred_districts)

    # Generate all combinations
    from itertools import product
    combinations = []

    # Build lookup for ngram_keys (token positions)
    # potential_provinces/districts/wards have format: [(name, score, (start_idx, end_idx)), ...]
    province_positions = {name: ngram_key for name, score, ngram_key in potential_provinces} if potential_provinces else {}
    district_positions = {name: ngram_key for name, score, ngram_key in potential_districts} if potential_districts else {}
    ward_positions = {name: ngram_key for name, score, ngram_key in potential_wards} if potential_wards else {}

    for (prov, prov_score), (dist, dist_score), (ward, ward_score) in product(
        province_candidates, district_candidates, ward_candidates
    ):
        # Build token_positions dict for this combination
        token_positions = {}
        if prov and prov in province_positions:
            token_positions['province'] = province_positions[prov]
        if dist and dist in district_positions:
            token_positions['district'] = district_positions[dist]
        if ward and ward in ward_positions:
            token_positions['ward'] = ward_positions[ward]

        # Calculate base fuzzy score (average of non-zero scores)
        scores = [s for s in [prov_score, dist_score, ward_score] if s > 0]
        base_score = sum(scores) / len(scores) if scores else 0

        # Calculate proximity score (NEW!)
        proximity_score = calculate_proximity_score(
            {'province': prov, 'district': dist, 'ward': ward},
            token_positions
        )

        # Calculate order bonus (NEW!)
        order_bonus = calculate_order_bonus(token_positions)

        # Calculate adjacency bonus (NEW!)
        # Give 15% bonus if ward is IMMEDIATELY BEFORE district (ward_end == district_start)
        adjacency_bonus = 1.0
        if 'ward' in token_positions and 'district' in token_positions:
            ward_end = token_positions['ward'][1]
            district_start = token_positions['district'][0]
            if ward_end == district_start:
                adjacency_bonus = 1.15  # 15% bonus for perfectly adjacent ward-district

        # Calculate match level
        match_level = 0
        if ward:
            match_level = 3
        elif dist:
            match_level = 2
        elif prov:
            match_level = 1

        # Completeness score
        completeness = 1.0 if match_level == 3 else 0.7 if match_level == 2 else 0.4

        # Validate hierarchy if we have province and ward/district
        hierarchy_valid = True
        if prov and (dist or ward):
            hierarchy_valid = validate_hierarchy(prov, dist, ward)

        # Combined score with new formula (prioritize proximity):
        # - Proximity: 50% (MAJOR - ward should be immediately before district)
        # - Base fuzzy scores: 30%
        # - Completeness: 15%
        # - Hierarchy: 5%
        # Then apply order bonus and adjacency bonus multipliers
        hierarchy_multiplier = 1.0 if hierarchy_valid else 0.5
        combined_score = (
            proximity_score * 0.5 +
            base_score * 0.3 +
            completeness * 0.15 +
            (1.0 if hierarchy_valid else 0.0) * 0.05
        ) * order_bonus * adjacency_bonus

        # NEW: Direct Text Match Bonus
        # Give bonus to candidates whose district/ward appears in ORIGINAL text (before abbreviation expansion)
        # This prevents false matches from abbreviation expansion (e.g., "TP" -> "Tan Phu" when "Go Vap" is correct)
        original_text_for_match = extraction_result.get('original_text_for_matching', normalized_text)
        direct_match_bonus = 1.0

        # Check district match in original text (before expansion)
        if dist and original_text_for_match:
            # Normalize district for comparison (remove accents, lowercase)
            from ..utils.text_utils import remove_vietnamese_accents
            dist_normalized = remove_vietnamese_accents(dist.lower())
            original_normalized = remove_vietnamese_accents(original_text_for_match.lower())

            # Check if district name appears in original text
            if dist_normalized in original_normalized:
                direct_match_bonus *= 1.15  # +15% bonus for district in original text

        # Check ward match in original text (before expansion)
        if ward and original_text_for_match:
            from ..utils.text_utils import remove_vietnamese_accents
            ward_normalized = remove_vietnamese_accents(ward.lower())
            original_normalized = remove_vietnamese_accents(original_text_for_match.lower())

            # Check if ward name appears in original text
            if ward_normalized in original_normalized:
                direct_match_bonus *= 1.10  # +10% bonus for ward in original text

        # Apply direct match bonus
        combined_score *= direct_match_bonus

        # IMPROVED: Allow candidates with missing levels (e.g., province + district only)
        # Common in real-world addresses where ward/commune is not specified
        # Only strict requirement: must have at least province OR district
        # Hierarchy validation still applies if multiple levels are present
        has_minimal_info = bool(prov or dist)
        if has_minimal_info and (hierarchy_valid or not (prov and dist and ward)):
            # Lookup full administrative names from database
            province_full, district_full, ward_full = lookup_full_names(prov, dist, ward)

            combinations.append({
                'province': prov,
                'district': dist,
                'ward': ward,
                'province_full': province_full,
                'district_full': district_full,
                'ward_full': ward_full,
                'province_score': prov_score,  # Already 0-1 for Phase 4
                'district_score': dist_score,  # Already 0-1 for Phase 4
                'ward_score': ward_score,      # Already 0-1 for Phase 4
                'combined_score': combined_score,
                'match_level': match_level,
                'confidence': combined_score,  # Already 0-1
                'geographic_hint_used': best_match['geographic_known_used'],  # For Phase 4 scoring
                'method': best_match['method'],
                'hierarchy_valid': hierarchy_valid,
                # NEW: Proximity scoring metadata
                'proximity_score': proximity_score,
                'order_bonus': order_bonus,
                'token_positions': token_positions,  # Keep for debugging
                # Add attributes needed by Phase 4 calculate_confidence_score()
                'match_type': 'exact',  # Database-based candidates are exact matches
                'at_rule': match_level,  # at_rule equals match_level (1=province, 2=district, 3=ward)
                'source': 'db_exact_match'  # Source for Phase 4 source weighting
            })

    # NEW: Generate street-based candidates
    # When we have province + street matches but no clear district/ward
    # Use admin_streets table to lookup district for each street
    if potential_streets and best_match['province']:
        # FIX 3: Sort potential_streets to prioritize multi-token over single-token
        # "giai phong" (2 tokens) should rank higher than "22" (1 token)
        # Sort by: (token_count DESC, score DESC)
        sorted_streets = sorted(
            potential_streets,
            key=lambda x: (len(x[0].split()), x[1]),  # (token_count, score)
            reverse=True
        )

        for street_name, street_score, ngram_key in sorted_streets[:3]:  # Limit to top 3 streets
            # Query admin_streets to get all districts for this street in the province
            street_districts = get_streets_by_province(
                province=best_match['province'],
                street=street_name
            )

            for street_record in street_districts:
                dist_from_street = street_record.get('district_name_normalized')

                # Skip if this district is already in our regular candidates
                # (to avoid duplicates with higher scores)
                if any(c['district'] == dist_from_street and c['ward'] is None
                       for c in combinations):
                    continue

                # Create street-based candidate
                # Score: Lower than ward matches but higher than province-only
                # Formula: (province_score + street_match_score) / 2 * 0.75 (25% penalty for being street-based)
                # Rationale: Phase 4 will further differentiate via source_weight (street_based=8 < db_exact_match=15)
                prov_score = best_match['province_score']
                street_match_score = street_score  # Already 0-1
                combined_score = ((prov_score + street_match_score) / 2) * 0.75  # 25% penalty

                # FIX 2: Penalty for inferred district NOT in text
                # If district is inferred from database but doesn't appear in input text → heavy penalty
                # This prevents "22" street → "long bien" from ranking high when "long bien" not in text
                district_in_text = dist_from_street in normalized_text if normalized_text else False
                if not district_in_text:
                    combined_score *= 0.3  # 70% penalty for inferred district not in text

                # Validate hierarchy
                hierarchy_valid = validate_hierarchy(
                    best_match['province'],
                    dist_from_street,
                    None
                )

                if hierarchy_valid:
                    # Lookup full administrative names from database
                    province_full, district_full, ward_full = lookup_full_names(
                        best_match['province'],
                        dist_from_street,
                        None
                    )

                    combinations.append({
                        'province': best_match['province'],
                        'district': dist_from_street,
                        'ward': None,
                        'province_full': province_full,
                        'district_full': district_full,
                        'ward_full': ward_full,
                        'province_score': prov_score,
                        'district_score': street_match_score,
                        'ward_score': 0,
                        'combined_score': combined_score,
                        'match_level': 2,  # Province + District
                        'confidence': combined_score,  # Already 0-1
                        'geographic_known_used': best_match['geographic_known_used'],
                        'source': 'street_based',  # Changed from 'method' to 'source' for Phase 4 recognition
                        'match_type': 'hierarchical_fallback',  # Lower priority than exact/fuzzy matches
                        'at_rule': 2,  # Province + District (no ward)
                        'hierarchy_valid': hierarchy_valid,
                        'street_name': street_name  # Keep street info for debugging
                    })

    # Sort by combined_score descending, then by match_level descending
    combinations.sort(key=lambda x: (x['combined_score'], x['match_level']), reverse=True)

    # Limit to top N
    return combinations[:max_candidates]


def calculate_proximity_score(candidate: Dict, token_positions: Dict[str, Tuple[int, int]]) -> float:
    """
    Calculate proximity score based on token distances between components.

    Principle: Components closer together in text are more likely to be related.

    Args:
        candidate: Candidate dictionary with component names
        token_positions: Dict mapping component type to (start_idx, end_idx) tuples
            e.g., {'province': (7, 9), 'district': (4, 7), 'ward': (2, 4)}

    Returns:
        Proximity score (0.0-1.0), higher = components closer together

    Example:
        Input: "YEN LAC VINH TUY HAI BA TRUNG HA NOI"
               street  ward     district      province
               (0,2)   (2,4)    (4,7)        (7,9)

        Distances:
        - ward→district: |4-4| = 0 (adjacent) → score 1.0
        - district→province: |7-7| = 0 (adjacent) → score 1.0

        Final: avg(1.0, 1.0) = 1.0 (perfect proximity)
    """
    if not token_positions:
        return 0.5  # Neutral score if no position info

    # Distance → score mapping (STRICT: heavily penalize non-adjacent)
    def dist_to_score(distance: int) -> float:
        """Convert token distance to proximity score."""
        if distance <= 1:
            return 1.0  # Adjacent or overlapping (PERFECT)
        elif distance <= 3:
            return 0.6  # Close (moderate penalty)
        elif distance <= 5:
            return 0.3  # Medium distance (heavy penalty)
        else:
            return 0.1  # Far apart (severe penalty)

    scores = []

    # Calculate pairwise distances for available components
    # Priority: ward-district, district-province (street-ward distance less reliable)

    if 'ward' in token_positions and 'district' in token_positions:
        ward_pos = token_positions['ward']
        district_pos = token_positions['district']
        # Distance = gap between components (0 = adjacent)
        distance = abs(district_pos[0] - ward_pos[1])
        scores.append(dist_to_score(distance))

    if 'district' in token_positions and 'province' in token_positions:
        district_pos = token_positions['district']
        province_pos = token_positions['province']
        distance = abs(province_pos[0] - district_pos[1])
        scores.append(dist_to_score(distance))

    # If only ward-province available (no district)
    if ('ward' in token_positions and 'province' in token_positions
            and 'district' not in token_positions):
        ward_pos = token_positions['ward']
        province_pos = token_positions['province']
        distance = abs(province_pos[0] - ward_pos[1])
        scores.append(dist_to_score(distance))

    # Return average proximity score
    if scores:
        return sum(scores) / len(scores)
    else:
        return 0.5  # Neutral if no pairs available


def calculate_order_bonus(token_positions: Dict[str, Tuple[int, int]]) -> float:
    """
    Calculate bonus if components follow geographic order (ward < district < province).

    Note: Order is NOT mandatory (30% of real addresses violate this).
    This is just a small bonus, not a requirement.

    Args:
        token_positions: Dict mapping component type to (start_idx, end_idx) tuples

    Returns:
        Multiplier: 1.1 if correct order, 1.0 otherwise

    Example:
        Input: ward=(2,4), district=(4,7), province=(7,9)
        Order: 2 < 4 < 7 ✓ → bonus 1.1 (+10%)

        Input: district=(4,7), ward=(2,4), province=(7,9)
        Order: 4 > 2 ✗ → no bonus 1.0
    """
    if not token_positions:
        return 1.0

    # Extract start positions
    positions = []

    if 'ward' in token_positions:
        positions.append(('ward', token_positions['ward'][0]))
    if 'district' in token_positions:
        positions.append(('district', token_positions['district'][0]))
    if 'province' in token_positions:
        positions.append(('province', token_positions['province'][0]))

    # Need at least 2 components to check order
    if len(positions) < 2:
        return 1.0

    # Check if order is correct: ward < district < province
    # Define expected order
    expected_order = ['ward', 'district', 'province']

    # Get sorted positions by token index
    sorted_positions = sorted(positions, key=lambda x: x[1])
    actual_order = [comp_type for comp_type, _ in sorted_positions]

    # Check if actual order matches expected order (for components that exist)
    # Filter expected_order to only include components that exist
    filtered_expected = [comp for comp in expected_order if comp in [p[0] for p in positions]]

    if actual_order == filtered_expected:
        return 1.1  # +10% bonus for correct order
    else:
        return 1.0  # No penalty for incorrect order (common in real data)


def _calculate_extraction_confidence(
    province_score: float,
    district_score: float,
    ward_score: float,
    match_level: int,
    has_known: bool
) -> float:
    """
    Calculate confidence based on match scores and level.

    Formula:
    - Base: Average of match scores
    - Bonus: +0.1 for match_level 3, +0.05 for level 2
    - Bonus: +0.1 if geographic known values were used
    """
    scores = []
    if province_score > 0:
        scores.append(province_score)
    if district_score > 0:
        scores.append(district_score)
    if ward_score > 0:
        scores.append(ward_score)

    if not scores:
        return 0.0

    # Base confidence (average of scores)
    base = sum(scores) / len(scores)

    # Match level bonus
    if match_level == 3:
        base += 0.1
    elif match_level == 2:
        base += 0.05

    # Geographic known bonus
    if has_known:
        base += 0.1

    return min(base, 1.0)


# =============================================================================
# NEW: Multi-Branch Hierarchical Search Functions
# =============================================================================

def find_token_position(phrase: str, tokens: List[str]) -> int:
    """
    Find the start index of a phrase in a token list.

    Args:
        phrase: The phrase to find (e.g., "ha noi")
        tokens: List of tokens to search in

    Returns:
        Start index of phrase in tokens, or -1 if not found

    Example:
        >>> find_token_position("ha noi", ["phuong", "3", "ha", "noi", "viet", "nam"])
        2
        >>> find_token_position("ha noi", ["phuong", "3", "hanoi"])
        -1
    """
    if not phrase or not tokens:
        return -1

    phrase_tokens = phrase.split()
    if not phrase_tokens:
        return -1

    # Search for phrase in tokens
    for i in range(len(tokens) - len(phrase_tokens) + 1):
        if tokens[i:i+len(phrase_tokens)] == phrase_tokens:
            return i

    return -1


def adjust_scores_by_position(
    candidates: List[Tuple],
    tokens: List[str],
    name_index: int = 0
) -> List[Tuple]:
    """
    Adjust candidate scores based on their position in tokens.
    Candidates closer to the end get higher scores (tokens at end are more reliable).

    Formula: multiplier = 0.8 + (relative_position * POSITION_PENALTY_FACTOR)
    - Token at start (pos=0): 0.8x
    - Token at end (pos=1): 1.0x

    Args:
        candidates: List of tuples (name, score, source, ...) or (name, score, source)
        tokens: List of tokens to find positions in
        name_index: Index of 'name' in each candidate tuple (default: 0)

    Returns:
        List of candidates with adjusted scores

    Example:
        >>> candidates = [("loc hoa", 0.95, "fuzzy"), ("hoa phu", 0.95, "fuzzy")]
        >>> tokens = ["phuoc", "loc", "hoa", "phu", "long", "ho"]
        >>> adjusted = adjust_scores_by_position(candidates, tokens)
        >>> # "loc hoa" (pos=1) → 0.95 * 0.83 = 0.79
        >>> # "hoa phu" (pos=2) → 0.95 * 1.00 = 0.95 ✓
    """
    from ..config import POSITION_PENALTY_FACTOR

    if len(candidates) <= 1:
        return candidates

    # Find positions for all candidates
    positions = []
    for cand in candidates:
        name = cand[name_index]
        pos = find_token_position(name, tokens)
        positions.append(pos)

    # Filter out candidates with position = -1 (not found)
    valid_candidates = [(cand, pos) for cand, pos in zip(candidates, positions) if pos >= 0]

    if len(valid_candidates) <= 1:
        return candidates  # No adjustment needed

    # Get min/max positions
    valid_positions = [pos for _, pos in valid_candidates]
    min_pos = min(valid_positions)
    max_pos = max(valid_positions)

    # Adjust scores based on position
    adjusted = []
    for cand, pos in zip(candidates, positions):
        if pos < 0:
            # Position unknown - keep original score
            adjusted.append(cand)
        elif max_pos > min_pos:
            # Calculate relative position (0.0 = start, 1.0 = end)
            relative = (pos - min_pos) / (max_pos - min_pos)
            multiplier = (1.0 - POSITION_PENALTY_FACTOR) + (relative * POSITION_PENALTY_FACTOR)
            # multiplier ranges from 0.8 to 1.0 (with PENALTY=0.2)

            # Adjust score (score is at index 1 in tuple)
            cand_list = list(cand)
            cand_list[1] = cand_list[1] * multiplier
            adjusted.append(tuple(cand_list))
        else:
            # All at same position - no adjustment
            adjusted.append(cand)

    return adjusted


def extract_province_candidates(
    tokens: List[str],
    province_known: Optional[str] = None,
    fuzzy_threshold: float = 0.90
) -> List[Tuple[str, float, str, bool]]:
    """
    Extract province candidates from multiple sources (mimics human reading).

    Strategy:
    1. Known value (100% confidence) - highest priority
    2. Rightmost tokens (last 1-3 words) - where province usually appears
    3. Full n-gram scan - fallback

    Args:
        tokens: List of normalized tokens
        province_known: Known province value (optional, trusted 100%)
        fuzzy_threshold: Minimum fuzzy score for full scan (default: 0.6)

    Returns:
        List of (province_name, score, source, has_district_collision) tuples, sorted by score DESC
        - has_district_collision: True if this province name also exists as a district name

    Example:
        >>> extract_province_candidates(['phuong', '3', 'dha', 'quang', 'tri'], province_known='quang tri')
        [('quang tri', 1.0, 'known', False)]
        >>> extract_province_candidates(['bach', 'khoa', 'ha', 'noi'])
        [('ha noi', 1.0, 'rightmost', False), ...]
        >>> extract_province_candidates(['phuong', '5', 'ben', 'tre'])
        [('ben tre', 1.0, 'rightmost', True), ...]  # ben tre is both province AND district
    """
    from .db_utils import check_province_district_collision

    candidates = []
    province_set = get_province_set()

    # Source 1: Known value (check if also in text for double-match bonus)
    if province_known:
        # Check if known province also appears in text
        # This handles ambiguous cases like "BAC LIEU" (can be province OR district)
        # If it's in both known + text → highest priority (1.2 score)
        province_in_text = False

        # Check rightmost tokens (where province usually appears)
        for n in range(min(3, len(tokens)), 0, -1):
            ngram_tokens = tokens[-n:]
            ngram = ' '.join(ngram_tokens)
            score = ensemble_fuzzy_score(ngram, province_known)
            if score >= 0.95:  # Very strict threshold
                province_in_text = True
                break

        # If not in rightmost, check full text (less common but possible)
        if not province_in_text:
            all_ngrams = generate_ngrams(tokens, max_n=3)
            for ngram, _, _ in all_ngrams:
                if ngram.isdigit():
                    continue
                score = ensemble_fuzzy_score(ngram, province_known)
                if score >= 0.95:
                    province_in_text = True
                    break

        if province_in_text:
            # DOUBLE MATCH: Known + In Text → Highest priority (1.2 score)
            # This prioritizes correct interpretation when name is ambiguous
            # Example: "BAC LIEU" in text + Tỉnh=BAC LIEU → treat as province, not district
            candidates.append((province_known, 1.2, 'known_and_in_text'))
        else:
            # Only known, not in text → Normal priority
            candidates.append((province_known, 1.0, 'known'))

        # Remove duplicates and check for province/district collisions
        result = []
        for prov, score, source in candidates:
            collision_info = check_province_district_collision(prov)
            has_collision = collision_info['has_collision']
            result.append((prov, score, source, has_collision))

        # Adjust scores based on position
        adjusted_result = []
        for prov, score, source, has_collision in result:
            adjusted_scores = adjust_scores_by_position([(prov, score, source)], tokens, name_index=0)
            if adjusted_scores:
                adjusted_result.append((adjusted_scores[0][0], adjusted_scores[0][1], adjusted_scores[0][2], has_collision))
            else:
                adjusted_result.append((prov, score, source, has_collision))

        # Sort by score DESC
        adjusted_result.sort(key=lambda x: x[1], reverse=True)

        # IMPORTANT: If province_known is provided, return only it
        # Don't search for alternative candidates - known province is 100% trusted
        # This prevents false positives from province names appearing in the address text
        return adjusted_result

    # Source 2: Rightmost tokens (last 1-3 words)
    # Vietnamese addresses typically end with province
    rightmost_ngrams = []
    for n in range(min(3, len(tokens)), 0, -1):
        ngram_tokens = tokens[-n:]
        ngram_text = ' '.join(ngram_tokens)
        ngram_key = (len(tokens) - n, len(tokens))
        rightmost_ngrams.append((ngram_text, ngram_key))

    for ngram, ngram_key in rightmost_ngrams:
        match_results = match_in_set(
            ngram,
            province_set,
            threshold=0.85,  # Balanced threshold (handles typos & spacing like "co nhue1")
            level='province'
        )
        # NEW: match_in_set now returns list of tuples
        for match_name, match_score in match_results:
            candidates.append((match_name, match_score, 'rightmost'))

    # Source 3: Full n-gram scan
    # CHANGED: Always run full scan (not just when no rightmost match)
    # This ensures we find ALL exact matches in text
    # Deduplicate logic (line 1386) will handle duplicates
    all_ngrams = generate_ngrams(tokens, max_n=3)
    for ngram, ngram_key, _ in all_ngrams:
        # Skip numeric tokens
        if ngram.isdigit():
            continue
        # Skip noise words
        if has_noise_word(ngram, tokens, ngram_key[0], ngram_key[1]):
            continue

        match_results = match_in_set(
            ngram,
            province_set,
            threshold=fuzzy_threshold,
            level='province'
        )
        # NEW: match_in_set now returns list of tuples
        for match_name, match_score in match_results:
            candidates.append((match_name, match_score, 'full_scan'))

    # Remove duplicates (keep highest score for each province)
    # Priority: known_and_in_text (1.2) > known (1.0) > rightmost/full_scan
    unique_candidates = {}
    source_priority = {
        'known_and_in_text': 3,
        'known': 2,
        'rightmost': 1,
        'full_scan': 0
    }

    for prov, score, source in candidates:
        if prov not in unique_candidates:
            unique_candidates[prov] = (score, source)
        else:
            # Keep candidate with higher score, or higher source priority if scores equal
            existing_score, existing_source = unique_candidates[prov]
            if score > existing_score:
                unique_candidates[prov] = (score, source)
            elif score == existing_score and source_priority.get(source, 0) > source_priority.get(existing_source, 0):
                unique_candidates[prov] = (score, source)

    # Convert back to list and check for province/district collisions
    result = []
    for prov, (score, source) in unique_candidates.items():
        # Check if this province name also exists as a district
        collision_info = check_province_district_collision(prov)
        has_collision = collision_info['has_collision']
        result.append((prov, score, source, has_collision))

    # Adjust scores based on position (tokens at end are more reliable)
    # Update to handle 4-tuple format
    adjusted_result = []
    for prov, score, source, has_collision in result:
        adjusted_scores = adjust_scores_by_position([(prov, score, source)], tokens, name_index=0)
        if adjusted_scores:
            adjusted_result.append((adjusted_scores[0][0], adjusted_scores[0][1], adjusted_scores[0][2], has_collision))
        else:
            adjusted_result.append((prov, score, source, has_collision))

    # Sort by score DESC, then by source priority
    adjusted_result.sort(key=lambda x: (x[1], source_priority.get(x[2], 0)), reverse=True)

    return adjusted_result


def extract_district_scoped(
    tokens: List[str],
    province_context: str,
    province_tokens_used: Tuple[int, int],
    district_known: Optional[str] = None,
    fuzzy_threshold: float = 0.90,
    allow_token_reuse: bool = False
) -> List[Tuple[str, float, str, Tuple[int, int]]]:
    """
    Extract district candidates scoped to a specific province.

    Strategy:
    1. If district_known provided, return it directly (100% confidence)
    2. Remove province tokens from search space (unless allow_token_reuse=True)
    3. Check rightmost remaining tokens first (where district usually appears)
    4. Try abbreviation expansion with province context (e.g., "DHA" + "quang tri" → "dong ha")
    5. Fuzzy match with districts of the province
    6. FALLBACK: If no district found, try finding ward and infer district

    Args:
        tokens: List of normalized tokens
        province_context: Confirmed province name (normalized)
        province_tokens_used: (start_idx, end_idx) of province in tokens
        district_known: Known district value (optional, trusted 100%)
        fuzzy_threshold: Minimum fuzzy score (default: 0.5, lower because we have province context)
        allow_token_reuse: If True, allow district search on province tokens (for collision cases)

    Returns:
        List of (district_name, score, source, (start_idx, end_idx)) tuples

    Example:
        >>> extract_district_scoped(['phuong', '3', 'dha'], 'quang tri', (3, 3), None)
        [('dong ha', 0.67, 'fuzzy', (2, 3))]
        >>> extract_district_scoped(['phuong', '5', 'ben', 'tre'], 'ben tre', (2, 4), allow_token_reuse=True)
        [('ben tre', 1.0, 'exact', (2, 4))]  # Reuses province tokens for district match
    """
    candidates = []

    # Source 1: Known value (100% confidence)
    if district_known:
        # District known but we don't know its position in tokens
        # Return with dummy position (-1, -1)
        candidates.append((district_known, 1.0, 'known', (-1, -1)))
        return candidates

    # Get districts scoped to province
    from .db_utils import get_districts_by_province
    districts_data = get_districts_by_province(province_context)
    districts_set = {d['district_name_normalized'] for d in districts_data}

    if not districts_set:
        return []  # No districts for this province (shouldn't happen)

    # Remove province tokens from search space
    # COLLISION FIX: If allow_token_reuse=True, include province tokens in district search
    # This handles cases where province name == district name (e.g., "ben tre")
    prov_start, prov_end = province_tokens_used

    # Log token removal
    if prov_start != -1 and prov_end != -1:
        removed_tokens = tokens[prov_start:prov_end]
        logger.debug(f"[TOKEN] Province tokens matched at positions [{prov_start}:{prov_end}]")
        logger.debug(f"[TOKEN] Removed tokens: {removed_tokens}")
        logger.debug(f"[TOKEN] Original token count: {len(tokens)}")

    available_tokens = []
    for i, token in enumerate(tokens):
        # If allow_token_reuse, include ALL tokens (even province tokens)
        # Otherwise, exclude province tokens
        if allow_token_reuse or i < prov_start or i >= prov_end:
            available_tokens.append((i, token))

    if allow_token_reuse:
        logger.debug(f"[⚠️ COLLISION] Token reuse enabled - including province tokens in district search")

    logger.debug(f"[TOKEN] Remaining tokens for district search: {len(available_tokens)} tokens")
    logger.debug(f"[TOKEN] Available: {[t for _, t in available_tokens]}")

    if not available_tokens:
        logger.debug("[TOKEN] No tokens left after removing province")
        return []  # No tokens left to search

    # ========== NEW: EXPAND AVAILABLE TOKENS WITH PROVINCE CONTEXT ==========
    # Sau khi xác định province, expand lại abbreviations với context
    # Ví dụ: "DHA" với province="quang tri" → "dong ha"
    token_strings = [t for _, t in available_tokens]
    original_token_strings = token_strings[:]  # Keep original for comparison

    expanded_strings = expand_tokens_with_context(
        token_strings,
        province_context=province_context
    )

    # Check if expansion happened
    if expanded_strings != original_token_strings:
        logger.debug(f"[EXPAND] District tokens expanded with province='{province_context}':")
        logger.debug(f"[EXPAND]   Before: {original_token_strings}")
        logger.debug(f"[EXPAND]   After:  {expanded_strings}")

        # Rebuild available_tokens với expanded tokens
        # IMPORTANT: Expansion có thể tăng số tokens (DHA → dong ha = 2 tokens)
        # Chúng ta cần map lại indices
        available_tokens_expanded = []
        orig_idx = 0
        for expanded_token in expanded_strings:
            if orig_idx < len(available_tokens):
                # Reuse original index for first expanded token
                original_idx = available_tokens[orig_idx][0]
                available_tokens_expanded.append((original_idx, expanded_token))
                orig_idx += 1
            else:
                # Additional tokens from expansion (no original index)
                # Use last original index + offset
                last_idx = available_tokens_expanded[-1][0] if available_tokens_expanded else 0
                available_tokens_expanded.append((last_idx, expanded_token))

        available_tokens = available_tokens_expanded
        logger.debug(f"[EXPAND] Updated available_tokens: {[t for _, t in available_tokens]}")
    # ========== END EXPANSION ==========

    # Source 2: Rightmost remaining tokens
    # Try from longest to shortest (3-gram → 2-gram → 1-gram)
    from ..config import NUMERIC_WITHOUT_KEYWORD_PENALTY, NUMERIC_WITH_KEYWORD_BONUS, ADMIN_KEYWORDS_FULL

    for n in range(min(3, len(available_tokens)), 0, -1):
        # Get last n available tokens
        last_n_tokens = available_tokens[-n:]
        ngram_tokens = [t for _, t in last_n_tokens]
        ngram_text = ' '.join(ngram_tokens)
        start_idx = last_n_tokens[0][0]
        end_idx = last_n_tokens[-1][0] + 1

        # Skip if long numeric (street numbers), but allow 1-2 digit numbers (districts/wards)
        if ngram_text.isdigit() and len(ngram_text) > 2:
            continue  # Skip "660", "123" but allow "8", "12"

        # Normalize leading zeros for numeric districts (08 → 8, 02 → 2)
        ngram_text_normalized = normalize_admin_number(ngram_text)

        # Check if this n-gram is preceded by an admin keyword (quan, huyen, etc.)
        # For rightmost tokens, we need to check if any token before the start is a keyword
        has_keyword = False
        if len(available_tokens) > n:
            # Check the token immediately before the rightmost n tokens
            prev_token = clean_token(available_tokens[-n-1][1])
            has_keyword = prev_token in ADMIN_KEYWORDS_FULL

        # Calculate keyword context multiplier for 1-2 digit numbers
        keyword_multiplier = 1.0
        if ngram_text_normalized.isdigit() and len(ngram_text_normalized) <= 2:
            if has_keyword:
                # Bonus for numbers with keywords (e.g., "quan 3")
                keyword_multiplier = NUMERIC_WITH_KEYWORD_BONUS
            else:
                # Penalty for standalone numbers (e.g., just "3")
                keyword_multiplier = NUMERIC_WITHOUT_KEYWORD_PENALTY

        # Try abbreviation expansion first (with province context)
        from .text_utils import expand_abbreviations
        expanded = expand_abbreviations(ngram_text_normalized, use_db=True, province_context=province_context)
        if expanded != ngram_text_normalized.lower():
            # Abbreviation was expanded, check if it matches a district
            if expanded in districts_set:
                # Apply keyword multiplier to abbreviation expansions too
                adjusted_score = 1.0 * keyword_multiplier
                candidates.append((expanded, adjusted_score, 'abbreviation', (start_idx, end_idx)))
                continue

        # Fuzzy match with districts of this province
        match_results = match_in_set(
            ngram_text_normalized,
            districts_set,
            threshold=fuzzy_threshold,
            province_filter=province_context,
            level='district'
        )
        # NEW: match_in_set now returns list of tuples
        for match_name, match_score in match_results:
            # Apply keyword context multiplier
            adjusted_score = match_score * keyword_multiplier
            candidates.append((match_name, adjusted_score, 'fuzzy', (start_idx, end_idx)))

    # Source 3: Full scan of remaining tokens
    # CHANGED: Always run full scan (not just when no rightmost match)
    # This ensures we find ALL exact matches in text (e.g., "THANH CHUONG" + "VINH")
    # Deduplicate logic (line 1625) will handle duplicates if same match found in both sources
    for i, (token_idx, token) in enumerate(available_tokens):
        # Try n-grams starting from this position
        for n in range(min(3, len(available_tokens) - i), 0, -1):
            ngram_tokens_data = available_tokens[i:i+n]
            ngram_tokens = [t for _, t in ngram_tokens_data]
            # Clean tokens to remove trailing punctuation
            ngram_tokens_cleaned = [clean_token(t) for t in ngram_tokens]
            ngram_text = ' '.join(ngram_tokens_cleaned)
            start_idx = ngram_tokens_data[0][0]
            end_idx = ngram_tokens_data[-1][0] + 1

            # Skip if long numeric (street numbers), but allow 1-2 digit numbers (districts/wards)
            if ngram_text.isdigit() and len(ngram_text) > 2:
                continue  # Skip "660", "123" but allow "8", "12"

            # Normalize leading zeros for numeric districts (08 → 8, 02 → 2)
            ngram_text_normalized = normalize_admin_number(ngram_text)

            # Check if this n-gram is preceded by an admin keyword (quan, huyen, etc.)
            has_keyword = False
            if i > 0:
                # Check the token immediately before this n-gram in available_tokens
                prev_token = clean_token(available_tokens[i-1][1])
                has_keyword = prev_token in ADMIN_KEYWORDS_FULL

            # Calculate keyword context multiplier for 1-2 digit numbers
            keyword_multiplier = 1.0
            if ngram_text_normalized.isdigit() and len(ngram_text_normalized) <= 2:
                if has_keyword:
                    # Bonus for numbers with keywords (e.g., "quan 3")
                    keyword_multiplier = NUMERIC_WITH_KEYWORD_BONUS
                else:
                    # Penalty for standalone numbers (e.g., just "3")
                    keyword_multiplier = NUMERIC_WITHOUT_KEYWORD_PENALTY

            # Try abbreviation expansion
            expanded = expand_abbreviations(ngram_text_normalized, use_db=True, province_context=province_context)
            if expanded != ngram_text_normalized.lower() and expanded in districts_set:
                # Apply keyword multiplier to abbreviation expansions too
                adjusted_score = 1.0 * keyword_multiplier
                candidates.append((expanded, adjusted_score, 'abbreviation', (start_idx, end_idx)))
                continue

            # Fuzzy match
            match_results = match_in_set(
                ngram_text_normalized,
                districts_set,
                threshold=fuzzy_threshold,
                province_filter=province_context,
                level='district'
            )
            # NEW: match_in_set now returns list of tuples
            for match_name, match_score in match_results:
                # Apply keyword context multiplier
                adjusted_score = match_score * keyword_multiplier
                candidates.append((match_name, adjusted_score, 'fuzzy', (start_idx, end_idx)))

    # FALLBACK: If no district found, try finding ward and infer district
    if not candidates:
        from .db_utils import infer_district_from_ward, query_all
        # Get wards scoped to province only (not all 7287 wards!)
        wards_data = query_all("""
            SELECT DISTINCT ward_name_normalized
            FROM admin_divisions
            WHERE province_name_normalized = ?
        """, (province_context,))
        wards_set = {w['ward_name_normalized'] for w in wards_data if w['ward_name_normalized']}

        for i, (token_idx, token) in enumerate(available_tokens):
            for n in range(min(3, len(available_tokens) - i), 0, -1):
                ngram_tokens_data = available_tokens[i:i+n]
                ngram_tokens = [t for _, t in ngram_tokens_data]
                # Clean tokens to remove trailing punctuation
                ngram_tokens_cleaned = [clean_token(t) for t in ngram_tokens]
                ngram_text = ' '.join(ngram_tokens_cleaned)
                start_idx = ngram_tokens_data[0][0]
                end_idx = ngram_tokens_data[-1][0] + 1

                # Skip if long numeric (street numbers), but allow 1-2 digit numbers (wards)
                if ngram_text.isdigit() and len(ngram_text) > 2:
                    continue  # Skip "660", "123" but allow "4", "12"

                # Normalize leading zeros for numeric wards (06 → 6, 08 → 8)
                ngram_text_normalized = normalize_admin_number(ngram_text)

                # Try ward match (higher threshold since it's a fallback)
                match_results = match_in_set(
                    ngram_text_normalized,
                    wards_set,
                    threshold=0.85,  # Balanced threshold (handles typos & spacing)
                    province_filter=province_context,
                    level='ward'
                )
                # NEW: match_in_set now returns list of tuples
                for ward_name, ward_score in match_results:
                    logger.debug(f"[INFERENCE] Found ward '{ward_name}' (score: {ward_score:.3f}), inferring district...")
                    # Infer district from ward
                    inferred_district = infer_district_from_ward(province_context, ward_name)
                    if inferred_district:
                        logger.debug(f"[INFERENCE] Inferred district '{inferred_district}' from ward '{ward_name}'")
                        # Store ward metadata in a dict as 5th element of tuple
                        ward_metadata = {
                            'ward_name': ward_name,
                            'ward_score': ward_score,
                            'ward_tokens': (start_idx, end_idx)
                        }
                        candidates.append((inferred_district, 0.9, 'inferred_from_ward', (start_idx, end_idx), ward_metadata))

    # Remove duplicates (keep highest score)
    unique_candidates = {}
    for candidate in candidates:
        # Handle both 4-tuple and 5-tuple formats
        if len(candidate) == 5:
            dist, score, source, pos, ward_metadata = candidate
            if dist not in unique_candidates or score > unique_candidates[dist][0]:
                unique_candidates[dist] = (score, source, pos, ward_metadata)
        else:
            dist, score, source, pos = candidate
            if dist not in unique_candidates or score > unique_candidates[dist][0]:
                unique_candidates[dist] = (score, source, pos, None)

    # Convert back to list - include ward_metadata if present
    result = []
    for dist, data in unique_candidates.items():
        if len(data) == 4 and data[3] is not None:
            score, source, pos, ward_metadata = data
            result.append((dist, score, source, pos, ward_metadata))
        else:
            score, source, pos = data[0], data[1], data[2]
            result.append((dist, score, source, pos))

    # Adjust scores based on position (tokens at end are more reliable)
    # For district_scoped, we use absolute positions from the 4th element
    if len(result) > 1:
        from ..config import POSITION_PENALTY_FACTOR

        # Extract positions (start_idx from pos tuple) - handle both 4-tuple and 5-tuple
        positions = []
        for item in result:
            pos = item[3]  # pos is always 4th element
            positions.append(pos[0] if pos != (-1, -1) else -1)
        valid_positions = [p for p in positions if p >= 0]

        if len(valid_positions) > 1:
            min_pos = min(valid_positions)
            max_pos = max(valid_positions)

            # Adjust scores
            adjusted = []
            for item, position in zip(result, positions):
                # Handle both 4-tuple and 5-tuple formats
                if len(item) == 5:
                    dist, score, source, pos, ward_metadata = item
                    if position < 0 or max_pos == min_pos:
                        adjusted.append((dist, score, source, pos, ward_metadata))
                    else:
                        relative = (position - min_pos) / (max_pos - min_pos)
                        multiplier = (1.0 - POSITION_PENALTY_FACTOR) + (relative * POSITION_PENALTY_FACTOR)
                        adjusted.append((dist, score * multiplier, source, pos, ward_metadata))
                else:
                    dist, score, source, pos = item
                    if position < 0 or max_pos == min_pos:
                        adjusted.append((dist, score, source, pos))
                    else:
                        relative = (position - min_pos) / (max_pos - min_pos)
                        multiplier = (1.0 - POSITION_PENALTY_FACTOR) + (relative * POSITION_PENALTY_FACTOR)
                        adjusted.append((dist, score * multiplier, source, pos))

            result = adjusted

    # Sort by score DESC
    result.sort(key=lambda x: x[1], reverse=True)

    return result


def extract_ward_scoped(
    tokens: List[str],
    province_context: str,
    district_context: Optional[str],
    used_tokens: List[Tuple[int, int]],
    fuzzy_threshold=0.85
) -> List[Tuple[str, float, str, Tuple[int, int]]]:
    """
    Extract ward candidates scoped to a specific district (or province if district unknown).

    Strategy:
    1. Remove already-used tokens (province + district)
    2. Extract explicit patterns first (PHUONG 3, P.3, XA X, X.X)
    3. Fuzzy match remaining tokens with wards of the district/province

    Args:
        tokens: List of normalized tokens
        province_context: Confirmed province name (normalized)
        district_context: Confirmed district name (optional)
        used_tokens: List of (start_idx, end_idx) tuples already used by province/district
        fuzzy_threshold: Minimum fuzzy score (default: 0.7)

    Returns:
        List of (ward_name, score, source, (start_idx, end_idx)) tuples

    Example:
        >>> extract_ward_scoped(['phuong', '3', 'dong', 'ha'], 'quang tri', 'dong ha', [(2, 4)])
        [('3', 1.0, 'explicit_pattern', (0, 2))]
    """
    candidates = []

    # Create mask of available tokens
    used_ranges = set()
    for start, end in used_tokens:
        for i in range(start, end):
            used_ranges.add(i)

    # Log token removal for ward extraction
    if used_tokens:
        logger.debug(f"[TOKEN] Ward extraction - used token ranges: {used_tokens}")
        removed_tokens = [tokens[i] for i in sorted(used_ranges) if i < len(tokens)]
        logger.debug(f"[TOKEN] Removed tokens (province+district): {removed_tokens}")
        logger.debug(f"[TOKEN] Original token count: {len(tokens)}")

    available_tokens = []
    for i, token in enumerate(tokens):
        if i not in used_ranges:
            available_tokens.append((i, token))

    logger.debug(f"[TOKEN] Remaining tokens for ward search: {len(available_tokens)} tokens")
    logger.debug(f"[TOKEN] Available: {[t for _, t in available_tokens]}")

    if not available_tokens:
        logger.debug("[TOKEN] No tokens left after removing province+district")
        return []

    # ========== NEW: EXPAND AVAILABLE TOKENS WITH PROVINCE + DISTRICT CONTEXT ==========
    # Sau khi xác định province + district, expand lại abbreviations với context đầy đủ
    # Ví dụ: "DB" với province="ha noi" + district="ba dinh" → "dien bien"
    if province_context or district_context:
        token_strings = [t for _, t in available_tokens]
        original_token_strings = token_strings[:]  # Keep original for comparison

        expanded_strings = expand_tokens_with_context(
            token_strings,
            province_context=province_context,
            district_context=district_context
        )

        # Check if expansion happened
        if expanded_strings != original_token_strings:
            logger.debug(f"[EXPAND] Ward tokens expanded with province='{province_context}', district='{district_context}':")
            logger.debug(f"[EXPAND]   Before: {original_token_strings}")
            logger.debug(f"[EXPAND]   After:  {expanded_strings}")

            # Rebuild available_tokens với expanded tokens
            # IMPORTANT: Expansion có thể tăng số tokens
            available_tokens_expanded = []
            orig_idx = 0
            for expanded_token in expanded_strings:
                if orig_idx < len(available_tokens):
                    # Reuse original index for first expanded token
                    original_idx = available_tokens[orig_idx][0]
                    available_tokens_expanded.append((original_idx, expanded_token))
                    orig_idx += 1
                else:
                    # Additional tokens from expansion
                    last_idx = available_tokens_expanded[-1][0] if available_tokens_expanded else 0
                    available_tokens_expanded.append((last_idx, expanded_token))

            available_tokens = available_tokens_expanded
            logger.debug(f"[EXPAND] Updated available_tokens: {[t for _, t in available_tokens]}")
    # ========== END EXPANSION ==========

    # Get wards scoped to district or province
    from .db_utils import get_wards_by_district
    if district_context:
        wards_data = get_wards_by_district(province_context, district_context)
    else:
        # Fallback: Get all wards in province (less precise)
        from .db_utils import query_all
        wards_data = query_all("""
            SELECT DISTINCT ward_full, ward_name, ward_name_normalized
            FROM admin_divisions
            WHERE province_name_normalized = ?
        """, (province_context,))

    wards_set = {w['ward_name_normalized'] for w in wards_data}

    if not wards_set:
        return []

    # Source 1: Extract explicit patterns (PHUONG 3, P.3, XA X)
    # Reconstruct continuous token sequences from available_tokens
    token_sequences = []
    current_seq = []
    current_seq_indices = []

    for i in range(len(tokens)):
        if i not in used_ranges:
            current_seq.append(tokens[i])
            current_seq_indices.append(i)
        else:
            if current_seq:
                token_sequences.append((current_seq[:], current_seq_indices[:]))
                current_seq = []
                current_seq_indices = []

    if current_seq:
        token_sequences.append((current_seq, current_seq_indices))

    # Apply explicit pattern extraction to each sequence
    for seq_tokens, seq_indices in token_sequences:
        explicit_patterns = extract_explicit_patterns(seq_tokens)

        # Check ward patterns
        for ward_name, rel_start, rel_end in explicit_patterns['wards']:
            # Validate ward_name in wards_set
            match_results = match_in_set(
                ward_name,
                wards_set,
                threshold=0.7,
                level='ward'
            )
            # NEW: match_in_set now returns list of tuples
            for match_name, match_score in match_results:
                # Map relative indices to absolute indices
                abs_start = seq_indices[rel_start] if rel_start < len(seq_indices) else seq_indices[-1]
                abs_end = seq_indices[rel_end-1] + 1 if rel_end <= len(seq_indices) else seq_indices[-1] + 1
                candidates.append((match_name, match_score, 'explicit_pattern', (abs_start, abs_end)))

    # Source 2: Fuzzy match available tokens
    # CHANGED: Always run fuzzy match (not just when no explicit patterns)
    # This ensures we find ALL matches in text
    # Deduplicate logic (line 1838) will handle duplicates
    from ..config import NUMERIC_WITHOUT_KEYWORD_PENALTY, NUMERIC_WITH_KEYWORD_BONUS, ADMIN_KEYWORDS_FULL

    for i, (token_idx, token) in enumerate(available_tokens):
        # Try n-grams starting from this position
        for n in range(min(3, len(available_tokens) - i), 0, -1):
            ngram_tokens_data = available_tokens[i:i+n]
            ngram_tokens = [t for _, t in ngram_tokens_data]
            # Clean tokens to remove trailing punctuation
            ngram_tokens_cleaned = [clean_token(t) for t in ngram_tokens]
            ngram_text = ' '.join(ngram_tokens_cleaned)
            start_idx = ngram_tokens_data[0][0]
            end_idx = ngram_tokens_data[-1][0] + 1

            # Skip if just numbers (unless it matches a ward name like "1", "2")
            if ngram_text.isdigit() and len(ngram_text) > 2:
                continue

            # Normalize leading zeros for numeric wards before matching (06 → 6, 08 → 8)
            ngram_text_normalized = normalize_admin_number(ngram_text)

            # Check if this n-gram is preceded by an admin keyword (phuong, xa, etc.)
            has_keyword = False
            if i > 0:
                # Check the token immediately before this n-gram in available_tokens
                prev_token = clean_token(available_tokens[i-1][1])
                has_keyword = prev_token in ADMIN_KEYWORDS_FULL

            # Calculate keyword context multiplier for 1-2 digit numbers
            keyword_multiplier = 1.0
            if ngram_text_normalized.isdigit() and len(ngram_text_normalized) <= 2:
                if has_keyword:
                    # Bonus for numbers with keywords (e.g., "phuong 1")
                    keyword_multiplier = NUMERIC_WITH_KEYWORD_BONUS
                else:
                    # Penalty for standalone numbers (e.g., just "1")
                    keyword_multiplier = NUMERIC_WITHOUT_KEYWORD_PENALTY

            # Fuzzy match with wards
            match_results = match_in_set(
                ngram_text_normalized,
                wards_set,
                threshold=fuzzy_threshold if not ngram_text_normalized.isdigit() else 1.0,  # Exact for numbers
                province_filter=province_context,
                district_filter=district_context,
                level='ward'
            )
            # NEW: match_in_set now returns list of tuples
            for match_name, match_score in match_results:
                # Apply keyword context multiplier
                adjusted_score = match_score * keyword_multiplier
                candidates.append((match_name, adjusted_score, 'fuzzy', (start_idx, end_idx)))

    # Remove duplicates (keep highest score)
    unique_candidates = {}
    for ward, score, source, pos in candidates:
        if ward not in unique_candidates or score > unique_candidates[ward][0]:
            unique_candidates[ward] = (score, source, pos)

    # Convert back to list
    result = [(ward, score, source, pos) for ward, (score, source, pos) in unique_candidates.items()]

    # Adjust scores based on position (tokens at end are more reliable)
    # For ward_scoped, we use absolute positions from the 4th element
    if len(result) > 1:
        from ..config import POSITION_PENALTY_FACTOR

        # Extract positions (start_idx from pos tuple)
        positions = [pos[0] if pos != (-1, -1) else -1 for _, _, _, pos in result]
        valid_positions = [p for p in positions if p >= 0]

        if len(valid_positions) > 1:
            min_pos = min(valid_positions)
            max_pos = max(valid_positions)

            # Adjust scores
            adjusted = []
            for (ward, score, source, pos), position in zip(result, positions):
                if position < 0 or max_pos == min_pos:
                    # Keep original
                    adjusted.append((ward, score, source, pos))
                else:
                    # Calculate multiplier based on position
                    relative = (position - min_pos) / (max_pos - min_pos)
                    multiplier = (1.0 - POSITION_PENALTY_FACTOR) + (relative * POSITION_PENALTY_FACTOR)
                    adjusted.append((ward, score * multiplier, source, pos))

            result = adjusted

    # Sort by score DESC
    result.sort(key=lambda x: x[1], reverse=True)

    return result


def build_search_tree(
    tokens: List[str],
    province_known: Optional[str] = None,
    district_known: Optional[str] = None,
    max_branches: int = 5,
    phase2_segments: list = None
) -> List[Dict]:
    """
    Build multi-branch search tree using hierarchical scoped search.

    Mimics human reading: Province → District → Ward, with each level scoping the next.

    Strategy:
    1. Extract province candidates (known, rightmost, full scan)
    2. For each province → Extract district candidates (scoped to province)
    3. For each (province, district) → Extract ward candidates (scoped to district)
    4. Build final candidates with scores

    Args:
        tokens: List of normalized tokens
        province_known: Known province value (optional)
        district_known: Known district value (optional)
        max_branches: Maximum number of final candidates to return (default: 5)
        phase2_segments: Segments with boost scores from Phase 2 (optional)

    Returns:
        List of candidate dictionaries with province, district, ward, scores, and metadata

    Example:
        >>> build_search_tree(['phuong', '3', 'dha', 'quang', 'tri'], province_known='quang tri')
        [{
            'province': 'quang tri',
            'district': 'dong ha',
            'ward': '3',
            'province_score': 1.0,
            'district_score': 0.67,
            'ward_score': 1.0,
            'combined_score': 0.89,
            'search_path': ['known_province', 'fuzzy_district', 'pattern_ward']
        }]
    """
    logger.debug("[🔍 DEBUG] " + "═" * 76)
    logger.debug("[🔍 DEBUG] [PHASE 2] HIERARCHICAL SEARCH")
    logger.debug(f"[🔍 DEBUG]   📥 Tokens: {tokens}")
    logger.debug(f"[🔍 DEBUG]   📝 Known: province={province_known or 'None'}, district={district_known or 'None'}")

    # Build boost lookup map from Phase 2 segments
    # Map: segment_text → boost_score
    boost_map = {}
    if phase2_segments:
        for seg in phase2_segments:
            text = seg.get('text', '')
            boost = seg.get('boost', 0)
            if text and boost > 0:
                boost_map[text] = boost

        if boost_map:
            logger.debug(f"[🔍 DEBUG]   🎯 Phase 2 boost map: {boost_map}")

    all_candidates = []

    # STEP 1: Extract province candidates
    logger.debug("\n[🔍 DEBUG]   [STEP 1] PROVINCE EXTRACTION")
    province_candidates = extract_province_candidates(tokens, province_known, fuzzy_threshold=0.85)
    logger.debug(f"[🔍 DEBUG]   📤 Found {len(province_candidates)} province candidates")
    for i, (name, score, source, has_collision) in enumerate(province_candidates[:3], 1):
        collision_marker = " [⚠️ COLLISION: also exists as district]" if has_collision else ""
        logger.debug(f"[🔍 DEBUG]      {i}. '{name}' (score: {score:.3f}, source: {source}){collision_marker}")

    if not province_candidates:
        # No province found - return empty
        return []

    # STEP 2: For each province candidate → Search district
    # Process ALL province candidates (not just first one) to check both interpretations
    # Example: "BAC LIEU" can be province OR district - generate candidates for both
    # PRIORITY FIX: When collision detected (province name == district name), prioritize district interpretation
    logger.debug(f"\n[🔍 DEBUG]   [STEP 2] DISTRICT EXTRACTION (foreach province)")
    for idx, (prov_name, prov_score, prov_source, has_collision) in enumerate(province_candidates[:max_branches], 1):
        logger.debug(f"\n[🔍 DEBUG]   ─── Province {idx}/{min(len(province_candidates), max_branches)}: '{prov_name}' ───")

        # Determine province token position
        # If known-only (not in text), position is (-1, -1)
        # If known_and_in_text or found in text, find actual position
        if prov_source == 'known':
            prov_token_pos = (-1, -1)  # Known but not in text
            logger.debug(f"[TOKEN] Province '{prov_name}' is known-only (not in text)")
        else:
            # Find province tokens in text (known_and_in_text, rightmost, or full_scan)
            prov_tokens = prov_name.split()
            prov_token_pos = None
            for i in range(len(tokens) - len(prov_tokens) + 1):
                if tokens[i:i+len(prov_tokens)] == prov_tokens:
                    prov_token_pos = (i, i + len(prov_tokens))
                    break
            if not prov_token_pos:
                # Fallback: assume rightmost
                prov_token_pos = (len(tokens) - len(prov_tokens), len(tokens))
            logger.debug(f"[TOKEN] Province '{prov_name}' matched at positions {prov_token_pos}")
            logger.debug(f"[TOKEN] Province tokens: {tokens[prov_token_pos[0]:prov_token_pos[1]]}")

        # COLLISION HANDLING: If province name also exists as district, allow token reuse
        # This fixes cases like "BEN TRE" which is both province and district
        # Priority: District interpretation > Province-only interpretation
        collision_override = has_collision
        if collision_override:
            logger.debug(f"[⚠️ COLLISION] '{prov_name}' exists as both province and district")
            logger.debug(f"[⚠️ COLLISION] Allowing district search to reuse province tokens")

        # Extract district candidates for this province
        district_candidates = extract_district_scoped(
            tokens,
            province_context=prov_name,
            province_tokens_used=prov_token_pos,
            district_known=district_known,
            fuzzy_threshold=0.85,
            allow_token_reuse=collision_override  # Allow reuse when collision detected
        )

        logger.debug(f"[🔍 DEBUG]   📤 Found {len(district_candidates)} district candidates")
        for i, candidate in enumerate(district_candidates[:3], 1):
            # Handle both 4-tuple and 5-tuple formats
            if len(candidate) == 5:
                d_name, d_score, d_src, d_pos, ward_meta = candidate
                logger.debug(f"[🔍 DEBUG]      {i}. '{d_name}' (score: {d_score:.3f}, source: {d_src}) [has ward: {ward_meta['ward_name']}]")
            else:
                d_name, d_score, d_src, d_pos = candidate
                logger.debug(f"[🔍 DEBUG]      {i}. '{d_name}' (score: {d_score:.3f}, source: {d_src})")
            if d_pos != (-1, -1):
                logger.debug(f"[TOKEN]         District '{d_name}' at positions {d_pos}: {tokens[d_pos[0]:d_pos[1]]}")

        # If no district found, still create a candidate with province only
        if not district_candidates:
            logger.debug(f"[🔍 DEBUG]   → Creating province-only candidate")
            # Lookup full administrative names
            province_full, _, _ = lookup_full_names(prov_name, None, None)

            # Validate province exists
            hierarchy_valid = validate_hierarchy(prov_name, None, None)

            all_candidates.append({
                'province': prov_name,
                'district': None,
                'ward': None,
                'province_full': province_full,
                'district_full': None,
                'ward_full': None,
                'province_score': prov_score,
                'district_score': 0.0,
                'ward_score': 0.0,
                'combined_score': prov_score * 0.4,  # Province-only gets 40% weight
                'match_level': 1,
                'confidence': prov_score * 0.4,
                'search_path': [f'{prov_source}_province'],
                'method': 'hierarchical_search',
                'hierarchy_valid': hierarchy_valid,
                # Token positions for remaining address extraction
                'province_tokens': prov_token_pos,
                'district_tokens': (-1, -1),
                'ward_tokens': (-1, -1),
                'normalized_tokens': tokens
            })
            continue

        # STEP 3: For each district candidate → Search ward
        logger.debug(f"\n[🔍 DEBUG]   [STEP 3] WARD EXTRACTION (foreach district in '{prov_name}')")
        for d_idx, candidate in enumerate(district_candidates[:3], 1):  # Top 3 districts
            # Handle both 4-tuple and 5-tuple formats
            ward_metadata = None
            if len(candidate) == 5:
                dist_name, dist_score, dist_source, dist_token_pos, ward_metadata = candidate
            else:
                dist_name, dist_score, dist_source, dist_token_pos = candidate

            logger.debug(f"[🔍 DEBUG]   ─── District {d_idx}: '{dist_name}' ───")

            # Check if we already have ward from district inference
            if ward_metadata is not None:
                # Ward already found during district inference - reuse it!
                logger.debug(f"[WARD_REUSE] District '{dist_name}' was inferred from ward '{ward_metadata['ward_name']}'")
                logger.debug(f"[WARD_REUSE] Skipping redundant ward extraction - using inferred ward directly")
                ward_candidates = [(
                    ward_metadata['ward_name'],
                    ward_metadata['ward_score'],
                    'from_district_inference',
                    ward_metadata['ward_tokens']
                )]
            else:
                # Normal flow: extract ward candidates
                # Collect used token ranges
                used_tokens = []
                if prov_token_pos != (-1, -1):
                    used_tokens.append(prov_token_pos)
                if dist_token_pos != (-1, -1):
                    used_tokens.append(dist_token_pos)

                # Extract ward candidates for this (province, district)
                ward_candidates = extract_ward_scoped(
                    tokens,
                    province_context=prov_name,
                    district_context=dist_name,
                    used_tokens=used_tokens,
                    fuzzy_threshold=0.85
                )

            logger.debug(f"[🔍 DEBUG]   📤 Found {len(ward_candidates)} ward candidates")
            for i, (w_name, w_score, w_src, w_pos) in enumerate(ward_candidates[:2], 1):
                logger.debug(f"[🔍 DEBUG]      {i}. '{w_name}' (score: {w_score:.3f}, source: {w_src})")
                if w_pos != (-1, -1):
                    logger.debug(f"[TOKEN]         Ward '{w_name}' at positions {w_pos}: {tokens[w_pos[0]:w_pos[1]]}")

            # If no ward found, create candidate with province + district
            if not ward_candidates:
                logger.debug(f"[🔍 DEBUG]   → Creating province+district candidate")
                # Calculate combined score
                scores = [prov_score, dist_score]
                base_score = sum(scores) / len(scores)
                combined_score = base_score * 0.8  # Province+District gets 80% weight

                # Lookup full administrative names
                province_full, district_full, _ = lookup_full_names(prov_name, dist_name, None)

                # Validate province + district combination
                hierarchy_valid = validate_hierarchy(prov_name, dist_name, None)

                all_candidates.append({
                    'province': prov_name,
                    'district': dist_name,
                    'ward': None,
                    'province_full': province_full,
                    'district_full': district_full,
                    'ward_full': None,
                    'province_score': prov_score,
                    'district_score': dist_score,
                    'ward_score': 0.0,
                    'combined_score': combined_score,
                    'match_level': 2,
                    'confidence': combined_score,
                    'search_path': [f'{prov_source}_province', f'{dist_source}_district'],
                    'method': 'hierarchical_search',
                    'hierarchy_valid': hierarchy_valid,
                    # Token positions for remaining address extraction
                    'province_tokens': prov_token_pos,
                    'district_tokens': dist_token_pos,
                    'ward_tokens': (-1, -1),
                    'normalized_tokens': tokens
                })
                continue

            # STEP 4: For each ward candidate → Create final candidate
            for ward_name, ward_score, ward_source, ward_token_pos in ward_candidates[:2]:  # Top 2 wards
                # Calculate combined score (weighted average)
                scores = [prov_score, dist_score, ward_score]
                base_score = sum(scores) / len(scores)
                combined_score = base_score  # Full weight for complete match

                # Lookup full administrative names
                province_full, district_full, ward_full = lookup_full_names(prov_name, dist_name, ward_name)

                # Validate hierarchy before adding candidate
                hierarchy_valid = validate_hierarchy(prov_name, dist_name, ward_name)

                all_candidates.append({
                    'province': prov_name,
                    'district': dist_name,
                    'ward': ward_name,
                    'province_full': province_full,
                    'district_full': district_full,
                    'ward_full': ward_full,
                    'province_score': prov_score,
                    'district_score': dist_score,
                    'ward_score': ward_score,
                    'combined_score': combined_score,
                    'match_level': 3,
                    'confidence': combined_score,
                    'search_path': [
                        f'{prov_source}_province',
                        f'{dist_source}_district',
                        f'{ward_source}_ward'
                    ],
                    'method': 'hierarchical_search',
                    'hierarchy_valid': hierarchy_valid,
                    'source': 'db_exact_match',  # For Phase 4 compatibility
                    'at_rule': 3,  # For Phase 4 compatibility
                    'match_type': 'exact',  # For Phase 4 compatibility
                    # Token positions for remaining address extraction
                    'province_tokens': prov_token_pos,
                    'district_tokens': dist_token_pos,
                    'ward_tokens': ward_token_pos,
                    'normalized_tokens': tokens
                })

    # Apply Phase 2 boost scores before sorting
    if boost_map:
        logger.debug("\n[🔍 DEBUG]   [BOOST] Applying Phase 2 delimiter/keyword boosts")
        for cand in all_candidates:
            boost_applied = 0.0

            # Check district
            district = cand.get('district')
            if district and district in boost_map:
                boost_value = boost_map[district]
                cand['district_score'] = min(1.0, cand['district_score'] + boost_value)
                boost_applied += boost_value
                logger.debug(f"[🔍 DEBUG]      Boosted district '{district}' by +{boost_value:.2f}")

            # Check ward
            ward = cand.get('ward')
            if ward and ward in boost_map:
                boost_value = boost_map[ward]
                cand['ward_score'] = min(1.0, cand['ward_score'] + boost_value)
                boost_applied += boost_value
                logger.debug(f"[🔍 DEBUG]      Boosted ward '{ward}' by +{boost_value:.2f}")

            # Recalculate combined score if boost applied
            if boost_applied > 0:
                scores = [
                    cand['province_score'],
                    cand['district_score'],
                    cand['ward_score']
                ]
                non_zero_scores = [s for s in scores if s > 0]
                if non_zero_scores:
                    base_score = sum(non_zero_scores) / len(non_zero_scores)
                    # Apply weight based on match level
                    weight = 1.0 if cand['match_level'] == 3 else 0.8 if cand['match_level'] == 2 else 0.4
                    cand['combined_score'] = base_score * weight
                    cand['confidence'] = cand['combined_score']
                    logger.debug(f"[🔍 DEBUG]      → New combined_score: {cand['combined_score']:.3f}")

    # Sort by combined_score DESC
    all_candidates.sort(key=lambda x: x['combined_score'], reverse=True)

    # VALIDATION FILTER: Remove invalid hierarchy candidates
    # Only keep candidates where administrative hierarchy exists in database
    # This prevents impossible combinations like "Ward 14 + Tan Phu" (ward doesn't exist in that district)
    valid_candidates = [c for c in all_candidates if c.get('hierarchy_valid', True)]

    # Use valid candidates if any exist, otherwise fall back to all (preserve behavior for edge cases)
    if valid_candidates:
        all_candidates = valid_candidates
        logger.debug(f"[🔍 DEBUG]   ✓ Filtered to {len(valid_candidates)} hierarchy-valid candidates (removed {len(all_candidates) - len(valid_candidates)} invalid)")
    else:
        logger.debug(f"[🔍 DEBUG]   ⚠ No hierarchy-valid candidates found, keeping all {len(all_candidates)} candidates")

    # Limit to top N branches
    final_candidates = all_candidates[:max_branches]

    logger.debug(f"\n[🔍 DEBUG]   📊 FINAL RANKING:")
    logger.debug(f"[🔍 DEBUG]   Generated {len(all_candidates)} total candidates, returning top {len(final_candidates)}")
    for i, cand in enumerate(final_candidates, 1):
        logger.debug(f"[🔍 DEBUG]   {i}. [{cand['combined_score']:.3f}] {cand['ward'] or 'None'} | {cand['district'] or 'None'} | {cand['province']}")
    logger.debug("[🔍 DEBUG] " + "═" * 76 + "\n")

    return final_candidates


if __name__ == "__main__":
    # Test
    print("=" * 80)
    print("DATABASE EXTRACTION TEST")
    print("=" * 80)

    test_cases = [
        ("dien bien ba dinh ha noi", None, None),
        ("ha noi ba dinh dien bien", None, None),  # Reversed
        ("ba dinh ha noi", None, None),  # No ward
        ("ha noi", None, None),  # Province only
        ("22 ngo 629 giai phong ha noi", "ha noi", None),  # With known
        ("bach khoa ha noi", "ha noi", None),  # With known
    ]

    for text, prov_known, dist_known in test_cases:
        print(f"\nInput: '{text}'")
        if prov_known:
            print(f"Known: province={prov_known}")

        result = extract_with_database(text, prov_known, dist_known)

        print(f"  Province: {result['province']} (score: {result['province_score']:.2f})")
        print(f"  District: {result['district']} (score: {result['district_score']:.2f})")
        print(f"  Ward:     {result['ward']} (score: {result['ward_score']:.2f})")
        print(f"  Level:    {result['match_level']}")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Method:   {result['method']}")

    print("\n" + "=" * 80)
