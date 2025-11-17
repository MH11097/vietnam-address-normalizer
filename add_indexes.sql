-- Add indexes to admin_division_migration table for faster queries
-- This script adds indexes to support efficient lookup of old-to-new address mappings

-- Index for ward-level queries (exact match: old_province + old_district + old_ward)
CREATE INDEX IF NOT EXISTS idx_old_ward
ON admin_division_migration(old_province, old_district, old_ward);

-- Index for district-level queries (all wards in a district: old_province + old_district)
CREATE INDEX IF NOT EXISTS idx_old_district
ON admin_division_migration(old_province, old_district);

-- Index for province-level queries (all mappings from a province: old_province)
CREATE INDEX IF NOT EXISTS idx_old_province
ON admin_division_migration(old_province);

-- Analyze table to update query optimizer statistics
ANALYZE admin_division_migration;
