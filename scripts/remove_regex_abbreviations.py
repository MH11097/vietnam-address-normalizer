#!/usr/bin/env python3
"""
Script để xóa các abbreviations có regex pattern (legacy logic) khỏi database.
"""

import sqlite3
import re

DB_PATH = 'data/address.db'

# Ký tự đặc biệt của regex patterns
REGEX_CHARS = r'[\\\(\)\?\|\[\]]'

def find_regex_abbreviations(cursor):
    """Tìm các abbreviations có regex pattern."""
    cursor.execute("""
        SELECT id, key, word, province_context, district_context
        FROM abbreviations
        ORDER BY id
    """)

    regex_records = []
    for row in cursor.fetchall():
        id_, key, word, province_context, district_context = row
        # Kiểm tra nếu key chứa ký tự regex
        if re.search(REGEX_CHARS, key):
            regex_records.append({
                'id': id_,
                'key': key,
                'word': word,
                'province_context': province_context,
                'district_context': district_context
            })

    return regex_records

def remove_regex_abbreviations(cursor, records):
    """Xóa các regex abbreviations."""
    ids_to_delete = [r['id'] for r in records]

    if not ids_to_delete:
        return 0

    placeholders = ','.join('?' * len(ids_to_delete))
    cursor.execute(f"""
        DELETE FROM abbreviations
        WHERE id IN ({placeholders})
    """, ids_to_delete)

    return cursor.rowcount

def main():
    print("=" * 80)
    print("XÓA CÁC ABBREVIATIONS CÓ REGEX PATTERN (LEGACY LOGIC)")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Tìm các regex abbreviations
        print("Đang tìm các abbreviations có regex pattern...")
        regex_records = find_regex_abbreviations(cursor)

        print(f"Tìm thấy {len(regex_records)} records có regex pattern:")
        print()

        # Hiển thị danh sách
        for i, record in enumerate(regex_records, 1):
            print(f"{i}. ID={record['id']}: key='{record['key']}' → word='{record['word']}'")
            if record['province_context'] or record['district_context']:
                print(f"   Context: province={record['province_context']}, district={record['district_context']}")

        print()
        print("-" * 80)

        # Xóa
        print(f"Đang xóa {len(regex_records)} records...")
        deleted_count = remove_regex_abbreviations(cursor, regex_records)
        conn.commit()

        print(f"✓ Đã xóa thành công {deleted_count} records!")
        print()

        # Kiểm tra lại
        remaining_regex = find_regex_abbreviations(cursor)
        if remaining_regex:
            print(f"⚠ Cảnh báo: Vẫn còn {len(remaining_regex)} regex records!")
        else:
            print("✓ Không còn regex abbreviations trong database")

    except Exception as e:
        conn.rollback()
        print(f"✗ Lỗi: {e}")
        raise
    finally:
        conn.close()

    print()
    print("=" * 80)
    print("HOÀN THÀNH")
    print("=" * 80)

if __name__ == '__main__':
    main()
