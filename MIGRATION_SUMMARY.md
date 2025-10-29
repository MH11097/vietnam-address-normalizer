# Migration Summary: Abbreviations từ admin_divisions sang abbreviations table

## Tổng quan

Migration này di chuyển tất cả abbreviations từ bảng `admin_divisions` (các cột `province_abbreviation`, `district_abbreviation`, `ward_abbreviation`) sang bảng `abbreviations` với context-aware system mới.

**Ngày thực hiện**: 2025-10-29

---

## Những gì đã thay đổi

### 1. Database Schema

#### Bảng `abbreviations` (Updated)

**Cột mới thêm:**
- `district_context TEXT` - District context cho ward-level disambiguation

**Schema mới:**
```sql
CREATE TABLE abbreviations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    word TEXT NOT NULL,
    province_context TEXT,
    district_context TEXT,
    UNIQUE(key, province_context, district_context)
);
```

**Context hierarchy:**
- `province_context = NULL, district_context = NULL` → Global (Province level)
- `province_context = {province}, district_context = NULL` → District level
- `province_context = {province}, district_context = {district}` → Ward level

#### Bảng `admin_divisions` (Cleaned)

**Các cột đã xóa:**
- `province_abbreviation`
- `district_abbreviation`
- `ward_abbreviation`

---

### 2. Migration Data

**Script**: `scripts/migrate_abbreviations_from_admin.py`

**Kết quả migration:**
- Total admin_divisions records processed: **13,814**
- New province abbreviations added: **255**
- New district abbreviations added: **2,839**
- New ward abbreviations added: **46,299**
- **Total new abbreviations: 49,393**
- Duplicates skipped: **8,094**
- **Total abbreviations in database: 51,251**

**Context distribution:**
- Global (province level): **356**
- Province context (district level): **4,596**
- District context (ward level): **46,299**

---

### 3. Các loại Abbreviations được tạo

Với mỗi location (province, district, ward), hệ thống tạo **4 loại** abbreviations:

#### Type 1: Chữ cái đầu mỗi từ
- Input: `name_normalized` (không bao gồm prefix)
- Logic: Lấy chữ cái đầu của mỗi từ
- Ví dụ: `"ba dinh"` → `"bd"`

#### Type 2: Đầu + Full
- Input: `name_normalized`
- Logic: Chữ đầu từ thứ 1 + toàn bộ các từ còn lại
- Ví dụ: `"ba dinh"` → `"bdinh"`

#### Type 3: Full normalized (bao gồm prefix)
- Input: `full_normalized` (bao gồm cả prefix như quận, phường,...)
- Logic: Chữ cái đầu của tất cả các từ
- Ví dụ: `"quan ba dinh"` → `"qbd"`

#### Type 4: Viết liền
- Input: `name_normalized`
- Logic: Nối tất cả các từ lại (bỏ space)
- Ví dụ: `"ba dinh"` → `"badinh"`

**Ví dụ thực tế: "Thanh Xuân" (District in Hà Nội)**
```
tx          → thanh xuan  (Type 1: Chữ cái đầu)
txuan       → thanh xuan  (Type 2: Đầu + Full)
qtx         → thanh xuan  (Type 3: Full normalized)
thanhxuan   → thanh xuan  (Type 4: Viết liền)
```

---

### 4. Code Updates

#### File: `src/utils/db_utils.py`

**Function updated: `load_abbreviations()`**
```python
# Old signature
def load_abbreviations(province_context: Optional[str] = None)

# New signature
def load_abbreviations(
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
)
```

**Priority order:**
1. District-specific (highest priority)
2. Province-specific (medium priority)
3. Global (lowest priority)

**Function updated: `expand_abbreviation_from_admin()`**
```python
# Old: Query từ admin_divisions table
SELECT ward_name_normalized FROM admin_divisions
WHERE ward_abbreviation = ?

# New: Query từ abbreviations table
SELECT word FROM abbreviations
WHERE key = ? AND province_context = ? AND district_context = ?
```

---

#### File: `src/utils/text_utils.py`

**Function updated: `_load_db_abbreviations()`**
```python
# Old signature
def _load_db_abbreviations(province_context: str = None)

# New signature
def _load_db_abbreviations(
    province_context: str = None,
    district_context: str = None
)
```

**Function updated: `expand_abbreviations()`**
```python
# Old signature
def expand_abbreviations(text: str, use_db: bool = True, province_context: str = None)

# New signature
def expand_abbreviations(
    text: str,
    use_db: bool = True,
    province_context: str = None,
    district_context: str = None
)
```

**Function updated: `normalize_address()`**
```python
# Old signature
def normalize_address(text: str, province_context: str = None, keep_separators: bool = False)

# New signature
def normalize_address(
    text: str,
    province_context: str = None,
    district_context: str = None,
    keep_separators: bool = False
)
```

---

### 5. Context-Aware Disambiguation

**Ví dụ: Abbreviation "TX" có nhiều meanings**

