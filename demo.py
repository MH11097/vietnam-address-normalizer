"""
ADDRESS PARSING PIPELINE - DEMO
================================
Usage:
    # Single address mode
    python demo.py --address "NGO394 DOI CAN P.CONG VI BD HN"
    python demo.py --address "NGO394 DOI CAN P.CONG VI BD HN" --province "Hà Nội"

    # Batch mode (random sampling from DB, chỉ lấy chưa rated)
    python demo.py --limit 5
    python demo.py --limit 10 --auto

    # Reprocess mode (chạy lại records đã rated, UPDATE với rating mới)
    python demo.py --reprocess 0,2,3 --limit 10
    python demo.py --reprocess 3 --limit 5 --auto  # auto: set rating=0

Note: Debug mode is always enabled. Random sampling is always on.
"""
import sys
import argparse
import logging
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess
from src.utils.db_utils import query_all, save_user_rating
from src.utils.text_utils import normalize_hint
from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative
from src.utils.extraction_utils import lookup_full_names


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


# Cấu hình logging - chỉ hiển thị WARNING và ERROR (hoặc DEBUG nếu có flag)
def setup_logging(debug=False):
    """
    Thiết lập logging gọn gàng
    - Ẩn tất cả INFO log từ modules con (phase1-5, utils)
    - Chỉ hiển thị WARNING và ERROR (hoặc DEBUG nếu debug=True)
    """
    # Configure root logger
    root_logger = logging.getLogger()

    if debug:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.WARNING)

    # Xóa handlers cũ nếu có
    if root_logger.handlers:
        root_logger.handlers.clear()

    handler = logging.StreamHandler()
    if debug:
        handler.setFormatter(logging.Formatter('%(message)s'))  # Simple format for debug
        handler.setLevel(logging.DEBUG)
    else:
        handler.setFormatter(ColoredFormatter('%(levelname)s - %(message)s'))
        handler.setLevel(logging.WARNING)
    root_logger.addHandler(handler)

# Gọi setup (sẽ được gọi lại với debug flag trong main)
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


def load_samples(limit=3, offset=0, random=False):
    """
    Load sample addresses từ database (chỉ lấy records chưa xử lý)

    Args:
        limit: Số lượng records cần lấy
        offset: Vị trí bắt đầu
        random: Random order hay sequential

    Returns:
        List of address records (chỉ những records chưa có trong user_quality_ratings)
    """
    order_clause = "ORDER BY RANDOM()" if random else ""

    # Luôn luôn bỏ qua các records đã có trong user_quality_ratings
    query = f"""
    SELECT r.cif_no, r.dia_chi_thuong_tru,
           r.ten_tinh_thuong_tru, r.ten_quan_huyen_thuong_tru
    FROM raw_addresses r
    WHERE r.dia_chi_thuong_tru IS NOT NULL
      AND r.dia_chi_thuong_tru != ''
      AND NOT EXISTS (
          SELECT 1 FROM user_quality_ratings u
          WHERE u.original_address = r.dia_chi_thuong_tru
            AND COALESCE(u.known_province, '') = COALESCE(r.ten_tinh_thuong_tru, '')
            AND COALESCE(u.known_district, '') = COALESCE(r.ten_quan_huyen_thuong_tru, '')
      )
    {order_clause}
    LIMIT ? OFFSET ?
    """

    return query_all(query, (limit, offset))


