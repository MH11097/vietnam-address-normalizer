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

# Fuzzy matching thresholds
FUZZY_THRESHOLDS = {
    'province': 90,
    'district': 85,
    'ward': 80
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