| Context Level | Province | District | Expanded Word |
|--------------|----------|----------|---------------|
| Global | - | - | thi xa |
| Province | ca mau | - | tan xuyen |
| Province | ha noi | - | thanh xuan |
| Province | thanh hoa | - | thuong xuan |
| District | bac giang | bac giang | tho xuong |
| District | binh dinh | tay son | tay xuan |

**Cách sử dụng:**
```python
from src.utils.text_utils import normalize_address

# Không có context → "thi xa"
normalize_address("TX")

# Province context → "thanh xuan"
normalize_address("TX", province_context="ha noi")

# District context → "dien bien"
normalize_address("DB", province_context="ha noi", district_context="ba dinh")
```

---

## Test Results

**Test script**: `test_abbreviation_migration.py`

**All tests PASSED (6/6):**
- ✓ Test bảng abbreviations structure
- ✓ Test load_abbreviations với contexts
- ✓ Test expand_abbreviation_from_admin
- ✓ Test normalize_address với contexts
- ✓ Test admin_divisions columns đã bị xóa
- ✓ Test sample queries

---

## Scripts & Files

### Migration Script
- **File**: `scripts/migrate_abbreviations_from_admin.py`
- **Purpose**: Generate và migrate abbreviations từ admin_divisions
- **Usage**: `python3 scripts/migrate_abbreviations_from_admin.py`

### Test Scripts
- **File**: `test_abbreviation_migration.py`
- **Purpose**: Comprehensive test suite
- **Usage**: `python3 test_abbreviation_migration.py`

### Demo Script
- **File**: `demo_abbreviation_types.py`
- **Purpose**: Demo 4 loại abbreviations và context disambiguation
- **Usage**: `python3 demo_abbreviation_types.py`

---

## Statistics

### Database Size
- **Total abbreviations**: 51,251
- **Average abbreviations per location**: 3.74

### Most Common Abbreviation Keys (Top 10)
1. `tt` - 285 locations
2. `xtt` - 234 locations
3. `th` - 223 locations
4. `tl` - 215 locations
5. `xth` - 189 locations
6. `xtl` - 183 locations
7. `ht` - 172 locations
8. `dt` - 159 locations
9. `tp` - 153 locations
10. `xht` - 146 locations

---

## Backward Compatibility

### Breaking Changes
⚠️ **Admin_divisions columns removed**
- Code trực tiếp query `province_abbreviation`, `district_abbreviation`, `ward_abbreviation` từ `admin_divisions` sẽ **FAIL**

### Migration Path
Tất cả code đã được update để sử dụng bảng `abbreviations`:
- ✓ `db_utils.py::expand_abbreviation_from_admin()` - Updated
- ✓ `text_utils.py::expand_abbreviations()` - Updated
- ✓ `text_utils.py::normalize_address()` - Updated

### Optional Parameters
Các function đã update đều có `district_context` là **optional parameter**, nên code cũ vẫn chạy được:
```python
# Old code (still works)
normalize_address("TX", province_context="ha noi")

# New code (with district context)
normalize_address("DB", province_context="ha noi", district_context="ba dinh")
```

---

## Rollback Instructions

Nếu cần rollback, chạy:

```sql
-- 1. Add abbreviation columns back to admin_divisions
ALTER TABLE admin_divisions ADD COLUMN province_abbreviation TEXT;
ALTER TABLE admin_divisions ADD COLUMN district_abbreviation TEXT;
ALTER TABLE admin_divisions ADD COLUMN ward_abbreviation TEXT;

-- 2. Restore abbreviation data (nếu có backup)
-- ...

-- 3. Remove district_context from abbreviations
-- (Requires recreating table - see migration script for reference)
```

**Note**: Nên backup database trước khi migration!

---

## Performance Impact

### Cache Updates
- `load_abbreviations()` cache size increased: `maxsize=128` → `maxsize=256`
- Signature changed → cache keys different → old cache invalidated

### Query Performance
- ✓ **Improved**: Abbreviations table có index trên `(key, province_context, district_context)`
- ✓ **Faster**: Không cần JOIN với admin_divisions
- ✓ **Scalable**: Context-based queries có selectivity tốt hơn

---

## Future Enhancements

### Potential Improvements
1. **Add abbreviation source tracking**: Track which type (1-4) each abbreviation came from
2. **Confidence scoring**: Add confidence score based on abbreviation type
3. **User-defined abbreviations**: Allow custom abbreviations override
4. **Abbreviation validation**: Detect and flag ambiguous abbreviations

### Monitoring
Monitor các metrics sau:
- Abbreviation match rate (% addresses có abbreviation được expand)
- Context usage rate (% queries sử dụng context)
- Disambiguation accuracy (manual validation needed)

---

## Contact & Support

Nếu có vấn đề hoặc câu hỏi:
1. Check test results: `python3 test_abbreviation_migration.py`
2. Run demo: `python3 demo_abbreviation_types.py`
3. Check logs trong migration script output

---

**Migration Status**: ✅ **COMPLETED SUCCESSFULLY**

**Date**: 2025-10-29
**Migration Time**: ~30 seconds
**Data Integrity**: ✅ All tests passed
