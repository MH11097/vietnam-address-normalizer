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

# Fuzzy matching thresholds (Very strict - 95%+ for all levels)
FUZZY_THRESHOLDS = {
    'province': 95,
    'district': 95,
    'ward': 95
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

# Position-based scoring settings
POSITION_PENALTY_FACTOR = 0.2  # 20% max penalty for tokens far from end (0.8x-1.0x)

# Ensemble scoring weights
ENSEMBLE_WEIGHTS = {
    'token_sort': 0.5,
    'levenshtein': 0.3,
    'jaccard': 0.2
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
DEBUG_EXTRACTION = True # Log extraction flow details

# Fuzzy logging modes explained:
# - 'OFF' or False: No fuzzy logs
# - 'WINNERS': Only log the winning match (best score) - RECOMMENDED for debugging
# - 'TOP3': Log top 3 candidates by score
# - 'FULL' or True: Log every single comparison (200+ lines) - Use sparingly!
