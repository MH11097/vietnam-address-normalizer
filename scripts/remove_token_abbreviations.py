#!/usr/bin/env python3
"""
⚠️ DEPRECATED - USE V2 INSTEAD ⚠️

This script is deprecated and NO LONGER FUNCTIONAL.
It queries admin_divisions abbreviation columns which have been REMOVED.

MIGRATION DATE: 2025-10-29
REASON: Abbreviations moved to dedicated 'abbreviations' table

USE INSTEAD: scripts/remove_token_abbreviations_v2.py

The V2 script:
- Queries the abbreviations table directly
- Handles context-aware abbreviations properly
- Has been tested and verified

See TOKEN_REMOVAL_SUMMARY.md for details.

---

OLD DESCRIPTION (for reference):
Script to remove abbreviations that are actual tokens in place names.

Logic: If an abbreviation appears as a word in any địa danh, it's not really
an abbreviation - it's a meaningful Vietnamese word that should not be expanded.

Example:
  - "tu" appears in "phuong tu", "tu lien", "duc tu" → Remove "tu" as abbreviation
  - "hcm" does NOT appear as token in any name → Keep "hcm" (real abbreviation)
"""

import sqlite3
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple
from collections import defaultdict

# Exit immediately if someone tries to run this
print("=" * 80)
print("⚠️  ERROR: This script is DEPRECATED")
print("=" * 80)
print("\nThis script queries admin_divisions abbreviation columns which")
print("have been removed from the database.\n")
print("USE INSTEAD: scripts/remove_token_abbreviations_v2.py\n")
print("The V2 script works with the new abbreviations table structure.")
print("See TOKEN_REMOVAL_SUMMARY.md for details.")
print("=" * 80)
sys.exit(1)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import DB_PATH


