"""
Configuration settings for address parsing.
"""
from pathlib import Path


# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
OUTPUT_DIR = BASE_DIR / 'output'

# Database
DB_PATH = DATA_DIR / 'address.db'

# Data files (deprecated - now use database)
HELPER_FILE = DATA_DIR / 'merge_file3.csv'
HELPER_MANUAL_FILE = DATA_DIR / 'merged_file_manual3.csv'
ABBREVIATIONS_FILE = DATA_DIR / 'tenVietTat.csv'

# Fuzzy matching thresholds (Updated: 0.90 for balanced approach)
# Increased from 0.85 to 0.90 to reduce false positives while allowing some tolerance
# Combined with 100% Levenshtein weight
# Note: All scores use 0-1 scale for consistency
FUZZY_THRESHOLDS = {
    'province': 0.90,
    'district': 0.90,
    'ward': 0.90
}

# Confidence thresholds for quality flags
CONFIDENCE_THRESHOLDS = {
    'high': 0.8,
    'medium': 0.6,
    'low': 0.4
}

# Processing settings
CHUNK_SIZE = 100000  # For batch processing
MAX_WORKERS = None  # None = auto-detect (65% of CPU cores)

# Cache settings
CACHE_MAX_SIZE = 10000
CACHE_AUTO_CLEAR_THRESHOLD = 50000

# Output settings
OUTPUT_ENCODING = 'utf-8-sig'
REMAINING_ADDRESS_MAX_LENGTH = 120  # Split into 3x40 chars

# At-rule definitions
AT_RULE_LEVELS = {
    0: 'no_match',
    1: 'province_only',
    2: 'province_district',
    3: 'full_address'
}

# Match type priorities
MATCH_TYPE_WEIGHTS = {
    'exact': 50,
    'fuzzy': 30,
    'hierarchical_fallback': 20
}

# Geographic context settings
GEOGRAPHIC_CONTEXT_BONUS = 1.1  # 10% bonus for matches within hint scope
HIERARCHY_INVALID_PENALTY = 0.8  # 20% penalty for invalid hierarchy
WARD_INHERIT_PENALTY = 0.85  # 15% penalty when district is inherited/inferred from ward (not explicit)
DISTRICT_INHERIT_PENALTY = 0.85  # 15% penalty when province is inherited/inferred from district (not explicit)

# Position-based scoring settings
POSITION_PENALTY_FACTOR = 0.2  # 20% max penalty for tokens far from end (0.8x-1.0x)

# Delimiter handling settings
# When users include delimiters, they have clear intent - respect segment boundaries
USE_DELIMITER_HINTS = True  # Enable/disable delimiter-aware scoring
DELIMITER_CHARS = [',', '-', '_', '/']  # Characters treated as delimiters
DELIMITER_CROSS_PENALTY = 0.85  # 15% penalty when n-gram crosses delimiter boundary
DELIMITER_WITHIN_BONUS = 1.10  # 10% bonus when n-gram is fully within segment

# Segment containment scoring (Phase 2 structural integration)
# When address has delimiters (comma, dash), segments are identified
# N-grams fully within a segment get bonus, cross-boundary gets penalty
SEGMENT_CONTAINMENT_BONUS = 1.20    # +20% for n-grams fully within segment
SEGMENT_CROSS_PENALTY = 0.85        # -15% for n-grams crossing segment boundaries

# Slash handling in address numbers (e.g., "55/2 Nguyen Trai")
# Slash is kept as part of token when it's between digits
SLASH_NUMBER_PATTERN = r'\d+/\d+'  # Pattern to detect address numbers with slash

# Keyword context scoring for numeric administrative divisions
# When numbers appear standalone (e.g., "1") vs with keywords (e.g., "phuong 1")
NUMERIC_WITHOUT_KEYWORD_PENALTY = 0.7  # 30% penalty (0.7x score) for standalone 1-2 digit numbers
NUMERIC_WITH_KEYWORD_BONUS = 1.2       # 20% bonus (1.2x score) for numbers with preceding keywords

# Fuzzy quality penalty exponent
# Low fuzzy scores get exponential penalties: score^EXPONENT
# 0.85^2=0.72, 0.90^2=0.81, 0.95^2=0.90, 1.0^2=1.0
FUZZY_QUALITY_EXPONENT = 2

