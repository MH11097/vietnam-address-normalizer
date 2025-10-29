#!/usr/bin/env python3
"""
Remove abbreviations that match tokens from place names.

Strategy: Simple aggressive removal
1. Extract all tokens from province/district/ward names
2. Delete abbreviations whose key matches any token
3. Generate report and SQL script

This prevents false matches during address parsing where an abbreviation
is actually a real Vietnamese word appearing in place names.
"""

import sqlite3
import sys
from pathlib import Path
from collections import Counter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH


def get_all_tokens_from_names():
    """
    Extract all unique tokens (words) from place names in admin_divisions.

    Returns:
        set: All unique tokens from province/district/ward names
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tokens = set()

    # Query all normalized names
    cursor.execute("""
        SELECT DISTINCT
            province_name_normalized,
            district_name_normalized,
            ward_name_normalized
        FROM admin_divisions
    """)

    for row in cursor.fetchall():
        for name in row:
            if name:
                # Split by space and add each word
                words = name.split()
                tokens.update(words)

    conn.close()

    return tokens


def get_all_abbreviation_keys():
    """
    Get all unique abbreviation keys from abbreviations table.

    Returns:
        set: All unique abbreviation keys
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT key FROM abbreviations")
    keys = {row[0] for row in cursor.fetchall()}

    conn.close()

    return keys


def get_abbreviations_by_key(key):
    """
    Get all abbreviation records for a specific key.

    Args:
        key: Abbreviation key

    Returns:
        list: List of (key, word, province_context, district_context) tuples
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT key, word, province_context, district_context
        FROM abbreviations
        WHERE key = ?
        ORDER BY province_context, district_context
    """, (key,))

    results = cursor.fetchall()
    conn.close()

    return results