def get_all_tokens_from_names() -> Set[str]:
    """
    Extract all unique tokens (words) from all place names in admin_divisions.

    Returns:
        Set of all tokens that appear in province/district/ward names

    Example:
        Names: ["thanh xuan", "ba dinh", "phuong tu"]
        Returns: {"thanh", "xuan", "ba", "dinh", "phuong", "tu"}
    """
    print("📚 Extracting all tokens from place names...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tokens = set()

    # Get all normalized names
    query = """
    SELECT DISTINCT
        province_name_normalized,
        district_name_normalized,
        ward_name_normalized
    FROM admin_divisions
    WHERE province_name_normalized IS NOT NULL
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    for row in rows:
        # Extract tokens from each name
        for name in [row['province_name_normalized'],
                     row['district_name_normalized'],
                     row['ward_name_normalized']]:
            if name:
                # Split by space and add each word
                words = name.split()
                tokens.update(words)

    conn.close()

    print(f"✓ Found {len(tokens)} unique tokens in place names")
    print(f"  Sample tokens: {list(sorted(tokens))[:20]}")

    return tokens


def get_all_abbreviations() -> Dict[str, Dict[str, List[str]]]:
    """
    Get all abbreviations from admin_divisions table.

    Returns:
        Dictionary with structure:
        {
            'ward': {'tu': ['tan uyen', 'phuong tu', ...], 'tx': [...]},
            'district': {'bd': ['ba dinh', ...], ...},
            'province': {'hcm': ['ho chi minh'], ...}
        }
    """
    print("\n🔍 Collecting all abbreviations from database...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    result = {
        'ward': defaultdict(set),
        'district': defaultdict(set),
        'province': defaultdict(set)
    }

    # Query all abbreviations with their full names
    query = """
    SELECT DISTINCT
        ward_abbreviation,
        ward_name_normalized,
        district_abbreviation,
        district_name_normalized,
        province_abbreviation,
        province_name_normalized
    FROM admin_divisions
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    for row in rows:
        # Ward level
        if row['ward_abbreviation'] and row['ward_name_normalized']:
            result['ward'][row['ward_abbreviation']].add(row['ward_name_normalized'])

        # District level
        if row['district_abbreviation'] and row['district_name_normalized']:
            result['district'][row['district_abbreviation']].add(row['district_name_normalized'])

        # Province level
        if row['province_abbreviation'] and row['province_name_normalized']:
            result['province'][row['province_abbreviation']].add(row['province_name_normalized'])

    conn.close()

    # Convert sets to lists for JSON serialization
    result = {
        level: {abbr: sorted(list(names)) for abbr, names in abbrs.items()}
        for level, abbrs in result.items()
    }

    print(f"✓ Found abbreviations:")
    print(f"  - Ward: {len(result['ward'])} unique abbreviations")
    print(f"  - District: {len(result['district'])} unique abbreviations")
    print(f"  - Province: {len(result['province'])} unique abbreviations")

    return result


def find_problematic_abbreviations(
    all_tokens: Set[str],
    all_abbreviations: Dict[str, Dict[str, List[str]]]
) -> Dict[str, List[Tuple[str, List[str]]]]:
    """
    Find abbreviations that match real tokens in place names.

    Args:
        all_tokens: Set of all words appearing in place names
        all_abbreviations: Dictionary of abbreviations by level

    Returns:
        Dictionary with structure:
        {
            'ward': [('tu', ['tan uyen', 'phuong tu', ...]), ...],
            'district': [('bd', ['ba dinh']), ...],
            'province': []
        }
    """
    print("\n🚨 Identifying problematic abbreviations (matching real tokens)...")

    problematic = {
        'ward': [],
        'district': [],
        'province': []
    }

    for level in ['ward', 'district', 'province']:
        abbr_dict = all_abbreviations[level]

        for abbr, full_names in abbr_dict.items():
            # Check if abbreviation is a real token
            if abbr in all_tokens:
                problematic[level].append((abbr, full_names))

    # Sort by number of collisions (descending)
    for level in problematic:
        problematic[level].sort(key=lambda x: len(x[1]), reverse=True)

    print(f"✓ Found problematic abbreviations:")
    print(f"  - Ward: {len(problematic['ward'])}")
    print(f"  - District: {len(problematic['district'])}")
    print(f"  - Province: {len(problematic['province'])}")

    return problematic


def generate_report(
    problematic: Dict[str, List[Tuple[str, List[str]]]],
    output_file: str = 'abbreviation_removal_report.txt'
) -> None:
    """
    Generate human-readable report of problematic abbreviations.

    Args:
        problematic: Dictionary of problematic abbreviations by level
        output_file: Path to output report file
    """
    print(f"\n📝 Generating report to {output_file}...")

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("ABBREVIATION REMOVAL REPORT")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append("Logic: Remove abbreviations that appear as actual words in place names")
    report_lines.append("")

    total_to_remove = sum(len(items) for items in problematic.values())
    report_lines.append(f"SUMMARY: {total_to_remove} abbreviations to remove")
    report_lines.append("")

    for level in ['ward', 'district', 'province']:
        items = problematic[level]

        if not items:
            continue

        report_lines.append("=" * 80)
        report_lines.append(f"{level.upper()} LEVEL: {len(items)} problematic abbreviations")
        report_lines.append("=" * 80)
        report_lines.append("")

        for abbr, full_names in items:
            report_lines.append(f"Abbreviation: \"{abbr}\"")
            report_lines.append(f"  ✓ Is a real token (appears in {len(full_names)} place names)")
            report_lines.append(f"  ✓ Collision count: {len(full_names)} different full names")
            report_lines.append(f"  Full names:")

            # Show up to 10 examples
            for name in full_names[:10]:
                report_lines.append(f"    - {name}")

            if len(full_names) > 10:
                report_lines.append(f"    ... and {len(full_names) - 10} more")

            report_lines.append(f"  → ACTION: REMOVE (set to NULL in database)")
            report_lines.append("")

    # Write to file
    output_path = Path(__file__).parent / output_file
    output_path.write_text('\n'.join(report_lines), encoding='utf-8')

    print(f"✓ Report saved to: {output_path}")

    # Also print summary to console
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total abbreviations to remove: {total_to_remove}")
    print(f"  - Ward level: {len(problematic['ward'])}")
    print(f"  - District level: {len(problematic['district'])}")
    print(f"  - Province level: {len(problematic['province'])}")
    print("")
    print("Top 10 most problematic (highest collision count):")

    all_items = []
    for level, items in problematic.items():
        for abbr, full_names in items:
            all_items.append((abbr, len(full_names), level))

    all_items.sort(key=lambda x: x[1], reverse=True)

    for i, (abbr, count, level) in enumerate(all_items[:10], 1):
        print(f"  {i}. \"{abbr}\" ({level}): {count} collisions")


def generate_sql_script(
    problematic: Dict[str, List[Tuple[str, List[str]]]],
    output_file: str = 'remove_abbreviations.sql'
) -> None:
    """
    Generate SQL script to remove problematic abbreviations.

    Args:
        problematic: Dictionary of problematic abbreviations by level
        output_file: Path to output SQL file
    """
    print(f"\n💾 Generating SQL script to {output_file}...")

    sql_lines = []
    sql_lines.append("-- SQL Script to Remove Problematic Abbreviations")
    sql_lines.append("-- Generated by remove_token_abbreviations.py")
    sql_lines.append("--")
    sql_lines.append("-- Logic: Remove abbreviations that are actual tokens in place names")
    sql_lines.append("--")
    sql_lines.append("")
    sql_lines.append("BEGIN TRANSACTION;")
    sql_lines.append("")

    # Statistics before
    sql_lines.append("-- Statistics BEFORE removal")
    sql_lines.append("SELECT 'BEFORE' as timing,")
    sql_lines.append("       COUNT(*) FILTER (WHERE ward_abbreviation IS NOT NULL) as ward_count,")
    sql_lines.append("       COUNT(*) FILTER (WHERE district_abbreviation IS NOT NULL) as district_count,")
    sql_lines.append("       COUNT(*) FILTER (WHERE province_abbreviation IS NOT NULL) as province_count")
    sql_lines.append("FROM admin_divisions;")
    sql_lines.append("")

    # Ward level
    if problematic['ward']:
        sql_lines.append("-- Ward level abbreviations removal")
        ward_abbrs = [abbr for abbr, _ in problematic['ward']]
        ward_abbrs_quoted = ', '.join(f"'{abbr}'" for abbr in ward_abbrs)

        sql_lines.append(f"-- Removing {len(ward_abbrs)} ward abbreviations")
        sql_lines.append("UPDATE admin_divisions")
        sql_lines.append("SET ward_abbreviation = NULL")
        sql_lines.append(f"WHERE ward_abbreviation IN ({ward_abbrs_quoted});")
        sql_lines.append("")

    # District level
    if problematic['district']:
        sql_lines.append("-- District level abbreviations removal")
        district_abbrs = [abbr for abbr, _ in problematic['district']]
        district_abbrs_quoted = ', '.join(f"'{abbr}'" for abbr in district_abbrs)

        sql_lines.append(f"-- Removing {len(district_abbrs)} district abbreviations")
        sql_lines.append("UPDATE admin_divisions")
        sql_lines.append("SET district_abbreviation = NULL")
        sql_lines.append(f"WHERE district_abbreviation IN ({district_abbrs_quoted});")
        sql_lines.append("")

    # Province level
    if problematic['province']:
        sql_lines.append("-- Province level abbreviations removal")
        province_abbrs = [abbr for abbr, _ in problematic['province']]
        province_abbrs_quoted = ', '.join(f"'{abbr}'" for abbr in province_abbrs)

        sql_lines.append(f"-- Removing {len(province_abbrs)} province abbreviations")
        sql_lines.append("UPDATE admin_divisions")
        sql_lines.append("SET province_abbreviation = NULL")
        sql_lines.append(f"WHERE province_abbreviation IN ({province_abbrs_quoted});")
        sql_lines.append("")

    # Statistics after
    sql_lines.append("-- Statistics AFTER removal")
    sql_lines.append("SELECT 'AFTER' as timing,")
    sql_lines.append("       COUNT(*) FILTER (WHERE ward_abbreviation IS NOT NULL) as ward_count,")
    sql_lines.append("       COUNT(*) FILTER (WHERE district_abbreviation IS NOT NULL) as district_count,")
    sql_lines.append("       COUNT(*) FILTER (WHERE province_abbreviation IS NOT NULL) as province_count")
    sql_lines.append("FROM admin_divisions;")
    sql_lines.append("")

    sql_lines.append("COMMIT;")

    # Write to file
    output_path = Path(__file__).parent / output_file
    output_path.write_text('\n'.join(sql_lines), encoding='utf-8')

    print(f"✓ SQL script saved to: {output_path}")


def execute_sql_script(sql_file: str) -> None:
    """
    Execute the generated SQL script on the database.

    Args:
        sql_file: Path to SQL script file
    """
    print(f"\n🚀 Executing SQL script from {sql_file}...")

    sql_path = Path(__file__).parent / sql_file

    if not sql_path.exists():
        print(f"❌ SQL file not found: {sql_path}")
        return

    sql_content = sql_path.read_text(encoding='utf-8')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Execute the script
        cursor.executescript(sql_content)
        conn.commit()
        print("✓ SQL script executed successfully")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error executing SQL: {e}")
        raise
    finally:
        conn.close()


def main():
    """Main execution flow."""
    print("🚀 Starting Abbreviation Cleanup Process")
    print("=" * 80)

    # Step 1: Extract all tokens from place names
    all_tokens = get_all_tokens_from_names()

    # Step 2: Get all abbreviations
    all_abbreviations = get_all_abbreviations()

    # Step 3: Find problematic abbreviations
    problematic = find_problematic_abbreviations(all_tokens, all_abbreviations)

    # Step 4: Generate report
    generate_report(problematic)

    # Step 5: Generate SQL script
    generate_sql_script(problematic)

    print("\n" + "=" * 80)
    print("✅ ANALYSIS COMPLETE")
    print("=" * 80)
    print("")
    print("Next steps:")
    print("1. Review the report: scripts/abbreviation_removal_report.txt")
    print("2. Execute SQL script: scripts/remove_abbreviations.sql")
    print("   Option A: Run manually with sqlite3")
    print("   Option B: Uncomment and run execute_sql_script() below")
    print("")

    # Uncomment to auto-execute (be careful!)
    # user_input = input("Execute SQL script now? (yes/no): ")
    # if user_input.lower() == 'yes':
    #     execute_sql_script('remove_abbreviations.sql')


if __name__ == '__main__':
    main()
