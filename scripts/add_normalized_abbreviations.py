#!/usr/bin/env python3
"""
Script để thêm các abbreviations normalized (không có ký tự đặc biệt)
cho các keys có apostrophe ('), hyphen (-), hoặc dot (.)
"""

import sqlite3
import re

DB_PATH = 'data/address.db'

# Ký tự đặc biệt đơn giản cần normalize
SIMPLE_SPECIAL_CHARS = r"['\-\.]"

# Ký tự regex (để bỏ qua)
REGEX_CHARS = r'[\\\(\)\?\|\[\]]'

def find_simple_special_abbreviations(cursor):
    """Tìm các abbreviations có ký tự đặc biệt đơn giản (không phải regex)."""
    cursor.execute("""
        SELECT id, key, word, province_context, district_context
        FROM abbreviations
        ORDER BY id
    """)

    simple_special_records = []
    for row in cursor.fetchall():
        id_, key, word, province_context, district_context = row

        # Bỏ qua nếu là regex pattern
        if re.search(REGEX_CHARS, key):
            continue

        # Kiểm tra nếu có ký tự đặc biệt đơn giản
        if re.search(SIMPLE_SPECIAL_CHARS, key):
            simple_special_records.append({
                'id': id_,
                'key': key,
                'word': word,
                'province_context': province_context,
                'district_context': district_context
            })

    return simple_special_records

def normalize_key(key):
    """Loại bỏ ký tự đặc biệt đơn giản khỏi key."""
    return re.sub(SIMPLE_SPECIAL_CHARS, '', key)

def key_exists(cursor, key, province_context, district_context):
    """Kiểm tra xem (key, province_context, district_context) đã tồn tại chưa."""
    cursor.execute("""
        SELECT COUNT(*) FROM abbreviations
        WHERE key = ?
          AND province_context IS ?
          AND district_context IS ?
    """, (key, province_context, district_context))

    count = cursor.fetchone()[0]
    return count > 0

def add_normalized_abbreviations(cursor, records):
    """Thêm các normalized abbreviations."""
    added = []
    skipped = []

    for record in records:
        original_key = record['key']
        normalized = normalize_key(original_key)

        # Bỏ qua nếu normalized key giống original (không có gì thay đổi)
        if normalized == original_key:
            continue

        # Bỏ qua nếu normalized key rỗng
        if not normalized:
            skipped.append({
                'original_key': original_key,
                'normalized_key': normalized,
                'reason': 'Key rỗng sau khi normalize'
            })
            continue

        # Kiểm tra xem đã tồn tại chưa
        if key_exists(cursor, normalized, record['province_context'], record['district_context']):
            skipped.append({
                'original_key': original_key,
                'normalized_key': normalized,
                'reason': 'Key đã tồn tại'
            })
            continue

        # Thêm record mới
        cursor.execute("""
            INSERT INTO abbreviations (key, word, province_context, district_context)
            VALUES (?, ?, ?, ?)
        """, (normalized, record['word'], record['province_context'], record['district_context']))

        added.append({
            'original_key': original_key,
            'normalized_key': normalized,
            'word': record['word'],
            'province_context': record['province_context'],
            'district_context': record['district_context']
        })

    return added, skipped

def main():
    print("=" * 80)
    print("THÊM NORMALIZED ABBREVIATIONS (KHÔNG CÓ KÝ TỰ ĐẶC BIỆT)")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Tìm các abbreviations có ký tự đặc biệt đơn giản
        print("Đang tìm các abbreviations có ký tự đặc biệt đơn giản (', -, .)...")
        records = find_simple_special_abbreviations(cursor)

        print(f"Tìm thấy {len(records)} records:")
        print()

        # Hiển thị một vài ví dụ
        print("Ví dụ:")
        for i, record in enumerate(records[:10], 1):
            normalized = normalize_key(record['key'])
            print(f"{i}. '{record['key']}' → '{normalized}' (word: {record['word']})")

        if len(records) > 10:
            print(f"... và {len(records) - 10} records khác")

        print()
        print("-" * 80)

        # Thêm normalized keys
        print(f"Đang thêm normalized keys...")
        added, skipped = add_normalized_abbreviations(cursor, records)
        conn.commit()

        print()
        print(f"✓ Đã thêm thành công {len(added)} records mới!")
        print(f"⊘ Bỏ qua {len(skipped)} records")
        print()

        # Chi tiết records đã thêm
        if added:
            print("RECORDS ĐÃ THÊM:")
            for i, item in enumerate(added[:20], 1):
                print(f"{i}. '{item['original_key']}' → '{item['normalized_key']}' (word: {item['word']})")
                if item['province_context'] or item['district_context']:
                    print(f"   Context: province={item['province_context']}, district={item['district_context']}")

            if len(added) > 20:
                print(f"... và {len(added) - 20} records khác")

        print()

        # Chi tiết records bỏ qua
        if skipped:
            print("RECORDS BỎ QUA:")
            for i, item in enumerate(skipped[:10], 1):
                print(f"{i}. '{item['original_key']}' → '{item['normalized_key']}' - {item['reason']}")

            if len(skipped) > 10:
                print(f"... và {len(skipped) - 10} records khác")

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
