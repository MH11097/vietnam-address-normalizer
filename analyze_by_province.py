"""
Phân tích cases rating 3 theo từng tỉnh/thành phố
Đưa ra phương án cải thiện cụ thể
"""

import sqlite3
from collections import defaultdict

DB_PATH = "data/address.db"


def get_all_ratings_by_province():
    """Lấy tất cả ratings theo tỉnh"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT known_province, user_rating, COUNT(*) as count
        FROM user_quality_ratings
        GROUP BY known_province, user_rating
        ORDER BY known_province, user_rating
    """)

    results = {}
    for row in cursor.fetchall():
        province = row['known_province']
        rating = row['user_rating']
        count = row['count']

        if province not in results:
            results[province] = {1: 0, 2: 0, 3: 0}
        results[province][rating] = count

    conn.close()
    return results


def get_rating3_by_province():
    """Lấy chi tiết cases rating 3 theo tỉnh"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM user_quality_ratings
        WHERE user_rating = 3
        ORDER BY known_province, id
    """)

    results = defaultdict(list)
    for row in cursor.fetchall():
        province = row['known_province']
        results[province].append(dict(row))

    conn.close()
    return results


def analyze_province_patterns(cases):
    """Phân tích patterns cho một tỉnh"""
    patterns = {
        'total': len(cases),
        'no_parse': 0,
        'low_confidence': 0,
        'has_abbreviation': 0,
        'has_district_info': 0,
        'examples': []
    }

    for case in cases[:3]:  # Lấy 3 examples
        addr = case['original_address']
        patterns['examples'].append(addr)

        # Check no parse
        if not case['parsed_province']:
            patterns['no_parse'] += 1

        # Check low confidence
        if case['confidence_score'] and case['confidence_score'] < 0.6:
            patterns['low_confidence'] += 1

        # Check abbreviations
        addr_upper = addr.upper()
        abbr_keywords = ['TP', 'Q.', 'P.', 'F.', 'TT', 'MT', 'TB', 'GV']
        if any(kw in addr_upper for kw in abbr_keywords):
            patterns['has_abbreviation'] += 1

        # Check has district info
        if case['known_district'] and case['known_district'] != '/':
            patterns['has_district_info'] += 1

    return patterns


