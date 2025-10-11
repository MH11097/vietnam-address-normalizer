"""
OpenStreetMap Nominatim geocoding utilities.
ALWAYS called in Phase 3 (no opt-in flag).
"""
import requests
import time
import logging
from typing import Dict, Optional, List
from functools import lru_cache

logger = logging.getLogger(__name__)

# Configuration
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "Vietnamese Address Parser/1.0 (github.com/user/address-parser)"
REQUEST_TIMEOUT = 5  # seconds
RATE_LIMIT_DELAY = 1.0  # 1 request/second (OSM policy)

_last_request_time = 0

# Province bounding boxes (approximate coordinates: left, bottom, right, top)
# Format: 'province_normalized': 'min_lon,min_lat,max_lon,max_lat'
PROVINCE_BBOXES = {
    'ha noi': '105.4,20.8,106.0,21.4',
    'ho chi minh': '106.4,10.3,107.0,11.2',
    'da nang': '107.9,15.8,108.3,16.3',
    'hai phong': '106.4,20.6,107.1,21.0',
    'can tho': '105.5,9.8,106.0,10.3',
    'ha nam': '105.8,20.3,106.2,20.8',
    'ha giang': '104.6,22.5,105.6,23.4',
    'cao bang': '105.8,22.2,106.9,23.1',
    'bac kan': '105.5,21.8,106.2,22.5',
    'tuyen quang': '104.9,21.5,105.6,22.4',
    'lao cai': '103.5,22.1,104.5,23.0',
    'dien bien': '102.8,21.0,103.5,22.1',
    'lai chau': '102.9,21.8,103.6,22.6',
    'son la': '103.4,20.6,104.5,21.5',
    'yen bai': '104.3,21.3,105.2,22.2',
    'hoa binh': '105.0,20.3,105.7,21.2',
    'thai nguyen': '105.5,21.3,106.3,22.1',
    'lang son': '106.4,21.4,107.3,22.4',
    'quang ninh': '107.0,20.7,108.3,21.8',
    'bac giang': '106.0,21.0,106.8,21.8',
    'phu tho': '104.9,21.1,105.5,21.7',
    'vinh phuc': '105.3,21.1,105.8,21.6',
    'bac ninh': '106.0,20.9,106.3,21.3',
    'hai duong': '106.0,20.6,106.6,21.0',
    'hung yen': '106.0,20.5,106.3,20.9',
    'thai binh': '106.1,20.3,106.7,20.8',
    'ha nam': '105.8,20.3,106.2,20.8',
    'nam dinh': '106.0,20.0,106.5,20.6',
    'ninh binh': '105.6,20.0,106.2,20.4',
    'thanh hoa': '105.0,19.3,106.0,20.5',
    'nghe an': '104.3,18.3,105.9,19.9',
    'ha tinh': '105.5,18.0,106.3,18.6',
    'quang binh': '105.8,17.1,106.9,18.1',
    'quang tri': '106.8,16.4,107.6,17.2',
    'thua thien hue': '107.1,16.0,107.9,16.8',
    'quang nam': '107.2,14.8,108.9,16.1',
    'quang ngai': '108.3,14.5,109.2,15.5',
    'binh dinh': '108.5,13.5,109.3,14.6',
    'phu yen': '108.8,12.8,109.6,13.9',
    'khanh hoa': '108.8,11.8,109.5,12.8',
    'ninh thuan': '108.5,11.3,109.2,12.0',
    'binh thuan': '107.4,10.4,108.6,11.6',
    'kon tum': '107.5,14.0,108.5,15.2',
    'gia lai': '107.5,13.3,108.8,14.6',
    'dak lak': '107.5,12.2,108.8,13.3',
    'dak nong': '107.3,11.6,108.3,12.7',
    'lam dong': '107.4,10.8,108.8,12.3',
    'binh phuoc': '106.4,11.3,107.5,12.3',
    'tay ninh': '105.8,11.0,106.7,11.8',
    'binh duong': '106.4,10.8,107.0,11.5',
    'dong nai': '106.6,10.4,107.6,11.6',
    'ba ria vung tau': '107.0,10.1,107.7,10.8',
    'long an': '105.8,10.2,106.9,11.1',
    'tien giang': '105.8,10.0,106.6,10.7',
    'ben tre': '105.9,9.8,106.7,10.5',
    'tra vinh': '106.0,9.5,106.6,10.1',
    'vinh long': '105.7,9.8,106.3,10.4',
    'dong thap': '105.3,10.2,106.0,11.2',
    'an giang': '104.7,10.0,105.6,10.9',
    'kien giang': '104.3,9.0,105.5,10.6',
    'soc trang': '105.7,9.3,106.3,9.9',
    'bac lieu': '105.4,9.0,105.9,9.6',
    'ca mau': '104.6,8.4,105.5,9.4',
}


