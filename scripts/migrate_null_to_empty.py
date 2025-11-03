"""
Migration script: Convert NULL values to empty strings in user_quality_ratings

This migration is needed to fix the UNIQUE constraint issue where SQLite
treats NULL != NULL, which can cause duplicate records.

Usage:
    python scripts/migrate_null_to_empty.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.db_utils import get_db_connection, DB_PATH


def migrate_null_values():
    """Convert all NULL values in known_province and known_district to empty strings"""

    print("="*60)
    print("Migrating NULL values to empty strings")
    print("="*60 + "\n")
    print(f"Database: {DB_PATH}\n")

    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check how many NULL values exist
            cursor.execute("""
                SELECT COUNT(*) FROM user_quality_ratings
                WHERE known_province IS NULL OR known_district IS NULL
            """)
            null_count = cursor.fetchone()[0]

            if null_count == 0:
                print("✅ No NULL values found - database is already clean!")
                return True

            print(f"Found {null_count} records with NULL values\n")

            # Show breakdown
            cursor.execute("""
                SELECT COUNT(*) FROM user_quality_ratings WHERE known_province IS NULL
            """)
            null_province = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM user_quality_ratings WHERE known_district IS NULL
            """)
            null_district = cursor.fetchone()[0]

            print(f"  - NULL in known_province: {null_province}")
            print(f"  - NULL in known_district: {null_district}\n")

            # Migrate NULL to empty string
            print("Migrating NULL → '' ...")

            cursor.execute("""
                UPDATE user_quality_ratings
                SET known_province = ''
                WHERE known_province IS NULL
            """)
            updated_province = cursor.rowcount

            cursor.execute("""
                UPDATE user_quality_ratings
                SET known_district = ''
                WHERE known_district IS NULL
            """)
            updated_district = cursor.rowcount

            conn.commit()

            print(f"✅ Updated {updated_province} records in known_province")
            print(f"✅ Updated {updated_district} records in known_district")

            # Verify no NULLs remain
            cursor.execute("""
                SELECT COUNT(*) FROM user_quality_ratings
                WHERE known_province IS NULL OR known_district IS NULL
            """)
            remaining_nulls = cursor.fetchone()[0]

            if remaining_nulls == 0:
                print(f"\n✅ Migration successful - no NULL values remain!")
                return True
            else:
                print(f"\n❌ Warning: {remaining_nulls} NULL values still exist")
                return False

    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_unique_index():
    """Verify the unique index exists and uses COALESCE"""

    print("\n" + "="*60)
    print("Verifying unique index")
    print("="*60 + "\n")

    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if index exists
            cursor.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='index' AND name='idx_unique_address_location'
            """)
            result = cursor.fetchone()

            if not result:
                print("❌ Unique index 'idx_unique_address_location' not found!")
                print("\nYou need to create it with:")
                print("""
DROP INDEX IF EXISTS idx_unique_address_location;
CREATE UNIQUE INDEX idx_unique_address_location
ON user_quality_ratings (
    original_address,
    COALESCE(known_province, ''),
    COALESCE(known_district, '')
);
                """)
                return False

            index_sql = result[0]
            print(f"Found index:\n{index_sql}\n")

            if "COALESCE" in index_sql:
                print("✅ Index correctly uses COALESCE")
                return True
            else:
                print("⚠️  Warning: Index does NOT use COALESCE")
                print("\nYou should recreate it with:")
                print("""
DROP INDEX idx_unique_address_location;
CREATE UNIQUE INDEX idx_unique_address_location
ON user_quality_ratings (
    original_address,
    COALESCE(known_province, ''),
    COALESCE(known_district, '')
);
                """)
                return False

    except Exception as e:
        print(f"\n❌ Error checking index: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""

    print("\n")
    success1 = migrate_null_values()
    success2 = verify_unique_index()

    print("\n" + "="*60)
    if success1 and success2:
        print("🎉 Migration completed successfully!")
    elif success1:
        print("⚠️  Migration completed with warnings")
    else:
        print("❌ Migration failed!")
    print("="*60)

    return 0 if success1 else 1


if __name__ == "__main__":
    sys.exit(main())
