"""
TSDB Address Mapping Script
============================
Process địa chỉ từ file tsdb_address.parquet qua pipeline mapping.

Usage:
    python scripts/process_tsdb.py
    python scripts/process_tsdb.py --limit 1000  # Test với 1000 records
    python scripts/process_tsdb.py --workers 8   # Số worker processes
"""
import sys
import os
import argparse
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial

import pandas as pd
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processors.phase1_preprocessing import preprocess
from src.processors.phase2_structural import structural_parse
from src.processors.phase3_extraction import extract_components
from src.processors.phase4_candidates import generate_candidates
from src.processors.phase5_validation import validate_and_rank
from src.processors.phase6_postprocessing import postprocess
from src.utils.text_utils import normalize_address
from src.utils.db_utils import get_streets_by_district, get_streets_by_province
from src.utils.matching_utils import ensemble_fuzzy_score


def lookup_street_fuzzy(street_text, province, district=None, threshold=0.90):
    """
    Lookup street using same methodology as ward extraction.
    Follows pattern: normalize → exact match → fuzzy match

    Args:
        street_text: Raw street address text (EOM_dia_chi_cleaned)
        province: Normalized province name from extraction
        district: Normalized district name from extraction (optional)
        threshold: Fuzzy match threshold (default: 0.90)

    Returns:
        Street name (original with accents) or None
    """
    # Skip empty input
    if not street_text or pd.isna(street_text) or str(street_text).strip() == '':
        return None

    if not province:
        return None

    street_text = str(street_text).strip()

    # Step 1: Normalize with context-aware expansion
    street_normalized = normalize_address(
        street_text,
        province_context=province,
        district_context=district
    )

    if not street_normalized:
        return None

    # Step 2: Get scoped candidates from database
    if district:
        # Narrow scope: Get streets in specific district
        street_records = get_streets_by_district(province, district)
    else:
        # Broad scope: Get all streets in province
        street_records = get_streets_by_province(province)

    if not street_records:
        return None

    # Build set for exact match check
    street_set = {s['street_name_normalized']: s['street_name'] for s in street_records}

    # Step 3: Exact match first (O(1))
    if street_normalized in street_set:
        return street_set[street_normalized]

    # Step 4: Fuzzy match using ensemble_fuzzy_score()
    best_match = None
    best_score = 0.0

    for record in street_records:
        candidate_name = record['street_name_normalized']

        # Calculate fuzzy score (100% Levenshtein + substring bonus)
        score = ensemble_fuzzy_score(
            street_normalized,
            candidate_name,
            log=False,
            has_district_context=bool(district)  # Context-aware substring bonus
        )

        if score >= threshold and score > best_score:
            best_score = score
            best_match = record['street_name']  # Original name with accents

    return best_match


def process_single_address(row_data):
    """
    Process một địa chỉ qua pipeline mapping.

    Args:
        row_data: tuple (index, address, eom_dia_chi_cleaned)

    Returns:
        dict với kết quả mapping
    """
    idx, address, eom_dia_chi = row_data

    # Skip empty addresses
    if not address or pd.isna(address) or str(address).strip() == '':
        return {
            'index': idx,
            'parsed_province': None,
            'parsed_district': None,
            'parsed_ward': None,
            'confidence_score': 0.0,
            'remaining_address': None,
            'match_type': None,
            'parsed_street': None,
            'processing_time_ms': 0
        }

    try:
        address = str(address).strip()

        # Phase 1: Preprocessing (no known hints - pure extraction)
        p1 = preprocess(address, province_known=None)

        # Phase 2: Structural Parsing
        structural_result = structural_parse(
            p1['normalized'],
            province_known=None,
            district_known=None
        )

        # Phase 3: Extraction
        if structural_result['confidence'] >= 0.85:
            # Use structural result
            from src.utils.extraction_utils import lookup_full_names

            province = structural_result.get('province')
            district = structural_result.get('district')
            ward = structural_result.get('ward')

            province_full, district_full, ward_full = lookup_full_names(province, district, ward)

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
                    'confidence': structural_result['confidence'],
                    'source': f"structural_{structural_result['method']}",
                    'hierarchy_valid': True,
                    'match_level': match_level,
                    'at_rule': match_level,
                    'match_type': 'exact',
                    'final_confidence': structural_result['confidence']
                }

            p2 = {
                'candidates': [candidate] if candidate else [],
                'potential_provinces': [(province, 1.0, (-1, -1))] if province else [],
                'potential_districts': [(district, 1.0, (-1, -1))] if district else [],
                'potential_wards': [(ward, 1.0, (-1, -1))] if ward else [],
                'potential_streets': [],
                'processing_time_ms': 0,
                'source': 'structural',
                'normalized_text': p1.get('normalized', ''),
                'original_address': address
            }
        else:
            # Fallback to n-gram extraction
            p2 = extract_components(p1, None, None)

        # Phase 4: Generate Candidates
        p3 = generate_candidates(p2)

        # Phase 5: Validation & Ranking
        p4 = validate_and_rank(p3)

        # Phase 6: Postprocessing
        p5 = postprocess(p4, {
            'original_address': address,
            'matched_components': p4.get('best_match', {})
        })

        # Extract results
        best = p4.get('best_match')
        formatted = p5.get('formatted_output', {})

        # Post-extraction street lookup
        matched_street = None
        if best:
            province = best.get('province')  # normalized
            district = best.get('district')  # normalized

            if province and district and eom_dia_chi:
                matched_street = lookup_street_fuzzy(
                    eom_dia_chi,
                    province,
                    district,
                    threshold=0.90
                )

        total_time = sum([
            p1.get('processing_time_ms', 0),
            p2.get('processing_time_ms', 0),
            p3.get('processing_time_ms', 0),
            p4.get('processing_time_ms', 0),
            p5.get('processing_time_ms', 0)
        ])

        return {
            'index': idx,
            'parsed_province': formatted.get('province'),
            'parsed_district': formatted.get('district'),
            'parsed_ward': formatted.get('ward'),
            'confidence_score': best.get('confidence', 0.0) if best else 0.0,
            'remaining_address': formatted.get('remaining_1', ''),
            'match_type': best.get('match_type') if best else None,
            'parsed_street': matched_street,
            'processing_time_ms': total_time
        }

    except Exception as e:
        return {
            'index': idx,
            'parsed_province': None,
            'parsed_district': None,
            'parsed_ward': None,
            'confidence_score': 0.0,
            'remaining_address': None,
            'match_type': f'error: {str(e)[:50]}',
            'parsed_street': None,
            'processing_time_ms': 0
        }


