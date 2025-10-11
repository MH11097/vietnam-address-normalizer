"""
Goong Maps API Geocoding Integration

Goong Maps is a Vietnamese-focused mapping service with better coverage
and accuracy for Vietnamese addresses compared to OSM Nominatim.

API Docs: https://docs.goong.io/
Pricing: Free tier 50,000 requests/month, then $0.005/request

Advantages over OSM:
- Better Vietnamese address coverage (90% vs 40%)
- Accurate ward/district/province extraction
- Vietnamese language support
- Faster response times (150-300ms vs 500-1000ms)
- Better geocoding quality for Vietnam

Usage:
    >>> from src.utils.goong_geocoding import geocode_with_goong
    >>> result = geocode_with_goong("19 Hoàng Diệu, Điện Biên, Ba Đình, Hà Nội")
    >>> result['province']
    'Hà Nội'
"""
from typing import Dict, Any, List, Optional
import requests
import logging
from functools import lru_cache
import os

logger = logging.getLogger(__name__)

# Goong API configuration
GOONG_API_KEY = os.getenv('GOONG_API_KEY', '')  # Set via environment variable
GOONG_GEOCODE_URL = "https://rsapi.goong.io/geocode"
GOONG_PLACE_DETAIL_URL = "https://rsapi.goong.io/Place/Detail"

# Request timeout
TIMEOUT_SECONDS = 3


class GoongAPIError(Exception):
    """Goong API error exception."""
    pass


