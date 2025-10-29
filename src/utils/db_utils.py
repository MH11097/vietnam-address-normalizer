"""
Database utilities for SQLite operations.
Provides connection management, query helpers, and data loading.
"""
import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from functools import lru_cache

logger = logging.getLogger(__name__)


# Database path (relative to project root)
DB_PATH = Path(__file__).parent.parent.parent / 'data' / 'address.db'


@contextmanager
def get_db_connection(db_path: Path = DB_PATH):
    """
    Context manager for database connections.
    Automatically handles connection close and commit.

    Args:
        db_path: Path to SQLite database file

    Yields:
        sqlite3.Connection object

    Example:
        >>> with get_db_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM admin_divisions LIMIT 1")
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def query_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    Execute query and return single row as dictionary.

    Args:
        query: SQL query string
        params: Query parameters (tuple)

    Returns:
        Dictionary with column names as keys, or None if no result

    Example:
        >>> query_one("SELECT * FROM admin_divisions WHERE id = ?", (1,))
        {'id': 1, 'province_full': 'THÀNH PHỐ HÀ NỘI', ...}
    """
    from ..config import DEBUG_SQL

    start_time = time.time() if DEBUG_SQL else 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if DEBUG_SQL:
            # Log query and params
            query_preview = query.replace('\n', ' ').strip()
           
            logger.debug(f"[SQL] {query_preview}")
            logger.debug(f"[SQL] Params: {params}")

        cursor.execute(query, params)
        row = cursor.fetchone()
        result = dict(row) if row else None

        if DEBUG_SQL:
            elapsed_ms = (time.time() - start_time) * 1000
            result_str = "1 row" if result else "0 rows"
            logger.debug(f"[SQL] → {result_str} | {elapsed_ms:.1f}ms")

        return result


def query_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """
    Execute query and return all rows as list of dictionaries.

    Args:
        query: SQL query string
        params: Query parameters (tuple)

    Returns:
        List of dictionaries with column names as keys

    Example:
        >>> query_all("SELECT * FROM abbreviations LIMIT 5")
        [{'id': 1, 'key': 'hbt', 'word': 'hai ba trung'}, ...]
    """
    from ..config import DEBUG_SQL

    start_time = time.time() if DEBUG_SQL else 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if DEBUG_SQL:
            # Log query and params
            query_preview = query.replace('\n', ' ').strip()
            if len(query_preview) > 150:
                query_preview = query_preview[:150] + "..."
            logger.debug(f"[SQL] {query_preview}")
            if params:
                logger.debug(f"[SQL] Params: {params}")

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]

        if DEBUG_SQL:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"[SQL] → {len(result)} rows | {elapsed_ms:.1f}ms")

        return result


