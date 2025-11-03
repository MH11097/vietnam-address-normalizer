-- ============================================================================
-- Normalize Leading Zeros in Ward and District Names
-- ============================================================================
-- Purpose: Remove leading zeros from single-digit ward/district numbers
--          to ensure consistent matching (01→1, 02→2, etc.)
--
-- Affected: ~150 records nationwide
-- Database: data/address.db
-- Table: admin_divisions
--
-- Examples:
--   - "Phường 01" → "Phường 1" (ward_name_normalized: "01" → "1")
--   - "Quận 08" → "Quận 8" (district_name_normalized: "08" → "8")
--   - "Phường 10" stays unchanged (not a leading zero case)
-- ============================================================================

-- Create backup of current state (for rollback if needed)
BEGIN TRANSACTION;

-- ============================================================================
-- WARD NAME NORMALIZATION (01-09)
-- ============================================================================

-- Update ward_name_normalized: 01 → 1
UPDATE admin_divisions
SET ward_name_normalized = '1'
WHERE ward_name_normalized = '01';

-- Update ward_name_normalized: 02 → 2
UPDATE admin_divisions
SET ward_name_normalized = '2'
WHERE ward_name_normalized = '02';

-- Update ward_name_normalized: 03 → 3
UPDATE admin_divisions
SET ward_name_normalized = '3'
WHERE ward_name_normalized = '03';

-- Update ward_name_normalized: 04 → 4
UPDATE admin_divisions
SET ward_name_normalized = '4'
WHERE ward_name_normalized = '04';

-- Update ward_name_normalized: 05 → 5
UPDATE admin_divisions
SET ward_name_normalized = '5'
WHERE ward_name_normalized = '05';

-- Update ward_name_normalized: 06 → 6
UPDATE admin_divisions
SET ward_name_normalized = '6'
WHERE ward_name_normalized = '06';

-- Update ward_name_normalized: 07 → 7
UPDATE admin_divisions
SET ward_name_normalized = '7'
WHERE ward_name_normalized = '07';

-- Update ward_name_normalized: 08 → 8
UPDATE admin_divisions
SET ward_name_normalized = '8'
WHERE ward_name_normalized = '08';

-- Update ward_name_normalized: 09 → 9
UPDATE admin_divisions
SET ward_name_normalized = '9'
WHERE ward_name_normalized = '09';

-- ============================================================================
-- DISTRICT NAME NORMALIZATION (01-09)
-- ============================================================================

-- Update district_name_normalized: 01 → 1
UPDATE admin_divisions
SET district_name_normalized = '1'
WHERE district_name_normalized = '01';

-- Update district_name_normalized: 02 → 2
UPDATE admin_divisions
SET district_name_normalized = '2'
WHERE district_name_normalized = '02';

-- Update district_name_normalized: 03 → 3
UPDATE admin_divisions
SET district_name_normalized = '3'
WHERE district_name_normalized = '03';

-- Update district_name_normalized: 04 → 4
UPDATE admin_divisions
SET district_name_normalized = '4'
WHERE district_name_normalized = '04';

-- Update district_name_normalized: 05 → 5
UPDATE admin_divisions
SET district_name_normalized = '5'
WHERE district_name_normalized = '05';

-- Update district_name_normalized: 06 → 6
UPDATE admin_divisions
SET district_name_normalized = '6'
WHERE district_name_normalized = '06';

-- Update district_name_normalized: 07 → 7
UPDATE admin_divisions
SET district_name_normalized = '7'
WHERE district_name_normalized = '07';

-- Update district_name_normalized: 08 → 8
UPDATE admin_divisions
SET district_name_normalized = '8'
WHERE district_name_normalized = '08';

-- Update district_name_normalized: 09 → 9
UPDATE admin_divisions
SET district_name_normalized = '9'
WHERE district_name_normalized = '09';

-- ============================================================================
-- VERIFICATION QUERIES (run after commit to verify changes)
-- ============================================================================

-- Show updated records count
SELECT 'Ward updates completed' AS status,
       COUNT(*) AS records_updated
FROM admin_divisions
WHERE ward_name_normalized IN ('1','2','3','4','5','6','7','8','9');

SELECT 'District updates completed' AS status,
       COUNT(*) AS records_updated
FROM admin_divisions
WHERE district_name_normalized IN ('1','2','3','4','5','6','7','8','9');

-- Verify no leading zeros remain (should return 0)
SELECT COUNT(*) AS leading_zeros_remaining
FROM admin_divisions
WHERE ward_name_normalized IN ('01','02','03','04','05','06','07','08','09')
   OR district_name_normalized IN ('01','02','03','04','05','06','07','08','09');

COMMIT;
