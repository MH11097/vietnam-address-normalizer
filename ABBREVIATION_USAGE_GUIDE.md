# Abbreviation System - Usage Guide

## Quick Start

### Basic Usage (Không có context)

```python
from src.utils.text_utils import normalize_address

# Expand abbreviations toàn cục
text = normalize_address("P. Điện Biên, Q. Ba Đình, HN")
# Output: "phuong dien bien quan ba dinh ha noi"
```

### Province Context

```python
# Sử dụng province context để disambiguate
text = normalize_address("TX", province_context="ha noi")
# Output: "thanh xuan"

text = normalize_address("TX", province_context="ca mau")
# Output: "tan xuyen"
```

### District Context (Ward-level disambiguation)

```python
# Sử dụng cả province và district context
text = normalize_address("DB",
                        province_context="ha noi",
                        district_context="ba dinh")
# Output: "dien bien"
```

---

## API Reference

### 1. normalize_address()

**Location**: `src/utils/text_utils.py`

**Full signature:**
```python
def normalize_address(
    text: str,
    province_context: str = None,
    district_context: str = None,
    keep_separators: bool = False
) -> str
```

**Parameters:**
- `text`: Raw address text cần normalize
- `province_context`: Province name (normalized) - optional
- `district_context`: District name (normalized) - optional, requires province_context
- `keep_separators`: Giữ lại commas và dashes (default: False)

**Returns:** Normalized address string

**Example:**
```python
# Basic normalization
normalize_address("P. 1, Q. 3, TP.HCM")
# → "phuong 1 quan 3 thanh pho ho chi minh"

# With province context
normalize_address("TX, HN", province_context="ha noi")
# → "thanh xuan ha noi"

# With district context
normalize_address("DB", province_context="ha noi", district_context="ba dinh")
# → "dien bien"

# Keep separators for parsing
normalize_address("P. 1, Q. 3", keep_separators=True)
# → "phuong 1, quan 3"
```

---

### 2. expand_abbreviations()

**Location**: `src/utils/text_utils.py`

**Full signature:**
```python
def expand_abbreviations(
    text: str,
    use_db: bool = True,
    province_context: str = None,
    district_context: str = None
) -> str
```

**Parameters:**
- `text`: Text có chứa abbreviations
- `use_db`: Sử dụng database abbreviations (default: True)
- `province_context`: Province name (normalized) - optional
- `district_context`: District name (normalized) - optional

**Returns:** Text với abbreviations đã được expand

**Priority order:**
1. Hardcoded patterns (P., Q., TP.)
2. Database abbreviations (district > province > global)

**Example:**
```python
# Basic expansion
expand_abbreviations("P. 1, Q. 2")
# → "phuong 1, quan 2"

# With province context
expand_abbreviations("TX", province_context="ha noi")
# → "thanh xuan"

# Without database
expand_abbreviations("P. 1", use_db=False)
# → "phuong 1" (only hardcoded patterns)
```

---

### 3. load_abbreviations()

**Location**: `src/utils/db_utils.py`

**Full signature:**
```python
def load_abbreviations(
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> Dict[str, str]
```

**Parameters:**
- `province_context`: Province name (normalized) - optional
- `district_context`: District name (normalized) - optional

**Returns:** Dictionary mapping abbreviation key → expanded word

**Priority order:**
1. District-specific (highest priority)
2. Province-specific
3. Global (lowest priority)

**Example:**
```python
from src.utils.db_utils import load_abbreviations

# Global abbreviations only
abbr_global = load_abbreviations()
# {'hn': 'ha noi', 'hcm': 'ho chi minh', ...}

# Province context (includes global + province-specific)
abbr_hn = load_abbreviations(province_context='ha noi')
# {'hn': 'ha noi', 'tx': 'thanh xuan', 'bd': 'ba dinh', ...}

# District context (includes all levels)
abbr_bd = load_abbreviations(province_context='ha noi',
                             district_context='ba dinh')
# {'hn': 'ha noi', 'tx': 'thanh xuan', 'db': 'dien bien', ...}
```

---

### 4. expand_abbreviation_from_admin()

**Location**: `src/utils/db_utils.py`

**Full signature:**
```python
def expand_abbreviation_from_admin(
    abbr: str,
    level: str = 'ward',
    province_context: Optional[str] = None,
    district_context: Optional[str] = None
) -> Optional[str]
```

