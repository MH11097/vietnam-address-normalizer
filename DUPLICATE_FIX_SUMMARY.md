# Tóm Tắt: Sửa Lỗi Duplicate khi có NULL Values

## Vấn Đề
Khi chạy lại cùng một `(original_address, known_province, known_district)`, hệ thống tạo bản ghi mới (INSERT) thay vì cập nhật (UPDATE), gây ra lỗi:
```
❌ UNIQUE constraint failed: index 'idx_unique_address_location'
```

## Nguyên Nhân
SQLite coi `NULL != NULL` trong unique index, nên:
- Record 1: `('address', 'ha noi', NULL)`
- Record 2: `('address', 'ha noi', NULL)`
→ SQLite cho phép cả 2 records (coi là khác nhau)

## Giải Pháp

### 1. **Database Schema** ✅
Tạo lại unique index với `COALESCE()`:
```sql
DROP INDEX IF EXISTS idx_unique_address_location;

CREATE UNIQUE INDEX idx_unique_address_location
ON user_quality_ratings (
    original_address,
    COALESCE(known_province, ''),
    COALESCE(known_district, '')
);
```

### 2. **Code Changes** ✅

#### File: `src/utils/db_utils.py`
**Thay đổi hàm `save_user_rating()`:**
- Normalize NULL → empty string: `known_province = known_province if known_province else ''`
- Implement manual UPSERT logic:
  1. Thử UPDATE trước (với `COALESCE` trong WHERE clause)
  2. Nếu không có row nào bị update → INSERT mới
  3. Trả về đúng ID trong cả 2 trường hợp

**Code mới (lines 896-976):**
```python
# Normalize NULL values to empty strings
known_province = rating_data.get('known_province')
known_district = rating_data.get('known_district')
known_province = known_province if known_province else ''
known_district = known_district if known_district else ''

# Try UPDATE first (with COALESCE to match both NULL and '')
update_query = """
UPDATE user_quality_ratings
SET timestamp = ?, cif_no = ?, ...
WHERE original_address = ?
    AND COALESCE(known_province, '') = ?
    AND COALESCE(known_district, '') = ?
"""

cursor.execute(update_query, update_params)

# If no rows updated, INSERT new record
if cursor.rowcount == 0:
    cursor.execute(insert_query, insert_params)
    return cursor.lastrowid
else:
    # Return ID of updated record
    return cursor.fetchone()[0]
```

#### File: `scripts/create_ratings_table.py`
**Thêm unique index vào migration script:**
```python
create_unique_index_sql = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_address_location
ON user_quality_ratings (
    original_address,
    COALESCE(known_province, ''),
    COALESCE(known_district, '')
)
"""
```

### 3. **Data Migration** ✅
Chuyển NULL values hiện có thành empty strings:
```sql
UPDATE user_quality_ratings
SET known_province = ''
WHERE known_province IS NULL;

UPDATE user_quality_ratings
SET known_district = ''
WHERE known_district IS NULL;
```

## Kết Quả

### ✅ Trước đây (CÓ LỖI):
```
1st run: INSERT → ID 1
2nd run: INSERT → ID 2 (DUPLICATE!)
Error: UNIQUE constraint failed
```

### ✅ Bây giờ (ĐÃ SỬA):
```
1st run: INSERT → ID 1
2nd run: UPDATE → ID 1 (SAME ID, no duplicate!)
No error, record updated successfully
```

## Test Results

### Test 1: NULL values
```bash
python3 test_duplicate_prevention.py
```
✅ Same address + NULL district → UPDATE (same ID)
✅ Only 1 record exists (no duplicates)
✅ Second values overwrite first values
✅ Different addresses create separate records

### Test 2: Real database record
```bash
python3 test_real_update.py
```
✅ UPDATE với record thật từ database
✅ Không tạo duplicate
✅ Values được cập nhật đúng

### Test 3: Data migration
```bash
python3 scripts/migrate_null_to_empty.py
```
✅ Migrate 51 NULL records → empty strings
✅ Unique index đã có COALESCE
✅ Database sạch, không còn NULL

## Files Đã Thay Đổi

1. **src/utils/db_utils.py** (lines 896-976)
   - Rewrite `save_user_rating()` function
   - Manual UPSERT với COALESCE

2. **scripts/create_ratings_table.py** (lines 51-76)
   - Thêm unique index creation

3. **data/address.db**
   - Recreate unique index với COALESCE
   - Migrate NULL → empty string

## Scripts Mới

1. **test_duplicate_prevention.py**
   - Test UPDATE/INSERT logic với NULL values

2. **test_real_update.py**
   - Test với dữ liệu thật từ database

3. **scripts/migrate_null_to_empty.py**
   - Migration script cho database khác

## Cách Sử Dụng

### Trong demo.py và app.py
**Không cần thay đổi gì!** Chỉ cần chạy như bình thường:

```bash
# demo.py
python3 demo.py

# app.py
python3 app.py
```

Khi user rate kết quả với cùng address:
- Lần 1: Tạo record mới
- Lần 2+: Cập nhật record cũ (không tạo duplicate)

### Nếu migrate database khác
```bash
# 1. Chạy migration script
python3 scripts/migrate_null_to_empty.py

# 2. Hoặc chạy SQL trực tiếp:
sqlite3 your_database.db <<EOF
-- Migrate NULL values
UPDATE user_quality_ratings SET known_province = '' WHERE known_province IS NULL;
UPDATE user_quality_ratings SET known_district = '' WHERE known_district IS NULL;

-- Recreate unique index
DROP INDEX IF EXISTS idx_unique_address_location;
CREATE UNIQUE INDEX idx_unique_address_location
ON user_quality_ratings (
    original_address,
    COALESCE(known_province, ''),
    COALESCE(known_district, '')
);
EOF
```

## Lưu Ý Quan Trọng

1. **NULL vs Empty String**: Code hiện tại normalize tất cả NULL → `''` (empty string)

2. **COALESCE trong WHERE**: Đảm bảo tìm được record cả khi database có NULL hoặc empty string

3. **Unique Index**: Phải dùng COALESCE để SQLite coi `NULL` và `''` là giống nhau

4. **Backward Compatible**: Code mới hoạt động với cả database cũ (có NULL) và mới (có empty string)

## Tóm Tắt

| Trước | Sau |
|-------|-----|
| INSERT duplicate → Error | UPDATE existing → Success |
| NULL != NULL | COALESCE(NULL, '') = '' |
| Manual ON CONFLICT (không work với COALESCE) | Manual UPDATE then INSERT |
| Lỗi UNIQUE constraint | ✅ Tự động UPDATE |

---

**Ngày hoàn thành:** 2025-11-03
**Status:** ✅ COMPLETED
**All tests:** PASSED
