#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Vietnamese Administrative Divisions from vietnam_dataset API

API Source: https://github.com/thien0291/vietnam_dataset
- Index: https://cdn.jsdelivr.net/gh/thien0291/vietnam_dataset@1.0.0/Index.json
- Province data: https://cdn.jsdelivr.net/gh/thien0291/vietnam_dataset@1.0.0/data/{CODE}.json

Output: JSON files saved to data/vietnam_dataset/
"""

import json
import requests
from pathlib import Path
from typing import Dict, Any
import time


# Constants
BASE_URL = "https://cdn.jsdelivr.net/gh/thien0291/vietnam_dataset@1.0.0"
INDEX_URL = f"{BASE_URL}/Index.json"
OUTPUT_DIR = Path(__file__).parent / "data" / "vietnam_dataset"
PROVINCES_DIR = OUTPUT_DIR / "provinces"
DELAY_BETWEEN_REQUESTS = 0.2  # seconds (to be respectful to CDN)


def fetch_json(url: str) -> Dict[str, Any]:
    """
    Fetch JSON data from URL

    Args:
        url: URL to fetch

    Returns:
        Parsed JSON data
    """
    print(f"Fetching: {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def save_json(data: Dict[str, Any], filepath: Path):
    """
    Save data to JSON file

    Args:
        data: Data to save
        filepath: Output file path
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


def fetch_index() -> Dict[str, Any]:
    """
    Fetch index of all provinces

    Returns:
        Dictionary with province names as keys and {code, file_path} as values
    """
    print("\n" + "=" * 80)
    print("FETCHING INDEX")
    print("=" * 80)

    index_data = fetch_json(INDEX_URL)

    # Save index
    save_json(index_data, OUTPUT_DIR / "index.json")

    print(f"Found {len(index_data)} provinces")
    return index_data


def fetch_province_data(province_name: str, province_code: str) -> Dict[str, Any]:
    """
    Fetch data for a single province

    Args:
        province_name: Name of province
        province_code: Code of province (e.g., "SG", "HN")

    Returns:
        Province data dictionary
    """
    url = f"{BASE_URL}/data/{province_code}.json"
    data = fetch_json(url)

    # Save individual province file
    filename = f"{province_code}.json"
    save_json(data, PROVINCES_DIR / filename)

    return data


def fetch_all_provinces(index_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data for all provinces

    Args:
        index_data: Index data from API

    Returns:
        Dictionary with all province data
    """
    print("\n" + "=" * 80)
    print("FETCHING PROVINCE DATA")
    print("=" * 80)

    all_data = {}
    total = len(index_data)

    for i, (province_name, province_info) in enumerate(index_data.items(), 1):
        province_code = province_info['code']
        print(f"\n[{i}/{total}] {province_name} ({province_code})")

        try:
            province_data = fetch_province_data(province_name, province_code)
            all_data[province_name] = province_data

            # Be respectful to CDN
            if i < total:
                time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            print(f"ERROR: Failed to fetch {province_name}: {e}")
            continue

    return all_data


def create_summary(all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create summary statistics

    Args:
        all_data: All province data

    Returns:
        Summary dictionary
    """
    total_provinces = len(all_data)
    total_districts = sum(len(p.get('district', [])) for p in all_data.values())
    total_wards = sum(
        len(d.get('ward', []))
        for p in all_data.values()
        for d in p.get('district', [])
    )
    total_streets = sum(
        len(d.get('street', []))
        for p in all_data.values()
        for d in p.get('district', [])
    )

    return {
        'total_provinces': total_provinces,
        'total_districts': total_districts,
        'total_wards': total_wards,
        'total_streets': total_streets,
        'provinces': list(all_data.keys())
    }


def main():
    """Main execution"""
    print("=" * 80)
    print("VIETNAM ADMINISTRATIVE DIVISIONS FETCHER")
    print("=" * 80)
    print(f"Source: {BASE_URL}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 80)

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVINCES_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch index
    index_data = fetch_index()

    # Step 2: Fetch all provinces
    all_data = fetch_all_provinces(index_data)

    # Step 3: Save combined data
    print("\n" + "=" * 80)
    print("SAVING COMBINED DATA")
    print("=" * 80)
    save_json(all_data, OUTPUT_DIR / "all_provinces.json")

    # Step 4: Create and save summary
    print("\n" + "=" * 80)
    print("CREATING SUMMARY")
    print("=" * 80)
    summary = create_summary(all_data)
    save_json(summary, OUTPUT_DIR / "summary.json")

    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Provinces: {summary['total_provinces']}")
    print(f"Districts: {summary['total_districts']}")
    print(f"Wards: {summary['total_wards']}")
    print(f"Streets: {summary['total_streets']}")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("COMPLETED")
    print("=" * 80)
    print(f"\nFiles saved to: {OUTPUT_DIR}")
    print(f"  - index.json (province list)")
    print(f"  - all_provinces.json (all data combined)")
    print(f"  - summary.json (statistics)")
    print(f"  - provinces/*.json (individual provinces)")
    print("=" * 80)


if __name__ == "__main__":
    main()