def load_rated_samples(ratings, limit=3):
    """
    Load addresses từ user_quality_ratings với user_rating cụ thể (để reprocess)

    Args:
        ratings: List of user_rating values to filter (e.g., [0, 2, 3])
        limit: Số lượng records cần lấy

    Returns:
        List of address records từ user_quality_ratings với format:
        {
            'cif_no': ...,
            'dia_chi_thuong_tru': original_address,
            'ten_tinh_thuong_tru': known_province,
            'ten_quan_huyen_thuong_tru': known_district,
            'record_id': id (for UPDATE later)
        }
    """
    # Build placeholders for IN clause
    placeholders = ','.join(['?' for _ in ratings])

    query = f"""
    SELECT id, cif_no, original_address, known_province, known_district
    FROM user_quality_ratings
    WHERE user_rating IN ({placeholders})
    ORDER BY RANDOM()
    LIMIT ?
    """

    params = tuple(ratings) + (limit,)
    results = query_all(query, params)

    # Map to same format as load_samples() for compatibility
    mapped_results = []
    for row in results:
        mapped_results.append({
            'record_id': row['id'],  # Keep ID for UPDATE
            'cif_no': row['cif_no'],
            'dia_chi_thuong_tru': row['original_address'],
            'ten_tinh_thuong_tru': row['known_province'] if row['known_province'] else None,
            'ten_quan_huyen_thuong_tru': row['known_district'] if row['known_district'] else None
        })

    return mapped_results


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

    print(f"📥 Địa chỉ: {address_colored}, Huyện={dist_colored}, Tỉnh={prov_colored}")

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

    # ========== PHASE 2: Structural Parsing (NEW) ==========
    # Try to parse using separators and keywords first
    province_normalized = normalize_hint(province_known) if province_known else None
    district_normalized = normalize_hint(district_known) if district_known else None

    structural_result = structural_parse(
        p1['normalized'],
        province_known=province_normalized,
        district_known=district_normalized
    )

    structural_confidence = structural_result['confidence']
    structural_time = structural_result['processing_time_ms']

    print(f"\n⏱ {colorize(f'{structural_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 2: Structural Parsing', Colors.BOLD)}")
    confidence_str = f"{structural_confidence:.2f}"
    print(f"  └─ Method: {colorize(structural_result['method'], Colors.CYAN)} | Confidence: {colorize(confidence_str, score_color(structural_confidence * 100))}")

    if structural_confidence >= 0.85:
        print(f"  └─ {colorize('✓ High confidence structural parsing - using result', Colors.GREEN)}")
        if structural_result.get('ward'):
            print(f"     └─ Ward: {colorize(structural_result['ward'], Colors.GREEN_BOLD)}")
        if structural_result.get('district'):
            print(f"     └─ District: {colorize(structural_result['district'], Colors.GREEN)}")
        if structural_result.get('province'):
            print(f"     └─ Province: {colorize(structural_result['province'], Colors.CYAN)}")
    else:
        print(f"  └─ {colorize('⚠ Low confidence - will fallback to n-gram extraction', Colors.YELLOW)}")

    # ========== PHASE 3: Trích xuất (Extract Potentials) ==========
    # Decision: Use structural or n-gram?
    if structural_confidence >= 0.85:
        # Build phase3-like result from structural parsing
        province = structural_result.get('province')
        district = structural_result.get('district')
        ward = structural_result.get('ward')

        province_full, district_full, ward_full = lookup_full_names(province, district, ward)

        # Build candidate from structural result
        # Only create candidate if DB lookup succeeded
        candidate = None
        if province_full and (not district or district_full) and (not ward or ward_full):
            match_level = sum([1 if province else 0, 1 if district else 0, 1 if ward else 0])
            candidate = {
                'ward': ward,
                'district': district,
                'province': province,
                'ward_full': ward_full,
                'district_full': district_full,
                'province_full': province_full,
                'ward_score': 95 if ward else 0,
                'district_score': 95 if district else 0,
                'province_score': 100 if province else 0,
                'confidence': structural_confidence,
                'source': f"structural_{structural_result['method']}",
                'hierarchy_valid': True,
                'match_level': match_level,
                'at_rule': match_level,
                'match_type': 'exact',
                'final_confidence': structural_confidence
            }

        p2 = {
            'candidates': [candidate] if candidate else [],
            'potential_provinces': [(province, 1.0, (-1, -1))] if province else [],
            'potential_districts': [(district, 1.0, (-1, -1))] if district else [],
            'potential_wards': [(ward, 1.0, (-1, -1))] if ward else [],
            'potential_streets': [],
            'processing_time_ms': 0,  # Already counted in structural_time
            'source': 'structural',
            'normalized_text': p1.get('normalized', ''),
            'geographic_known_used': province is not None,
            'original_address': address_text,
            'province': province,
            'district': district,
            'ward': ward,
            'province_score': 100 if province else 0,
            'district_score': 95 if district else 0,
            'ward_score': 95 if ward else 0
        }

        print(f"\n⏱ {colorize(f'  0.0ms', Colors.YELLOW)} | {colorize('Phase 3: Skipped (using structural result)', Colors.BOLD)}")
    else:
        # Fallback to n-gram extraction
        p2 = extract_components(p1, province_known, district_known)
        p2_time = p2['processing_time_ms']
        print(f"\n⏱ {colorize(f'{p2_time:5.1f}ms', Colors.YELLOW)} | {colorize('Phase 3: N-gram Extraction', Colors.BOLD)}")

        # Explain the algorithm (only for n-gram extraction)
        print(f"  └─ {colorize('Thuật toán:', Colors.BOLD)} Hierarchical Scoped Search (tìm kiếm phân cấp)")
        print(f"     ├─ Bước 1: Tạo N-grams từ văn bản (1-gram → 4-gram)")
        print(f"     ├─ Bước 2: Match với 9,991 xã/phường trong database")
        print(f"     ├─ Bước 3: Tính điểm dựa trên: vị trí, độ dài, fuzzy similarity")
        print(f"     └─ Bước 4: Lọc và xếp hạng theo confidence score")

        # Show N-gram generation stats
        normalized = p1.get('normalized', '')
        tokens = normalized.split()
        total_ngrams = sum(max(0, len(tokens) - n + 1) for n in range(1, min(5, len(tokens) + 1)))
        print(f"\n  {colorize('N-gram Generation:', Colors.BOLD)}")
        print(f"     ├─ Số tokens: {colorize(str(len(tokens)), Colors.CYAN)}")
        print(f"     ├─ Tổng n-grams sinh ra: {colorize(str(total_ngrams), Colors.YELLOW)} (1-4 grams)")
        print(f"     └─ {colorize(' '.join([f'[{t}]' for t in tokens]), Colors.GREEN)}")

    # Show known values first (if provided)
    if province_known or district_known:
        print(f"\n  {colorize('Known Values (Trusted 100%):', Colors.BOLD)}")
        if province_known:
            print(f"     └─ Province: {colorize(province_known, Colors.CYAN_BOLD)} (từ dữ liệu gốc)")
        if district_known:
            print(f"     └─ District: {colorize(district_known, Colors.GREEN_BOLD)} (từ dữ liệu gốc)")

    # Show number of potentials extracted (NEW structure - no candidates yet)
    potential_provinces = p2.get('potential_provinces', [])
    potential_districts = p2.get('potential_districts', [])
    potential_wards = p2.get('potential_wards', [])
    potential_streets = p2.get('potential_streets', [])

    total_potentials = len(potential_provinces) + len(potential_districts) + len(potential_wards) + len(potential_streets)

    # Show detailed potentials for each level
    print(f"\n  {colorize('Potentials Extracted:', Colors.BOLD)} (tổng {colorize(str(total_potentials), Colors.YELLOW)})")

    if potential_provinces:
        print(f"\n     {colorize('Provinces:', Colors.CYAN_BOLD)} ({len(potential_provinces)} found)")
        for idx, (name, score, pos) in enumerate(potential_provinces[:5], 1):
            # Explain score
            score_pct = score * 100
            pos_str = f"pos:{pos[0]}-{pos[1]}" if pos != (-1, -1) else "known"
            score_colored = colorize(f"{score:.3f}", score_color(score_pct))
            print(f"       {idx}. {colorize(name, Colors.CYAN)} | score:{score_colored} | {pos_str}")
            # Add explanation for first one
            if idx == 1:
                if score >= 1.0:
                    print(f"          └─ {colorize('Exact match hoặc known value', Colors.GREEN)}")
                elif score >= 0.95:
                    print(f"          └─ {colorize('Very high similarity (vị trí cuối văn bản)', Colors.GREEN)}")
                else:
                    print(f"          └─ {colorize(f'Fuzzy match {score_pct:.0f}%', Colors.YELLOW)}")

    if potential_districts:
        print(f"\n     {colorize('Districts:', Colors.GREEN_BOLD)} ({len(potential_districts)} found)")
        for idx, (name, score, pos) in enumerate(potential_districts[:5], 1):
            score_pct = score * 100
            pos_str = f"pos:{pos[0]}-{pos[1]}" if pos != (-1, -1) else "known"
            score_colored = colorize(f"{score:.3f}", score_color(score_pct))

            # Check if from abbreviation
            original_text = address_text.upper()
            normalized_lower = p1.get('normalized', '').lower()
            abbr_note = ""
            if 'DHA' in original_text and name == 'dong ha':
                abbr_note = f" {colorize('[DHA→dong ha]', Colors.YELLOW)}"
            elif 'TX' in original_text and 'tan' in name:
                abbr_note = f" {colorize('[TX expansion]', Colors.YELLOW)}"

            print(f"       {idx}. {colorize(name, Colors.GREEN)} | score:{score_colored} | {pos_str}{abbr_note}")
            if idx == 1:
                if score >= 1.0:
                    print(f"          └─ {colorize('Exact match từ pattern hoặc abbreviation', Colors.GREEN)}")
                elif score >= 0.90:
                    print(f"          └─ {colorize('High confidence (scoped to province)', Colors.GREEN)}")
                else:
                    print(f"          └─ {colorize(f'Fuzzy match trong phạm vi province', Colors.YELLOW)}")

    if potential_wards:
        print(f"\n     {colorize('Wards:', Colors.GREEN_BOLD)} ({len(potential_wards)} found)")
        for idx, (name, score, pos) in enumerate(potential_wards[:5], 1):
            score_pct = score * 100
            pos_str = f"pos:{pos[0]}-{pos[1]}" if pos != (-1, -1) else "inferred"
            score_colored = colorize(f"{score:.3f}", score_color(score_pct))

            # Check if from pattern extraction
            pattern_note = ""
            normalized_lower = p1.get('normalized', '').lower()
            if name.isdigit() and f'phuong {name}' in normalized_lower:
                pattern_note = f" {colorize('[PHUONG pattern]', Colors.YELLOW)}"
            elif name.isdigit() and f'p {name}' in normalized_lower:
                pattern_note = f" {colorize('[P. pattern]', Colors.YELLOW)}"

            print(f"       {idx}. {colorize(name, Colors.GREEN_BOLD)} | score:{score_colored} | {pos_str}{pattern_note}")
            if idx == 1:
                if score >= 1.0:
                    print(f"          └─ {colorize('Exact match từ explicit pattern (PHUONG X, P.X)', Colors.GREEN)}")
                elif score >= 0.95:
                    print(f"          └─ {colorize('Very high match (scoped to district)', Colors.GREEN)}")
                else:
                    print(f"          └─ {colorize(f'Fuzzy match trong district/province', Colors.YELLOW)}")

    if potential_streets:
        print(f"\n     {colorize('Streets:', Colors.YELLOW)} ({len(potential_streets)} found - dùng để fallback)")
        for idx, (name, score, pos) in enumerate(potential_streets[:3], 1):
            score_colored = colorize(f"{score:.3f}", score_color(score * 100))
            print(f"       {idx}. {name} | score:{score_colored}")

    if total_potentials == 0:
        if not province_known and not district_known:
            print(f"     └─ {colorize('⚠ Không tìm thấy potentials nào', Colors.RED)}")
        else:
            print(f"     └─ Không trích xuất thêm từ văn bản (dùng known values)")

    # Show hierarchical search path with detailed explanation
    print(f"\n  {colorize('Search Path (Best Match):', Colors.BOLD)}")
    print(f"     {colorize('Giải thích:', Colors.YELLOW)} Tìm kiếm phân cấp Province → District → Ward")
    print(f"     {colorize('Mỗi level thu hẹp phạm vi tìm kiếm cho level tiếp theo', Colors.YELLOW)}")

    # Step 1: Province
    print(f"\n     {colorize('1. Province:', Colors.BOLD)}")
    if province_known:
        print(f"        └─ {colorize(province_known, Colors.CYAN_BOLD)} {colorize('[KNOWN]', Colors.GREEN)}")
        print(f"           └─ Từ dữ liệu gốc (trusted 100%)")
    elif potential_provinces:
        p_name, p_score, p_pos = potential_provinces[0]
        score_colored = colorize(f"[{p_score:.3f}]", score_color(p_score * 100))
        print(f"        └─ {colorize(p_name, Colors.CYAN_BOLD)} {score_colored}")
        if p_score >= 1.0:
            print(f"           └─ Exact match ở cuối văn bản (vị trí điển hình)")
        elif p_score >= 0.95:
            print(f"           └─ Very high similarity (rightmost tokens)")
        else:
            print(f"           └─ Fuzzy match với confidence {p_score*100:.0f}%")
    else:
        print(f"        └─ {colorize('not found', Colors.RED)}")
        print(f"           └─ Không tìm thấy province trong văn bản")

    # Step 2: District
    print(f"\n     {colorize('2. District:', Colors.BOLD)} {colorize('(scoped to province)', Colors.YELLOW)}")
    if district_known:
        print(f"        └─ {colorize(district_known, Colors.GREEN_BOLD)} {colorize('[KNOWN]', Colors.GREEN)}")
        print(f"           └─ Từ dữ liệu gốc (trusted 100%)")
    elif potential_districts:
        d_name, d_score, d_pos = potential_districts[0]
        score_colored = colorize(f"[{d_score:.3f}]", score_color(d_score * 100))

        # Check if from abbreviation expansion
        abbr_note = ""
        abbr_explanation = ""
        original_text = address_text.upper()
        normalized_lower = p1.get('normalized', '').lower()


        print(f"        └─ {colorize(d_name, Colors.GREEN_BOLD)} {score_colored}{abbr_note}")
        if d_score >= 1.0:
            print(f"           └─ Exact match hoặc từ abbreviation expansion")
        elif d_score >= 0.90:
            print(f"           └─ High confidence match trong scope của province")
        else:
            print(f"           └─ Fuzzy match {d_score*100:.0f}% trong districts của province")
        if abbr_explanation:
            print(abbr_explanation)
    else:
        print(f"        └─ {colorize('not found', Colors.RED)}")
        print(f"           └─ Không tìm thấy district trong văn bản")

    # Step 3: Ward
    print(f"\n     {colorize('3. Ward:', Colors.BOLD)} {colorize('(scoped to district)', Colors.YELLOW)}")
    if potential_wards:
        w_name, w_score, w_pos = potential_wards[0]
        score_colored = colorize(f"[{w_score:.3f}]", score_color(w_score * 100))

        # Check if from pattern extraction
        pattern_note = ""
        pattern_explanation = ""
        normalized_lower = p1.get('normalized', '').lower()
        if w_name.isdigit() and f'phuong {w_name}' in normalized_lower:
            pattern_note = colorize(f" [PHUONG {w_name}→{w_name}]", Colors.YELLOW)
            pattern_explanation = f"\n           └─ Trích xuất từ pattern 'PHUONG {w_name}' (explicit pattern)"
        elif w_name.isdigit() and f'p {w_name}' in normalized_lower:
            pattern_note = colorize(f" [P.{w_name}→{w_name}]", Colors.YELLOW)
            pattern_explanation = f"\n           └─ Trích xuất từ pattern 'P.{w_name}' (abbreviated pattern)"

        print(f"        └─ {colorize(w_name, Colors.GREEN_BOLD)} {score_colored}{pattern_note}")
        if w_score >= 1.0:
            print(f"           └─ Exact match từ explicit pattern (PHUONG X, P.X, XA X)")
        elif w_score >= 0.95:
            print(f"           └─ Very high match trong wards của district")
        else:
            print(f"           └─ Fuzzy match {w_score*100:.0f}% trong scope của district")
        if pattern_explanation:
            print(pattern_explanation)
    else:
        print(f"        └─ {colorize('not found', Colors.RED)}")
        print(f"           └─ Không tìm thấy ward (có thể chỉ có province+district)")

    # Show scoring formula explanation
    print(f"\n  {colorize('Score Calculation:', Colors.BOLD)}")
    print(f"     ├─ {colorize('Fuzzy Similarity:', Colors.YELLOW)} So sánh chuỗi (ensemble_fuzzy_score)")
    print(f"     ├─ {colorize('Position Bonus:', Colors.YELLOW)} Càng gần vị trí điển hình càng cao điểm")
    print(f"     ├─ {colorize('Length Bonus:', Colors.YELLOW)} N-gram dài hơn (specific) → điểm cao hơn")
    print(f"     └─ {colorize('Final Score:', Colors.YELLOW)} Weighted combination of above factors")

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

            # Calculate remaining for this candidate using token positions
            from src.processors.phase6_postprocessing import extract_remaining_address
            normalized_tokens = candidate.get('normalized_tokens', [])
            if normalized_tokens:
                token_positions = {
                    'province': candidate.get('province_tokens', (-1, -1)),
                    'district': candidate.get('district_tokens', (-1, -1)),
                    'ward': candidate.get('ward_tokens', (-1, -1))
                }
                cand_remaining = extract_remaining_address(normalized_tokens, token_positions)
            else:
                cand_remaining = ''

            # Format remaining (uppercase, no diacritics, truncate to 40 chars)
            from src.processors.phase6_postprocessing import remove_diacritics_and_uppercase
            cand_remaining_formatted = remove_diacritics_and_uppercase(cand_remaining)[:40] if cand_remaining else '____'

            # Get full names with diacritics (ALREADY populated by Phase 3)
            # No DB lookups needed - use pre-populated values
            from src.processors.phase6_postprocessing import _capitalize_full_name

            province_full = candidate.get('province_full', '')
            district_full = candidate.get('district_full', '')
            ward_full = candidate.get('ward_full', '')

            # Capitalize full names with administrative prefixes
            province_display = _capitalize_full_name(province_full) if province_full else (cand_province.capitalize() if cand_province else '____')
            district_display = _capitalize_full_name(district_full) if district_full else (cand_district.capitalize() if cand_district else '____')
            ward_display = _capitalize_full_name(ward_full) if ward_full else (cand_ward.capitalize() if cand_ward else '____')

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

    return {
        'phase1': p1,
        'phase2_structural': structural_result,
        'phase3_extraction': p2,
        'phase4_candidates': p3,
        'phase5_validation': p4,
        'phase6_postprocessing': p5
    }


