"""
Flask Web App for Vietnamese Address Parser
Tận dụng logic từ demo.py để cung cấp web interface
"""
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import traceback
import uuid

# Import functions từ demo.py và utils
from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess
from src.utils.db_utils import (query_all, save_user_rating, get_rating_stats, execute_query, query_one,
                                 get_review_records, update_existing_rating, get_review_statistics)
from src.utils.text_utils import normalize_hint
from src.utils.iterative_preprocessing import iterative_preprocess, should_use_iterative

app = Flask(__name__)
app.secret_key = 'vietnamese-address-parser-secret-key-2025'  # Thay bằng random key trong production


# ============================================================================
# SESSION MANAGEMENT FUNCTIONS
# ============================================================================

def start_review_session():
    """
    Tạo session mới để theo dõi review metrics
    Returns: session_id (str)
    """
    session_id = str(uuid.uuid4())

    query = """
    INSERT INTO review_sessions (session_id, start_time, status)
    VALUES (?, ?, 'active')
    """
    execute_query(query, (session_id, datetime.now().isoformat()))

    # Store in Flask session
    session['review_session_id'] = session_id
    session['session_stats'] = {
        'total': 0,
        'rating_1': 0,
        'rating_2': 0,
        'rating_3': 0,
        'accuracy': 0.0
    }

    return session_id


def get_current_session_stats():
    """
    Lấy thống kê của session hiện tại từ database
    Returns: dict với session stats hoặc None
    """
    session_id = session.get('review_session_id')
    if not session_id:
        return None

    query = """
    SELECT session_id, total_reviews, rating_1_count, rating_2_count,
           rating_3_count, accuracy_rate, status
    FROM review_sessions
    WHERE session_id = ?
    """
    result = query_one(query, (session_id,))

    if result:
        return {
            'session_id': result['session_id'],
            'total': result['total_reviews'],
            'rating_1': result['rating_1_count'],
            'rating_2': result['rating_2_count'],
            'rating_3': result['rating_3_count'],
            'accuracy': result['accuracy_rate'],
            'status': result['status']
        }
    return None


def update_session_stats(session_id, rating):
    """
    Cập nhật thống kê session sau khi user submit rating
    Args:
        session_id: UUID của session
        rating: 1, 2, hoặc 3
    """
    # Increment counters
    rating_col = f'rating_{rating}_count'
    query = f"""
    UPDATE review_sessions
    SET total_reviews = total_reviews + 1,
        {rating_col} = {rating_col} + 1
    WHERE session_id = ?
    """
    execute_query(query, (session_id,))

    # Recalculate accuracy rate (rating 1 + 2 count as accurate)
    query = """
    UPDATE review_sessions
    SET accuracy_rate = CAST((rating_1_count + rating_2_count) AS REAL) / total_reviews * 100
    WHERE session_id = ? AND total_reviews > 0
    """
    execute_query(query, (session_id,))

    # Update Flask session stats for quick access
    stats = get_current_session_stats()
    if stats:
        session['session_stats'] = stats


def complete_review_session(session_id):
    """
    Đánh dấu session đã hoàn thành
    Args:
        session_id: UUID của session
    """
    query = """
    UPDATE review_sessions
    SET status = 'completed',
        end_time = ?
    WHERE session_id = ?
    """
    execute_query(query, (datetime.now().isoformat(), session_id))


def load_random_sample(province_filter=None):
    """
    Load 1 random address từ database
    Args:
        province_filter: Optional province name to filter by
    """
    if province_filter:
        query = """
        SELECT cif_no, dia_chi_thuong_tru,
               ten_tinh_thuong_tru, ten_quan_huyen_thuong_tru
        FROM raw_addresses
        WHERE dia_chi_thuong_tru IS NOT NULL
          AND dia_chi_thuong_tru != ''
          AND ten_tinh_thuong_tru = ?
        ORDER BY RANDOM()
        LIMIT 1
        """
        results = query_all(query, (province_filter,))
    else:
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

    address = (data.get('address') or '').strip()
    province = (data.get('province') or '').strip() or None
    district = (data.get('district') or '').strip() or None
    cif_no = (data.get('cif_no') or '').strip() or None

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
    # Auto-start review session if not exists
    if not session.get('review_session_id'):
        session_id = start_review_session()
        print(f"Started new review session: {session_id}")

    # Get province filter from query parameter
    province_filter = request.args.get('province', '').strip() or None

    sample = load_random_sample(province_filter)

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


@app.route('/provinces')
def get_provinces():
    """API endpoint để lấy danh sách tỉnh/thành phố"""
    query = """
    SELECT DISTINCT ten_tinh_thuong_tru as province_name
    FROM raw_addresses
    WHERE ten_tinh_thuong_tru IS NOT NULL
      AND ten_tinh_thuong_tru != ''
    ORDER BY ten_tinh_thuong_tru
    """
    provinces = query_all(query)

    return jsonify({
        'success': True,
        'provinces': [p['province_name'] for p in provinces]
    })


