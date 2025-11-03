#!/usr/bin/env python3
"""
Script to remove ALL duplicate abbreviations from the database.
When a key appears 2+ times in the same context, ALL occurrences are deleted.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "address.db"
REPORT_PATH = Path(__file__).parent.parent / "abbreviation_duplicate_removal_report.txt"


def get_db_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def get_initial_stats(conn):
    """Get initial statistics before deletion."""
    cursor = conn.cursor()

    # Total rows
    total_rows = cursor.execute("SELECT COUNT(*) FROM abbreviations").fetchone()[0]

    # Duplicate groups
    duplicate_groups = cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
    """).fetchone()[0]

    # Total rows in duplicate groups
    rows_in_duplicates = cursor.execute("""
        SELECT COUNT(*) FROM abbreviations
        WHERE (province_context, district_context, key) IN (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
    """).fetchone()[0]

    return {
        'total_rows': total_rows,
        'duplicate_groups': duplicate_groups,
        'rows_in_duplicates': rows_in_duplicates
    }


def get_duplicate_details(conn):
    """Get detailed information about duplicates."""
    cursor = conn.cursor()

    # Get duplicate groups by context
    context_stats = cursor.execute("""
        SELECT
            COALESCE(province_context, 'NULL') as province,
            COUNT(DISTINCT key) as duplicate_keys,
            COUNT(*) as total_rows
        FROM abbreviations
        WHERE (province_context, district_context, key) IN (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
        GROUP BY province_context
        ORDER BY total_rows DESC
    """).fetchall()

    # Get sample duplicates
    sample_duplicates = cursor.execute("""
        SELECT
            COALESCE(province_context, 'NULL') as province,
            COALESCE(district_context, 'NULL') as district,
            key,
            COUNT(*) as count,
            GROUP_CONCAT(word, ' | ') as all_words
        FROM abbreviations
        GROUP BY province_context, district_context, key
        HAVING COUNT(*) >= 2
        ORDER BY count DESC
        LIMIT 50
    """).fetchall()

    return {
        'context_stats': context_stats,
        'sample_duplicates': sample_duplicates
    }


def create_backup_table(conn):
    """Create backup table with all rows that will be deleted."""
    cursor = conn.cursor()

    # Drop existing backup table if exists
    cursor.execute("DROP TABLE IF EXISTS abbreviations_duplicates_backup")

    # Create backup table with rows to be deleted
    cursor.execute("""
        CREATE TABLE abbreviations_duplicates_backup AS
        SELECT * FROM abbreviations
        WHERE (province_context, district_context, key) IN (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
    """)

    backup_count = cursor.execute(
        "SELECT COUNT(*) FROM abbreviations_duplicates_backup"
    ).fetchone()[0]

    conn.commit()
    return backup_count


def delete_all_duplicates(conn):
    """Delete ALL rows that are part of duplicate groups."""
    cursor = conn.cursor()

    # Delete all rows in duplicate groups
    cursor.execute("""
        DELETE FROM abbreviations
        WHERE (province_context, district_context, key) IN (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
    """)

    deleted_count = cursor.rowcount
    conn.commit()

    return deleted_count


