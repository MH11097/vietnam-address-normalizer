#!/usr/bin/env python3
"""
Migration script: Generate và migrate abbreviations từ admin_divisions sang abbreviations table

Tạo 4 loại viết tắt cho mỗi level (province, district, ward):
1. Chữ cái đầu: "ba dinh" → "bd"
2. Đầu + Full: "ba dinh" → "bdinh"
3. Full normalized: "quan ba dinh" → "qbd"
4. Viết liền: "ba dinh" → "badinh"

Context được lưu theo hierarchy:
- Province: province_context=NULL, district_context=NULL
- District: province_context={province}, district_context=NULL
- Ward: province_context={province}, district_context={district}
"""

import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DB_PATH


def generate_abbreviation_type1(normalized_name: str) -> str:
    """Type 1: Chữ cái đầu mỗi từ - 'ba dinh' → 'bd'"""
    if not normalized_name:
        return ""
    words = normalized_name.split()
    return "".join(w[0] for w in words if w)


def generate_abbreviation_type2(normalized_name: str) -> str:
    """Type 2: Đầu + Full - 'ba dinh' → 'bdinh'"""
    if not normalized_name:
        return ""
    words = normalized_name.split()
    if len(words) == 1:
        return words[0][:3] if len(words[0]) > 3 else words[0]
    return words[0][0] + "".join(words[1:])


def generate_abbreviation_type3(full_normalized: str) -> str:
    """Type 3: Full normalized với prefix - 'quan ba dinh' → 'qbd'"""
    if not full_normalized:
        return ""
    words = full_normalized.split()
    return "".join(w[0] for w in words if w)


def generate_abbreviation_type4(normalized_name: str) -> str:
    """Type 4: Viết liền - 'ba dinh' → 'badinh'"""
    if not normalized_name:
        return ""
    return normalized_name.replace(" ", "")


def get_admin_divisions(conn):
    """Lấy tất cả records từ admin_divisions"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            province_name_normalized,
            province_full_normalized,
            district_name_normalized,
            district_full_normalized,
            ward_name_normalized,
            ward_full_normalized
        FROM admin_divisions
        WHERE province_name_normalized IS NOT NULL
    """)
    return cursor.fetchall()


def insert_abbreviation(conn, key, word, province_context, district_context):
    """Insert abbreviation if not exists"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO abbreviations
            (key, word, province_context, district_context)
            VALUES (?, ?, ?, ?)
        """, (key, word, province_context, district_context))
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False