def normalize_ground_truth(value):
    """
    Normalize ground truth value from database.

    Handles special cases:
    - "/" → None (unknown/missing in DB)
    - "" → None (empty)
    - Valid string → normalized (using normalize_hint)

    Args:
        value: Raw value from database

    Returns:
        Normalized string or None

    Example:
        >>> normalize_ground_truth("/")
        None
        >>> normalize_ground_truth("HA NOI")
        "ha noi"
    """
    if not value or value == '/':
        return None
    return normalize_hint(value)


def batch_test_with_accuracy(limit=100, offset=0, random_sample=True, test_mode='assisted'):
    """
    Batch test with accuracy metrics.

    Tests N addresses and compares results with ground truth (province/district hints).

    Args:
        limit: Number of addresses to test (default: 100)
        offset: Starting offset in database (default: 0)
        random_sample: Whether to use random sampling (default: True)
        test_mode: 'blind' (no hints) or 'assisted' (with hints like production)

    Returns:
        dict with accuracy metrics
    """
    print(f"\n{'='*80}")
    print(colorize(f"🧪 BATCH ACCURACY TEST - {limit} Addresses", Colors.CYAN_BOLD))
    print(f"{'='*80}\n")

    # Load samples from database
    samples = load_samples(limit, offset, random_sample)

    if not samples:
        print(colorize("❌ No samples found!", Colors.RED))
        return None

    print(f"✅ Loaded {len(samples)} records\n")
    print(f"Test Mode: {colorize(test_mode.upper(), Colors.CYAN_BOLD)}")
    print("Processing...\n")

    # Metrics
    correct_province = 0
    correct_district = 0
    correct_full = 0  # Both province and district correct
    total_confidence = 0.0
    total_proximity = 0.0
    total_processing_time = 0.0

    # Ground truth availability counters
    province_gt_count = 0
    district_gt_count = 0

    results = []

    for i, sample in enumerate(samples, 1):
        raw_address = sample['dia_chi_thuong_tru']

        # Normalize ground truth (/ → None)
        ground_truth_province = normalize_ground_truth(sample.get('ten_tinh_thuong_tru'))
        ground_truth_district = normalize_ground_truth(sample.get('ten_quan_huyen_thuong_tru'))

        # Count ground truth availability
        if ground_truth_province:
            province_gt_count += 1
        if ground_truth_district:
            district_gt_count += 1

        # Process address based on test mode
        if test_mode == 'blind':
            # Blind extraction (no hints - pure extraction test)
            p1 = preprocess(raw_address, province_known=None)
            p2 = extract_components(p1, province_known=None, district_known=None)
        else:  # assisted
            # Assisted extraction (with hints - production mode)
            p1 = preprocess(raw_address, province_known=ground_truth_province)
            p2 = extract_components(p1, province_known=ground_truth_province, district_known=ground_truth_district)

        p3 = generate_candidates(p2)
        p4 = validate_and_rank(p3)

        best = p4.get('best_match') if p4 else None
        extracted_province = best.get('province', '') if best else ''
        extracted_district = best.get('district', '') if best else ''
        extracted_ward = best.get('ward', '') if best else ''
        confidence = best.get('confidence', 0.0) if best else 0.0
        proximity_score = best.get('proximity_score', 0.0) if best else 0.0
        processing_time = (
            p1.get('processing_time_ms', 0) +
            p2.get('processing_time_ms', 0) +
            p3.get('processing_time_ms', 0) +
            p4.get('processing_time_ms', 0)
        )

        # Compare with ground truth (only if ground truth exists!)
        province_match = None
        if ground_truth_province:
            province_match = (extracted_province == ground_truth_province)
            if province_match:
                correct_province += 1

        district_match = None
        if ground_truth_district:
            district_match = (extracted_district == ground_truth_district)
            if district_match:
                correct_district += 1

        # Full match: both correct (only count if both GT available)
        if ground_truth_province and ground_truth_district:
            if province_match and district_match:
                correct_full += 1

        total_confidence += confidence
        total_proximity += proximity_score
        total_processing_time += processing_time

        results.append({
            'address': raw_address[:60] + '...' if len(raw_address) > 60 else raw_address,
            'province_match': province_match,
            'district_match': district_match,
            'confidence': confidence,
            'proximity': proximity_score
        })

        # Progress indicator
        if i % 10 == 0:
            print(f"  Processed {i}/{len(samples)}...")

    # Calculate metrics (based on available ground truth!)
    total = len(samples)
    province_accuracy = (correct_province / province_gt_count * 100) if province_gt_count > 0 else 0
    district_accuracy = (correct_district / district_gt_count * 100) if district_gt_count > 0 else 0

    # Full accuracy: count records with both GT available
    full_gt_count = sum(1 for s in samples
                       if normalize_ground_truth(s.get('ten_tinh_thuong_tru'))
                       and normalize_ground_truth(s.get('ten_quan_huyen_thuong_tru')))
    full_accuracy = (correct_full / full_gt_count * 100) if full_gt_count > 0 else 0

    avg_confidence = total_confidence / total if total > 0 else 0
    avg_proximity = total_proximity / total if total > 0 else 0
    avg_time = total_processing_time / total if total > 0 else 0

    # Print results
    print(f"\n{'='*80}")
    print(colorize("📊 GROUND TRUTH QUALITY", Colors.CYAN_BOLD))
    print(f"{'='*80}\n")

    print(f"Total Samples:           {total}")
    print(f"Province GT Available:   {province_gt_count}/{total} ({province_gt_count/total*100:.1f}%)")
    print(f"District GT Available:   {district_gt_count}/{total} ({district_gt_count/total*100:.1f}%)")
    print(f"Both GT Available:       {full_gt_count}/{total} ({full_gt_count/total*100:.1f}%)")
    print(f"Test Mode:               {colorize(test_mode.upper(), Colors.CYAN_BOLD)}")

    print(f"\n{'='*80}")
    print(colorize("📊 ACCURACY METRICS", Colors.GREEN_BOLD))
    print(f"{'='*80}\n")

    print(f"Province Accuracy:   {colorize(f'{province_accuracy:.1f}%', Colors.GREEN if province_accuracy >= 90 else Colors.YELLOW)} ({correct_province}/{province_gt_count})")
    print(f"District Accuracy:   {colorize(f'{district_accuracy:.1f}%', Colors.GREEN if district_accuracy >= 80 else Colors.YELLOW)} ({correct_district}/{district_gt_count})")
    print(f"Full Match Accuracy: {colorize(f'{full_accuracy:.1f}%', Colors.GREEN if full_accuracy >= 75 else Colors.YELLOW)} ({correct_full}/{full_gt_count})")
    print()
    print(f"Avg Confidence Score:  {avg_confidence:.3f}")
    print(f"Avg Proximity Score:   {avg_proximity:.3f}")
    print(f"Avg Processing Time:   {avg_time:.1f} ms/address")
    print(f"\n{'='*80}\n")

    # Show some failed cases
    failed = [r for r in results if r['province_match'] == False or r['district_match'] == False]
    if failed and len(failed) <= 10:
        print(colorize("❌ Failed Cases:", Colors.YELLOW_BOLD))
        for r in failed[:10]:
            prov_icon = "✓" if r['province_match'] else "✗"
            dist_icon = "✓" if r['district_match'] else "✗"
            print(f"  {prov_icon}{dist_icon} {r['address']}")
        print()

    return {
        'province_accuracy': province_accuracy,
        'district_accuracy': district_accuracy,
        'full_accuracy': full_accuracy,
        'avg_confidence': avg_confidence,
        'avg_proximity': avg_proximity,
        'avg_processing_time': avg_time
    }


