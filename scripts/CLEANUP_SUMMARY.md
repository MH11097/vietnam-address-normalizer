# Abbreviation Cleanup Summary

## Vấn Đề Ban Đầu

Một số abbreviations trong database trùng với các từ tiếng Việt có nghĩa, gây nhầm lẫn trong quá trình matching. Ví dụ điển hình:

- **"tu"**: Có thể là viết tắt của "tan uyen", nhưng cũng là tên thực của xã "Tu" (Quảng Nam) và từ trong "phuong tu", "tu lien", v.v.
- **"nam"**: Từ phổ biến trong địa danh (hướng Nam, số 5)
- **"ba"**, **"dong"**, **"tay"**: Các từ tiếng Việt có nghĩa

## Giải Pháp

**Logic đơn giản:** Nếu một abbreviation xuất hiện như một từ (token) trong bất kỳ địa danh nào → Xóa bỏ abbreviation đó

### Quy Trình

1. **Trích xuất tokens**: Lấy tất cả các từ từ 9,991 địa danh trong `admin_divisions`
   - Kết quả: 1,131 tokens unique

2. **Phân tích abbreviations**: So sánh 1,322 abbreviations với tokens
   - Ward level: 995 abbreviations
   - District level: 274 abbreviations
   - Province level: 53 abbreviations

3. **Xác định problematic abbreviations**: 174 abbreviations trùng với tokens
   - Ward level: 134 abbreviations
   - District level: 35 abbreviations
   - Province level: 5 abbreviations

4. **Cập nhật database**: Set problematic abbreviations = NULL

## Kết Quả

### Before vs After Statistics

| Level | Before | After | Removed |
|-------|--------|-------|---------|
| **Ward** | 13,814 | 12,473 | 1,341 |
| **District** | 13,814 | 12,657 | 1,157 |
| **Province** | 13,814 | 12,540 | 1,274 |

### Top Problematic Abbreviations Removed

| Abbreviation | Level | Collisions | Examples |
|--------------|-------|------------|----------|
| `nt` | Ward | 106 | na tam, na tau, nam tam, nam tan, nam thanh |
| `ta` | Ward | 24 | tam an, tan an, tay an, thai an, thanh an |
| `ha` | Ward | 17 | ha an, hai an, hoa an, hong an, hung an |
| `tu` | Ward | 8 | **tu, phuong tu, tan uyen, tan uoc** |
| `ba` | Ward | 13 | ba an, bac an, ban an, binh an |
| `an` | Ward | 14 | an nghia, an nhon, an ninh |

### Ví Dụ Cụ Thể: "tu"

**Trước khi cleanup:**
```sql
ward_name_normalized='tu', ward_abbreviation='tu'  -- Abbreviation of itself!
ward_name_normalized='phuong tu', ward_abbreviation='tu'  -- Collision
ward_name_normalized='tan uyen', ward_abbreviation='tu'  -- Collision
```

**Sau khi cleanup:**
```sql
ward_name_normalized='tu', ward_abbreviation=NULL  -- Fixed!
ward_name_normalized='phuong tu', ward_abbreviation=NULL  -- No confusion
ward_name_normalized='tan uyen', ward_abbreviation=NULL  -- Correct
```

## Impact

### Positive Changes

✅ **Giảm nhầm lẫn**: Các từ phổ biến như "tu", "nam", "ba" không còn bị expand sai nữa

✅ **Tăng accuracy**: User input "Tu Son, Bac Ninh" không bị expand thành "Tan Uyen Son"

✅ **Safer matching**: Abbreviations còn lại đều là viết tắt thực sự (hcm, sg, hbt, v.v.)

### Trade-offs

⚠️ **Mất một số abbreviations hợp lệ**: Một số abbreviations 2 chữ cái bị xóa do trùng tên

- Ví dụ: "ba" có thể là viết tắt hợp lệ cho "ba ria" nhưng cũng là từ trong "ba an", "ba vi"
- Giải pháp: Vẫn có thể rely on fuzzy matching (0.95 threshold)

⚠️ **Numeric abbreviations removed**: Các số như "1", "2", "3" bị xóa vì trùng với tên phường/xã số

- Impact nhỏ vì user hiếm khi viết tắt phường số

## Files Generated

1. **`scripts/remove_token_abbreviations.py`**: Script phân tích và generate reports
2. **`scripts/abbreviation_removal_report.txt`**: Báo cáo chi tiết 174 abbreviations
3. **`scripts/remove_abbreviations.sql`**: SQL script thực thi cleanup
4. **`scripts/CLEANUP_SUMMARY.md`**: Tài liệu này

## Verification

### Test Case: "tu" abbreviation

```bash
# Before cleanup
sqlite3 data/address.db "SELECT COUNT(*) FROM admin_divisions WHERE ward_abbreviation = 'tu';"
# Result: 8 rows

# After cleanup
sqlite3 data/address.db "SELECT COUNT(*) FROM admin_divisions WHERE ward_abbreviation = 'tu';"
# Result: 0 rows ✓
```

### Test Expansion Behavior

```python
# Before: "tu son" might expand to "tan uyen son" (wrong!)
# After: "tu son" stays as "tu son" (correct!)

from src.utils.text_utils import expand_abbreviations

# Test without database abbreviations (they're removed now)
result = expand_abbreviations("tu son", use_db=True, province_context="bac ninh")
print(result)  # Expected: "tu son" (unchanged)
```

## Recommendations

### Future Improvements

1. **Whitelist High-Confidence Abbreviations**: Manually curate list of safe abbreviations
   - Examples: `hcm`, `sg`, `hbt`, `brvt` (clearly abbreviations, not words)

2. **Context-Aware Restoration**: For specific provinces, restore some abbreviations
   - Example: "ba" could be valid for "ba ria" only in "ba ria vung tau" province

3. **Minimum Length Rule**: In future regeneration, skip abbreviations < 3 chars
   - Prevents single/double letter collisions

4. **Frequency Analysis**: Weight abbreviations by usage in real addresses
   - Common real abbreviations should be prioritized

## Conclusion

Cleanup thành công! Database hiện tại sạch hơn với **174 problematic abbreviations** đã được loại bỏ. Hệ thống matching giờ đây chính xác hơn khi xử lý các địa danh có chứa từ phổ biến như "tu", "nam", "ba", v.v.

---

**Date:** 2025-10-28
**Tool:** `scripts/remove_token_abbreviations.py`
**Database:** `data/address.db`
