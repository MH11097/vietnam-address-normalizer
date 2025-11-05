"""
Comprehensive test for spacing and weight adjustment.

Tests 3 configurations:
- Baseline: Token Sort 65%, Levenshtein 35%, threshold 0.88
- Option A: Token Sort 50%, Levenshtein 50%, threshold 0.85 (BALANCED)
- Option B: Token Sort 10%, Levenshtein 90%, threshold 0.88 (EXTREME)
"""
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils.matching_utils import (
    token_sort_ratio,
    levenshtein_normalized,
    ensemble_fuzzy_score
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def custom_ensemble_score(s1: str, s2: str, weights: dict) -> float:
    """Calculate ensemble score with custom weights."""
    if not s1 or not s2:
        return 0.0

    score = 0.0
    if 'token_sort' in weights:
        score += token_sort_ratio(s1, s2) * weights['token_sort']
    if 'levenshtein' in weights:
        score += levenshtein_normalized(s1, s2) * weights['levenshtein']

    return score


def test_single_case(query: str, candidate: str, config_name: str, weights: dict, threshold: float) -> dict:
    """Test a single matching case."""
    token_score = token_sort_ratio(query, candidate)
    lev_score = levenshtein_normalized(query, candidate)
    ensemble = custom_ensemble_score(query, candidate, weights)
    passed = ensemble >= threshold

    return {
        'config': config_name,
        'query': query,
        'candidate': candidate,
        'token_sort': token_score,
        'levenshtein': lev_score,
        'ensemble': ensemble,
        'threshold': threshold,
        'passed': passed,
        'weights': weights
    }


def print_result(result: dict, show_details: bool = False):
    """Print result."""
    status = "✓ PASS" if result['passed'] else "✗ FAIL"
    gap = result['ensemble'] - result['threshold']

    if show_details:
        logger.info(f"  Query: '{result['query']}' vs '{result['candidate']}'")
        logger.info(f"  Token Sort: {result['token_sort']:.4f} × {result['weights'].get('token_sort', 0):.2f} "
                   f"= {result['token_sort'] * result['weights'].get('token_sort', 0):.4f}")
        logger.info(f"  Levenshtein: {result['levenshtein']:.4f} × {result['weights'].get('levenshtein', 0):.2f} "
                   f"= {result['levenshtein'] * result['weights'].get('levenshtein', 0):.4f}")
        logger.info(f"  Ensemble: {result['ensemble']:.4f} (threshold: {result['threshold']:.2f}, gap: {gap:+.4f}) → {status}")
    else:
        logger.info(f"  {result['ensemble']:.4f} ({gap:+.4f}) → {status}")


def compare_configs(test_cases: list):
    """Compare multiple configurations."""

    configs = [
        {
            'name': 'Baseline (Current)',
            'weights': {'token_sort': 0.65, 'levenshtein': 0.35},
            'threshold': 0.88,
            'desc': 'Current config after Jaccard removal'
        },
        {
            'name': 'Option A (Balanced)',
            'weights': {'token_sort': 0.50, 'levenshtein': 0.50},
            'threshold': 0.85,
            'desc': 'Equal weights + lower threshold (RECOMMENDED)'
        },
        {
            'name': 'Option B (Extreme)',
            'weights': {'token_sort': 0.10, 'levenshtein': 0.90},
            'threshold': 0.88,
            'desc': 'Heavy Levenshtein + keep threshold'
        }
    ]

    logger.info("=" * 80)
    logger.info("COMPREHENSIVE SPACING & WEIGHT TEST")
    logger.info("=" * 80)

    for i, config in enumerate(configs, 1):
        logger.info(f"\nConfig {i}: {config['name']}")
        logger.info(f"  Weights: Token Sort {config['weights']['token_sort']:.0%}, "
                   f"Levenshtein {config['weights']['levenshtein']:.0%}")
        logger.info(f"  Threshold: {config['threshold']:.2f}")
        logger.info(f"  Description: {config['desc']}")

    # Test categories
    categories = {
        'spacing': [
            ("co nhue1", "co nhue 1", "co nhue1 vs co nhue 1 (reported issue)"),
            ("phuong1", "phuong 1", "phuong1 vs phuong 1"),
            ("xa2", "xa 2", "xa2 vs xa 2"),
            ("tho1", "tho 1", "tho1 vs tho 1"),
            ("12ba", "12 ba", "12ba vs 12 ba (number-letter)"),
        ],
        'word_order': [
            ("ba dinh ha noi", "ha noi ba dinh", "Word order reversed"),
            ("thanh xuan trung", "trung thanh xuan", "3-word order reversed"),
            ("mo cay nam", "nam mo cay", "District name reversed"),
        ],
        'typos': [
            ("tmo cay", "mo cay", "Extra letter 't'"),
            ("ba din", "ba dinh", "Missing letter 'h'"),
            ("hanoi", "ha noi", "Missing space"),
        ]
    }

    # Track stats per config per category
    stats = {config['name']: {} for config in configs}

    # Test each category
    for category, cases in categories.items():
        logger.info(f"\n{'=' * 80}")
        logger.info(f"CATEGORY: {category.upper()}")
        logger.info("=" * 80)

        for config in configs:
            stats[config['name']][category] = {'pass': 0, 'fail': 0, 'scores': []}

        for i, (query, candidate, description) in enumerate(cases, 1):
            logger.info(f"\nTest #{i}: {description}")
            logger.info(f"  '{query}' vs '{candidate}'")

            for config in configs:
                result = test_single_case(
                    query, candidate,
                    config['name'],
                    config['weights'],
                    config['threshold']
                )

                status = "✓ PASS" if result['passed'] else "✗ FAIL"
                gap = result['ensemble'] - result['threshold']
                logger.info(f"  [{config['name']:25s}] {result['ensemble']:.4f} ({gap:+.4f}) → {status}")

                # Update stats
                if result['passed']:
                    stats[config['name']][category]['pass'] += 1
                else:
                    stats[config['name']][category]['fail'] += 1
                stats[config['name']][category]['scores'].append(result['ensemble'])

    # Print summary
    logger.info(f"\n{'=' * 80}")
    logger.info("SUMMARY BY CATEGORY")
    logger.info("=" * 80)

    for config in configs:
        logger.info(f"\n{config['name']}")
        logger.info(f"  Weights: {config['weights']['token_sort']:.0%}/{config['weights']['levenshtein']:.0%}, "
                   f"Threshold: {config['threshold']:.2f}")

        total_pass = 0
        total_fail = 0

        for category in categories.keys():
            cat_stats = stats[config['name']][category]
            total = cat_stats['pass'] + cat_stats['fail']
            avg_score = sum(cat_stats['scores']) / len(cat_stats['scores']) if cat_stats['scores'] else 0

            total_pass += cat_stats['pass']
            total_fail += cat_stats['fail']

            logger.info(f"  {category:15s}: {cat_stats['pass']}/{total} pass "
                       f"({cat_stats['pass']/total*100:5.1f}%), avg={avg_score:.3f}")

        total = total_pass + total_fail
        logger.info(f"  {'TOTAL':15s}: {total_pass}/{total} pass ({total_pass/total*100:.1f}%)")

    # Recommendation
    logger.info(f"\n{'=' * 80}")
    logger.info("RECOMMENDATION")
    logger.info("=" * 80)

    # Calculate overall scores
    overall = {}
    for config in configs:
        total_pass = sum(stats[config['name']][cat]['pass'] for cat in categories.keys())
        total_tests = sum(len(cases) for cases in categories.values())
        overall[config['name']] = {
            'pass': total_pass,
            'total': total_tests,
            'rate': total_pass / total_tests
        }

    # Find best
    best_config = max(overall.items(), key=lambda x: x[1]['rate'])

    logger.info(f"\nBest configuration: {best_config[0]}")
    logger.info(f"  Pass rate: {best_config[1]['pass']}/{best_config[1]['total']} "
               f"({best_config[1]['rate']*100:.1f}%)")

    # Analysis
    logger.info(f"\nAnalysis:")

    baseline_spacing = stats['Baseline (Current)']['spacing']['pass']
    optionA_spacing = stats['Option A (Balanced)']['spacing']['pass']
    optionB_spacing = stats['Option B (Extreme)']['spacing']['pass']

    logger.info(f"  Spacing issues:")
    logger.info(f"    Baseline: {baseline_spacing}/5 pass")
    logger.info(f"    Option A: {optionA_spacing}/5 pass ({optionA_spacing - baseline_spacing:+d})")
    logger.info(f"    Option B: {optionB_spacing}/5 pass ({optionB_spacing - baseline_spacing:+d})")

    baseline_order = stats['Baseline (Current)']['word_order']['pass']
    optionA_order = stats['Option A (Balanced)']['word_order']['pass']
    optionB_order = stats['Option B (Extreme)']['word_order']['pass']

    logger.info(f"  Word order:")
    logger.info(f"    Baseline: {baseline_order}/3 pass")
    logger.info(f"    Option A: {optionA_order}/3 pass ({optionA_order - baseline_order:+d})")
    logger.info(f"    Option B: {optionB_order}/3 pass ({optionB_order - baseline_order:+d})")

    # Final recommendation
    if best_config[0] == 'Option A (Balanced)':
        logger.info(f"\n✓ RECOMMEND Option A: Balanced approach")
        logger.info(f"  - Better spacing handling")
        logger.info(f"  - Preserves word order matching")
        logger.info(f"  - Lower threshold compensates for score loss")
    elif best_config[0] == 'Option B (Extreme)':
        logger.info(f"\n⚠ Option B wins but has trade-offs:")
        logger.info(f"  - Best spacing handling")
        logger.info(f"  - May hurt word order matching")
        logger.info(f"  - Consider Option A if word order is important")
    else:
        logger.info(f"\n✓ Baseline is still best overall")
        logger.info(f"  - No changes needed")


def main():
    """Main test function."""
    compare_configs([])

    logger.info(f"\n{'=' * 80}")
    logger.info("Test completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