def debug_failed_extractions(limit=100, show_first=10):
    """
    Debug failed province extractions in BLIND mode.
    Shows detailed trace for first N failed cases.
    """
    from src.utils.db_utils import get_province_set

    print(f"\n{'='*80}")
    print(colorize("🔍 DEBUG: Failed Province Extractions (BLIND Mode)", Colors.CYAN_BOLD))
    print(f"{'='*80}\n")

    samples = load_samples(limit, random_sample=True)
    failed_cases = []

    for sample in samples:
        raw = sample['dia_chi_thuong_tru']
        gt_province = normalize_ground_truth(sample.get('ten_tinh_thuong_tru'))

        if not gt_province:
            continue

        # BLIND extraction
        p1 = preprocess(raw, province_known=None)
        p2 = extract_components(p1, province_known=None, district_known=None)
        p3 = generate_candidates(p2)
        p4 = validate_and_rank(p3)

        best = p4.get('best_match') if p4 else None
        extracted = best.get('province') if best else None

        # Failed?
        if extracted != gt_province:
            failed_cases.append({
                'raw': raw,
                'normalized': p1.get('normalized'),
                'gt_province': gt_province,
                'extracted_province': extracted,
                'candidates': p3.get('candidates', []),
                'potentials': p2.get('potential_provinces', [])
            })

    print(f"Total Failed: {len(failed_cases)}/{len([s for s in samples if normalize_ground_truth(s.get('ten_tinh_thuong_tru'))])}\n")

    # Show first N cases
    province_set = get_province_set()

    for i, case in enumerate(failed_cases[:show_first], 1):
        print(f"\n{colorize(f'--- CASE #{i} ---', Colors.YELLOW_BOLD)}")
        print(f"Raw:        {case['raw'][:70]}...")
        print(f"Normalized: {case['normalized'][:70]}...")
        print(f"GT:         {colorize(case['gt_province'], Colors.GREEN)}")
        print(f"Extracted:  {colorize(case['extracted_province'] or 'None', Colors.RED)}")

        # Check if GT in normalized text
        gt_in_text = case['gt_province'] in case['normalized']
        print(f"GT in text: {colorize('✓ YES', Colors.GREEN) if gt_in_text else colorize('✗ NO (incomplete)', Colors.RED)}")

        # Check if GT in province set
        gt_in_set = case['gt_province'] in province_set
        print(f"GT in DB:   {colorize('✓ YES', Colors.GREEN) if gt_in_set else colorize('✗ NO (format mismatch)', Colors.RED)}")

        # Potentials found
        print(f"\nPotentials Found ({len(case['potentials'])}):")
        if case['potentials']:
            for name, score, pos in case['potentials'][:3]:
                print(f"  - {name:20s} score: {score:.3f} pos: {pos}")
        else:
            print(f"  {colorize('(none)', Colors.RED)}")

        # Candidates
        print(f"\nCandidates ({len(case['candidates'])}):")
        if case['candidates']:
            for j, cand in enumerate(case['candidates'][:2], 1):
                print(f"  {j}. {cand.get('province', 'None'):20s} score: {cand.get('combined_score', 0):.3f}")
        else:
            print(f"  {colorize('(none)', Colors.RED)}")

    # Categorize
    print(f"\n{'='*80}")
    print(colorize("📊 FAILURE CATEGORIES", Colors.CYAN_BOLD))
    print(f"{'='*80}\n")

    not_in_text = sum(1 for c in failed_cases if c['gt_province'] not in c['normalized'])
    not_in_set = sum(1 for c in failed_cases if c['gt_province'] not in province_set)
    no_potentials = sum(1 for c in failed_cases if not c['potentials'])
    wrong_extracted = sum(1 for c in failed_cases if c['extracted_province'] and c['extracted_province'] != c['gt_province'])

    total_failed = len(failed_cases)
    print(f"Province not in text:      {not_in_text:3d} ({not_in_text/total_failed*100:.1f}%)")
    print(f"GT not in province set:    {not_in_set:3d} ({not_in_set/total_failed*100:.1f}%)")
    print(f"No potentials found:       {no_potentials:3d} ({no_potentials/total_failed*100:.1f}%)")
    print(f"Wrong province extracted:  {wrong_extracted:3d} ({wrong_extracted/total_failed*100:.1f}%)")

    print(f"\n{'='*80}\n")