**Parameters:**
- `abbr`: Abbreviation cần expand
- `level`: Level to search - 'ward', 'district', or 'province' (kept for compatibility)
- `province_context`: Province name (normalized) - optional
- `district_context`: District name (normalized) - optional

**Returns:** Expanded word or None

**Example:**
```python
from src.utils.db_utils import expand_abbreviation_from_admin

# Province level
expand_abbreviation_from_admin('hn', 'province')
# → 'ha noi'

# District level with province context
expand_abbreviation_from_admin('bd', 'district', province_context='ha noi')
# → 'ba dinh'

# Ward level with full context
expand_abbreviation_from_admin('db', 'ward',
                              province_context='ha noi',
                              district_context='ba dinh')
# → 'dien bien'
```

---

## Common Patterns

### Pattern 1: Normalize Raw Address Input

```python
from src.utils.text_utils import normalize_address

# User input từ form
raw_input = "P. Điện Biên, Q. Ba Đình, TP. Hà Nội"

# Normalize để matching
normalized = normalize_address(raw_input)
# → "phuong dien bien quan ba dinh thanh pho ha noi"
```

### Pattern 2: Context-Aware Processing

```python
from src.utils.text_utils import normalize_address

# Nếu đã biết province từ raw data
known_province = "Hà Nội"
known_province_norm = normalize_address(known_province)  # "ha noi"

# Parse address với province context
address = "TX, Đống Đa"
normalized = normalize_address(address, province_context=known_province_norm)
# → "thanh xuan dong da"
```

### Pattern 3: Progressive Disambiguation

```python
from src.utils.text_utils import normalize_address

# Step 1: Normalize province hint
province_hint = normalize_address("HN")  # "ha noi"

# Step 2: Normalize district với province context
district_hint = normalize_address("Q.BD", province_context=province_hint)
# "quan ba dinh" → extract "ba dinh"

# Step 3: Normalize ward với full context
ward = normalize_address("P.DB",
                        province_context=province_hint,
                        district_context="ba dinh")
# "phuong dien bien"
```

---

## Abbreviation Types

Hệ thống tự động tạo 4 loại abbreviations cho mỗi location:

### Type 1: Chữ cái đầu
- `"ba dinh"` → `"bd"`
- `"thanh xuan"` → `"tx"`
- `"ho chi minh"` → `"hcm"`

### Type 2: Đầu + Full
- `"ba dinh"` → `"bdinh"`
- `"thanh xuan"` → `"txuan"`
- `"ho chi minh"` → `"hchi minh"` (note: first char only)

### Type 3: Full normalized (với prefix)
- `"quan ba dinh"` → `"qbd"`
- `"phuong dien bien"` → `"pdb"`
- `"thanh pho ha noi"` → `"tphn"`

### Type 4: Viết liền
- `"ba dinh"` → `"badinh"`
- `"thanh xuan"` → `"thanhxuan"`
- `"ho chi minh"` → `"hochiminh"`

---

## Context Hierarchy

```
Global (province_context=NULL, district_context=NULL)
  │
  ├─── Example: 'hn' → 'ha noi'
  │
  └─── Province Context (province_context='ha noi', district_context=NULL)
         │
         ├─── Example: 'tx' → 'thanh xuan'
         │
         └─── District Context (province_context='ha noi', district_context='ba dinh')
                │
                └─── Example: 'db' → 'dien bien'
```

**Priority**: District > Province > Global

---

## Database Queries

### Get all abbreviations for a word

```python
from src.utils.db_utils import query_all

result = query_all("""
    SELECT key, province_context, district_context
    FROM abbreviations
    WHERE word = ?
    ORDER BY province_context, district_context
""", ("thanh xuan",))
```

### Get context-specific abbreviations

```python
from src.utils.db_utils import query_all

# District-level abbreviations trong Hà Nội
result = query_all("""
    SELECT key, word
    FROM abbreviations
    WHERE province_context = 'ha noi'
      AND district_context IS NULL
    ORDER BY word
""")

# Ward-level abbreviations trong Ba Đình, Hà Nội
result = query_all("""
    SELECT key, word
    FROM abbreviations
    WHERE province_context = 'ha noi'
      AND district_context = 'ba dinh'
    ORDER BY word
""")
```

---

## Performance Tips