@app.route('/districts')
def get_districts():
    """API endpoint để lấy danh sách quận/huyện (có thể filter theo tỉnh)"""
    province = request.args.get('province', '').strip() or None

    if province:
        query = """
        SELECT DISTINCT ten_quan_huyen_thuong_tru as district_name
        FROM raw_addresses
        WHERE ten_quan_huyen_thuong_tru IS NOT NULL
          AND ten_quan_huyen_thuong_tru != ''
          AND ten_tinh_thuong_tru = ?
        ORDER BY ten_quan_huyen_thuong_tru
        """
        districts = query_all(query, (province,))
    else:
        query = """
        SELECT DISTINCT ten_quan_huyen_thuong_tru as district_name
        FROM raw_addresses
        WHERE ten_quan_huyen_thuong_tru IS NOT NULL
          AND ten_quan_huyen_thuong_tru != ''
        ORDER BY ten_quan_huyen_thuong_tru
        """
        districts = query_all(query)

    return jsonify({
        'success': True,
        'districts': [d['district_name'] for d in districts]
    })


@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    """API endpoint để submit user rating"""
    data = request.get_json()
    rating = data.get('rating')

    if rating not in [0, 1, 2, 3]:
        return jsonify({
            'success': False,
            'error': 'Rating phải là 0, 1, 2, hoặc 3'
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

    # Get current session_id
    session_id = session.get('review_session_id')

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
        'match_type': best_match.get('match_type') if best_match else None,
        'session_id': session_id  # Link rating to session
    }

    try:
        record_id = save_user_rating(rating_data)

        # Update session stats if session exists
        if session_id:
            update_session_stats(session_id, rating)

        # Get updated session stats to return
        session_stats = get_current_session_stats()

        return jsonify({
            'success': True,
            'record_id': record_id,
            'message': 'Đã lưu đánh giá thành công!',
            'session_stats': session_stats  # Return updated stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/session_stats')
def session_stats():
    """API endpoint để lấy thống kê session hiện tại"""
    stats = get_current_session_stats()

    if stats:
        return jsonify({
            'success': True,
            'stats': stats
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Chưa có session nào đang active'
        })


@app.route('/end_session', methods=['POST'])
def end_session():
    """API endpoint để kết thúc session hiện tại"""
    session_id = session.get('review_session_id')

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'Không có session nào đang active'
        }), 400

    try:
        # Get final stats before completing
        final_stats = get_current_session_stats()

        # Complete the session
        complete_review_session(session_id)

        # Clear Flask session
        session.pop('review_session_id', None)
        session.pop('session_stats', None)

        return jsonify({
            'success': True,
            'message': 'Session đã được kết thúc',
            'summary': final_stats
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


# ============================================================================
# REVIEW TAB ROUTES
# ============================================================================

@app.route('/review')
def review():
    """Trang review - hiển thị các records đã được batch process hoặc manual parse"""
    return render_template('index.html')  # Same template, different tab


@app.route('/get_review_records')
def get_review_records_api():
    """
    API endpoint để lấy danh sách records để review
    Query params:
        - user_rating: Filter by rating (0, 1, 2, 3). Optional (default: all)
        - limit: Number of records (default: 20)
        - offset: Pagination offset (default: 0)
    """
    try:
        # Get query parameters
        user_rating_str = request.args.get('user_rating', '').strip()
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        # Validate limit
        if limit < 1 or limit > 500:
            return jsonify({
                'success': False,
                'error': 'Limit phải từ 1 đến 500'
            }), 400

        # Parse user_rating filter
        user_rating_filter = None
        if user_rating_str and user_rating_str != 'all':
            try:
                user_rating_filter = int(user_rating_str)
                if user_rating_filter not in (0, 1, 2, 3):
                    return jsonify({
                        'success': False,
                        'error': 'user_rating phải là 0, 1, 2, 3 hoặc "all"'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'user_rating phải là số hoặc "all"'
                }), 400

        # Get records from database
        records = get_review_records(user_rating_filter, limit, offset)

        # Get total count for pagination
        if user_rating_filter is not None:
            count_query = "SELECT COUNT(*) as total FROM user_quality_ratings WHERE user_rating = ?"
            count_result = query_one(count_query, (user_rating_filter,))
        else:
            count_query = "SELECT COUNT(*) as total FROM user_quality_ratings"
            count_result = query_one(count_query)

        total_count = count_result['total'] if count_result else 0

        return jsonify({
            'success': True,
            'records': records,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/update_rating', methods=['POST'])
def update_rating_api():
    """
    API endpoint để update rating của một record
    Body: {record_id: int, new_rating: int (0-3)}
    """
    try:
        data = request.get_json()
        record_id = data.get('record_id')
        new_rating = data.get('new_rating')

        if not record_id:
            return jsonify({
                'success': False,
                'error': 'record_id là bắt buộc'
            }), 400

        if new_rating not in [0, 1, 2, 3]:
            return jsonify({
                'success': False,
                'error': 'new_rating phải là 0, 1, 2, hoặc 3'
            }), 400

        # Update the rating
        success = update_existing_rating(record_id, new_rating)

        if not success:
            return jsonify({
                'success': False,
                'error': f'Không tìm thấy record với ID {record_id}'
            }), 404

        return jsonify({
            'success': True,
            'message': f'Đã cập nhật rating thành công'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/get_review_stats')
def get_review_stats_api():
    """
    API endpoint để lấy thống kê review
    Returns: {
        total_records: int,
        rating_counts: {0: int, 1: int, 2: int, 3: int},
        rating_percentages: {0: float, 1: float, 2: float, 3: float},
        avg_confidence: {0: float, 1: float, 2: float, 3: float}
    }
    """
    try:
        stats = get_review_statistics()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9797)
