"""
Phân tích chi tiết các cases TP HỒ CHÍ MINH có rating = 3
"""

import sqlite3
import re

DB_PATH = "data/address.db"


def get_hcm_cases():
    """Lấy tất cả cases HCM theo rating"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Rating 3
    cursor.execute("""
        SELECT * FROM user_quality_ratings
        WHERE known_province = 'HO CHI MINH' AND user_rating = 3
        ORDER BY id
    """)
    rating3 = [dict(row) for row in cursor.fetchall()]

    # Rating 1
    cursor.execute("""
        SELECT * FROM user_quality_ratings
        WHERE known_province = 'HO CHI MINH' AND user_rating = 1
        ORDER BY id
    """)
    rating1 = [dict(row) for row in cursor.fetchall()]

    # Rating 2
    cursor.execute("""
        SELECT * FROM user_quality_ratings
        WHERE known_province = 'HO CHI MINH' AND user_rating = 2
        ORDER BY id
    """)
    rating2 = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return rating3, rating1, rating2


def extract_district_ward_pattern(address):
    """Extract quận/phường pattern từ địa chỉ HCM"""
    patterns = {
        'quan': None,
        'phuong': None,
        'format': None
    }

    # Các pattern phổ biến ở HCM
    # Q1, Q2, ..., Q12, Quận 1, Quận Tân Bình, etc.
    quan_patterns = [
        r'Q\.?\s*(\d+)',  # Q1, Q.1, Q 1
        r'Q\.?\s*([A-Z\s]+)',  # Q.GO VAP, Q TAN BINH, Q.TB
        r'QUAN\s+(\d+)',  # QUAN 1
        r'QUAN\s+([A-Z\s]+)',  # QUAN TAN BINH
    ]

    # P1, P2, ..., Phường 1, etc.
    phuong_patterns = [
        r'P\.?\s*(\d+)',  # P1, P.1, P 1
        r'P\.?\s*([A-Z\s]+)',  # P.TAN THANH
        r'PHUONG\s+(\d+)',  # PHUONG 1
        r'PHUONG\s+([A-Z\s]+)',  # PHUONG TAN THANH
        r'F\.?\s*(\d+)',  # F7 (floor hoặc phường?)
    ]

    address_upper = address.upper()

    # Tìm quận
    for pattern in quan_patterns:
        match = re.search(pattern, address_upper)
        if match:
            patterns['quan'] = match.group(1).strip()
            break

    # Tìm phường
    for pattern in phuong_patterns:
        match = re.search(pattern, address_upper)
        if match:
            patterns['phuong'] = match.group(1).strip()
            break

    # Xác định format
    if 'Q.' in address or 'P.' in address:
        patterns['format'] = 'viet_tat_co_cham'
    elif re.search(r'Q\d+', address_upper) or re.search(r'P\d+', address_upper):
        patterns['format'] = 'viet_tat_khong_cham'
    else:
        patterns['format'] = 'day_du'

    return patterns


def analyze_hcm_rating3():
    """Phân tích chi tiết cases HCM rating 3"""
    rating3, rating1, rating2 = get_hcm_cases()

    print("="*80)
    print("PHÂN TÍCH CHI TIẾT CASES TP HỒ CHÍ MINH")
    print("="*80)
    print(f"\n📊 Tổng quan:")
    print(f"   Rating 1 (tốt):  {len(rating1)} cases")
    print(f"   Rating 2 (khá):  {len(rating2)} cases")
    print(f"   Rating 3 (tệ):   {len(rating3)} cases")
    print(f"   Success rate: {len(rating1)/(len(rating1)+len(rating2)+len(rating3))*100:.1f}%")

    print("\n" + "="*80)
    print("PHÂN TÍCH 8 CASES RATING = 3")
    print("="*80)

    for i, record in enumerate(rating3, 1):
        address = record['original_address']
        pattern = extract_district_ward_pattern(address)

        print(f"\n[Case {i}] ID: {record['id']}")
        print(f"{'='*80}")
        print(f"Địa chỉ: {address}")
        print(f"Known district: {record['known_district']}")
        print(f"Parsed: {record['parsed_province'] or '(null)'} / "
              f"{record['parsed_district'] or '(null)'} / "
              f"{record['parsed_ward'] or '(null)'}")

        if record['confidence_score']:
            print(f"Confidence: {record['confidence_score']:.2f}")

        print(f"\nPattern detected:")
        print(f"  • Quận: {pattern['quan'] or '(không tìm thấy)'}")
        print(f"  • Phường: {pattern['phuong'] or '(không tìm thấy)'}")
        print(f"  • Format: {pattern['format']}")

        # Phân tích nguyên nhân
        print(f"\n🔍 Nguyên nhân thất bại:")

        if pattern['quan']:
            print(f"  ✓ Có quận trong text: {pattern['quan']}")

            # Chuẩn hóa tên quận
            if pattern['quan'].isdigit():
                quan_full = f"quan {pattern['quan']}"
            elif pattern['quan'] in ['GO VAP', 'TAN PHU', 'TAN BINH', 'TB']:
                quan_mapping = {
                    'GO VAP': 'go vap',
                    'TAN PHU': 'tan phu',
                    'TAN BINH': 'tan binh',
                    'TB': 'tan binh',
                    'GV': 'go vap'
                }
                quan_full = f"quan {quan_mapping.get(pattern['quan'], pattern['quan'].lower())}"
            else:
                quan_full = pattern['quan'].lower()

            print(f"  → Nên parse được: {quan_full}")

            # Kiểm tra format
            if pattern['format'] == 'viet_tat_co_cham':
                print(f"  ⚠️  Format có dấu chấm (Q., P.) - có thể gây lỗi")
            if pattern['format'] == 'viet_tat_khong_cham':
                print(f"  ⚠️  Format viết tắt không khoảng cách (Q8, P15)")

        else:
            print(f"  ✗ KHÔNG có quận rõ ràng trong text")

        if pattern['phuong']:
            print(f"  ✓ Có phường trong text: {pattern['phuong']}")

            if pattern['phuong'].isdigit():
                phuong_full = f"phuong {pattern['phuong']}"
            else:
                phuong_full = pattern['phuong'].lower()

            print(f"  → Nên parse được: {phuong_full}")
        else:
            print(f"  ✗ KHÔNG có phường rõ ràng trong text")

        # Recommendations
        print(f"\n💡 Recommendation:")
        if pattern['quan'] or pattern['phuong']:
            print(f"  • Cần improve preprocessing để expand:")
            if pattern['quan']:
                if pattern['quan'] == 'TB':
                    print(f"    - 'Q.TB' → 'quan tan binh'")
                elif pattern['quan'] == 'GV':
                    print(f"    - 'Q GV' → 'quan go vap'")
                elif pattern['quan'].isdigit():
                    print(f"    - 'Q{pattern['quan']}' → 'quan {pattern['quan']}'")
                else:
                    print(f"    - 'Q.{pattern['quan']}' → 'quan {pattern['quan'].lower()}'")
            if pattern['phuong']:
                if pattern['phuong'].isdigit():
                    print(f"    - 'P{pattern['phuong']}' → 'phuong {pattern['phuong']}'")
        else:
            print(f"  • Địa chỉ thiếu thông tin, khó parse")

    # Phân tích patterns chung
    print("\n" + "="*80)
    print("TỔNG HỢP PATTERNS")
    print("="*80)

    formats = {}
    has_quan = 0
    has_phuong = 0

    for record in rating3:
        pattern = extract_district_ward_pattern(record['original_address'])
        fmt = pattern['format']
        formats[fmt] = formats.get(fmt, 0) + 1

        if pattern['quan']:
            has_quan += 1
        if pattern['phuong']:
            has_phuong += 1

    print(f"\nFormat distribution:")
    for fmt, count in sorted(formats.items(), key=lambda x: x[1], reverse=True):
        print(f"  {fmt:30s}: {count} cases")

    print(f"\nThông tin trong text:")
    print(f"  Có quận:   {has_quan}/8 ({has_quan/8*100:.1f}%)")
    print(f"  Có phường: {has_phuong}/8 ({has_phuong/8*100:.1f}%)")

    # So sánh với rating 1
    print("\n" + "="*80)
    print("SO SÁNH VỚI RATING 1 (Successful cases)")
    print("="*80)

    print(f"\nVí dụ về cases thành công:")
    for i, record in enumerate(rating1[:3], 1):
        print(f"\n[Success {i}] ID: {record['id']}")
        print(f"  Address: {record['original_address']}")
        print(f"  Parsed: {record['parsed_province']} / "
              f"{record['parsed_district'] or '(null)'} / "
              f"{record['parsed_ward'] or '(null)'}")
        if record['confidence_score']:
            print(f"  Confidence: {record['confidence_score']:.2f}")

        pattern = extract_district_ward_pattern(record['original_address'])
        print(f"  Pattern: Q={pattern['quan']}, P={pattern['phuong']}, "
              f"Format={pattern['format']}")


if __name__ == "__main__":
    analyze_hcm_rating3()