### 1. Cache is your friend
Functions đã được cache với `@lru_cache`:
- `load_abbreviations()` - maxsize=256
- `normalize_address()` - maxsize=10000
- `expand_abbreviations()` - maxsize=10000

**Sử dụng cùng parameters để tận dụng cache!**

### 2. Load abbreviations một lần

```python
# ❌ BAD: Load nhiều lần
for address in addresses:
    abbr = load_abbreviations(province_context='ha noi')  # Reload mỗi lần
    # ...

# ✅ GOOD: Load một lần, reuse
abbr = load_abbreviations(province_context='ha noi')
for address in addresses:
    # Use abbr dict
    # ...
```

### 3. Context specificity

```python
# ❌ Over-specific context khi không cần thiết
normalize_address("HN", province_context='ha noi', district_context='ba dinh')

# ✅ Chỉ dùng context khi cần disambiguate
normalize_address("HN")  # Global abbreviation is enough
```

---

## Troubleshooting

### Problem: Abbreviation không được expand

**Solution:**
1. Check abbreviation tồn tại trong database:
   ```python
   from src.utils.db_utils import query_all
   result = query_all("SELECT * FROM abbreviations WHERE key = ?", ("your_abbr",))
   ```

2. Check context đúng chưa:
   ```python
   # Thử với global context
   expand_abbreviation_from_admin('your_abbr', 'ward')

   # Thử với province context
   expand_abbreviation_from_admin('your_abbr', 'ward', province_context='ha noi')
   ```

### Problem: Wrong expansion

**Solution:**
Abbreviation có thể có nhiều meanings. Cần provide đúng context:
```python
# ❌ Wrong: 'tx' mà không có context → 'thi xa' (generic)
normalize_address("TX")

# ✅ Right: 'tx' với ha noi context → 'thanh xuan'
normalize_address("TX", province_context="ha noi")
```

### Problem: Cache stale

**Solution:**
Clear cache nếu database updated:
```python
from src.utils import db_utils, text_utils

db_utils.clear_cache()
text_utils.clear_cache()
```

---

## Testing

### Run full test suite
```bash
python3 test_abbreviation_migration.py
```

### Run demo
```bash
python3 demo_abbreviation_types.py
```

### Quick test in Python
```python
from src.utils.text_utils import normalize_address

# Test basic
assert normalize_address("HN") == "ha noi"

# Test with context
assert normalize_address("TX", province_context="ha noi") == "thanh xuan"
```

---

## Examples from Real Data

### Example 1: Hà Nội addresses

```python
addresses = [
    "P. Điện Biên, Q. Ba Đình, HN",
    "TX, HN",
    "Phường Láng Thượng, Đống Đa, Hà Nội"
]

for addr in addresses:
    normalized = normalize_address(addr, province_context="ha noi")
    print(f"{addr:50} → {normalized}")
```

Output:
```
P. Điện Biên, Q. Ba Đình, HN                       → phuong dien bien quan ba dinh ha noi
TX, HN                                             → thanh xuan ha noi
Phường Láng Thượng, Đống Đa, Hà Nội               → phuong lang thuong dong da ha noi
```

### Example 2: Context-aware processing

```python
# Địa chỉ có abbreviation "DB" - có thể là nhiều wards khác nhau
addresses = [
    ("DB", "ha noi", "ba dinh"),      # Điện Biên
    ("DB", "quang ninh", "ha long"),  # Bãi Dầu (example)
]

for abbr, prov, dist in addresses:
    result = normalize_address(abbr,
                              province_context=prov,
                              district_context=dist)
    print(f"{abbr} [{prov}/{dist}] → {result}")
```

---

## Migration Notes

- ✅ Abbreviation columns đã bị xóa khỏi `admin_divisions`
- ✅ Tất cả code đã được update để sử dụng `abbreviations` table
- ✅ Backward compatible: district_context là optional parameter

**Nếu gặp error về missing columns:**
```
OperationalError: no such column: province_abbreviation
```

→ Code cũ đang query trực tiếp từ `admin_divisions`. Cần update để sử dụng `load_abbreviations()` hoặc `expand_abbreviation_from_admin()`.

---

## See Also

- **MIGRATION_SUMMARY.md** - Chi tiết về migration process
- **scripts/migrate_abbreviations_from_admin.py** - Migration script
- **test_abbreviation_migration.py** - Test suite
- **demo_abbreviation_types.py** - Demo script