def generate_batch_rating_report(ratings_list):
    """
    Tạo báo cáo đánh giá độ chính xác sau khi chạy batch.

    Args:
        ratings_list: List các rating đã được người dùng chấm (1/2/3)
                     Chỉ chứa các địa chỉ đã được rate (bỏ qua những địa chỉ skip)

    Returns:
        None (chỉ hiển thị báo cáo)
    """
    if not ratings_list:
        print(f"\n{colorize('⚠️ Không có đánh giá nào được ghi nhận', Colors.YELLOW)}")
        return

    total = len(ratings_list)
    rating_1_count = sum(1 for r in ratings_list if r == 1)
    rating_2_count = sum(1 for r in ratings_list if r == 2)
    rating_3_count = sum(1 for r in ratings_list if r == 3)

    # Tính phần trăm
    rating_1_pct = (rating_1_count / total * 100) if total > 0 else 0
    rating_2_pct = (rating_2_count / total * 100) if total > 0 else 0
    rating_3_pct = (rating_3_count / total * 100) if total > 0 else 0

    # Độ chính xác = % rating 1
    accuracy = rating_1_pct

    # Hiển thị báo cáo
    print(f"\n{'═'*60}")
    print(f"║{colorize('   BÁO CÁO ĐÁNH GIÁ BATCH', Colors.CYAN_BOLD).center(68)}║")
    print(f"{'═'*60}")
    print(f"║ {colorize('Tổng số địa chỉ đã chấm điểm:', Colors.BOLD)} {str(total).ljust(27)}║")
    print(f"║{' '*58}║")

    # Rating 1 (Tốt)
    bar_1 = '█' * int(rating_1_pct / 2)  # Max 50 chars for 100%
    rating_1_line = f"║ {colorize('✓ Rating 1 (Tốt):', Colors.GREEN_BOLD)} {str(rating_1_count).rjust(3)} ({rating_1_pct:5.1f}%)"
    print(f"{rating_1_line.ljust(68)}║")
    if rating_1_count > 0:
        print(f"║   {colorize(bar_1, Colors.GREEN)}{' ' * (50 - len(bar_1))}║")

    # Rating 2 (Trung bình)
    bar_2 = '█' * int(rating_2_pct / 2)
    rating_2_line = f"║ {colorize('○ Rating 2 (Trung bình):', Colors.YELLOW_BOLD)} {str(rating_2_count).rjust(3)} ({rating_2_pct:5.1f}%)"
    print(f"{rating_2_line.ljust(68)}║")
    if rating_2_count > 0:
        print(f"║   {colorize(bar_2, Colors.YELLOW)}{' ' * (50 - len(bar_2))}║")

    # Rating 3 (Kém)
    bar_3 = '█' * int(rating_3_pct / 2)
    rating_3_line = f"║ {colorize('✗ Rating 3 (Kém):', Colors.RED_BOLD)} {str(rating_3_count).rjust(3)} ({rating_3_pct:5.1f}%)"
    print(f"{rating_3_line.ljust(68)}║")
    if rating_3_count > 0:
        print(f"║   {colorize(bar_3, Colors.RED)}{' ' * (50 - len(bar_3))}║")

    print(f"║{' '*58}║")

    # Độ chính xác tổng thể
    accuracy_color = Colors.GREEN if accuracy >= 80 else (Colors.YELLOW if accuracy >= 60 else Colors.RED)
    accuracy_line = f"║ {colorize('📊 Độ chính xác:', Colors.BOLD)} {colorize(f'{accuracy:.1f}%', accuracy_color)}"
    print(f"{accuracy_line.ljust(68)}║")
    print(f"{'═'*60}\n")


