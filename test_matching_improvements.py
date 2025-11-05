"""
Test script to compare matching algorithm configurations.

Tests current config (3 algos, threshold 0.95) vs proposed config (2 algos, threshold 0.90)
"""
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils.matching_utils import (
    token_sort_ratio,
    levenshtein_normalized,
    jaccard_similarity,
    ensemble_fuzzy_score
)
from src.utils.db_utils import query_all

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def custom_ensemble_score(s1: str, s2: str, weights: dict) -> float:
    """
    Calculate ensemble score with custom weights.

    Args:
        s1: First string
        s2: Second string
        weights: Dictionary with weights for each algorithm

    Returns:
        Ensemble score (0.0-1.0)
    """
    if not s1 or not s2:
        return 0.0

    score = 0.0

    if 'token_sort' in weights:
        score += token_sort_ratio(s1, s2) * weights['token_sort']

    if 'levenshtein' in weights:
        score += levenshtein_normalized(s1, s2) * weights['levenshtein']

    if 'jaccard' in weights:
        score += jaccard_similarity(s1, s2) * weights['jaccard']

    return score


def test_single_case(query: str, candidate: str, config_name: str, weights: dict, threshold: float) -> dict:
    """
    Test a single matching case with given configuration.

    Args:
        query: Query string
        candidate: Candidate string to match against
        config_name: Name of the configuration
        weights: Weight dictionary
        threshold: Score threshold for pass/fail

    Returns:
        Dictionary with test results
    """
    # Calculate individual scores
    token_score = token_sort_ratio(query, candidate)
    lev_score = levenshtein_normalized(query, candidate)
    jac_score = jaccard_similarity(query, candidate)

    # Calculate ensemble score
    ensemble = custom_ensemble_score(query, candidate, weights)

    # Pass/fail based on threshold
    passed = ensemble >= threshold

    return {
        'config': config_name,
        'query': query,
        'candidate': candidate,
        'token_sort': token_score,
        'levenshtein': lev_score,
        'jaccard': jac_score,
        'ensemble': ensemble,
        'threshold': threshold,
        'passed': passed,
        'weights': weights
    }


def print_result(result: dict):
    """Pretty print a test result."""
    logger.info(f"\n  Query: '{result['query']}' vs Candidate: '{result['candidate']}'")
    logger.info(f"  Config: {result['config']} (threshold: {result['threshold']:.2f})")
    logger.info(f"  Individual scores:")

    if 'token_sort' in result['weights']:
        weight = result['weights']['token_sort']
        contrib = result['token_sort'] * weight
        logger.info(f"    Token Sort:    {result['token_sort']:.4f} × {weight:.2f} = {contrib:.4f}")

    if 'levenshtein' in result['weights']:
        weight = result['weights']['levenshtein']
        contrib = result['levenshtein'] * weight
        logger.info(f"    Levenshtein:   {result['levenshtein']:.4f} × {weight:.2f} = {contrib:.4f}")

    if 'jaccard' in result['weights']:
        weight = result['weights']['jaccard']
        contrib = result['jaccard'] * weight
        logger.info(f"    Jaccard:       {result['jaccard']:.4f} × {weight:.2f} = {contrib:.4f}")

    status = "✓ PASS" if result['passed'] else "✗ FAIL"
    logger.info(f"  Ensemble: {result['ensemble']:.4f} → {status}")