def migrate_abbreviations():
    """Main migration function"""

    conn = sqlite3.connect(DB_PATH)

    try:
        print("=" * 80)
        print("MIGRATION: Generate Abbreviations từ admin_divisions")
        print("=" * 80)

        # Statistics
        stats = {
            'total_records': 0,
            'province_abbr': 0,
            'district_abbr': 0,
            'ward_abbr': 0,
            'duplicates': 0,
            'errors': 0
        }

        # Track để tránh duplicate trong cùng 1 run
        seen_provinces = set()
        seen_districts = defaultdict(set)  # {province: set(districts)}

        # Lấy dữ liệu
        print("\n1. Đang load dữ liệu từ admin_divisions...")
        records = get_admin_divisions(conn)
        stats['total_records'] = len(records)
        print(f"   ✓ Loaded {stats['total_records']} records")

        print("\n2. Đang generate abbreviations...")

        for record in records:
            (province_name_norm, province_full_norm,
             district_name_norm, district_full_norm,
             ward_name_norm, ward_full_norm) = record

            # PROVINCE LEVEL (global context)
            if province_name_norm and province_name_norm not in seen_provinces:
                seen_provinces.add(province_name_norm)

                province_abbrs = [
                    (generate_abbreviation_type1(province_name_norm), province_name_norm),
                    (generate_abbreviation_type2(province_name_norm), province_name_norm),
                    (generate_abbreviation_type3(province_full_norm), province_name_norm),
                    (generate_abbreviation_type4(province_name_norm), province_name_norm),
                ]

                for abbr, word in province_abbrs:
                    if abbr and len(abbr) >= 2:  # Chỉ lưu abbr có ít nhất 2 ký tự
                        if insert_abbreviation(conn, abbr, word, None, None):
                            stats['province_abbr'] += 1
                        else:
                            stats['duplicates'] += 1

            # DISTRICT LEVEL (province context)
            if district_name_norm and district_name_norm not in seen_districts[province_name_norm]:
                seen_districts[province_name_norm].add(district_name_norm)

                district_abbrs = [
                    (generate_abbreviation_type1(district_name_norm), district_name_norm),
                    (generate_abbreviation_type2(district_name_norm), district_name_norm),
                    (generate_abbreviation_type3(district_full_norm), district_name_norm),
                    (generate_abbreviation_type4(district_name_norm), district_name_norm),
                ]

                for abbr, word in district_abbrs:
                    if abbr and len(abbr) >= 2:
                        if insert_abbreviation(conn, abbr, word, province_name_norm, None):
                            stats['district_abbr'] += 1
                        else:
                            stats['duplicates'] += 1

            # WARD LEVEL (province + district context)
            if ward_name_norm:
                ward_abbrs = [
                    (generate_abbreviation_type1(ward_name_norm), ward_name_norm),
                    (generate_abbreviation_type2(ward_name_norm), ward_name_norm),
                    (generate_abbreviation_type3(ward_full_norm), ward_name_norm),
                    (generate_abbreviation_type4(ward_name_norm), ward_name_norm),
                ]

                for abbr, word in ward_abbrs:
                    if abbr and len(abbr) >= 2:
                        if insert_abbreviation(conn, abbr, word, province_name_norm, district_name_norm):
                            stats['ward_abbr'] += 1
                        else:
                            stats['duplicates'] += 1

        # Commit changes
        conn.commit()

        # Final statistics
        print("\n" + "=" * 80)
        print("MIGRATION COMPLETED!")
        print("=" * 80)
        print(f"\nStatistics:")
        print(f"  • Total admin_divisions records processed: {stats['total_records']:,}")
        print(f"  • New province abbreviations added: {stats['province_abbr']:,}")
        print(f"  • New district abbreviations added: {stats['district_abbr']:,}")
        print(f"  • New ward abbreviations added: {stats['ward_abbr']:,}")
        print(f"  • Total new abbreviations: {stats['province_abbr'] + stats['district_abbr'] + stats['ward_abbr']:,}")
        print(f"  • Duplicates skipped: {stats['duplicates']:,}")

        # Count total in table
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM abbreviations")
        total_in_db = cursor.fetchone()[0]
        print(f"  • Total abbreviations in database: {total_in_db:,}")

        # Sample records
        print("\n" + "=" * 80)
        print("SAMPLE RECORDS")
        print("=" * 80)

        # Province level
        print("\nProvince level (global context):")
        cursor.execute("""
            SELECT key, word, province_context, district_context
            FROM abbreviations
            WHERE province_context IS NULL AND district_context IS NULL
            ORDER BY RANDOM()
            LIMIT 5
        """)
        for key, word, prov, dist in cursor.fetchall():
            print(f"  {key:15} → {word:30} [global]")

        # District level
        print("\nDistrict level (province context):")
        cursor.execute("""
            SELECT key, word, province_context, district_context
            FROM abbreviations
            WHERE province_context IS NOT NULL AND district_context IS NULL
            ORDER BY RANDOM()
            LIMIT 5
        """)
        for key, word, prov, dist in cursor.fetchall():
            print(f"  {key:15} → {word:30} [province: {prov}]")

        # Ward level
        print("\nWard level (province + district context):")
        cursor.execute("""
            SELECT key, word, province_context, district_context
            FROM abbreviations
            WHERE province_context IS NOT NULL AND district_context IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 5
        """)
        for key, word, prov, dist in cursor.fetchall():
            print(f"  {key:15} → {word:30} [province: {prov}, district: {dist}]")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

    return True


if __name__ == "__main__":
    success = migrate_abbreviations()
    sys.exit(0 if success else 1)