def prompt_user_rating(result_data: dict, auto_flag = None):
    """
    Hỏi người dùng đánh giá chất lượng kết quả và lưu vào database.

    Args:
        result_data: Dictionary chứa thông tin về kết quả parsing và các thông tin cần lưu
            - cif_no: Customer ID (optional)
            - original_address: Địa chỉ gốc
            - known_province: Province hint from DB
            - known_district: District hint from DB
            - parsed_province: Extracted province
            - parsed_district: Extracted district
            - parsed_ward: Extracted ward
            - confidence_score: Confidence score
            - processing_time_ms: Total processing time
            - match_type: Match type

    Returns:
        int (1/2/3) if rating was saved, None if user skipped
    """
    print(f"\n{colorize('⭐ ĐÁNH GIÁ CHẤT LƯỢNG KẾT QUẢ', Colors.CYAN_BOLD)}")
    print(f"{'─'*60}")
    print(f"  {colorize('1', Colors.GREEN_BOLD)} = Tốt (kết quả chính xác)")
    print(f"  {colorize('2', Colors.YELLOW_BOLD)} = Trung bình (gần đúng nhưng thiếu/sai một số thông tin)")
    print(f"  {colorize('3', Colors.RED_BOLD)} = Kém (kết quả sai hoàn toàn)")
    print(f"  {colorize('Enter', Colors.CYAN)} = Bỏ qua")
    print(f"{'─'*60}")

    while True:
        try:
            if not auto_flag:
                user_input = input(f"Nhập lựa chọn {colorize('(1/2/3)', Colors.YELLOW)} hoặc {colorize('Enter', Colors.CYAN)} để bỏ qua: ").strip()

                # User skipped
                if not user_input:
                    print(f"{colorize('⏭ Đã bỏ qua đánh giá', Colors.YELLOW)}\n")
                    return None

                # Validate input
                if user_input not in ['1', '2', '3']:
                    print(f"{colorize('❌ Lựa chọn không hợp lệ. Vui lòng nhập 1, 2, 3 hoặc Enter.', Colors.RED)}")
                    continue

                # Valid rating
                rating = int(user_input)
            else:
                rating = int(0)

            # Prepare data for database
            rating_data = {
                'timestamp': datetime.now().isoformat(),
                'cif_no': result_data.get('cif_no'),
                'original_address': result_data.get('original_address'),
                'known_province': result_data.get('known_province'),
                'known_district': result_data.get('known_district'),
                'parsed_province': result_data.get('parsed_province'),
                'parsed_district': result_data.get('parsed_district'),
                'parsed_ward': result_data.get('parsed_ward'),
                'confidence_score': result_data.get('confidence_score'),
                'user_rating': rating,
                'processing_time_ms': result_data.get('processing_time_ms'),
                'match_type': result_data.get('match_type')
            }
            
            # Save to database
            record_id = save_user_rating(rating_data)
            
            # Show confirmation with color based on rating
            rating_label = {
                0: colorize('Chưa đánh giá', Colors.YELLOW_BOLD),
                1: colorize('Tốt', Colors.GREEN_BOLD),
                2: colorize('Trung bình', Colors.YELLOW_BOLD),
                3: colorize('Kém', Colors.RED_BOLD)
            }[rating]
            
            print(f"{colorize('✅', Colors.GREEN)} Đã lưu đánh giá: {rating_label} (ID: {record_id})\n")
            return rating

        except KeyboardInterrupt:
            print(f"\n{colorize('⏭ Đã bỏ qua đánh giá', Colors.YELLOW)}\n")
            return None
        except Exception as e:
            print(f"{colorize(f'❌ Lỗi khi lưu đánh giá: {e}', Colors.RED)}")
            return None