def verify_no_duplicates(conn):
    """Verify that no duplicates remain."""
    cursor = conn.cursor()

    remaining_duplicates = cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT province_context, district_context, key
            FROM abbreviations
            GROUP BY province_context, district_context, key
            HAVING COUNT(*) >= 2
        )
    """).fetchone()[0]

    total_remaining = cursor.execute("SELECT COUNT(*) FROM abbreviations").fetchone()[0]

    return {
        'remaining_duplicates': remaining_duplicates,
        'total_remaining': total_remaining
    }


def generate_report(initial_stats, duplicate_details, backup_count, deleted_count, final_stats):
    """Generate detailed report of the deletion process."""

    report = []
    report.append("=" * 80)
    report.append("ABBREVIATIONS DUPLICATE REMOVAL REPORT")
    report.append("Strategy: Delete ALL occurrences when duplicates are found")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Initial statistics
    report.append("INITIAL STATE:")
    report.append("-" * 80)
    report.append(f"Total rows in abbreviations table: {initial_stats['total_rows']:,}")
    report.append(f"Number of duplicate groups: {initial_stats['duplicate_groups']:,}")
    report.append(f"Total rows in duplicate groups: {initial_stats['rows_in_duplicates']:,}")
    report.append("")

    # Context-based statistics
    report.append("DUPLICATES BY PROVINCE CONTEXT:")
    report.append("-" * 80)
    report.append(f"{'Province':<30} {'Duplicate Keys':<15} {'Total Rows':<15}")
    report.append("-" * 80)
    for province, dup_keys, total_rows in duplicate_details['context_stats'][:20]:
        report.append(f"{province:<30} {dup_keys:<15} {total_rows:<15}")
    report.append("")

    # Sample duplicates
    report.append("SAMPLE DUPLICATE GROUPS (Top 50):")
    report.append("-" * 80)
    for province, district, key, count, words in duplicate_details['sample_duplicates']:
        report.append(f"\nContext: {province} / {district}")
        report.append(f"  Key: '{key}' appears {count} times")
        report.append(f"  Words: {words}")
    report.append("")

    # Deletion results
    report.append("\nDELETION RESULTS:")
    report.append("-" * 80)
    report.append(f"Rows backed up to 'abbreviations_duplicates_backup': {backup_count:,}")
    report.append(f"Rows deleted from 'abbreviations': {deleted_count:,}")
    report.append("")

    # Final state
    report.append("FINAL STATE:")
    report.append("-" * 80)
    report.append(f"Remaining rows in abbreviations table: {final_stats['total_remaining']:,}")
    report.append(f"Remaining duplicate groups: {final_stats['remaining_duplicates']}")
    report.append("")

    # Summary
    report.append("SUMMARY:")
    report.append("-" * 80)
    reduction_pct = (deleted_count / initial_stats['total_rows']) * 100
    report.append(f"Total rows deleted: {deleted_count:,} ({reduction_pct:.2f}% of original)")
    report.append(f"Duplicate groups removed: {initial_stats['duplicate_groups']:,}")

    if final_stats['remaining_duplicates'] == 0:
        report.append("\n✓ SUCCESS: All duplicates have been removed!")
    else:
        report.append(f"\n⚠ WARNING: {final_stats['remaining_duplicates']} duplicate groups still remain!")

    report.append("=" * 80)

    return "\n".join(report)


def main():
    """Main execution function."""
    print("=" * 80)
    print("ABBREVIATIONS DUPLICATE REMOVAL")
    print("Strategy: Delete ALL occurrences when duplicates are found")
    print("=" * 80)
    print()

    conn = get_db_connection()

    try:
        # Step 1: Get initial statistics
        print("Step 1: Analyzing initial state...")
        initial_stats = get_initial_stats(conn)
        print(f"  Total rows: {initial_stats['total_rows']:,}")
        print(f"  Duplicate groups: {initial_stats['duplicate_groups']:,}")
        print(f"  Rows in duplicates: {initial_stats['rows_in_duplicates']:,}")
        print()

        # Step 2: Get duplicate details
        print("Step 2: Gathering duplicate details...")
        duplicate_details = get_duplicate_details(conn)
        print(f"  Contexts with duplicates: {len(duplicate_details['context_stats'])}")
        print()

        # Step 3: Create backup table
        print("Step 3: Creating backup table...")
        backup_count = create_backup_table(conn)
        print(f"  Backed up {backup_count:,} rows to 'abbreviations_duplicates_backup'")
        print()

        # Step 4: Delete duplicates
        print("Step 4: Deleting ALL duplicate rows...")
        deleted_count = delete_all_duplicates(conn)
        print(f"  Deleted {deleted_count:,} rows")
        print()

        # Step 5: Verify
        print("Step 5: Verifying results...")
        final_stats = verify_no_duplicates(conn)
        print(f"  Remaining rows: {final_stats['total_remaining']:,}")
        print(f"  Remaining duplicates: {final_stats['remaining_duplicates']}")
        print()

        # Step 6: Generate report
        print("Step 6: Generating report...")
        report = generate_report(
            initial_stats,
            duplicate_details,
            backup_count,
            deleted_count,
            final_stats
        )

        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"  Report saved to: {REPORT_PATH}")
        print()

        # Print summary
        print("=" * 80)
        print("COMPLETION SUMMARY")
        print("=" * 80)
        reduction_pct = (deleted_count / initial_stats['total_rows']) * 100
        print(f"✓ Deleted {deleted_count:,} rows ({reduction_pct:.2f}% of original)")
        print(f"✓ Removed {initial_stats['duplicate_groups']:,} duplicate groups")
        print(f"✓ Remaining rows: {final_stats['total_remaining']:,}")

        if final_stats['remaining_duplicates'] == 0:
            print("✓ SUCCESS: All duplicates removed!")
        else:
            print(f"⚠ WARNING: {final_stats['remaining_duplicates']} duplicates remain")

        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