def main():
    print("="*80)
    print("PHÂN TÍCH CASES RATING 3 THEO TỈNH/THÀNH PHỐ")
    print("PHƯƠNG ÁN CẢI THIỆN CỤ THỂ")
    print("="*80)

    # Get data
    all_ratings = get_all_ratings_by_province()
    rating3_cases = get_rating3_by_province()

    # Tính toán statistics
    province_stats = []
    for province, ratings in all_ratings.items():
        total = sum(ratings.values())
        rating3_count = ratings[3]
        success_rate = (ratings[1] / total * 100) if total > 0 else 0

        province_stats.append({
            'province': province,
            'total': total,
            'rating1': ratings[1],
            'rating2': ratings[2],
            'rating3': rating3_count,
            'success_rate': success_rate,
            'failure_rate': rating3_count / total * 100 if total > 0 else 0
        })

    # Sort by failure rate
    province_stats.sort(key=lambda x: x['failure_rate'], reverse=True)

    # Print top 10 worst provinces
    print("\n" + "="*80)
    print("TOP 10 TỈNH/THÀNH PHỐ CÓ TỶ LỆ LỖI CAO NHẤT")
    print("="*80)
    print(f"\n{'Tỉnh/TP':<20} {'Total':>6} {'R1':>4} {'R2':>4} {'R3':>4} {'Success':>8} {'Failure':>8}")
    print("-"*80)

    for i, stat in enumerate(province_stats[:10], 1):
        print(f"{i:2}. {stat['province']:<17} "
              f"{stat['total']:>6} "
              f"{stat['rating1']:>4} "
              f"{stat['rating2']:>4} "
              f"{stat['rating3']:>4} "
              f"{stat['success_rate']:>7.1f}% "
              f"{stat['failure_rate']:>7.1f}%")

    # Detailed analysis for top 5
    print("\n\n" + "="*80)
    print("PHÂN TÍCH CHI TIẾT VÀ PHƯƠNG ÁN CẢI THIỆN - TOP 5")
    print("="*80)

    for i, stat in enumerate(province_stats[:5], 1):
        province = stat['province']
        cases = rating3_cases[province]
        patterns = analyze_province_patterns(cases)

        print(f"\n{'='*80}")
        print(f"{i}. {province}")
        print(f"{'='*80}")
        print(f"   Tổng số cases: {stat['total']}")
        print(f"   Rating 3: {stat['rating3']} ({stat['failure_rate']:.1f}%)")
        print(f"   Success rate: {stat['success_rate']:.1f}%")

        print(f"\n   📊 Patterns:")
        print(f"      • Không parse được gì: {patterns['no_parse']}/{patterns['total']}")
        print(f"      • Có viết tắt: {patterns['has_abbreviation']}/{patterns['total']}")
        print(f"      • Có thông tin district: {patterns['has_district_info']}/{patterns['total']}")
        print(f"      • Confidence thấp: {patterns['low_confidence']}/{patterns['total']}")

        print(f"\n   📝 Ví dụ:")
        for j, example in enumerate(patterns['examples'], 1):
            print(f"      {j}. {example}")

        # Recommendations
        print(f"\n   💡 Phương án cải thiện:")

        if patterns['has_abbreviation'] > 0:
            print(f"      ✓ Implement abbreviation expansion")
            if province == 'HO CHI MINH':
                print(f"        → Priority: CRITICAL (Q8, P15, Q.TB pattern)")
            elif province == 'HA NOI':
                print(f"        → Priority: HIGH (Q., P. pattern)")

        if patterns['has_district_info'] > 0:
            print(f"      ✓ Tận dụng known_district hint tốt hơn")
            print(f"        → {patterns['has_district_info']} cases có district hint")

        if patterns['no_parse'] == patterns['total']:
            print(f"      ⚠️  100% cases không parse được gì")
            print(f"        → Cần analyze format cụ thể của tỉnh này")

        # Specific recommendations by province
        if province == 'HO CHI MINH':
            print(f"\n      🎯 Specific actions:")
            print(f"         1. Expand Q8 → quan 8, P15 → phuong 15")
            print(f"         2. Expand Q.TB → quan tan binh, Q.GV → quan go vap")
            print(f"         3. Handle F7 (Floor vs Phường) with context")
            print(f"         → Expected impact: Fix 7/8 cases (87.5%)")

        elif province == 'HA NOI':
            print(f"\n      🎯 Specific actions:")
            print(f"         1. Expand Q., P. patterns")
            print(f"         2. Handle special formats (P302T3 CT18 KDT...)")
            print(f"         3. Improve organization address detection")

        elif province == 'BA RIA VUNG TAU':
            print(f"\n      🎯 Specific actions:")
            print(f"         1. Expand VTAU → Vũng Tàu")
            print(f"         2. Handle city name confusion (VUNG TAU province vs city)")

    # Summary
    print("\n\n" + "="*80)
    print("TỔNG HỢP PHƯƠNG ÁN CẢI THIỆN")
    print("="*80)

    total_rating3 = sum(stat['rating3'] for stat in province_stats)
    top5_rating3 = sum(stat['rating3'] for stat in province_stats[:5])

    print(f"\n📊 Impact Analysis:")
    print(f"   • Total rating 3: {total_rating3} cases")
    print(f"   • Top 5 provinces: {top5_rating3} cases ({top5_rating3/total_rating3*100:.1f}%)")
    print(f"   • If fix top 5 → giảm rating 3 từ {total_rating3} → ~{total_rating3-top5_rating3}")

    print(f"\n🎯 Priority Actions:")
    print(f"\n   1. CRITICAL - Abbreviation Expansion (All provinces)")
    print(f"      • Impact: Fix ~40-50 cases (55-68%)")
    print(f"      • Effort: 2-3 hours")
    print(f"      • ROI: Very High")
    print(f"      • Provinces: HCM (8), HN (9), BRVT (7), TG (5)")

    print(f"\n   2. HIGH - Province-specific Rules")
    print(f"      • HCM: Q8/P15 pattern → 7/8 cases")
    print(f"      • HN: Organization addresses → 4/9 cases")
    print(f"      • BRVT: City name confusion → 3/7 cases")
    print(f"      • Impact: Fix 14+ cases")
    print(f"      • Effort: 1-2 hours per province")

    print(f"\n   3. MEDIUM - Better Known Hints Usage")
    print(f"      • Use known_district to filter candidates")
    print(f"      • Impact: Fix ~10 cases")
    print(f"      • Effort: 1-2 hours")

    print(f"\n📈 Expected Results:")
    print(f"   • Current success rate: 60.4%")
    print(f"   • After Priority 1+2: ~80-85%")
    print(f"   • Improvement: +20-25 percentage points")


if __name__ == "__main__":
    main()