def count_token_occurrences(token):
    """
    Count how many place names contain this token.

    Args:
        token: Token to search for

    Returns:
        int: Number of places containing this token
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Count occurrences in each level
    cursor.execute("""
        SELECT COUNT(DISTINCT id) as count
        FROM admin_divisions
        WHERE province_name_normalized LIKE ?
           OR district_name_normalized LIKE ?
           OR ward_name_normalized LIKE ?
    """, (f'%{token}%', f'%{token}%', f'%{token}%'))

    count = cursor.fetchone()[0]
    conn.close()

    return count


def find_problematic_abbreviations(tokens, abbr_keys):
    """
    Find abbreviations whose keys match tokens.

    Args:
        tokens: Set of all tokens from place names
        abbr_keys: Set of all abbreviation keys

    Returns:
        list: List of problematic keys (sorted by collision count)
    """
    # Find intersection
    problematic_keys = tokens & abbr_keys

    # Sort by collision count (descending)
    key_counts = []
    for key in problematic_keys:
        count = count_token_occurrences(key)
        key_counts.append((key, count))

    # Sort by count descending
    key_counts.sort(key=lambda x: x[1], reverse=True)

    return key_counts


def generate_report(problematic_keys, tokens, abbr_keys):
    """
    Generate detailed report about abbreviations to be removed.

    Args:
        problematic_keys: List of (key, count) tuples
        tokens: Set of all tokens
        abbr_keys: Set of all abbreviation keys
    """
    report_path = Path(__file__).parent.parent / "abbreviation_removal_report_v2.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ABBREVIATION REMOVAL REPORT - V2\n")
        f.write("Strategy: Remove abbreviations matching place name tokens\n")
        f.write("=" * 80 + "\n\n")

        # Statistics
        f.write("STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total unique tokens extracted: {len(tokens):,}\n")
        f.write(f"Total unique abbreviation keys: {len(abbr_keys):,}\n")
        f.write(f"Problematic keys to remove: {len(problematic_keys):,}\n")
        f.write(f"Percentage of keys affected: {len(problematic_keys)/len(abbr_keys)*100:.1f}%\n\n")

        # Get total records count
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Count total abbreviations
        cursor.execute("SELECT COUNT(*) FROM abbreviations")
        total_abbr = cursor.fetchone()[0]

        # Count abbreviations to be removed
        placeholders = ','.join('?' * len(problematic_keys))
        cursor.execute(f"""
            SELECT COUNT(*) FROM abbreviations
            WHERE key IN ({placeholders})
        """, [k for k, _ in problematic_keys])
        to_remove = cursor.fetchone()[0]

        conn.close()

        f.write(f"Total abbreviation records: {total_abbr:,}\n")
        f.write(f"Records to be removed: {to_remove:,}\n")
        f.write(f"Records remaining: {total_abbr - to_remove:,}\n")
        f.write(f"Percentage removed: {to_remove/total_abbr*100:.1f}%\n\n")

        # Top problematic abbreviations
        f.write("=" * 80 + "\n")
        f.write("TOP 50 PROBLEMATIC ABBREVIATIONS (by collision count)\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"{'Key':<10} {'Collision Count':<20} {'Sample Expansions':<50}\n")
        f.write("-" * 80 + "\n")

        for key, count in problematic_keys[:50]:
            # Get sample expansions
            records = get_abbreviations_by_key(key)
            samples = [r[1] for r in records[:3]]  # First 3 words
            sample_str = ", ".join(samples)
            if len(records) > 3:
                sample_str += f" (+{len(records)-3} more)"

            f.write(f"{key:<10} {count:<20} {sample_str:<50}\n")

        # Full list
        f.write("\n" + "=" * 80 + "\n")
        f.write("FULL LIST OF PROBLEMATIC KEYS\n")
        f.write("=" * 80 + "\n\n")

        for key, count in problematic_keys:
            f.write(f"{key:<15} (appears in {count} place names)\n")

        # Details per key
        f.write("\n" + "=" * 80 + "\n")
        f.write("DETAILED BREAKDOWN (Top 20)\n")
        f.write("=" * 80 + "\n\n")

        for key, count in problematic_keys[:20]:
            f.write(f"\nKey: '{key}' (appears in {count} place names)\n")
            f.write("-" * 80 + "\n")

            records = get_abbreviations_by_key(key)
            f.write(f"Total abbreviation records with this key: {len(records)}\n\n")

            # Show all records
            for rec in records[:10]:  # Limit to 10 for readability
                key_val, word, prov, dist = rec
                context = []
                if prov:
                    context.append(f"province={prov}")
                if dist:
                    context.append(f"district={dist}")
                context_str = ", ".join(context) if context else "global"
                f.write(f"  {key_val:10} → {word:30} [{context_str}]\n")

            if len(records) > 10:
                f.write(f"  ... and {len(records)-10} more records\n")

    print(f"✓ Report generated: {report_path}")
    return report_path


def generate_sql_script(problematic_keys):
    """
    Generate SQL script to remove problematic abbreviations.

    Args:
        problematic_keys: List of (key, count) tuples
    """
    sql_path = Path(__file__).parent.parent / "remove_abbreviations_v2.sql"

    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write("-- " + "=" * 76 + "\n")
        f.write("-- SQL SCRIPT: Remove Problematic Abbreviations\n")
        f.write("-- Generated by: remove_token_abbreviations_v2.py\n")
        f.write("-- Strategy: Remove abbreviations whose keys match place name tokens\n")
        f.write("-- " + "=" * 76 + "\n\n")

        f.write("-- IMPORTANT: Backup your database before running this script!\n")
        f.write("-- Execute in transaction mode for safety:\n")
        f.write("--   BEGIN TRANSACTION;\n")
        f.write("--   <run this script>\n")
        f.write("--   ROLLBACK;  -- to undo, or COMMIT; to apply\n\n")

        # Statistics
        f.write(f"-- Total problematic keys: {len(problematic_keys)}\n")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(problematic_keys))
        cursor.execute(f"""
            SELECT COUNT(*) FROM abbreviations
            WHERE key IN ({placeholders})
        """, [k for k, _ in problematic_keys])
        to_remove = cursor.fetchone()[0]
        conn.close()

        f.write(f"-- Total records to be removed: {to_remove:,}\n\n")

        # Main DELETE statement
        f.write("-- Delete all abbreviations with problematic keys\n")
        f.write("DELETE FROM abbreviations\nWHERE key IN (\n")

        # Write keys in groups of 10 per line
        keys_only = [k for k, _ in problematic_keys]
        for i in range(0, len(keys_only), 10):
            chunk = keys_only[i:i+10]
            # Escape single quotes by doubling them (SQL standard)
            quoted = []
            for k in chunk:
                escaped = k.replace("'", "''")
                quoted.append(f"'{escaped}'")
            line = "    " + ", ".join(quoted)
            if i + 10 < len(keys_only):
                line += ","
            f.write(line + "\n")

        f.write(");\n\n")

        # Verification query
        f.write("-- Verify removal\n")
        f.write("SELECT COUNT(*) as remaining_count FROM abbreviations;\n")

    print(f"✓ SQL script generated: {sql_path}")
    return sql_path


def main():
    """Main execution"""
    print("=" * 80)
    print("REMOVE TOKEN ABBREVIATIONS - V2")
    print("Strategy: Simple aggressive removal")
    print("=" * 80)

    # Step 1: Extract tokens
    print("\n1. Extracting tokens from place names...")
    tokens = get_all_tokens_from_names()
    print(f"   ✓ Extracted {len(tokens):,} unique tokens")
    print(f"   Sample tokens: {list(sorted(tokens))[:10]}")

    # Step 2: Get abbreviation keys
    print("\n2. Loading abbreviation keys...")
    abbr_keys = get_all_abbreviation_keys()
    print(f"   ✓ Loaded {len(abbr_keys):,} unique abbreviation keys")

    # Step 3: Find problematic
    print("\n3. Finding problematic abbreviations...")
    problematic_keys = find_problematic_abbreviations(tokens, abbr_keys)
    print(f"   ✓ Found {len(problematic_keys):,} problematic keys")

    # Show top 10
    print(f"\n   Top 10 by collision count:")
    for key, count in problematic_keys[:10]:
        print(f"     {key:10} → appears in {count:4} place names")

    # Step 4: Generate report
    print("\n4. Generating detailed report...")
    report_path = generate_report(problematic_keys, tokens, abbr_keys)

    # Step 5: Generate SQL
    print("\n5. Generating SQL removal script...")
    sql_path = generate_sql_script(problematic_keys)

    # Summary
    print("\n" + "=" * 80)
    print("COMPLETED")
    print("=" * 80)
    print(f"\nGenerated files:")
    print(f"  - Report: {report_path}")
    print(f"  - SQL Script: {sql_path}")
    print(f"\nNext steps:")
    print(f"  1. Review the report: cat {report_path}")
    print(f"  2. Backup database: cp data/address.db data/address.db.backup")
    print(f"  3. Execute SQL (in transaction):")
    print(f"     sqlite3 data/address.db < {sql_path}")
    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