def _wait_for_rate_limit():
    """Respect OSM 1 req/sec limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - elapsed
        logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
        time.sleep(sleep_time)
    _last_request_time = time.time()


def geocode_address(address: str, country_code: str = "vn", known_province: Optional[str] = None) -> Optional[Dict]:
    """
    Forward geocoding using OSM Nominatim with province-specific or Vietnam-wide bounding box.

    Args:
        address: Vietnamese address string
        country_code: 'vn' for Vietnam
        known_province: Known province (normalized) to restrict search to province bbox

    Returns:
        Dict with lat, lon, display_name, address components
        None if failed

    Example:
        >>> geocode_address("Phường Điện Biên, Quận Ba Đình, Hà Nội", known_province="ha noi")
        {
            'lat': '21.0341',
            'lon': '105.8372',
            'display_name': 'Điện Biên, Ba Đình, Hà Nội, Vietnam',
            'address': {
                'suburb': 'Điện Biên',
                'city_district': 'Ba Đình',
                'city': 'Hà Nội',
                'country': 'Vietnam'
            },
            'importance': 0.65
        }
    """
    _wait_for_rate_limit()

    try:
        params = {
            'q': address,
            'format': 'json',
            'countrycodes': country_code,
            'addressdetails': 1,
            'limit': 1
        }

        # Determine bounding box based on known province
        viewbox = None
        if known_province and known_province in PROVINCE_BBOXES:
            # Use province-specific bbox for higher accuracy
            viewbox = PROVINCE_BBOXES[known_province]
            logger.info(f"Using province bbox for '{known_province}': {viewbox}")
        else:
            # Fallback to Vietnam-wide bbox
            # Vietnam coordinates: SW(8.18, 102.14) to NE(23.39, 109.46)
            viewbox = '102.14,8.18,109.46,23.39'
            logger.info("Using Vietnam-wide bbox")

        if viewbox:
            params['viewbox'] = viewbox  # left,bottom,right,top
            params['bounded'] = 1  # Strict: only return results within viewbox

        headers = {'User-Agent': USER_AGENT}

        logger.info(f"Calling OSM Nominatim for: {address[:60]}...")

        response = requests.get(
            f"{NOMINATIM_BASE_URL}/search",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()
        results = response.json()

        if results and len(results) > 0:
            logger.info(f"OSM geocoding success: {results[0].get('display_name', 'N/A')[:60]}")
            return results[0]

        logger.warning(f"⚠️ OSM không tìm thấy kết quả: {address[:60]}")
        return None

    except requests.exceptions.Timeout:
        logger.warning(f"⚠️ OSM timeout sau {REQUEST_TIMEOUT}s: {address[:60]}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ OSM request thất bại: {e}")
        return None
    except Exception as e:
        logger.error(f"OSM geocoding unexpected error: {e}")
        return None


def parse_osm_to_candidates(osm_result: Dict) -> List[Dict]:
    """
    Parse OSM result into candidate format.
    May return multiple interpretations.

    OSM address components:
    - city/state/province: Province level (Hà Nội, Hồ Chí Minh)
    - city_district/county: District level (Ba Đình, Quận 1)
    - suburb/neighbourhood/quarter: Ward level (Điện Biên, Phường 1)
    - road: Street name
    - house_number: House number

    Args:
        osm_result: OSM API response

    Returns:
        List of candidate dicts

    Example:
        >>> osm_result = {'address': {'city': 'Hà Nội', 'city_district': 'Ba Đình', ...}}
        >>> parse_osm_to_candidates(osm_result)
        [
            {
                'province': 'ha noi',
                'district': 'ba dinh',
                'ward': 'dien bien',
                'source': 'osm_nominatim',
                'confidence': 0.85,
                ...
            }
        ]
    """
    if not osm_result:
        return []

    osm_address = osm_result.get('address', {})
    importance = osm_result.get('importance', 0.5)

    # Debug: Log OSM address components
    logger.debug(f"OSM address fields: {list(osm_address.keys())}")

    # Extract and normalize
    # Try multiple fields for each level (OSM Vietnamese addresses vary)
    province_raw = (
        osm_address.get('city') or
        osm_address.get('state') or
        osm_address.get('province') or
        osm_address.get('region')
    )
    province = _normalize_osm_field(province_raw)
    logger.debug(f"Province: '{province_raw}' → '{province}'")

    district_raw = (
        osm_address.get('city_district') or
        osm_address.get('county') or
        osm_address.get('municipality') or
        osm_address.get('town') or
        osm_address.get('historic')  # NEW: OSM Vietnam often uses 'historic' for districts
    )
    district = _normalize_osm_field(district_raw)
    logger.debug(f"District: '{district_raw}' → '{district}'")

    ward_raw = (
        osm_address.get('suburb') or
        osm_address.get('neighbourhood') or
        osm_address.get('quarter') or
        osm_address.get('hamlet')
    )
    ward = _normalize_osm_field(ward_raw)
    logger.debug(f"Ward: '{ward_raw}' → '{ward}'")

    candidates = []

    # Main interpretation
    if province or district or ward:
        at_rule = 0
        if ward:
            at_rule = 3
        elif district:
            at_rule = 2
        elif province:
            at_rule = 1

        # OSM importance → confidence proxy (scale to 0.5-0.95)
        # OSM importance is usually 0.0-1.0, higher = more important location
        base_confidence = 0.5 + (importance * 0.45)

        candidates.append({
            'province': province,
            'district': district,
            'ward': ward,
            'province_score': 1.0 if province else 0,
            'district_score': 1.0 if district else 0,
            'ward_score': 1.0 if ward else 0,
            'match_type': 'osm',
            'source': 'osm_nominatim',
            'at_rule': at_rule,
            'confidence': base_confidence,
            'osm_lat': osm_result.get('lat'),
            'osm_lon': osm_result.get('lon'),
            'osm_importance': importance,
            'osm_display_name': osm_result.get('display_name')
        })

        logger.debug(f"Created OSM candidate: {province}/{district}/{ward} (importance: {importance:.3f})")

    # Alternative interpretation: suburb as district
    # (OSM sometimes misclassifies suburb as ward when it should be district)
    if ward and not district:
        candidates.append({
            'province': province,
            'district': ward,  # Reinterpret suburb as district
            'ward': None,
            'province_score': 1.0 if province else 0,
            'district_score': 0.8,  # Lower confidence for reinterpretation
            'ward_score': 0,
            'match_type': 'osm',
            'source': 'osm_nominatim_alt',
            'at_rule': 2 if province else 1,
            'confidence': base_confidence * 0.85,  # Penalty for reinterpretation
            'osm_lat': osm_result.get('lat'),
            'osm_lon': osm_result.get('lon'),
            'osm_importance': importance,
            'interpretation': 'osm_suburb_as_district'
        })

        logger.debug(f"Created OSM alternative candidate: suburb '{ward}' as district")

    logger.info(f"Parsed {len(candidates)} candidates from OSM result")

    return candidates


def _normalize_osm_field(value: Optional[str]) -> Optional[str]:
    """
    Normalize OSM field to match database format.
    Strips Vietnamese administrative prefixes (Huyện, Thành phố, etc.)

    Args:
        value: OSM field value (may have diacritics, mixed case, with prefixes)
        Example: "Huyện Thanh Trì" → "thanh tri"
                 "Thành phố Hà Nội" → "ha noi"

    Returns:
        Normalized value (lowercase, no diacritics, no prefixes)
    """
    if not value:
        return None

    from .text_utils import normalize_address, strip_admin_prefixes

    # Step 1: Normalize (remove accents, lowercase, etc.)
    normalized = normalize_address(value)

    # Step 2: Strip Vietnamese administrative prefixes
    # OSM often includes: "huyen", "thanh pho", "quan", "phuong", "thi xa"
    stripped = strip_admin_prefixes(normalized)

    return stripped


if __name__ == "__main__":
    # Test geocoding
    print("=" * 80)
    print("OSM GEOCODING TEST")
    print("=" * 80)

    test_addresses = [
        "Phường Điện Biên, Quận Ba Đình, Hà Nội",
        "Thanh Trì, Hà Nội",
        "Văn Điển, Thanh Trì, Hà Nội",
        "Quận 1, Hồ Chí Minh"
    ]

    for address in test_addresses:
        print(f"\n{'='*80}")
        print(f"Address: {address}")
        print(f"{'='*80}")

        result = geocode_address(address)

        if result:
            print(f"✅ Success")
            print(f"  Display name: {result.get('display_name')}")
            print(f"  Coordinates: ({result.get('lat')}, {result.get('lon')})")
            print(f"  Importance: {result.get('importance', 0):.3f}")

            # Parse to candidates
            candidates = parse_osm_to_candidates(result)
            print(f"\n  Candidates generated: {len(candidates)}")

            for i, candidate in enumerate(candidates, 1):
                print(f"\n  {i}. Province: {candidate.get('province')}")
                print(f"     District: {candidate.get('district')}")
                print(f"     Ward: {candidate.get('ward')}")
                print(f"     Source: {candidate.get('source')}")
                print(f"     Confidence: {candidate.get('confidence', 0):.2f}")
        else:
            print(f"❌ No results or failed")

        # Wait for rate limit
        time.sleep(1.1)