def compare_configs(test_cases: list):
    """
    Compare current vs proposed configuration on test cases.

    Args:
        test_cases: List of (query, candidate, description) tuples
    """
    # Configuration A: Current (3 algorithms, threshold 0.95)
    config_a = {
        'name': 'Current (3 algos)',
        'weights': {'token_sort': 0.50, 'levenshtein': 0.30, 'jaccard': 0.20},
        'threshold': 0.95
    }

    # Configuration B: Proposed (2 algorithms, threshold 0.90)
    config_b = {
        'name': 'Proposed (2 algos)',
        'weights': {'token_sort': 0.65, 'levenshtein': 0.35},
        'threshold': 0.90
    }

    logger.info("=" * 80)
    logger.info("MATCHING ALGORITHM COMPARISON TEST")
    logger.info("=" * 80)

    logger.info("\nConfiguration A (Current):")
    logger.info(f"  Algorithms: Token Sort (50%), Levenshtein (30%), Jaccard (20%)")
    logger.info(f"  Threshold: 0.95")

    logger.info("\nConfiguration B (Proposed):")
    logger.info(f"  Algorithms: Token Sort (65%), Levenshtein (35%)")
    logger.info(f"  Threshold: 0.90")

    # Track statistics
    stats_a = {'pass': 0, 'fail': 0, 'scores': []}
    stats_b = {'pass': 0, 'fail': 0, 'scores': []}

    # Test each case
    for i, (query, candidate, description) in enumerate(test_cases, 1):
        logger.info("\n" + "=" * 80)
        logger.info(f"Test Case #{i}: {description}")
        logger.info("=" * 80)

        # Test with Config A
        result_a = test_single_case(query, candidate, config_a['name'],
                                     config_a['weights'], config_a['threshold'])
        print_result(result_a)

        stats_a['scores'].append(result_a['ensemble'])
        if result_a['passed']:
            stats_a['pass'] += 1
        else:
            stats_a['fail'] += 1

        # Test with Config B
        result_b = test_single_case(query, candidate, config_b['name'],
                                     config_b['weights'], config_b['threshold'])
        print_result(result_b)

        stats_b['scores'].append(result_b['ensemble'])
        if result_b['passed']:
            stats_b['pass'] += 1
        else:
            stats_b['fail'] += 1

        # Comparison
        logger.info(f"\n  Comparison:")
        logger.info(f"    Score change: {result_a['ensemble']:.4f} → {result_b['ensemble']:.4f} "
                   f"({result_b['ensemble'] - result_a['ensemble']:+.4f})")

        if result_a['passed'] and result_b['passed']:
            logger.info(f"    Both PASS ✓")
        elif not result_a['passed'] and not result_b['passed']:
            logger.info(f"    Both FAIL ✗")
        elif not result_a['passed'] and result_b['passed']:
            logger.info(f"    IMPROVED: Failed → Passed ⬆")
        else:
            logger.info(f"    DEGRADED: Passed → Failed ⬇")

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    total = len(test_cases)

    logger.info(f"\nConfig A (Current):")
    logger.info(f"  Pass: {stats_a['pass']}/{total} ({stats_a['pass']/total*100:.1f}%)")
    logger.info(f"  Fail: {stats_a['fail']}/{total} ({stats_a['fail']/total*100:.1f}%)")
    logger.info(f"  Avg Score: {sum(stats_a['scores'])/len(stats_a['scores']):.4f}")

    logger.info(f"\nConfig B (Proposed):")
    logger.info(f"  Pass: {stats_b['pass']}/{total} ({stats_b['pass']/total*100:.1f}%)")
    logger.info(f"  Fail: {stats_b['fail']}/{total} ({stats_b['fail']/total*100:.1f}%)")
    logger.info(f"  Avg Score: {sum(stats_b['scores'])/len(stats_b['scores']):.4f}")

    # Recommendation
    logger.info(f"\n{'=' * 80}")
    logger.info("RECOMMENDATION")
    logger.info("=" * 80)

    if stats_b['pass'] > stats_a['pass']:
        logger.info(f"✓ Config B is BETTER: {stats_b['pass'] - stats_a['pass']} more test cases passed")
        logger.info(f"  Recommendation: Apply Config B (remove Jaccard, adjust weights, lower threshold)")
    elif stats_b['pass'] == stats_a['pass']:
        avg_a = sum(stats_a['scores'])/len(stats_a['scores'])
        avg_b = sum(stats_b['scores'])/len(stats_b['scores'])
        if avg_b > avg_a:
            logger.info(f"✓ Config B is BETTER: Same pass rate but higher average score")
            logger.info(f"  Recommendation: Apply Config B (simpler and faster)")
        else:
            logger.info(f"≈ Configs are EQUIVALENT")
            logger.info(f"  Recommendation: Apply Config B for simplicity (2 algos vs 3)")
    else:
        logger.info(f"✗ Config A is BETTER: {stats_a['pass'] - stats_b['pass']} more test cases passed")
        logger.info(f"  Recommendation: Keep Config A or adjust Config B threshold")


def load_sample_data_from_db():
    """
    Load sample test cases from database.
    Returns list of (ward_name, ward_name_normalized, description) tuples.
    """
    # Get some wards with potential typo scenarios
    query = """
    SELECT DISTINCT
        ward_name_normalized,
        ward_name
    FROM admin_divisions
    WHERE province_name_normalized = 'ben tre'
    AND district_name_normalized = 'mo cay nam'
    LIMIT 10
    """

    results = query_all(query)
    return [(row['ward_name_normalized'], row['ward_name']) for row in results]


def main():
    """Main test function."""

    # Define test cases: (query, candidate, description)
    test_cases = [
        # Case 1: Typo with extra character (the reported issue)
        ("tmo cay", "mo cay", "Typo: Extra 't' prefix (reported issue)"),

        # Case 2: Typo with missing character
        ("ba din", "ba dinh", "Typo: Missing 'h'"),

        # Case 3: Spacing issue
        ("hanoi", "ha noi", "Spacing: Missing space"),

        # Case 4: Word order variation
        ("ba dinh ha noi", "ha noi ba dinh", "Word order: Reversed"),

        # Case 5: Missing administrative keyword
        ("dien bien", "phuong dien bien", "Missing prefix 'phuong'"),

        # Case 6: Hierarchical partial match (Province only vs Province+District)
        ("ha noi", "ha noi ba dinh", "Hierarchical: Province vs Province+District"),

        # Case 7: Similar names with small difference
        ("thanh xuan", "thanh xuan trung", "Partial match: thanh xuan vs thanh xuan trung"),

        # Case 8: Character transposition
        ("dien bein", "dien bien", "Typo: Character transposition 'ei' → 'ie'"),

        # Case 9: Multiple word typos
        ("ba dih ha noi", "ba dinh ha noi", "Typo: Multiple words 'dih' → 'dinh'"),

        # Case 10: Real case from user report
        ("mo cay", "mo cay nam", "Real case: mo cay vs mo cay nam"),
    ]

    # Run comparison
    compare_configs(test_cases)

    logger.info("\n" + "=" * 80)
    logger.info("Test completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
