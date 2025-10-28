"""
Script to populate abbreviation columns in admin_divisions table.

Generates abbreviations using first letters of words.
Examples:
  - "tan xuyen" → "tx"
  - "ba dinh" → "bd"
  - "ho chi minh" → "hcm"
"""
import re
import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_abbreviation(name: str) -> str:
    """
    Generate abbreviation from normalized name using first letters.

    Args:
        name: Normalized name (lowercase, no accents)

    Returns:
        Abbreviation string

    Examples:
        >>> generate_abbreviation("tan xuyen")
        'tx'
        >>> generate_abbreviation("ba dinh")
        'bd'
        >>> generate_abbreviation("ho chi minh")
        'hcm'
        >>> generate_abbreviation("1")
        '1'
    """
    if not name or not isinstance(name, str):
        return ''

    name = name.strip().lower()

    # Handle numeric wards (e.g., "1", "2", "10")
    if name.isdigit():
        return name

    # Remove administrative prefixes (if any - should already be removed in normalized)
    name = re.sub(r'^(phuong|quan|thi xa|thanh pho|tinh|huyen|xa)\s+', '', name)

    # Split into words
    words = name.split()

    if not words:
        return ''

    # Single word: take first 2-3 chars
    if len(words) == 1:
        word = words[0]
        if len(word) <= 2:
            return word
        elif len(word) <= 4:
            return word[:2]
        else:
            return word[:3]

    # Multiple words: take first letter of each word
    return ''.join(word[0] for word in words)


def populate_abbreviations(db_path: str = 'data/address.db'):
    """
    Populate abbreviation columns for all rows in admin_divisions.

    Args:
        db_path: Path to database file
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Fetching all admin divisions...")
    cursor.execute("""
        SELECT id,
               province_name_normalized,
               district_name_normalized,
               ward_name_normalized
        FROM admin_divisions
    """)

    rows = cursor.fetchall()
    total = len(rows)
    print(f"Found {total} rows to process")

    updates = []
    for i, row in enumerate(rows, 1):
        row_id = row['id']

        # Generate abbreviations
        prov_abbr = generate_abbreviation(row['province_name_normalized'])
        dist_abbr = generate_abbreviation(row['district_name_normalized'])
        ward_abbr = generate_abbreviation(row['ward_name_normalized'])

        updates.append((prov_abbr, dist_abbr, ward_abbr, row_id))

        # Progress indicator
        if i % 1000 == 0:
            print(f"  Processed {i}/{total} rows...")

    print(f"\nUpdating {len(updates)} rows...")
    cursor.executemany("""
        UPDATE admin_divisions
        SET province_abbreviation = ?,
            district_abbreviation = ?,
            ward_abbreviation = ?
        WHERE id = ?
    """, updates)

    conn.commit()
    print(f"✅ Successfully updated {cursor.rowcount} rows")

    # Show statistics
    print("\n" + "="*60)
    print("STATISTICS")
    print("="*60)

    cursor.execute("SELECT COUNT(DISTINCT province_abbreviation) FROM admin_divisions")
    print(f"Unique province abbreviations: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(DISTINCT district_abbreviation) FROM admin_divisions")
    print(f"Unique district abbreviations: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(DISTINCT ward_abbreviation) FROM admin_divisions")
    print(f"Unique ward abbreviations: {cursor.fetchone()[0]}")

    # Show collision examples
    print("\n" + "="*60)
    print("COLLISION EXAMPLES (same abbreviation, different names)")
    print("="*60)

    cursor.execute("""
        SELECT ward_abbreviation,
               COUNT(DISTINCT ward_name_normalized) as name_count,
               GROUP_CONCAT(ward_name || ' (' || district_name || ', ' || province_name || ')') as locations
        FROM admin_divisions
        WHERE ward_abbreviation IN ('tx', 'tb', 'th', 'tt')
        GROUP BY ward_abbreviation
        HAVING name_count > 1
        LIMIT 5
    """)

    for row in cursor.fetchall():
        abbr = row[0]
        count = row[1]
        locations = row[2][:200] if row[2] else ''  # Truncate long list
        print(f"\n'{abbr}' ({count} different names) →")
        print(f"  {locations}...")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Populate abbreviations in admin_divisions')
    parser.add_argument('--db', default='data/address.db', help='Database path')
    args = parser.parse_args()

    print("="*60)
    print("POPULATE ABBREVIATIONS SCRIPT")
    print("="*60)
    print(f"Database: {args.db}\n")

    populate_abbreviations(args.db)

    print("\n✅ Done!")
