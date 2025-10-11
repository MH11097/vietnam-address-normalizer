"""
ADDRESS PARSING PIPELINE - DEMO
================================
Usage:
    python demo.py --address "NGO394 DOI CAN P.CONG VI BD HN"
    python demo.py --address "NGO394 DOI CAN P.CONG VI BD HN" --province "Hà Nội"
    python demo.py --limit 5
"""
import sys
import argparse
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_extraction import extract_components
from src.processors.phase3_candidates import generate_candidates
from src.processors.phase4_validation import validate_and_rank
from src.processors.phase5_postprocessing import postprocess
from src.utils.db_utils import query_all
from src.utils.text_utils import normalize_hint
from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative


# Custom logging formatter với màu sắc
class ColoredFormatter(logging.Formatter):
    """Formatter với màu cho log levels"""
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[1m\033[91m',  # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


# Cấu hình logging - chỉ hiển thị WARNING và ERROR
def setup_logging():
    """
    Thiết lập logging gọn gàng
    - Ẩn tất cả INFO log từ modules con (phase1-5, utils)
    - Chỉ hiển thị WARNING và ERROR
    """
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)

    # Xóa handlers cũ nếu có
    if logger.handlers:
        logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Gọi setup
setup_logging()


# ANSI Color codes
class Colors:
    """Simple ANSI color codes for terminal output"""
    RESET = '\033[0m'
    BOLD = '\033[1m'

    # Basic colors
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'

    # Combined
    CYAN_BOLD = '\033[1m\033[96m'
    GREEN_BOLD = '\033[1m\033[92m'
    YELLOW_BOLD = '\033[1m\033[93m'
    RED_BOLD = '\033[1m\033[91m'

    @staticmethod
    def disable():
        """Disable colors (for non-supporting terminals)"""
        Colors.RESET = ''
        Colors.BOLD = ''
        Colors.CYAN = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.RED = ''
        Colors.CYAN_BOLD = ''
        Colors.GREEN_BOLD = ''
        Colors.YELLOW_BOLD = ''
        Colors.RED_BOLD = ''


def colorize(text, color):
    """Wrap text với màu ANSI"""
    return f"{color}{text}{Colors.RESET}"


def score_color(score):
    """Chọn màu dựa trên điểm số"""
    if score >= 80:
        return Colors.GREEN
    elif score >= 50:
        return Colors.YELLOW
    else:
        return Colors.RED


def load_samples(limit=3, offset=0):
    """Load sample addresses từ database"""
    query = """
    SELECT cif_no, dia_chi_thuong_tru,
           ten_tinh_thuong_tru, ten_quan_huyen_thuong_tru
    FROM raw_addresses
    WHERE dia_chi_thuong_tru IS NOT NULL
      AND dia_chi_thuong_tru != ''
    LIMIT ? OFFSET ?
    """
    return query_all(query, (limit, offset))


def process_one_address(address_text, province_known=None, district_known=None):
    """Xử lý một địa chỉ qua 5 phases"""
    address_colored = colorize(address_text, Colors.YELLOW)
    if province_known == '/':
        province_known = None
    if district_known == '/':
        district_known = None

    # Always define prov_colored and dist_colored
    prov_colored = colorize(province_known or '____', Colors.CYAN)
    dist_colored = colorize(district_known or '____', Colors.CYAN)

    print(f"📥 Địa chỉ: {address_colored}, Tỉnh={prov_colored}, Huyện={dist_colored}")

    # ========== PHASE 1: Tiền xử lý (with ITERATIVE preprocessing) ==========
    # Use iterative preprocessing to fix abbreviation expansion circular dependency
    use_iterative = should_use_iterative(address_text, province_known)

    if use_iterative:
        p1 = iterative_preprocess(address_text, province_known, district_known)
        method_label = "Iterative (2-pass)"
        iterations = p1.get('total_iterations', 1)
    else:
        p1 = preprocess(address_text, province_known=province_known)
        method_label = "Single pass"
        iterations = 1

    p1_time = p1['processing_time_ms']
    print(f"\n⏱ {colorize(f'{p1_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 1: Tiền xử lý văn bản', Colors.BOLD)} [{method_label}]")
    print(f"  └─ Chuẩn hóa unicode, expand abbreviations (với province context), loại bỏ dấu")

    if iterations > 1:
        print(f"  └─ {colorize(f'Iterations: {iterations}', Colors.CYAN)} (discovered province context)")

    normalized_display = p1['normalized'][:80] + ('...' if len(p1['normalized']) > 80 else '')
    print(f"  └─ Đầu ra: {colorize(normalized_display, Colors.GREEN)}")

    # ========== PHASE 2: Trích xuất (Extract Potentials) ==========
    p2 = extract_components(p1, province_known, district_known)
    p2_time = p2['processing_time_ms']
    print(f"\n⏱ {colorize(f'{p2_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 2: Trích xuất (Extract Potentials)', Colors.BOLD)}")
    print(f"  └─ N-gram matching với 9,991 xã/phường trong database")

    # Show number of potentials extracted (NEW structure - no candidates yet)
    potential_provinces = p2.get('potential_provinces', [])
    potential_districts = p2.get('potential_districts', [])
    potential_wards = p2.get('potential_wards', [])
    potential_streets = p2.get('potential_streets', [])

    total_potentials = len(potential_provinces) + len(potential_districts) + len(potential_wards) + len(potential_streets)

    if total_potentials > 0:
        print(f"  └─ Extracted {colorize(str(total_potentials), Colors.YELLOW)} potentials: "
              f"{len(potential_provinces)} provinces, {len(potential_districts)} districts, "
              f"{len(potential_wards)} wards, {len(potential_streets)} streets")

        # Show top 3 potentials for each level
        if potential_provinces:
            print(f"     └─ Top provinces: {', '.join([colorize(p[0], Colors.CYAN) for p in potential_provinces[:3]])}")
        if potential_districts:
            print(f"     └─ Top districts: {', '.join([colorize(d[0], Colors.GREEN) for d in potential_districts[:3]])}")
        if potential_wards:
            print(f"     └─ Top wards: {', '.join([colorize(w[0], Colors.GREEN_BOLD) for w in potential_wards[:3]])}")
    else:
        print(f"  └─ {colorize('No potentials found', Colors.RED)}")

    # ========== PHASE 3: Generate Candidates (Multi-source enrichment) ==========
    p3 = generate_candidates(p2)
    num_candidates = p3.get('total_candidates', 0)
    sources_used = p3.get('sources_used', [])
    local_count = p3.get('local_candidates_count', 0)
    osm_count = p3.get('osm_candidates_count', 0)

    # Candidate breakdown by source
    candidates_by_source = {}
    for c in p3.get('candidates', []):
        src = c.get('source', 'unknown')
        candidates_by_source[src] = candidates_by_source.get(src, 0) + 1

    # Build breakdown string
    breakdown_parts = [f"{src}:{cnt}" for src, cnt in sorted(candidates_by_source.items(), key=lambda x: x[1], reverse=True)]
    breakdown_str = ", ".join(breakdown_parts) if breakdown_parts else "none"

    # Build single-line summary
    sources_str = ', '.join(sources_used) if sources_used else "none"
    osm_str = f" | OSM:{osm_count}" if osm_count > 0 else ""

    p3_time = p3['processing_time_ms']
    print(f"\n⏱ {colorize(f'{p3_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 3: Generate Candidates (Multi-source)', Colors.BOLD)}")
    print(f"  └─ Local: {colorize(str(local_count), Colors.YELLOW)} | Output: {colorize(str(num_candidates), Colors.GREEN)}{osm_str} | Sources: {colorize(sources_str, Colors.GREEN)} ({breakdown_str})")

    # Display Phase 3 candidates
    p3_candidates = p3.get('candidates', [])
    if p3_candidates:
        for idx, candidate in enumerate(p3_candidates[:10], 1):  # Show top 10
            ward = candidate.get('ward', 'None')
            district = candidate.get('district', 'None')
            province = candidate.get('province', 'None')

            ward_score = candidate.get('ward_score', 0)
            district_score = candidate.get('district_score', 0)
            province_score = candidate.get('province_score', 0)
            confidence = candidate.get('confidence', 0)

            # Format with colors
            conf_colored = colorize(f"[{confidence:.2f}]", score_color(confidence * 100))
            ward_colored = colorize(f"{ward} ({ward_score:.0f})", Colors.GREEN_BOLD)
            district_colored = colorize(f"{district} ({district_score:.0f})", Colors.GREEN)
            province_colored = colorize(f"{province} ({province_score:.0f})", Colors.CYAN)

            print(f"  └─ {idx}. {conf_colored} {ward_colored} | {district_colored} | {province_colored}")

    # ========== PHASE 4: Validation & Ranking ==========
    p4 = validate_and_rank(p3)
    best = p4.get('best_match')
    p4_time = p4['processing_time_ms']
    print(f"\n⏱ {colorize(f'{p4_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 4: Validation & Ranking', Colors.BOLD)}")
    print(f"  └─ Xác thực phân cấp hành chính và xếp hạng candidates")

    # Display Phase 4 validated candidates
    p4_candidates = p4.get('validated_candidates', [])
    if p4_candidates:
        for idx, candidate in enumerate(p4_candidates[:10], 1):  # Show top 10
            ward = candidate.get('ward', 'None')
            district = candidate.get('district', 'None')
            province = candidate.get('province', 'None')

            ward_score = candidate.get('ward_score', 0)
            district_score = candidate.get('district_score', 0)
            province_score = candidate.get('province_score', 0)
            final_confidence = candidate.get('final_confidence', 0)
            source = candidate.get('source', 'unknown')
            hierarchy_valid = candidate.get('hierarchy_valid', False)

            # Format with colors
            conf_colored = colorize(f"[{final_confidence:.2f}]", score_color(final_confidence * 100))
            source_colored = colorize(f"[{source}]", Colors.YELLOW)
            valid_icon = "✓" if hierarchy_valid else "✗"
            valid_colored = colorize(valid_icon, Colors.GREEN if hierarchy_valid else Colors.RED)
            ward_colored = colorize(f"{ward} ({ward_score:.0f})", Colors.GREEN_BOLD)
            district_colored = colorize(f"{district} ({district_score:.0f})", Colors.GREEN)
            province_colored = colorize(f"{province} ({province_score:.0f})", Colors.CYAN)

            print(f"  └─ {idx}. {conf_colored} {source_colored} {valid_colored} {ward_colored} | {district_colored} | {province_colored}")

    if best:
        confidence = best.get('confidence', 0)
        conf_colored = colorize(f"{confidence:.2f}", score_color(confidence * 100))

        # Hiển thị best match chi tiết
        best_province = best.get('province', '')
        best_district = best.get('district', '')
        best_ward = best.get('ward', '')

        print(f"\n  {colorize('BEST MATCH:', Colors.GREEN_BOLD)}")
        if best_ward:
            print(f"  └─ Ward: {colorize(best_ward, Colors.GREEN_BOLD)}")
        if best_district:
            print(f"  └─ District: {colorize(best_district, Colors.GREEN_BOLD)}")
        if best_province:
            print(f"  └─ Province: {colorize(best_province, Colors.GREEN_BOLD)}")

        print(f"  └─ Confidence: {conf_colored}")
        print(f"  └─ Match type: {colorize(best.get('match_type', 'N/A'), Colors.CYAN)}")
    else:
        print(f"  └─ {colorize('❌ Không tìm thấy candidate phù hợp', Colors.RED)}")

    # ========== PHASE 5: Post-processing ==========
    # Pass original address to extract remaining parts
    p5 = postprocess(p4, {
        'original_address': address_text,
        'matched_components': p4.get('best_match', {})
    })
    formatted_output = p5.get('formatted_output', {})
    p5_time = p5['processing_time_ms']
    print(f"\n⏱ {colorize(f'{p5_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 5: Format kết quả cuối', Colors.BOLD)}")
    print(f"  └─ Định dạng địa chỉ đầy đủ và thêm STATE/COUNTY codes")

    # Always display in format: Ward, District, Province (with diacritics)
    # Use ____ if not found
    ward_display = formatted_output.get('ward') or '____'
    district_display = formatted_output.get('district') or '____'
    province_display = formatted_output.get('province') or '____'

    final_address = f"{ward_display}, {district_display}, {province_display}"
    addr_colored = colorize(final_address, Colors.GREEN_BOLD)

    print(f"  └─ Địa chỉ đầy đủ: {addr_colored}")
    print(f"  └─ Chất lượng: {colorize(p5.get('quality_flag', 'N/A'), Colors.YELLOW)}")

    # Hiển thị remaining address (phần còn lại chưa xử lý)
    remaining_1 = formatted_output.get('remaining_1', '')
    remaining_2 = formatted_output.get('remaining_2', '')
    remaining_3 = formatted_output.get('remaining_3', '')

    if remaining_1 or remaining_2 or remaining_3:
        print(f"  └─ Phần còn lại (street, house number):")
        if remaining_1:
            print(f"     └─ Part 1: {colorize(remaining_1, Colors.YELLOW)}")
        if remaining_2:
            print(f"     └─ Part 2: {colorize(remaining_2, Colors.YELLOW)}")
        if remaining_3:
            print(f"     └─ Part 3: {colorize(remaining_3, Colors.YELLOW)}")

    # Hiển thị codes nếu có
    if formatted_output.get('state_code'):
        print(f"  └─ STATE code: {colorize(formatted_output.get('state_code', ''), Colors.CYAN)}")
    if formatted_output.get('county_code'):
        print(f"  └─ COUNTY code: {colorize(formatted_output.get('county_code', ''), Colors.CYAN)}")

    # Tổng thời gian
    total_time = sum([p1['processing_time_ms'], p2['processing_time_ms'], p3['processing_time_ms'],
                      p4['processing_time_ms'], p5['processing_time_ms']])
    print(f"\n{'─'*60}")
    print(f"Tổng thời gian: {colorize(f'{total_time:.1f}ms', Colors.YELLOW)}")
    print(f"{'─'*60}")

    # ========== SUMMARY ==========
    print(f"\n{'='*60}")
    print(colorize("SUMMARY", Colors.BOLD))
    print(f"{'='*60}")

    # Input line
    known_dist_display = district_known if district_known else '____'
    known_prov_display = province_known if province_known else '____'
    input_line = f"{colorize('INPUT:', Colors.BOLD)}  {colorize(address_text, Colors.YELLOW)} | {colorize(known_dist_display, Colors.GREEN)} | {colorize(known_prov_display, Colors.CYAN)}"
    print(input_line)

    # Get all ranked candidates from Phase 4
    ranked_candidates = p4.get('validated_candidates', [])

    if ranked_candidates:
        print(f"\n{colorize('CANDIDATES (ordered by score DESC):', Colors.BOLD)}")

        # Process each candidate to get remaining address
        for idx, candidate in enumerate(ranked_candidates, 1):
            # Get confidence score
            confidence = candidate.get('final_confidence', 0)

            # Extract remaining for this candidate
            cand_province = candidate.get('province', '')
            cand_district = candidate.get('district', '')
            cand_ward = candidate.get('ward', '')

            # Calculate remaining for this candidate
            from src.processors.phase5_postprocessing import extract_remaining_address
            cand_remaining = extract_remaining_address(address_text, {
                'province': cand_province,
                'district': cand_district,
                'ward': cand_ward
            })

            # Format remaining (uppercase, no diacritics, truncate to 40 chars)
            from src.processors.phase5_postprocessing import remove_diacritics_and_uppercase
            cand_remaining_formatted = remove_diacritics_and_uppercase(cand_remaining)[:40] if cand_remaining else '____'

            # Get full names with diacritics (ALREADY populated by Phase 3)
            # No DB lookups needed - use pre-populated values
            from src.processors.phase5_postprocessing import _extract_name_from_full

            province_full = candidate.get('province_full', '')
            district_full = candidate.get('district_full', '')
            ward_full = candidate.get('ward_full', '')

            # Extract names without administrative prefixes
            province_display = _extract_name_from_full(province_full) if province_full else (cand_province.capitalize() if cand_province else '____')
            district_display = _extract_name_from_full(district_full) if district_full else (cand_district.capitalize() if cand_district else '____')
            ward_display = _extract_name_from_full(ward_full) if ward_full else (cand_ward.capitalize() if cand_ward else '____')

            # Get source and add color label
            source = candidate.get('source', 'unknown')
            if 'osm_nominatim_bbox' in source:
                src_label = colorize("[OSM-B]", Colors.YELLOW)  # OSM with bbox
            elif 'osm_nominatim_query' in source:
                src_label = colorize("[OSM-Q]", Colors.YELLOW_BOLD)  # OSM with province in query
            elif 'osm' in source:
                src_label = colorize("[OSM]", Colors.YELLOW)
            elif 'disambiguation' in source:
                src_label = colorize("[DIS]", Colors.CYAN)
            else:
                src_label = colorize("[LOC]", Colors.GREEN)

            # Print candidate line with colors
            score_colored = colorize(f"[{confidence:.2f}]", score_color(confidence * 100))
            remaining_colored = colorize(cand_remaining_formatted, Colors.YELLOW)
            ward_colored = colorize(ward_display, Colors.GREEN_BOLD)
            district_colored = colorize(district_display, Colors.GREEN)
            province_colored = colorize(province_display, Colors.CYAN)

            print(f"  └─ {idx}. {score_colored} {src_label} {remaining_colored} | {ward_colored} | {district_colored} | {province_colored}")

            # Show interpretation if available
            interpretation = candidate.get('interpretation')
            if interpretation:
                print(f"       └─ {colorize(interpretation, Colors.YELLOW)}")
    else:
        print(f"\nNo candidates found")

    print(f"{'='*60}\n")

    return {'phase1': p1, 'phase2': p2, 'phase3': p3, 'phase4': p4, 'phase5': p5}


def main():
    """Hàm chính"""
    parser = argparse.ArgumentParser(description='Demo xử lý địa chỉ')
    parser.add_argument('-a', '--address', type=str, help='Địa chỉ cần xử lý')
    parser.add_argument('-p', '--province', type=str, help='Gợi ý tỉnh')
    parser.add_argument('-d', '--district', type=str, help='Gợi ý huyện')
    parser.add_argument('-l', '--limit', type=int, default=3, help='Số mẫu từ DB (mặc định: 3)')
    parser.add_argument('-o', '--offset', type=int, default=0, help='Vị trí bắt đầu (mặc định: 0)')

    args = parser.parse_args()

    # CHẾ ĐỘ 1: Xử lý 1 địa chỉ
    if args.address:
        print(f"\n{'='*60}")
        print(colorize("📍 CHẾ ĐỘ: Xử lý địa chỉ đơn lẻ", Colors.CYAN_BOLD))
        print(f"{'='*60}")
        result = process_one_address(args.address, args.province, args.district)
        print(f"\n{colorize('✅ Hoàn thành!', Colors.GREEN_BOLD)}\n")

    # CHẾ ĐỘ 2: Xử lý từ database
    else:
        print(f"\n{'='*60}")
        print(colorize(f"CHẾ ĐỘ: Xử lý batch từ database", Colors.CYAN_BOLD))
        print(f"{'='*60}")

        samples = load_samples(args.limit, args.offset)

        if not samples:
            print(colorize("❌ Không tìm thấy mẫu nào!", Colors.RED))
            return

        print(f"✅ Đã tải {len(samples)} bản ghi\n")

        for i, sample in enumerate(samples, 1):
            cif = sample['cif_no']
            print(f"{colorize(f'MẪU {i}/{len(samples)} - CIF: {cif}', Colors.CYAN_BOLD)}")

            result = process_one_address(
                sample['dia_chi_thuong_tru'],
                sample.get('ten_tinh_thuong_tru'),
                sample.get('ten_quan_huyen_thuong_tru')
            )

            if i < len(samples):
                input(f"\n{colorize('▶ Nhấn Enter để tiếp tục...', Colors.YELLOW)}")

        print(f"\n{colorize('✅ Đã xử lý xong tất cả mẫu!', Colors.GREEN_BOLD)}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{colorize('⚠️ Đã dừng bởi người dùng', Colors.YELLOW)}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{colorize(f'❌ Lỗi: {e}', Colors.RED)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