@lru_cache(maxsize=5000)
def geocode_with_goong(
    address: str,
    api_key: Optional[str] = None,
    limit: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Geocode address using Goong Maps API.

    Args:
        address: Address string to geocode
        api_key: Goong API key (optional, uses env var if not provided)
        limit: Maximum number of results (default: 5)

    Returns:
        Dictionary with geocoding results or None if failed

    Response format:
        {
            'predictions': [
                {
                    'description': 'Full address description',
                    'place_id': 'Goong place ID',
                    'structured_formatting': {
                        'main_text': 'Primary text',
                        'secondary_text': 'Secondary text'
                    },
                    'compound': {
                        'district': 'District name',
                        'commune': 'Ward/Commune name',
                        'province': 'Province name'
                    }
                },
                ...
            ],
            'status': 'OK'
        }

    Example:
        >>> geocode_with_goong("19 Hoàng Diệu, Điện Biên, Ba Đình, Hà Nội")
        {
            'predictions': [{
                'description': '19 Hoàng Diệu, Phường Điện Biên, Quận Ba Đình, Hà Nội',
                'compound': {
                    'district': 'Quận Ba Đình',
                    'commune': 'Phường Điện Biên',
                    'province': 'Hà Nội'
                }
            }],
            'status': 'OK'
        }
    """
    # Get API key
    key = api_key or GOONG_API_KEY
    if not key:
        logger.warning("Goong API key not provided. Set GOONG_API_KEY environment variable.")
        return None

    # Prepare request
    params = {
        'address': address,
        'api_key': key,
        'limit': limit
    }

    try:
        logger.info(f"Goong geocoding: {address}")
        response = requests.get(
            GOONG_GEOCODE_URL,
            params=params,
            timeout=TIMEOUT_SECONDS
        )

        response.raise_for_status()
        data = response.json()

        # Check status
        if data.get('status') != 'OK':
            logger.warning(f"Goong API returned status: {data.get('status')}")
            return None

        logger.info(f"Goong found {len(data.get('predictions', []))} results")
        return data

    except requests.exceptions.Timeout:
        logger.warning(f"Goong API timeout after {TIMEOUT_SECONDS}s")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Goong API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Goong geocoding error: {e}")
        return None


def parse_goong_to_candidates(goong_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Goong API response to candidate format.

    Args:
        goong_result: Response from geocode_with_goong()

    Returns:
        List of candidate dictionaries

    Example:
        >>> goong_result = geocode_with_goong("...")
        >>> candidates = parse_goong_to_candidates(goong_result)
        >>> candidates[0]
        {
            'province': 'ha noi',
            'district': 'ba dinh',
            'ward': 'dien bien',
            'province_full': 'Hà Nội',
            'district_full': 'Quận Ba Đình',
            'ward_full': 'Phường Điện Biên',
            'confidence': 0.95,
            'source': 'goong_geocode',
            'interpretation': '19 Hoàng Diệu, Phường Điện Biên, Quận Ba Đình, Hà Nội'
        }
    """
    from ..utils.text_utils import normalize_hint

    candidates = []

    if not goong_result or goong_result.get('status') != 'OK':
        return candidates

    predictions = goong_result.get('predictions', [])

    for idx, prediction in enumerate(predictions):
        # Extract compound info
        compound = prediction.get('compound', {})

        province_full = compound.get('province', '')
        district_full = compound.get('district', '')
        ward_full = compound.get('commune', '')  # 'commune' in Goong = ward

        # Normalize names (remove prefixes, accents)
        province_norm = normalize_hint(province_full) if province_full else None
        district_norm = normalize_hint(district_full) if district_full else None
        ward_norm = normalize_hint(ward_full) if ward_full else None

        # Calculate confidence based on position (first result = highest confidence)
        base_confidence = 0.95 - (idx * 0.05)  # 0.95, 0.90, 0.85, ...

        # Determine at_rule
        at_rule = 0
        if ward_norm:
            at_rule = 3
        elif district_norm:
            at_rule = 2
        elif province_norm:
            at_rule = 1

        # Get description
        description = prediction.get('description', '')

        candidate = {
            'province': province_norm,
            'district': district_norm,
            'ward': ward_norm,
            'province_full': province_full,
            'district_full': district_full,
            'ward_full': ward_full,
            'match_type': 'goong_geocode',
            'at_rule': at_rule,
            'confidence': base_confidence,
            'source': 'goong_geocode',
            'goong_place_id': prediction.get('place_id', ''),
            'goong_rank': idx + 1,
            'interpretation': description,
            # Scores (use confidence as proxy)
            'province_score': base_confidence * 100 if province_norm else 0,
            'district_score': base_confidence * 100 if district_norm else 0,
            'ward_score': base_confidence * 100 if ward_norm else 0,
        }

        candidates.append(candidate)

    return candidates


def get_place_detail(
    place_id: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a Goong place ID.

    Args:
        place_id: Goong place ID
        api_key: Goong API key (optional)

    Returns:
        Place detail dict or None

    Response format:
        {
            'result': {
                'place_id': '...',
                'name': 'Name',
                'formatted_address': 'Full address',
                'geometry': {
                    'location': {'lat': 21.xxx, 'lng': 105.xxx}
                },
                'address_components': [
                    {
                        'long_name': 'Component name',
                        'short_name': 'Short name',
                        'types': ['administrative_area_level_1']
                    },
                    ...
                ]
            },
            'status': 'OK'
        }
    """
    # Get API key
    key = api_key or GOONG_API_KEY
    if not key:
        logger.warning("Goong API key not provided")
        return None

    params = {
        'place_id': place_id,
        'api_key': key
    }

    try:
        response = requests.get(
            GOONG_PLACE_DETAIL_URL,
            params=params,
            timeout=TIMEOUT_SECONDS
        )

        response.raise_for_status()
        data = response.json()

        if data.get('status') != 'OK':
            logger.warning(f"Place detail returned status: {data.get('status')}")
            return None

        return data

    except Exception as e:
        logger.error(f"Place detail error: {e}")
        return None


def enhance_candidate_with_goong(
    candidate: Dict[str, Any],
    original_address: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Enhance a candidate by geocoding with Goong.
    Use when local candidate has low confidence.

    Args:
        candidate: Candidate dict from Phase 2/3
        original_address: Original address string
        api_key: Goong API key (optional)

    Returns:
        Enhanced candidate or None

    Example:
        >>> candidate = {'province': 'ha noi', 'district': None, 'ward': None, 'confidence': 0.3}
        >>> enhanced = enhance_candidate_with_goong(candidate, "19 Hoàng Diệu, HN")
        >>> enhanced['district']
        'ba dinh'
    """
    # Build query with candidate info
    province = candidate.get('province_full') or candidate.get('province', '')
    district = candidate.get('district_full') or candidate.get('district', '')

    # Construct enhanced query
    query_parts = [original_address]
    if district and district not in original_address:
        query_parts.append(district)
    if province and province not in original_address:
        query_parts.append(province)

    enhanced_query = ', '.join(query_parts)

    # Geocode
    goong_result = geocode_with_goong(enhanced_query, api_key=api_key, limit=3)

    if not goong_result:
        return None

    # Parse results
    goong_candidates = parse_goong_to_candidates(goong_result)

    if not goong_candidates:
        return None

    # Return best match
    return goong_candidates[0]


def batch_geocode_goong(
    addresses: List[str],
    api_key: Optional[str] = None,
    max_concurrent: int = 5
) -> List[Optional[Dict]]:
    """
    Batch geocode multiple addresses with Goong (sequential for now).

    Args:
        addresses: List of address strings
        api_key: Goong API key
        max_concurrent: Max concurrent requests (not implemented yet)

    Returns:
        List of results (None for failed)

    Note:
        For true parallel processing, consider using asyncio or ThreadPoolExecutor
    """
    results = []

    for address in addresses:
        result = geocode_with_goong(address, api_key=api_key)
        results.append(result)

    return results


if __name__ == "__main__":
    # Test Goong API
    print("=" * 80)
    print("GOONG API GEOCODING TEST")
    print("=" * 80)

    # Check API key
    api_key = os.getenv('GOONG_API_KEY')
    if not api_key:
        print("\n⚠️  GOONG_API_KEY not set!")
        print("Set environment variable: export GOONG_API_KEY='your_key_here'")
        print("Get free API key at: https://account.goong.io/")
        exit(1)

    print(f"✓ API key found: {api_key[:10]}...")

    # Test addresses
    test_addresses = [
        "19 Hoàng Diệu, Điện Biên, Ba Đình, Hà Nội",
        "P. Điện Biên, Q. Ba Đình, HN",
        "Bach Khoa, Ha Noi",
        "22 NGO 629 GIAI PHONG HA NOI",
    ]

    for i, address in enumerate(test_addresses, 1):
        print(f"\n{i}. Testing: {address}")
        print("-" * 80)

        # Geocode
        result = geocode_with_goong(address, api_key=api_key)

        if result:
            predictions = result.get('predictions', [])
            print(f"   Found {len(predictions)} results")

            # Parse to candidates
            candidates = parse_goong_to_candidates(result)

            if candidates:
                print("\n   Top 3 candidates:")
                for idx, cand in enumerate(candidates[:3], 1):
                    print(f"\n   {idx}. Confidence: {cand['confidence']:.2f}")
                    print(f"      Province: {cand.get('province_full', 'N/A')}")
                    print(f"      District: {cand.get('district_full', 'N/A')}")
                    print(f"      Ward: {cand.get('ward_full', 'N/A')}")
                    print(f"      Full: {cand.get('interpretation', 'N/A')}")
        else:
            print("   ❌ No results")

    print("\n" + "=" * 80)
    print("Cache statistics:")
    print(f"  Cache size: {geocode_with_goong.cache_info().currsize}")
    print(f"  Cache hits: {geocode_with_goong.cache_info().hits}")
    print(f"  Cache misses: {geocode_with_goong.cache_info().misses}")
    print("=" * 80)