# Explicit pattern bonus (for "PHUONG X", "XA X" patterns detected by pattern matching)
EXPLICIT_PATTERN_BONUS = 1.5           # 50% bonus (1.5x score) for explicit admin patterns

# Full administrative keywords (no abbreviations per user preference)
ADMIN_KEYWORDS_FULL = {'phuong', 'xa', 'quan', 'huyen', 'thanh', 'thi', 'tran', 'pho'}

# Substring matching bonus (for concatenated admin divisions like "AN VINH NGAIKSND")
SUBSTRING_BONUS_ENABLED = True   # Enable/disable substring bonus in fuzzy matching
SUBSTRING_BONUS_VALUE = 0.50     # Boost value when substring match found (+50%)
SUBSTRING_MIN_LENGTH = 5         # Minimum candidate length to check (avoid "AN", "NGAI")

# Context-aware substring bonus (differentiate inherited vs explicit district context)
SUBSTRING_BONUS_WITH_CONTEXT = 0.50      # Full bonus when district is explicit in text (+50%)
SUBSTRING_BONUS_WITHOUT_CONTEXT = 0.25   # Reduced bonus when district is inherited/inferred (+25%, 50% reduction)

# Token coverage scoring (measures how much of input text is used in the match)
TOKEN_COVERAGE_ENABLED = True    # Enable/disable token coverage scoring
TOKEN_COVERAGE_WEIGHTS = {
    'coverage_ratio': 0.4,       # 40% - Percentage of meaningful tokens used
    'continuity': 0.3,           # 30% - How continuous/compact the matched tokens are
    'weighted': 0.3              # 30% - Weighted by token importance (explicit pattern > keyword > normal)
}
TOKEN_IMPORTANCE_WEIGHTS = {
    'explicit_pattern': 2.0,     # Tokens from explicit patterns (e.g., "xa hoa an") get 2x weight
    'keyword': 1.5,              # Tokens with admin keywords (e.g., "phuong 3") get 1.5x weight
    'normal': 1.0                # Normal tokens get 1x weight
}
TOKEN_COVERAGE_MULTIPLIERS = {
    0.95: 1.25,  # >=95% coverage: +25% bonus (near perfect, ward-heavy)
    0.90: 1.20,  # >=90% coverage: +20% bonus (excellent)
    0.80: 1.15,  # >=80% coverage: +15% bonus (very good)
    0.70: 1.10,  # >=70% coverage: +10% bonus (good)
    0.60: 1.05,  # >=60% coverage: +5% bonus (above average)
    0.50: 1.00,  # >=50% coverage: neutral
    0.40: 0.95,  # >=40% coverage: -5% penalty
    0.20: 0.90,  # >=20% coverage: -10% penalty
    0.0: 0.85    # <20% coverage: -15% penalty
}

# Ensemble scoring weights (Simplified: 100% Levenshtein)
# Token Sort removed - Vietnamese addresses have fixed order, not needed
# Jaccard removed - penalizes hierarchical addresses
# Using pure Levenshtein for best typo & spacing handling
ENSEMBLE_WEIGHTS = {
    'levenshtein': 1.0    # 100% Levenshtein (simplest, fastest, most effective)
    # 'token_sort': removed (not needed for Vietnamese addresses)
    # 'jaccard': removed (caused false negatives)
}

# Scoring component weights (Phase 4)
SCORING_WEIGHTS = {
    'match_type': 0.5,  # 50%
    'at_rule': 0.3,     # 30%
    'string_similarity': 0.2  # 20%
}

# Debug logging flags (can be toggled independently)
# Format: True/False or 'OFF'/'SUMMARY'/'FULL'/'WINNERS'/'TOP3'
DEBUG_SQL = True        # Log SQL queries, params, and row counts
DEBUG_FUZZY = 'WINNERS' # Fuzzy matching: OFF | WINNERS (only log best match) | TOP3 | FULL (all comparisons)
DEBUG_NGRAMS = False    # Log n-gram generation and testing
DEBUG_EXTRACTION = True # Log extraction flow details (OFF/SUMMARY/FULL)

# Fuzzy logging modes explained:
# - 'OFF' or False: No fuzzy logs
# - 'WINNERS': Only log the winning match (best score) - RECOMMENDED for debugging
# - 'TOP3': Log top 3 candidates by score
# - 'FULL' or True: Log every single comparison (200+ lines) - Use sparingly!
