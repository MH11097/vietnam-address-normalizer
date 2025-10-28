#!/usr/bin/env python3
"""
Main entry point for address parsing.

Simple and clean interface:
- Process single address
- Process batch from file
- Output results to CSV
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from .pipeline import AddressPipeline


def process_single(address: str, output_format: str = 'text'):
    """
    Process a single address.

    Args:
        address: Raw address string
        output_format: 'text' or 'json'
    """
    pipeline = AddressPipeline()
    result = pipeline.process(address)

    if output_format == 'json':
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Text format
        print(f"\nInput:  {result['raw_input']}")
        print(f"Status: {result['status']} ({result['quality_flag']})")
        print(f"Time:   {result['total_time_ms']}ms")

        output = result['final_output']
        if 'error' not in output:
            print(f"\nResult:")
            print(f"  Province:  {output.get('province')}")
            print(f"  District:  {output.get('district')}")
            print(f"  Ward:      {output.get('ward')}")
            print(f"  STATE:     {output.get('state_code')}")
            print(f"  COUNTY:    {output.get('county_code')}")
            print(f"  Remaining: {output.get('remaining_1')}")
            print(f"  Confidence: {output.get('confidence', 0):.3f}")
        else:
            print(f"\nError: {output['error']}")


def process_batch(input_file: str, output_file: str = None):
    """
    Process addresses from CSV file.

    Expected CSV columns: Either just addresses, or with COT1, COT2, COT3

    Args:
        input_file: Path to input CSV
        output_file: Path to output CSV (optional)
    """
    pipeline = AddressPipeline()

    # Read input
    print(f"Reading from: {input_file}")
    addresses = []

    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try to combine multiple columns if they exist
                if 'COT1' in row or 'cot1' in row:
                    # Legacy format
                    parts = [
                        row.get('COT1', '') or row.get('cot1', ''),
                        row.get('COT2', '') or row.get('cot2', ''),
                        row.get('COT3', '') or row.get('cot3', '')
                    ]
                    address = ' '.join([p for p in parts if p]).strip()
                else:
                    # Assume first column is address
                    address = list(row.values())[0]

                if address:
                    addresses.append(address)

    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)

    print(f"Found {len(addresses)} addresses to process")

    # Process
    print("Processing...")
    results = pipeline.process_batch(addresses)

    # Categorize results by quality
    full_address = []
    partial_address = []
    province_only = []
    failed = []

    for result in results:
        quality = result['quality_flag']
        if quality == 'full_address':
            full_address.append(result)
        elif quality == 'partial_address':
            partial_address.append(result)
        elif quality == 'province_only':
            province_only.append(result)
        else:
            failed.append(result)

    # Print stats
    print(f"\nProcessing complete:")
    print(f"  Full address:     {len(full_address)}")
    print(f"  Partial address:  {len(partial_address)}")
    print(f"  Province only:    {len(province_only)}")
    print(f"  Failed:           {len(failed)}")

    stats = pipeline.get_stats()
    print(f"  Success rate:     {stats['success_rate']:.1%}")

    # Save results
    if output_file:
        save_path = Path(output_file)
        save_dir = save_path.parent
        save_name = save_path.stem

        # Create output directory if needed
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save categorized files
        save_results_to_csv(full_address, save_dir / f"{save_name}_full.csv")
        save_results_to_csv(partial_address, save_dir / f"{save_name}_partial.csv")
        save_results_to_csv(province_only, save_dir / f"{save_name}_province.csv")
        save_results_to_csv(failed, save_dir / f"{save_name}_failed.csv")

        print(f"\nResults saved to:")
        print(f"  {save_dir / f'{save_name}_full.csv'}")
        print(f"  {save_dir / f'{save_name}_partial.csv'}")
        print(f"  {save_dir / f'{save_name}_province.csv'}")
        print(f"  {save_dir / f'{save_name}_failed.csv'}")


def save_results_to_csv(results: list, filepath: Path):
    """Save results to CSV file."""
    if not results:
        return

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = [
            'raw_input', 'province', 'district', 'ward',
            'state_code', 'county_code',
            'remaining_1', 'remaining_2', 'remaining_3',
            'at_rule', 'confidence', 'quality_flag', 'total_time_ms'
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            output = result['final_output']
            row = {
                'raw_input': result['raw_input'],
                'province': output.get('province', ''),
                'district': output.get('district', ''),
                'ward': output.get('ward', ''),
                'state_code': output.get('state_code', ''),
                'county_code': output.get('county_code', ''),
                'remaining_1': output.get('remaining_1', ''),
                'remaining_2': output.get('remaining_2', ''),
                'remaining_3': output.get('remaining_3', ''),
                'at_rule': output.get('at_rule', 0),
                'confidence': output.get('confidence', 0),
                'quality_flag': result['quality_flag'],
                'total_time_ms': result['total_time_ms']
            }
            writer.writerow(row)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Vietnamese Address Parsing Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process single address
  python -m src.main -a "P. Điện Biên, Q. Ba Đình, HN"

  # Process from file
  python -m src.main -i input.csv -o results.csv

  # JSON output
  python -m src.main -a "Q. 1, TP. HCM" --json
        '''
    )

    parser.add_argument(
        '-a', '--address',
        help='Single address to process'
    )

    parser.add_argument(
        '-i', '--input',
        help='Input CSV file with addresses'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output CSV file path'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON (for single address)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.address and not args.input:
        parser.print_help()
        print("\nError: Either --address or --input must be provided")
        sys.exit(1)

    # Process
    if args.address:
        # Single address mode
        output_format = 'json' if args.json else 'text'
        process_single(args.address, output_format)

    elif args.input:
        # Batch mode
        if not args.output:
            print("Warning: No output file specified. Results will not be saved.")
            print("Use --output to specify output file.")
            response = input("Continue? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)

        process_batch(args.input, args.output)


if __name__ == '__main__':
    main()
