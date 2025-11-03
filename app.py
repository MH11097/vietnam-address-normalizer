"""
Flask Web App for Vietnamese Address Parser
Tận dụng logic từ demo.py để cung cấp web interface
"""
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import traceback

# Import functions từ demo.py và utils
from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess
from src.utils.db_utils import query_all, save_user_rating, get_rating_stats
from src.utils.text_utils import normalize_hint
from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative

app = Flask(__name__)
app.secret_key = 'vietnamese-address-parser-secret-key-2025'  # Thay bằng random key trong production


def load_random_sample():
    """Load 1 random address từ database"""
    query = """
    SELECT cif_no, dia_chi_thuong_tru,
           ten_tinh_thuong_tru, ten_quan_huyen_thuong_tru
    FROM raw_addresses
    WHERE dia_chi_thuong_tru IS NOT NULL
      AND dia_chi_thuong_tru != ''
    ORDER BY RANDOM()
    LIMIT 1
    """
    results = query_all(query)
    return results[0] if results else None


def process_address_for_web(address_text, province_known=None, district_known=None):
    """
    Xử lý địa chỉ và trả về kết quả dưới dạng dict để serialize thành JSON.
    Tương tự process_one_address() trong demo.py nhưng return dict thay vì print.
    """
    try:
        # Normalize hints
        if province_known == '/' or not province_known:
            province_known = None
        if district_known == '/' or not district_known:
            district_known = None

        # Phase 1: Preprocessing
        use_iterative = should_use_iterative(address_text, province_known)
        if use_iterative:
            p1 = iterative_preprocess(address_text, province_known, district_known)
            method = "Iterative (2-pass)"
        else:
            p1 = preprocess(address_text, province_known=province_known)
            method = "Single pass"

        # Phase 2: Structural Parsing
        province_normalized = normalize_hint(province_known) if province_known else None
        district_normalized = normalize_hint(district_known) if district_known else None

        structural_result = structural_parse(
            p1['normalized'],
            province_known=province_normalized,
            district_known=district_normalized
        )

        # Phase 3: Extraction
        if structural_result['confidence'] >= 0.75:
            # Use structural result directly
            p2 = {
                'potential_provinces': [(structural_result['province'], 1.0, (-1, -1))] if structural_result.get('province') else [],
                'potential_districts': [(structural_result['district'], 1.0, (-1, -1))] if structural_result.get('district') else [],
                'potential_wards': [(structural_result['ward'], 1.0, (-1, -1))] if structural_result.get('ward') else [],
                'potential_streets': [],
                'processing_time_ms': 0,
                'source': 'structural'
            }
        else:
            p2 = extract_components(p1, province_known, district_known)

        # Phase 4: Generate Candidates
        p3 = generate_candidates(p2)

        # Phase 5: Validation & Ranking
        p4 = validate_and_rank(p3)

        # Phase 6: Postprocessing
        p5 = postprocess(p4, {
            'original_address': address_text,
            'matched_components': p4.get('best_match', {})
        })

        # Tổng thời gian
        total_time = sum([
            p1.get('processing_time_ms', 0),
            structural_result.get('processing_time_ms', 0),
            p2.get('processing_time_ms', 0),
            p3.get('processing_time_ms', 0),
            p4.get('processing_time_ms', 0),
            p5.get('processing_time_ms', 0)
        ])

        # Prepare result
        best_match = p4.get('best_match')
        formatted_output = p5.get('formatted_output', {})

        return {
            'success': True,
            'data': {
                'phase1': {
                    'normalized': p1.get('normalized', ''),
                    'processing_time_ms': p1.get('processing_time_ms', 0),
                    'method': method,
                    'iterations': p1.get('total_iterations', 1)
                },
                'phase2': {
                    'method': structural_result.get('method', ''),
                    'confidence': structural_result.get('confidence', 0),
                    'processing_time_ms': structural_result.get('processing_time_ms', 0),
                    'province': structural_result.get('province'),
                    'district': structural_result.get('district'),
                    'ward': structural_result.get('ward')
                },
                'phase3': {
                    'potential_provinces': p2.get('potential_provinces', [])[:5],  # Top 5
                    'potential_districts': p2.get('potential_districts', [])[:5],
                    'potential_wards': p2.get('potential_wards', [])[:5],
                    'processing_time_ms': p2.get('processing_time_ms', 0),
                    'source': p2.get('source', 'ngram')
                },
                'phase4': {
                    'candidates': p3.get('candidates', [])[:10],  # Top 10
                    'total_candidates': p3.get('total_candidates', 0),
                    'sources_used': p3.get('sources_used', []),
                    'processing_time_ms': p3.get('processing_time_ms', 0)
                },
                'phase5': {
                    'validated_candidates': p4.get('validated_candidates', [])[:10],  # Top 10
                    'best_match': best_match,
                    'processing_time_ms': p4.get('processing_time_ms', 0)
                },
                'phase6': {
                    'formatted_output': formatted_output,
                    'processing_time_ms': p5.get('processing_time_ms', 0)
                }
            },
            'summary': {
                'ward': formatted_output.get('ward') or '____',
                'district': formatted_output.get('district') or '____',
                'province': formatted_output.get('province') or '____',
                'confidence': best_match.get('confidence', 0) if best_match else 0,
                'match_type': best_match.get('match_type', 'N/A') if best_match else 'N/A'
            },
            'metadata': {
                'original_address': address_text,
                'known_ward': None,  # Usually not provided in raw data
                'known_district': district_known,
                'known_province': province_known,
                'remaining_address': formatted_output.get('remaining_1', '') or formatted_output.get('remaining_2', '') or formatted_output.get('remaining_3', ''),
                'total_time_ms': total_time
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@app.route('/')
def index():
    """Trang chủ - form nhập địa chỉ"""
    return render_template('index.html')


@app.route('/parse', methods=['POST'])
def parse():
    """API endpoint để parse địa chỉ"""
    data = request.get_json()

    address = data.get('address', '').strip()
    province = data.get('province', '').strip() or None
    district = data.get('district', '').strip() or None
    cif_no = data.get('cif_no', '').strip() or None

    if not address:
        return jsonify({
            'success': False,
            'error': 'Địa chỉ không được để trống'
        }), 400

    # Process address
    result = process_address_for_web(address, province, district)

    # Store in session for rating feature
    if result['success']:
        session['last_parse'] = {
            'cif_no': cif_no,
            'address': address,
            'province': province,
            'district': district,
            'result': result
        }

    return jsonify(result)


@app.route('/random')
def random_address():
    """API endpoint để load random address từ database"""
    sample = load_random_sample()

    if not sample:
        return jsonify({
            'success': False,
            'error': 'Không tìm thấy địa chỉ trong database'
        }), 404

    return jsonify({
        'success': True,
        'data': {
            'cif_no': sample['cif_no'],
            'address': sample['dia_chi_thuong_tru'],
            'province': sample.get('ten_tinh_thuong_tru'),
            'district': sample.get('ten_quan_huyen_thuong_tru')
        }
    })


@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    """API endpoint để submit user rating"""
    data = request.get_json()
    rating = data.get('rating')

    if rating not in [1, 2, 3]:
        return jsonify({
            'success': False,
            'error': 'Rating phải là 1, 2, hoặc 3'
        }), 400

    # Get last parse from session
    last_parse = session.get('last_parse')
    if not last_parse:
        return jsonify({
            'success': False,
            'error': 'Không tìm thấy kết quả parsing gần nhất'
        }), 400

    result = last_parse['result']
    best_match = result['data']['phase5']['best_match']

    # Prepare rating data
    rating_data = {
        'timestamp': datetime.now().isoformat(),
        'cif_no': last_parse.get('cif_no'),
        'original_address': last_parse['address'],
        'known_province': last_parse.get('province'),
        'known_district': last_parse.get('district'),
        'parsed_province': best_match.get('province') if best_match else None,
        'parsed_district': best_match.get('district') if best_match else None,
        'parsed_ward': best_match.get('ward') if best_match else None,
        'confidence_score': best_match.get('confidence') if best_match else None,
        'user_rating': rating,
        'processing_time_ms': result['metadata']['total_time_ms'],
        'match_type': best_match.get('match_type') if best_match else None
    }

    try:
        record_id = save_user_rating(rating_data)
        return jsonify({
            'success': True,
            'record_id': record_id,
            'message': 'Đã lưu đánh giá thành công!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stats')
def stats():
    """Trang hiển thị statistics về ratings"""
    try:
        stats_data = get_rating_stats()
        return render_template('stats.html', stats=stats_data)
    except Exception as e:
        return f"Error loading stats: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9797)