def main():
    """Hàm chính"""
    parser = argparse.ArgumentParser(description='Demo xử lý địa chỉ')
    parser.add_argument('-a', '--address', type=str, help='Địa chỉ cần xử lý')
    parser.add_argument('-p', '--province', type=str, help='Gợi ý tỉnh')
    parser.add_argument('-d', '--district', type=str, help='Gợi ý huyện')
    parser.add_argument('-l', '--limit', type=int, default=3, help='Số mẫu từ DB (mặc định: 3, chỉ lấy records chưa xử lý)')
    parser.add_argument('--auto', action='store_true', help='Tự động chạy hết không cần nhấn Enter (auto-save với rating=0)')
    parser.add_argument('--reprocess', type=str, help='Chạy lại records có user_rating cụ thể (comma-separated: 0,2,3)')

    args = parser.parse_args()

    # Parse and validate --reprocess ratings
    reprocess_ratings = None
    if args.reprocess:
        try:
            reprocess_ratings = [int(r.strip()) for r in args.reprocess.split(',')]
            # Validate ratings are in [0, 1, 2, 3]
            invalid = [r for r in reprocess_ratings if r not in [0, 1, 2, 3]]
            if invalid:
                print(f"{colorize(f'❌ Lỗi: Invalid ratings {invalid}. Chỉ chấp nhận 0,1,2,3', Colors.RED)}")
                sys.exit(1)
            if not reprocess_ratings:
                print(f"{colorize('❌ Lỗi: --reprocess không được để trống', Colors.RED)}")
                sys.exit(1)
        except ValueError:
            print(f"{colorize('❌ Lỗi: --reprocess phải là comma-separated numbers. Ví dụ: --reprocess 0,2,3', Colors.RED)}")
            sys.exit(1)

    # Always enable debug logging for all modes
    setup_logging(debug=True)
    from src import config
    config.DEBUG_SQL = True
    config.DEBUG_FUZZY = True
    config.DEBUG_NGRAMS = True
    config.DEBUG_EXTRACTION = True
    print(f"{colorize('🐛 DEBUG MODE ENABLED', Colors.YELLOW_BOLD)} - Detailed logging for all phases")
    print(f"  └─ SQL={Colors.GREEN}✓{Colors.RESET} | FUZZY={Colors.GREEN}✓{Colors.RESET} | NGRAMS={Colors.GREEN}✓{Colors.RESET} | EXTRACTION={Colors.GREEN}✓{Colors.RESET}\n")

    # CHẾ ĐỘ 1: Xử lý 1 địa chỉ
    if args.address:
        print(f"\n{'='*60}")
        print(colorize("📍 CHẾ ĐỘ: Xử lý địa chỉ đơn lẻ", Colors.CYAN_BOLD))
        print(f"{'='*60}")
        result = process_one_address(args.address, args.province, args.district)
        print(f"\n{colorize('✅ Hoàn thành!', Colors.GREEN_BOLD)}\n")

        # Hỏi đánh giá chất lượng
        p5 = result.get('phase6_postprocessing', {})
        best_match = result.get('phase5_validation', {}).get('best_match')

        result_data = {
            'cif_no': None,  # No CIF for single address mode
            'original_address': args.address,
            'known_province': args.province,
            'known_district': args.district,
            'parsed_province': best_match.get('province') if best_match else None,
            'parsed_district': best_match.get('district') if best_match else None,
            'parsed_ward': best_match.get('ward') if best_match else None,
            'confidence_score': best_match.get('confidence') if best_match else None,
            'processing_time_ms': sum([
                result.get('phase1', {}).get('processing_time_ms', 0),
                result.get('phase3_extraction', {}).get('processing_time_ms', 0),
                result.get('phase4_candidates', {}).get('processing_time_ms', 0),
                result.get('phase5_validation', {}).get('processing_time_ms', 0),
                result.get('phase6_postprocessing', {}).get('processing_time_ms', 0)
            ]),
            'match_type': best_match.get('match_type') if best_match else None
        }

        prompt_user_rating(result_data)

    # CHẾ ĐỘ 2: Xử lý từ database
    else:
        print(f"\n{'='*60}")

        # Check if reprocess mode
        if reprocess_ratings:
            print(colorize(f"CHẾ ĐỘ: REPROCESS - Chạy lại records đã rated", Colors.CYAN_BOLD))
            print(colorize(f"  🔄 Filter ratings: {reprocess_ratings}", Colors.YELLOW))
            samples = load_rated_samples(reprocess_ratings, args.limit)
        else:
            print(colorize(f"CHẾ ĐỘ: Xử lý batch từ database", Colors.CYAN_BOLD))
            print(colorize("  🔄 Chỉ xử lý records chưa có trong user_quality_ratings", Colors.YELLOW))
            samples = load_samples(args.limit, offset=0, random=True)

        print(f"{'='*60}")

        if not samples:
            print(colorize("❌ Không tìm thấy mẫu nào!", Colors.RED))
            return

        print(f"✅ Đã tải {len(samples)} bản ghi (random sampling)\n")

        # Track ratings for batch report
        batch_ratings = []

        for i, sample in enumerate(samples, 1):
            cif = sample['cif_no']
            print(f"{colorize(f'MẪU {i}/{len(samples)} - CIF: {cif}', Colors.CYAN_BOLD)}")

            result = process_one_address(
                sample['dia_chi_thuong_tru'],
                sample.get('ten_tinh_thuong_tru'),
                sample.get('ten_quan_huyen_thuong_tru')
            )

            # Hỏi đánh giá chất lượng (skip nếu có --auto flag)
            best_match = result.get('phase5_validation', {}).get('best_match')

            result_data = {
                'cif_no': cif,
                'original_address': sample['dia_chi_thuong_tru'],
                'known_province': sample.get('ten_tinh_thuong_tru'),
                'known_district': sample.get('ten_quan_huyen_thuong_tru'),
                'parsed_province': best_match.get('province') if best_match else None,
                'parsed_district': best_match.get('district') if best_match else None,
                'parsed_ward': best_match.get('ward') if best_match else None,
                'confidence_score': best_match.get('confidence') if best_match else None,
                'processing_time_ms': sum([
                    result.get('phase1', {}).get('processing_time_ms', 0),
                    result.get('phase3_extraction', {}).get('processing_time_ms', 0),
                    result.get('phase4_candidates', {}).get('processing_time_ms', 0),
                    result.get('phase5_validation', {}).get('processing_time_ms', 0),
                    result.get('phase6_postprocessing', {}).get('processing_time_ms', 0)
                ]),
                'match_type': best_match.get('match_type') if best_match else None
            }

            # Ask for rating (or auto-save if --auto flag)
            # prompt_user_rating will save to DB (INSERT or UPDATE based on unique constraint)
            rating = prompt_user_rating(result_data, args.auto)

            # Track rating if provided (not None)
            if rating is not None:
                batch_ratings.append(rating)

            # Prompt to continue (skip only if auto mode)
            if not args.auto:
                if i < len(samples):
                    input(f"\n{colorize('▶ Nhấn Enter để tiếp tục...', Colors.YELLOW)}")
            else:
                if i < len(samples):
                    print()  # Empty line between records

        print(f"\n{colorize('✅ Đã xử lý xong tất cả mẫu!', Colors.GREEN_BOLD)}\n")

        # Show batch rating report (only if not in auto mode and there are ratings)
        if not args.auto and batch_ratings:
            generate_batch_rating_report(batch_ratings)


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