def execute_query(query: str, params: tuple = ()) -> int:
    """
    Execute UPDATE/INSERT/DELETE query and return number of affected rows.

    Args:
        query: SQL query string (UPDATE/INSERT/DELETE)
        params: Query parameters (tuple)

    Returns:
        Number of rows affected

    Example:
        >>> execute_query("UPDATE admin_divisions SET province_name_normalized = ? WHERE id = ?", ('ha noi', 1))
        1
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.rowcount


@lru_cache(maxsize=256)
def load_abbreviations(
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> Dict[str, str]:
    """
    Load abbreviations from database with optional province and district context.
    Priority: District-specific > Province-specific > Global
    (More specific context overwrites less specific for same key)
    Cached for performance.

    Args:
        province_context: Province name (normalized) to filter context-specific abbreviations.
                         If None, returns only global abbreviations.
        district_context: District name (normalized) for ward-level disambiguation.
                         Requires province_context to be set.

    Returns:
        Dictionary mapping abbreviation key to full word
        Example: {'hbt': 'hai ba trung', 'brvt': 'ba ria vung tau'}

    Example:
        >>> abbr = load_abbreviations()  # Global only
        >>> abbr['hn']
        'ha noi'

        >>> abbr_hn = load_abbreviations('ha noi')  # Global + Hanoi-specific
        >>> abbr_hn['tx']
        'thanh xuan'  # Province-specific overrides generic 'thi xa'

        >>> abbr_ward = load_abbreviations('ha noi', 'ba dinh')  # Include ward-level
        >>> abbr_ward['db']
        'dien bien'  # Ward-specific in Ba Dinh district
    """
    result = {}

    # Step 1: Load global abbreviations first (lowest priority)
    query_global = """
        SELECT key, word FROM abbreviations
        WHERE province_context IS NULL AND district_context IS NULL
    """
    rows_global = query_all(query_global)
    for row in rows_global:
        result[row['key']] = row['word']

    # Step 2: Load province-specific abbreviations (medium priority - overwrites global)
    if province_context:
        query_province = """
            SELECT key, word FROM abbreviations
            WHERE province_context = ? AND district_context IS NULL
        """
        rows_province = query_all(query_province, (province_context,))
        for row in rows_province:
            result[row['key']] = row['word']  # Overwrite global if exists

        # Step 3: Load district-specific abbreviations (highest priority - overwrites all)
        if district_context:
            query_district = """
                SELECT key, word FROM abbreviations
                WHERE province_context = ? AND district_context = ?
            """
            rows_district = query_all(query_district, (province_context, district_context))
            for row in rows_district:
                result[row['key']] = row['word']  # Overwrite province/global if exists

    return result


def expand_abbreviation_from_admin(
    abbr: str,
    level: str = 'ward',
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> Optional[str]:
    """
    Expand abbreviation using abbreviations table (migrated from admin_divisions).

    NOTE: This function now uses the abbreviations table instead of admin_divisions.
    The admin_divisions abbreviation columns have been deprecated.

    Args:
        abbr: Abbreviation to expand (e.g., "tx", "bd")
        level: Level to search - 'ward', 'district', or 'province' (kept for compatibility)
        province_context: Province context for disambiguation (recommended for ward/district)
        district_context: District context for ward-level disambiguation

    Returns:
        Expanded name (normalized) or None if not found

    Example:
        >>> expand_abbreviation_from_admin('tx', 'ward', 'ha noi')
        'thanh xuan'
        >>> expand_abbreviation_from_admin('bd', 'district', 'ha noi')
        'ba dinh'
        >>> expand_abbreviation_from_admin('db', 'ward', 'ha noi', 'ba dinh')
        'dien bien'
    """
    if not abbr:
        return None

    abbr = abbr.lower().strip()

    # Query abbreviations table with context
    # Note: We don't filter by level anymore since abbreviations table stores all levels
    conditions = ["key = ?"]
    params = [abbr]

    if province_context and district_context:
        # Most specific: ward level
        conditions.append("province_context = ?")
        conditions.append("district_context = ?")
        params.extend([province_context, district_context])
    elif province_context:
        # District level
        conditions.append("province_context = ?")
        conditions.append("district_context IS NULL")
        params.append(province_context)
    else:
        # Global level (province)
        conditions.append("province_context IS NULL")
        conditions.append("district_context IS NULL")

    query = f"""
        SELECT word FROM abbreviations
        WHERE {' AND '.join(conditions)}
        LIMIT 1
    """

    result = query_one(query, tuple(params))
    return result['word'] if result else None


@lru_cache(maxsize=1)
def load_admin_divisions_all() -> List[Dict[str, Any]]:
    """
    Load all admin divisions from database.
    Cached for performance.

    Returns:
        List of all admin division records

    Example:
        >>> divisions = load_admin_divisions_all()
        >>> len(divisions)
        9991
    """
    query = """
    SELECT
        id,
        province_full, province_name, province_name_normalized,
        district_full, district_name, district_name_normalized,
        ward_full, ward_name, ward_name_normalized
    FROM admin_divisions
    """
    return query_all(query)


@lru_cache(maxsize=1)
def get_province_set() -> set:
    """
    Get set of all normalized province names for fast O(1) lookup.

    Returns:
        Set of province names (normalized)

    Example:
        >>> provinces = get_province_set()
        >>> 'ha noi' in provinces
        True
    """
    query = "SELECT DISTINCT province_name_normalized FROM admin_divisions"
    rows = query_all(query)
    return {row['province_name_normalized'] for row in rows if row['province_name_normalized']}


@lru_cache(maxsize=1)
def get_district_set() -> set:
    """
    Get set of all normalized district names for fast O(1) lookup.

    Returns:
        Set of district names (normalized)

    Example:
        >>> districts = get_district_set()
        >>> 'ba dinh' in districts
        True
    """
    query = "SELECT DISTINCT district_name_normalized FROM admin_divisions"
    rows = query_all(query)
    return {row['district_name_normalized'] for row in rows if row['district_name_normalized']}


@lru_cache(maxsize=1)
def get_ward_set() -> set:
    """
    Get set of all normalized ward names for fast O(1) lookup.

    Returns:
        Set of ward names (normalized)

    Example:
        >>> wards = get_ward_set()
        >>> 'dien bien' in wards
        True
    """
    query = "SELECT DISTINCT ward_name_normalized FROM admin_divisions"
    rows = query_all(query)
    return {row['ward_name_normalized'] for row in rows if row['ward_name_normalized']}


@lru_cache(maxsize=1)
def get_street_set() -> set:
    """
    Get set of all normalized street names for fast O(1) lookup.

    Returns:
        Set of street names (normalized)

    Example:
        >>> streets = get_street_set()
        >>> 'tran hung dao' in streets
        True
    """
    query = "SELECT DISTINCT street_name_normalized FROM admin_streets"
    rows = query_all(query)
    return {row['street_name_normalized'] for row in rows if row['street_name_normalized']}


def find_exact_match(
    province: Optional[str],
    district: Optional[str],
    ward: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Find exact match in admin_divisions table.

    IMPORTANT: Requires at least 2 components (province + district OR province + ward)
    to prevent returning random results.

    Args:
        province: Normalized province name
        district: Normalized district name
        ward: Normalized ward name

    Returns:
        Matched record or None

    Example:
        >>> find_exact_match('ha noi', 'ba dinh', 'dien bien')
        {'province_full': 'THÀNH PHỐ HÀ NỘI', ...}
        >>> find_exact_match('ha noi', None, None)
        None  # Prevents random results
    """
    from ..config import DEBUG_SQL

    if DEBUG_SQL:
        logger.debug(f"[SQL] find_exact_match(province={province}, district={district}, ward={ward})")

    conditions = []
    params = []

    if province:
        conditions.append("province_name_normalized = ?")
        params.append(province)
    if district:
        conditions.append("district_name_normalized = ?")
        params.append(district)
    if ward:
        conditions.append("ward_name_normalized = ?")
        params.append(ward)

    # IMPORTANT: Require at least 2 conditions to prevent random results
    # If only province is provided, we would get arbitrary ward/district
    if len(conditions) < 2:
        if DEBUG_SQL:
            logger.debug(f"[SQL] → None (requires at least 2 components)")
        return None

    query = f"""
    SELECT * FROM admin_divisions
    WHERE {' AND '.join(conditions)}
    ORDER BY id ASC
    LIMIT 1
    """

    result = query_one(query, tuple(params))

    if result:
        # Clear fields that weren't queried to prevent using random LIMIT 1 values
        if not ward:
            result['ward_full'] = None
            result['ward_name'] = None
            result['ward_name_normalized'] = None
        if not district:
            result['district_full'] = None
            result['district_name'] = None
            result['district_name_normalized'] = None

        if DEBUG_SQL:
            # Only show components that were actually queried
            parts = []
            if province:
                parts.append(result.get('province_full', ''))
            if district:
                parts.append(result.get('district_full', ''))
            if ward:
                parts.append(result.get('ward_full', ''))
            logger.debug(f"[SQL] → Match found: {' / '.join(parts)}")

    return result


