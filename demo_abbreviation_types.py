#!/usr/bin/env python3
"""
Demo script để show các loại abbreviations được generate
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.db_utils import query_all


def demo_abbreviation_types():
    """Demo 4 loại abbreviations cho một location"""
    print("=" * 80)
    print("DEMO: 4 LOẠI ABBREVIATIONS")
    print("=" * 80)

    # Pick a sample location
    location = "thanh xuan"
    province = "ha noi"

    print(f"\nLocation: '{location}' (District in {province})")
    print("-" * 80)

    result = query_all("""
        SELECT key, word, province_context, district_context
        FROM abbreviations
        WHERE word = ?
          AND province_context = ?
          AND district_context IS NULL
        ORDER BY LENGTH(key), key
    """, (location, province))

    print(f"\nTìm thấy {len(result)} abbreviations:")
    print(f"\n{'Abbreviation':<20} {'Type':<30} {'Word':<20}")
    print("-" * 70)

    # Phân loại các abbreviations
    for row in result:
        key = row['key']
        word = row['word']

        # Phân loại dựa trên pattern
        if len(key) == 2 and key[0] == word.split()[0][0] and key[1] == word.split()[1][0]:
            abbr_type = "Type 1: Chữ cái đầu"
        elif key[0] == word.split()[0][0] and key[1:] == word.split()[1]:
            abbr_type = "Type 2: Đầu + Full"
        elif key == word.replace(" ", ""):
            abbr_type = "Type 4: Viết liền"
        elif key.startswith("q") or key.startswith("h") or key.startswith("tx"):
            abbr_type = "Type 3: Full normalized"
        else:
            abbr_type = "Other"

        print(f"{key:<20} {abbr_type:<30} {word:<20}")


def demo_context_disambiguation():
    """Demo context-aware disambiguation"""
    print("\n\n" + "=" * 80)
    print("DEMO: CONTEXT-AWARE DISAMBIGUATION")
    print("=" * 80)

    # Pick an abbreviation that exists in multiple contexts
    abbr = "tx"

    print(f"\nAbbreviation: '{abbr}' có nhiều meanings khác nhau tùy context")
    print("-" * 80)

    result = query_all("""
        SELECT key, word, province_context, district_context
        FROM abbreviations
        WHERE key = ?
        ORDER BY
            CASE
                WHEN province_context IS NULL THEN 0
                WHEN district_context IS NULL THEN 1
                ELSE 2
            END,
            province_context,
            district_context
        LIMIT 10
    """, (abbr,))

    print(f"\n{'Context Level':<20} {'Province':<20} {'District':<20} {'Expanded Word':<20}")
    print("-" * 80)

    for row in result:
        prov = row['province_context'] or 'GLOBAL'
        dist = row['district_context'] or '-'
        word = row['word']

        if row['province_context'] is None:
            level = "Global"
        elif row['district_context'] is None:
            level = "Province"
        else:
            level = "District"

        print(f"{level:<20} {prov:<20} {dist:<20} {word:<20}")


def demo_statistics():
    """Show statistics về abbreviations"""
    print("\n\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)

    # Total counts
    result = query_all("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN province_context IS NULL THEN 1 END) as global,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NULL THEN 1 END) as province,
            COUNT(CASE WHEN province_context IS NOT NULL AND district_context IS NOT NULL THEN 1 END) as district
        FROM abbreviations
    """)

    stats = result[0]
    print(f"\nTotal abbreviations: {stats['total']:,}")
    print(f"  - Global (province level): {stats['global']:,}")
    print(f"  - Province context (district level): {stats['province']:,}")
    print(f"  - District context (ward level): {stats['district']:,}")

    # Average abbreviations per word
    result = query_all("""
        SELECT
            AVG(abbr_count) as avg_abbr_per_word
        FROM (
            SELECT word, COUNT(*) as abbr_count
            FROM abbreviations
            GROUP BY word, province_context, district_context
        )
    """)
    print(f"\nAverage abbreviations per location: {result[0]['avg_abbr_per_word']:.2f}")

    # Most common abbreviation keys
    result = query_all("""
        SELECT key, COUNT(*) as count
        FROM abbreviations
        GROUP BY key
        ORDER BY count DESC
        LIMIT 10
    """)
    print(f"\nTop 10 most common abbreviation keys:")
    for row in result:
        print(f"  {row['key']:<15} ({row['count']:,} locations)")


def main():
    """Run all demos"""
    demo_abbreviation_types()
    demo_context_disambiguation()
    demo_statistics()

    print("\n" + "=" * 80)
    print("DEMO COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
