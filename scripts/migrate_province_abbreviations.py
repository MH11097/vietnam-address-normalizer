#!/usr/bin/env python3
"""
Database migration script to add province-level abbreviations.

This script populates the abbreviations table with province abbreviations
where province_context IS NULL. This enables province-level branching for
ambiguous abbreviations like "dn" (Da Nang OR Dong Nai).

Usage:
    python scripts/migrate_province_abbreviations.py
"""

import sqlite3
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.db_utils import DB_PATH


def migrate_province_abbreviations():
    """Add province-level abbreviations to the database."""

    db_path = DB_PATH
    print(f"Connecting to database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Province abbreviations to add
    # Format: (key, word, province_context, district_context)
    # province_context=NULL means these are province-level abbreviations

    abbreviations = [
        # Unique abbreviations (single province match)
        ('hn', 'ha noi', None, None),
        ('hcm', 'ho chi minh', None, None),
        ('sg', 'ho chi minh', None, None),  # Saigon alias
        ('bdinh', 'binh dinh', None, None),
        ('bduong', 'binh duong', None, None),
        ('bphuoc', 'binh phuoc', None, None),
        ('bthuan', 'binh thuan', None, None),
        ('dlak', 'dak lak', None, None),
        ('daclac', 'dak lak', None, None),  # Alternative spelling
        ('dnong', 'dak nong', None, None),
        ('dacnong', 'dak nong', None, None),  # Alternative spelling
        ('kgiang', 'kien giang', None, None),
        ('khoahoa', 'khanh hoa', None, None),
        ('lchau', 'lai chau', None, None),
        ('ldong', 'lam dong', None, None),
        ('lamdong', 'lam dong', None, None),
        ('lson', 'lang son', None, None),
        ('langson', 'lang son', None, None),
        ('lcai', 'lao cai', None, None),
        ('laocai', 'lao cai', None, None),
        ('nan', 'long an', None, None),
        ('longan', 'long an', None, None),
        ('ndinh', 'nam dinh', None, None),
        ('namdinh', 'nam dinh', None, None),
        ('nan', 'nghe an', None, None),
        ('nghean', 'nghe an', None, None),
        ('nbinh', 'ninh binh', None, None),
        ('ninhbinh', 'ninh binh', None, None),
        ('nthuan', 'ninh thuan', None, None),
        ('ninhthuan', 'ninh thuan', None, None),
        ('pyen', 'phu yen', None, None),
        ('phuyen', 'phu yen', None, None),
        ('ptho', 'phu tho', None, None),
        ('phutho', 'phu tho', None, None),
        ('qbinh', 'quang binh', None, None),
        ('quangbinh', 'quang binh', None, None),
        ('qnam', 'quang nam', None, None),
        ('quangnam', 'quang nam', None, None),
        ('qngai', 'quang ngai', None, None),
        ('quangngai', 'quang ngai', None, None),
        ('qninh', 'quang ninh', None, None),
        ('quangninh', 'quang ninh', None, None),
        ('qtri', 'quang tri', None, None),
        ('quangtri', 'quang tri', None, None),
        ('sgiang', 'soc trang', None, None),
        ('soctrang', 'soc trang', None, None),
        ('sla', 'son la', None, None),
        ('sonla', 'son la', None, None),
        ('tninh', 'tay ninh', None, None),
        ('tayninh', 'tay ninh', None, None),
        ('tgiang', 'tien giang', None, None),
        ('tiengiang', 'tien giang', None, None),
        ('thoa', 'thanh hoa', None, None),
        ('thanhhoa', 'thanh hoa', None, None),
        ('tthien', 'thua thien hue', None, None),
        ('hue', 'thua thien hue', None, None),
        ('tgiang', 'tra vinh', None, None),
        ('travinh', 'tra vinh', None, None),
        ('tquang', 'tuyen quang', None, None),
        ('tuyenquang', 'tuyen quang', None, None),
        ('vlong', 'vinh long', None, None),
        ('vinhlong', 'vinh long', None, None),
        ('vphuc', 'vinh phuc', None, None),
        ('vinhphuc', 'vinh phuc', None, None),
        ('yen', 'yen bai', None, None),
        ('yenbai', 'yen bai', None, None),
        ('brvt', 'ba ria vung tau', None, None),
        ('bariavungtau', 'ba ria vung tau', None, None),
        ('br', 'ba ria vung tau', None, None),
        ('vt', 'ba ria vung tau', None, None),
        ('ct', 'can tho', None, None),
        ('cantho', 'can tho', None, None),
        ('hp', 'hai phong', None, None),
        ('haiphong', 'hai phong', None, None),
        ('danang', 'da nang', None, None),
        ('dongnai', 'dong nai', None, None),

        # Ambiguous abbreviations (multiple province matches - creates branches)
        # These will cause the system to create multiple candidate branches
        ('dn', 'da nang', None, None),
        ('dn', 'dong nai', None, None),
        ('bt', 'ben tre', None, None),
        ('bt', 'bac thuan', None, None),  # Binh Thuan alternative
        ('bn', 'bac ninh', None, None),
        ('bn', 'bac binh', None, None),  # If exists
        ('ag', 'an giang', None, None),
        ('angiang', 'an giang', None, None),
        ('bl', 'bac lieu', None, None),
        ('baclieu', 'bac lieu', None, None),
        ('bg', 'bac giang', None, None),
        ('bacgiang', 'bac giang', None, None),
        ('bk', 'bac kan', None, None),
        ('backan', 'bac kan', None, None),
        ('bentre', 'ben tre', None, None),
        ('bacninh', 'bac ninh', None, None),
        ('btri', 'binh tri', None, None),  # If exists
        ('binhthuan', 'binh thuan', None, None),
        ('caomau', 'ca mau', None, None),
        ('cm', 'ca mau', None, None),
        ('dbien', 'dien bien', None, None),
        ('dienbien', 'dien bien', None, None),
        ('db', 'dien bien', None, None),
        ('dthap', 'dong thap', None, None),
        ('dongthap', 'dong thap', None, None),
        ('dt', 'dong thap', None, None),
        ('gl', 'gia lai', None, None),
        ('gialai', 'gia lai', None, None),
        ('hduong', 'hai duong', None, None),
        ('haiduong', 'hai duong', None, None),
        ('hd', 'hai duong', None, None),
        ('hgiang', 'ha giang', None, None),
        ('hagiang', 'ha giang', None, None),
        ('hg', 'ha giang', None, None),
        ('hnam', 'ha nam', None, None),
        ('hanam', 'ha nam', None, None),
        ('hatinh', 'ha tinh', None, None),
        ('htinh', 'ha tinh', None, None),
        ('ht', 'ha tinh', None, None),
        ('hbinh', 'hoa binh', None, None),
        ('hoabinh', 'hoa binh', None, None),
        ('hb', 'hoa binh', None, None),
        ('hau', 'hau giang', None, None),
        ('haugiang', 'hau giang', None, None),
        ('hg', 'hau giang', None, None),
        ('hung', 'hung yen', None, None),
        ('hungyen', 'hung yen', None, None),
        ('hy', 'hung yen', None, None),
        ('kg', 'kien giang', None, None),
        ('kiengiang', 'kien giang', None, None),
        ('kh', 'khanh hoa', None, None),
        ('khanhhoa', 'khanh hoa', None, None),
        ('kontum', 'kon tum', None, None),
        ('kt', 'kon tum', None, None),
    ]

    print(f"\nAdding {len(abbreviations)} province abbreviations...")

    # Count how many are new vs already exist
    inserted_count = 0
    existing_count = 0

    for key, word, province_ctx, district_ctx in abbreviations:
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO abbreviations
                (key, word, province_context, district_context)
                VALUES (?, ?, ?, ?)
                """,
                (key, word, province_ctx, district_ctx)
            )

            if cursor.rowcount > 0:
                inserted_count += 1
                print(f"  ✓ Added: '{key}' → '{word}'")
            else:
                existing_count += 1
                print(f"  - Exists: '{key}' → '{word}'")

        except sqlite3.IntegrityError as e:
            print(f"  ✗ Error adding '{key}' → '{word}': {e}")

    # Commit changes
    conn.commit()

    print(f"\n{'='*60}")
    print(f"Migration completed:")
    print(f"  - New abbreviations added: {inserted_count}")
    print(f"  - Already existing: {existing_count}")
    print(f"  - Total: {len(abbreviations)}")
    print(f"{'='*60}")

    # Verify: Show ambiguous abbreviations
    print("\nAmbiguous abbreviations (will create branches):")
    cursor.execute("""
        SELECT key, GROUP_CONCAT(word, ', ') as words, COUNT(*) as count
        FROM abbreviations
        WHERE province_context IS NULL AND district_context IS NULL
        GROUP BY key
        HAVING count > 1
        ORDER BY key
    """)

    ambiguous = cursor.fetchall()
    if ambiguous:
        for row in ambiguous:
            print(f"  - '{row[0]}' → [{row[1]}]  ({row[2]} matches)")
    else:
        print("  (None found)")

    # Close connection
    conn.close()
    print(f"\nDatabase updated successfully: {db_path}")


if __name__ == '__main__':
    try:
        migrate_province_abbreviations()
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