def get_candidates_scoped(
    province_known: Optional[str] = None,
    district_known: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get candidate records with geographic scope filtering.

    Use case: Khi raw_addresses đã có sẵn ten_tinh hoặc ten_quan_huyen,
    ta chỉ cần tìm trong phạm vi đó thay vì toàn bộ 9,991 records.

    Args:
        province_known: Known province name from raw data (if available)
        district_known: Known district name from raw data (if available)

    Returns:
        List of candidate records (filtered by scope)

    Example:
        >>> # Nếu raw data có "HÀ NỘI" → chỉ lấy districts/wards trong Hà Nội
        >>> candidates = get_candidates_scoped(province_known="ha noi")
        >>> len(candidates)
        ~300  # Thay vì 9,991
    """
    conditions = []
    params = []

    if province_known:
        conditions.append("province_name_normalized = ?")
        params.append(province_known)

    if district_known:
        conditions.append("district_name_normalized = ?")
        params.append(district_known)

    if not conditions:
        # No known values → return all (fallback)
        return load_admin_divisions_all()

    where_clause = ' AND '.join(conditions)
    query = f"""
    SELECT * FROM admin_divisions
    WHERE {where_clause}
    """

    return query_all(query, tuple(params))


def validate_hierarchy(
    province: str,
    district: Optional[str] = None,
    ward: Optional[str] = None
) -> bool:
    """
    Validate that district belongs to province and ward belongs to district.

    Args:
        province: Normalized province name
        district: Normalized district name (optional)
        ward: Normalized ward name (optional)

    Returns:
        True if hierarchy is valid, False otherwise

    Example:
        >>> validate_hierarchy('ha noi', 'ba dinh', 'dien bien')
        True
        >>> validate_hierarchy('ha noi', 'district1', 'ward2')
        False
    """
    from ..config import DEBUG_SQL

    if DEBUG_SQL:
        components = [province]
        if district:
            components.append(district)
        if ward:
            components.append(ward)
        logger.debug(f"[SQL] validate_hierarchy({' > '.join(components)})")

    conditions = ["province_name_normalized = ?"]
    params = [province]

    if district:
        conditions.append("district_name_normalized = ?")
        params.append(district)
    if ward:
        conditions.append("ward_name_normalized = ?")
        params.append(ward)

    query = f"""
    SELECT COUNT(*) as count FROM admin_divisions
    WHERE {' AND '.join(conditions)}
    """

    result = query_one(query, tuple(params))
    is_valid = result['count'] > 0 if result else False

    if DEBUG_SQL:
        logger.debug(f"[SQL] → {'✓ Valid' if is_valid else '✗ Invalid'}")

    return is_valid


def get_districts_by_province(province: str) -> List[Dict[str, Any]]:
    """
    Get all districts belonging to a province.

    Args:
        province: Normalized province name

    Returns:
        List of district records

    Example:
        >>> districts = get_districts_by_province('ha noi')
        >>> len(districts)
        30  # Hà Nội has 30 districts
    """
    query = """
    SELECT DISTINCT
        district_full,
        district_name,
        district_name_normalized
    FROM admin_divisions
    WHERE province_name_normalized = ?
    """
    return query_all(query, (province,))


def check_province_district_collision(name: str) -> Dict[str, Any]:
    """
    Check if a normalized name exists as both a province and a district.

    This handles cases like 'ben tre' which is both:
    - A province: Tỉnh Bến Tre
    - A district: Thành phố Bến Tre (within Tỉnh Bến Tre)

    Args:
        name: Normalized name to check (e.g., 'ben tre')

    Returns:
        Dict with collision info:
        {
            'has_collision': bool,
            'province_name': str or None,
            'district_name': str or None,
            'district_province': str or None  # Which province contains the district
        }

    Example:
        >>> result = check_province_district_collision('ben tre')
        >>> result['has_collision']
        True
        >>> result['province_name']
        'ben tre'
        >>> result['district_name']
        'ben tre'
    """
    # Check if name exists as province
    province_query = """
    SELECT DISTINCT province_name_normalized, province_full
    FROM admin_divisions
    WHERE province_name_normalized = ?
    LIMIT 1
    """
    province_result = query_all(province_query, (name,))

    # Check if name exists as district
    district_query = """
    SELECT DISTINCT
        district_name_normalized,
        district_full,
        province_name_normalized
    FROM admin_divisions
    WHERE district_name_normalized = ?
    LIMIT 1
    """
    district_result = query_all(district_query, (name,))

    has_collision = len(province_result) > 0 and len(district_result) > 0

    return {
        'has_collision': has_collision,
        'province_name': province_result[0]['province_name_normalized'] if province_result else None,
        'district_name': district_result[0]['district_name_normalized'] if district_result else None,
        'district_province': district_result[0]['province_name_normalized'] if district_result else None,
        'province_full': province_result[0]['province_full'] if province_result else None,
        'district_full': district_result[0]['district_full'] if district_result else None,
    }


def get_wards_by_district(province: str, district: str) -> List[Dict[str, Any]]:
    """
    Get all wards belonging to a district in a province.

    Args:
        province: Normalized province name
        district: Normalized district name

    Returns:
        List of ward records

    Example:
        >>> wards = get_wards_by_district('ha noi', 'ba dinh')
        >>> len(wards)
        14  # Ba Đình has 14 wards
    """
    query = """
    SELECT
        ward_full,
        ward_name,
        ward_name_normalized
    FROM admin_divisions
    WHERE province_name_normalized = ?
      AND district_name_normalized = ?
    """
    return query_all(query, (province, district))


def get_streets_by_district(province: str, district: str) -> List[Dict[str, Any]]:
    """
    Get all streets belonging to a district in a province.

    Args:
        province: Normalized province name
        district: Normalized district name

    Returns:
        List of street records

    Example:
        >>> streets = get_streets_by_district('ha noi', 'ba dinh')
        >>> len(streets)
        182  # Ba Đình has 182 streets
    """
    query = """
    SELECT
        street_name,
        street_name_normalized,
        district_name_normalized,
        district_full
    FROM admin_streets
    WHERE province_name_normalized = ?
      AND district_name_normalized = ?
    """
    return query_all(query, (province, district))


def get_streets_by_province(province: str, street: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get all streets in a province, optionally filtered by street name.
    Returns district context for each street.

    Args:
        province: Normalized province name
        street: Normalized street name (optional filter)

    Returns:
        List of street records with district context

    Example:
        >>> streets = get_streets_by_province('ha noi', 'doi can')
        >>> streets[0]
        {
            'street_name': 'Đội Cấn',
            'street_name_normalized': 'doi can',
            'district_name_normalized': 'ba dinh',
            'district_full': 'Quận Ba Đình'
        }
    """
    if street:
        query = """
        SELECT DISTINCT
            street_name,
            street_name_normalized,
            district_name_normalized,
            district_full,
            province_name_normalized,
            province_full
        FROM admin_streets
        WHERE province_name_normalized = ?
          AND street_name_normalized = ?
        """
        return query_all(query, (province, street))
    else:
        query = """
        SELECT DISTINCT
            street_name,
            street_name_normalized,
            district_name_normalized,
            district_full,
            province_name_normalized,
            province_full
        FROM admin_streets
        WHERE province_name_normalized = ?
        """
        return query_all(query, (province,))


def infer_district_from_ward(province: str, ward: str) -> Optional[str]:
    """
    Infer district from ward within a province.
    Used when ward is found but district is missing in the input.

    Args:
        province: Normalized province name
        ward: Normalized ward name

    Returns:
        Normalized district name, or None if not found

    Example:
        >>> infer_district_from_ward('ha noi', 'bach khoa')
        'hai ba trung'
        >>> infer_district_from_ward('ha noi', 'dien bien')
        'ba dinh'
    """
    query = """
    SELECT DISTINCT district_name_normalized
    FROM admin_divisions
    WHERE province_name_normalized = ?
      AND ward_name_normalized = ?
    LIMIT 1
    """
    result = query_one(query, (province, ward))
    return result['district_name_normalized'] if result else None


def find_street_match(
    province: Optional[str] = None,
    district: Optional[str] = None,
    street: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Find street match in streets table.

    Args:
        province: Normalized province name (optional)
        district: Normalized district name (optional)
        street: Normalized street name (required)

    Returns:
        Matched street record or None

    Example:
        >>> find_street_match('ha noi', 'ba dinh', 'tran hung dao')
        {'province_full': 'Hà Nội', 'district_full': 'Quận Ba Đình', 'street_name': 'Trần Hưng Đạo', ...}
        >>> find_street_match(street='tran hung dao')
        # Returns first match across all provinces/districts
    """
    if not street:
        return None

    conditions = ["street_name_normalized = ?"]
    params = [street]

    if province:
        conditions.append("province_name_normalized = ?")
        params.append(province)
    if district:
        conditions.append("district_name_normalized = ?")
        params.append(district)

    query = f"""
    SELECT * FROM streets
    WHERE {' AND '.join(conditions)}
    ORDER BY id ASC
    LIMIT 1
    """

    return query_one(query, tuple(params))


def clear_cache():
    """Clear all LRU caches to free memory."""
    load_abbreviations.cache_clear()
    load_admin_divisions_all.cache_clear()
    get_province_set.cache_clear()
    get_district_set.cache_clear()
    get_ward_set.cache_clear()
    get_street_set.cache_clear()


def get_cache_stats() -> dict:
    """
    Get statistics about cache usage.

    Returns:
        Dictionary with cache statistics
    """
    return {
        'load_abbreviations': load_abbreviations.cache_info()._asdict(),
        'load_admin_divisions_all': load_admin_divisions_all.cache_info()._asdict(),
        'get_province_set': get_province_set.cache_info()._asdict(),
        'get_district_set': get_district_set.cache_info()._asdict(),
        'get_ward_set': get_ward_set.cache_info()._asdict(),
        'get_street_set': get_street_set.cache_info()._asdict(),
    }


if __name__ == "__main__":
    # Test database utilities
    print("=" * 80)
    print("DATABASE UTILITIES TEST")
    print("=" * 80)

    print("\n1. Loading abbreviations...")
    abbr = load_abbreviations()
    print(f"   Loaded {len(abbr)} abbreviations")
    print(f"   Sample: hbt -> {abbr.get('hbt')}")
    print(f"   Sample: brvt -> {abbr.get('brvt')}")

    print("\n2. Loading admin divisions...")
    divisions = load_admin_divisions_all()
    print(f"   Loaded {len(divisions)} admin divisions")
    print(f"   Sample: {divisions[0]}")

    print("\n3. Testing province/district/ward sets...")
    provinces = get_province_set()
    districts = get_district_set()
    wards = get_ward_set()
    print(f"   Provinces: {len(provinces)}")
    print(f"   Districts: {len(districts)}")
    print(f"   Wards: {len(wards)}")

    print("\n4. Testing exact match...")
    result = find_exact_match('ha noi', 'ba dinh', 'dien bien')
    if result:
        print(f"   Found: {result['province_full']} / {result['district_full']} / {result['ward_full']}")
    else:
        print("   Not found")

    print("\n5. Testing hierarchy validation...")
    valid = validate_hierarchy('ha noi', 'ba dinh', 'dien bien')
    print(f"   Valid: {valid}")

    print("\n6. Cache statistics:")
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"   {key}: hits={value['hits']}, misses={value['misses']}")

    print("\n" + "=" * 80)
