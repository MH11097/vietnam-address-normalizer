"""
Migration script: Create user_quality_ratings table

Tạo bảng để lưu đánh giá chất lượng kết quả parsing từ người dùng.

Usage:
    python scripts/create_ratings_table.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.db_utils import get_db_connection, DB_PATH


def create_ratings_table():
    """Tạo bảng user_quality_ratings nếu chưa tồn tại"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS user_quality_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cif_no TEXT,
        original_address TEXT NOT NULL,
        known_province TEXT,
        known_district TEXT,
        parsed_province TEXT,
        parsed_district TEXT,
        parsed_ward TEXT,
        confidence_score REAL,
        user_rating INTEGER NOT NULL CHECK(user_rating IN (1, 2, 3)),
        processing_time_ms REAL,
        match_type TEXT
    )
    """

    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_rating_timestamp
    ON user_quality_ratings(timestamp)
    """

    create_rating_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_rating_value
    ON user_quality_ratings(user_rating)
    """

    create_unique_index_sql = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_address_location
    ON user_quality_ratings (
        original_address,
        COALESCE(known_province, ''),
        COALESCE(known_district, '')
    )
    """

    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()

            # Create table
            cursor.execute(create_table_sql)
            print("✅ Table 'user_quality_ratings' created successfully (or already exists)")

            # Create indexes
            cursor.execute(create_index_sql)
            print("✅ Index 'idx_rating_timestamp' created successfully")

            cursor.execute(create_rating_index_sql)
            print("✅ Index 'idx_rating_value' created successfully")

            cursor.execute(create_unique_index_sql)
            print("✅ Unique index 'idx_unique_address_location' created successfully")

            conn.commit()

            # Verify table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='user_quality_ratings'
            """)
            result = cursor.fetchone()

            if result:
                print("\n✅ Migration completed successfully!")
                print(f"   Database: {DB_PATH}")

                # Show table schema
                cursor.execute("PRAGMA table_info(user_quality_ratings)")
                columns = cursor.fetchall()
                print("\n📋 Table Schema:")
                for col in columns:
                    col_id, name, col_type, not_null, default, pk = col
                    nullable = "NOT NULL" if not_null else "NULL"
                    pk_str = " PRIMARY KEY" if pk else ""
                    print(f"   - {name}: {col_type} {nullable}{pk_str}")
            else:
                print("\n❌ Error: Table was not created!")
                return False

        return True

    except Exception as e:
        print(f"\n❌ Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    print("="*60)
    print("Creating user_quality_ratings table...")
    print("="*60 + "\n")

    success = create_ratings_table()

    if success:
        print("\n" + "="*60)
        print("🎉 Migration completed successfully!")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("❌ Migration failed!")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