def main():
    parser = argparse.ArgumentParser(description='Process TSDB addresses')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of records to process')
    parser.add_argument('--workers', type=int, default=None, help='Number of worker processes')
    parser.add_argument('--input', type=str, default=None, help='Input parquet file path')
    parser.add_argument('--output', type=str, default=None, help='Output parquet file path')

    args = parser.parse_args()

    # Paths
    data_dir = project_root / 'data'
    input_file = Path(args.input) if args.input else data_dir / 'tsdb_address.parquet'
    output_file = Path(args.output) if args.output else data_dir / 'tsdb_address_mapped.parquet'

    # Load data
    print(f"Loading data from: {input_file}")
    df = pd.read_parquet(input_file)
    print(f"Total records: {len(df)}")

    # Apply limit if specified
    if args.limit:
        df = df.head(args.limit)
        print(f"Processing first {args.limit} records")

    # Concatenate 4 columns as raw address (separated by comma)
    def concat_address(row):
        parts = []
        for col in ['Dia_chi_TSDB',	'Duong',	'Phuong',	'Quan',	'Tinh']:
            val = row[col]
            if val and not pd.isna(val) and str(val).strip():
                parts.append(str(val).strip())
        return ', '.join(parts)

    # Add raw_address column to dataframe
    df['raw_address'] = df.apply(concat_address, axis=1)

    # Prepare data for processing
    row_data = [
        (idx, row['raw_address'], row['Dia_chi_TSDB'])
        for idx, row in df.iterrows()
    ]

    # Number of workers
    n_workers = args.workers if args.workers else max(1, cpu_count() - 1)
    print(f"Using {n_workers} workers")

    # Process in parallel with progress bar
    print(f"\nProcessing {len(row_data)} addresses...")

    results = []
    with Pool(n_workers) as pool:
        for result in tqdm(
            pool.imap(process_single_address, row_data, chunksize=100),
            total=len(row_data),
            desc="Mapping addresses"
        ):
            results.append(result)

    # Convert results to DataFrame
    results_df = pd.DataFrame(results)
    results_df = results_df.set_index('index')

    # Merge with original data
    df = df.join(results_df)

    # Select only 4 EOM columns + 4 parsed columns
    output_columns = [
        'raw_address',
        'Dia_chi_TSDB',
        'Duong',
        'Phuong',
        'Quan',
        'Tinh',
        'parsed_province',
        'parsed_district',
        'parsed_ward',
        'parsed_street'
    ]
    df_output = df[output_columns]

    # Save output
    print(f"\nSaving results to: {output_file}")
    df_output.to_parquet(output_file, index=False)

    # Statistics
    total = len(df_output)
    mapped = df_output['parsed_province'].notna().sum()
    street_mapped = df_output['parsed_street'].notna().sum()

    print(f"\n{'='*50}")
    print("PROCESSING COMPLETE")
    print(f"{'='*50}")
    print(f"Total records:     {total:,}")
    print(f"Mapped:            {mapped:,} ({mapped/total*100:.1f}%)")
    print(f"Street mapped:     {street_mapped:,} ({street_mapped/total*100:.1f}%)")
    print(f"Output saved to:   {output_file}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
