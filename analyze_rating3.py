"""
Script phân tích và phân loại các cases có rating = 3
Chia thành các nhóm dựa trên nguyên nhân thất bại
"""

import sqlite3
import re
from collections import defaultdict

DB_PATH = "data/address.db"


def get_rating3_records():
    """Lấy tất cả records có rating = 3"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM user_quality_ratings
        WHERE user_rating = 3
        ORDER BY id
    """)

    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records


def classify_failure_reason(record):
    """
    Phân loại nguyên nhân thất bại
    """
    address = record['original_address']
    known_province = record['known_province']
    known_district = record['known_district']
    parsed_province = record['parsed_province']
    parsed_district = record['parsed_district']
    parsed_ward = record['parsed_ward']
    confidence = record['confidence_score']

    # Nhóm 1: Không parse được gì (no match)
    if not parsed_province and not parsed_district and not parsed_ward:
        # Phân loại chi tiết hơn

        # 1.1: Viết tắt quá nhiều
        abbreviations = ['TP', 'TPTH', 'MT', 'TG', 'Q.', 'P.', 'F.', 'TT', 'TXHB', 'BMT']
        if any(abbr in address.upper() for abbr in abbreviations):
            return "1.1_VIET_TAT_QUA_NHIEU"

        # 1.2: Địa chỉ cơ quan/công ty (không có thông tin địa lý rõ ràng)
        org_keywords = ['TRUONG', 'CTY', 'CONG TY', 'BAN', 'SO', 'LU DOAN', 'TYT', 'HTX']
        if any(keyword in address.upper() for keyword in org_keywords):
            return "1.2_DIA_CHI_CO_QUAN"

        # 1.3: Format lạ/đặc biệt
        if '_' in address or '--' in address:
            return "1.3_FORMAT_LA"

        # 1.4: Chỉ có số nhà và tên đường (không có province/district/ward trong text)
        if known_district == '/':
            return "1.4_THIEU_THONG_TIN_DIA_LY"

        return "1.0_KHONG_PARSE_DUOC_GI"

    # Nhóm 2: Parse được nhưng confidence thấp (< 0.6)
    if confidence and confidence < 0.6:
        return "2_CONFIDENCE_THAP"

    # Nhóm 3: Parse được với confidence cao nhưng bị đánh giá rating 3
    if confidence and confidence >= 0.8:
        # 3.1: Parse sai district
        if parsed_district and known_district and known_district != '/' and parsed_district.lower() != known_district.lower():
            return "3.1_PARSE_SAI_DISTRICT"

        # 3.2: Parse đúng nhưng user không hiểu (có thể UX issue)
        return "3.2_CO_THE_UX_ISSUE"

    # Nhóm 4: Parse được một phần (confidence trung bình 0.6-0.8)
    if confidence and 0.6 <= confidence < 0.8:
        return "4_PARSE_MOT_PHAN"

    return "0_KHAC"


def analyze_records():
    """Phân tích và nhóm các records"""
    records = get_rating3_records()

    # Phân loại
    groups = defaultdict(list)
    for record in records:
        category = classify_failure_reason(record)
        groups[category].append(record)

    # In kết quả
    print("="*80)
    print("PHÂN LOẠI CÁC CASES RATING = 3")
    print("="*80)
    print(f"\nTổng số records: {len(records)}")
    print("\n" + "="*80)

    # Sắp xếp theo số lượng
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    for category, items in sorted_groups:
        print(f"\n{'='*80}")
        print(f"NHÓM: {category}")
        print(f"Số lượng: {len(items)} records ({len(items)/len(records)*100:.1f}%)")
        print(f"{'='*80}")

        # In ra một vài ví dụ điển hình (tối đa 10)
        for i, record in enumerate(items[:10], 1):
            print(f"\n[{i}] ID: {record['id']}")
            print(f"    Address: {record['original_address']}")
            print(f"    Known: {record['known_province']} / {record['known_district']}")

            if record['parsed_province']:
                print(f"    Parsed: {record['parsed_province']} / {record['parsed_district']} / {record['parsed_ward']}")
                print(f"    Confidence: {record['confidence_score']:.2f}")
            else:
                print(f"    Parsed: (không parse được gì)")

        if len(items) > 10:
            print(f"\n    ... và {len(items) - 10} records khác")

    # Tổng hợp thống kê
    print("\n" + "="*80)
    print("TỔNG HỢP THỐNG KÊ")
    print("="*80)

    for category, items in sorted_groups:
        print(f"{category:40s}: {len(items):3d} records ({len(items)/len(records)*100:5.1f}%)")


if __name__ == "__main__":
    analyze_records()
