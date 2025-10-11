"""
Address Parsing Pipeline - Orchestrates all 5 phases

Simple pipeline that chains:
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
"""
from typing import Dict, Any
import time
from .processors import phase1_preprocessing
from .processors import phase2_extraction
from .processors import phase3_candidates
from .processors import phase4_validation
from .processors import phase5_postprocessing


class AddressPipeline:
    """
    Main pipeline orchestrator for address parsing.

    Executes all 5 phases in sequence and collects results.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize pipeline with optional configuration.

        Args:
            config: Configuration dict (for future use)
        """
        self.config = config or {}
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0
        }

    def process(
        self,
        raw_address: str,
        province_known: str = None,
        district_known: str = None
    ) -> Dict[str, Any]:
        """
        Process a single address through all 5 phases.

        Args:
            raw_address: Raw input address string
            province_known: Known province from raw data (optional, trusted 100%)
            district_known: Known district from raw data (optional, trusted 100%)

        Returns:
            Dictionary containing:
            - final_output: Formatted result from Phase 5
            - intermediate_results: Results from each phase
            - total_time_ms: Total processing time
            - status: 'success' or 'failed'

        Example:
            >>> pipeline = AddressPipeline()
            >>> result = pipeline.process("P. Điện Biên, Q. Ba Đình, HN")
            >>> print(result['final_output']['province'])
            'Hà Nội'
        """
        start_time = time.time()

        # Track results from each phase
        phase_results = {}

        try:
            # Phase 1: Preprocessing (with province context for abbreviation expansion)
            phase1_result = phase1_preprocessing.preprocess(raw_address, province_known=province_known)
            phase_results['phase1'] = phase1_result

            # Phase 2: Extraction (với known values)
            phase2_result = phase2_extraction.extract_components(
                phase1_result,
                province_known=province_known,
                district_known=district_known
            )
            phase_results['phase2'] = phase2_result

            # Phase 3: Candidate Generation
            # Pass Phase 2 result directly (contains candidates list)
            phase3_result = phase3_candidates.generate_candidates(phase2_result)
            phase_results['phase3'] = phase3_result

            # Phase 4: Validation & Ranking
            phase4_result = phase4_validation.validate_and_rank(phase3_result)
            phase_results['phase4'] = phase4_result

            # Phase 5: Post-processing
            # Extract remaining address
            best_match = phase4_result.get('best_match', {})
            remaining_address = phase5_postprocessing.extract_remaining_address(
                raw_address,
                {
                    'province': best_match.get('province', ''),
                    'district': best_match.get('district', ''),
                    'ward': best_match.get('ward', '')
                }
            )

            extraction_metadata = {
                'remaining': remaining_address,
                'original': raw_address
            }

            phase5_result = phase5_postprocessing.postprocess(
                phase4_result,
                extraction_metadata
            )
            phase_results['phase5'] = phase5_result

            # Extract final output
            final_output = phase5_result['formatted_output']
            quality_flag = phase5_result['quality_flag']

            # Determine status
            status = 'success' if quality_flag != 'failed' else 'failed'

            # Update stats
            self.stats['total_processed'] += 1
            if status == 'success':
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1

        except Exception as e:
            # Handle errors
            status = 'error'
            final_output = {'error': str(e)}
            quality_flag = 'failed'
            phase_results['error'] = {'message': str(e), 'type': type(e).__name__}

            self.stats['total_processed'] += 1
            self.stats['failed'] += 1

        # Calculate total time
        total_time = (time.time() - start_time) * 1000

        return {
            'raw_input': raw_address,
            'final_output': final_output,
            'quality_flag': quality_flag,
            'status': status,
            'intermediate_results': phase_results,
            'total_time_ms': round(total_time, 3)
        }

    def process_batch(self, addresses: list) -> list:
        """
        Process multiple addresses.

        Args:
            addresses: List of raw address strings

        Returns:
            List of result dictionaries
        """
        results = []

        for address in addresses:
            result = self.process(address)
            results.append(result)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            'success_rate': (
                self.stats['successful'] / self.stats['total_processed']
                if self.stats['total_processed'] > 0 else 0
            )
        }

    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0
        }


if __name__ == "__main__":
    # Test pipeline
    test_addresses = [
        "P. Điện Biên, Q. Ba Đình, HN",
        "19 Hoàng Diệu, Phường Điện Biên, Quận Ba Đình, Hà Nội",
        "Q. 1, TP. HCM",
        "123 Lê Lợi, Phường Bến Thành, Quận 1, Hồ Chí Minh"
    ]

    print("=" * 80)
    print("PIPELINE TEST - Full Flow")
    print("=" * 80)

    pipeline = AddressPipeline()

    for i, address in enumerate(test_addresses, 1):
        print(f"\n{i}. Processing: {address}")
        print("-" * 80)

        result = pipeline.process(address)

        print(f"Status: {result['status']}")
        print(f"Quality: {result['quality_flag']}")
        print(f"Total time: {result['total_time_ms']}ms")

        output = result['final_output']
        if 'error' not in output:
            print(f"\nResult:")
            print(f"  Province:  {output.get('province')}")
            print(f"  District:  {output.get('district')}")
            print(f"  Ward:      {output.get('ward')}")
            print(f"  STATE:     {output.get('state_code')}")
            print(f"  COUNTY:    {output.get('county_code')}")
            print(f"  Remaining: {output.get('remaining_1')}")
            print(f"  At rule:   {output.get('at_rule')}")
            print(f"  Confidence: {output.get('confidence'):.3f}")
        else:
            print(f"\nError: {output['error']}")

        # Show phase timings
        print(f"\nPhase timings:")
        intermediate = result.get('intermediate_results', {})
        for phase_name, phase_result in intermediate.items():
            if isinstance(phase_result, dict) and 'processing_time_ms' in phase_result:
                print(f"  {phase_name}: {phase_result['processing_time_ms']}ms")

    print("\n" + "=" * 80)
    print("Pipeline Statistics")
    print("=" * 80)
    stats = pipeline.get_stats()
    print(f"Total processed: {stats['total_processed']}")
    print(f"Successful:      {stats['successful']}")
    print(f"Failed:          {stats['failed']}")
    print(f"Success rate:    {stats['success_rate']:.1%}")
