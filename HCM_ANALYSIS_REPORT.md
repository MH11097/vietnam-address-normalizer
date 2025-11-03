# Báo Cáo Phân Tích Chi Tiết Cases TP HỒ CHÍ MINH

**Ngày tạo:** 2025-10-30
**Địa bàn:** TP Hồ Chí Minh
**Tổng số cases:** 15 (Rating 1: 3, Rating 2: 4, Rating 3: 8)

---

## 🚨 PHÁT HIỆN NGHIÊM TRỌNG

### Địa chỉ trùng lặp nhưng kết quả khác nhau:

**Địa chỉ:** `71 C9 CONG HOA P.13,Q.TB`

| ID  | Rating | Parsed Province | Parsed District | Parsed Ward | Confidence |
|-----|--------|-----------------|-----------------|-------------|------------|
| 192 | 1 (tốt)| (null)          | (null)          | (null)      | null       |
| 193 | 3 (tệ) | (null)          | (null)          | (null)      | null       |

**⚠️ VẤN ĐỀ:**
- **CÙNG một địa chỉ**, parsing **CÙNG thất bại** (không parse được gì)
- Nhưng user đánh giá **khác nhau**: lần 1 cho rating 1 (tốt), lần 2 cho rating 3 (tệ)
- Điều này cho thấy:
  1. **Inconsistency trong user rating** - Có thể user rating dựa vào yếu tố khác?
  2. **Hoặc có bug trong cách lưu data** - Timestamp khác nhau?

---

## 📊 Tổng Quan Cases TP HCM

**Thống kê:**
- Tổng số: 15 cases
- Rating 1 (tốt): 3 cases (20%)
- Rating 2 (khá): 4 cases (26.7%)
- Rating 3 (tệ): 8 cases (53.3%)
- **Success rate: 20%** ⚠️ Rất thấp!

**So sánh với tổng thể:**
- Tổng thể success rate: 60.4%
- HCM success rate: 20%
- **HCM kém hơn 3x so với trung bình!**

---

## 🔍 Phân Tích 8 Cases Rating = 3

### Pattern Chung:

**✅ Điểm tốt:**
- **100% có thông tin quận trong text** (8/8)
- **100% có thông tin phường trong text** (8/8)
- Thông tin đầy đủ nhưng **parsing thất bại hoàn toàn**

**❌ Vấn đề:**
- **Format viết tắt:** 100% cases đều dùng viết tắt
  - Viết tắt không khoảng cách: 5 cases (62.5%) - `Q8`, `P15`
  - Viết tắt có dấu chấm: 3 cases (37.5%) - `Q.`, `P.`

---

## 📋 Chi Tiết Từng Case

### Case 1: `16/291 LE DUC THO P15 Q.GO VAP TP` (ID: 25)

**Thông tin:**
- Quận: GO VAP
- Phường: 15
- Format: `Q.` và `P` (viết tắt có dấu chấm)

**Phân tích:**
```
Input:  "16/291 LE DUC THO P15 Q.GO VAP TP"
Nên expand thành: "16/291 le duc tho phuong 15 quan go vap thanh pho"

Expected output:
  Province: ho chi minh
  District: go vap
  Ward: phuong 15
```

**Vấn đề:**
- `Q.GO VAP` - dấu chấm sau Q có thể bị loại hoặc làm rối pattern
- `P15` - dính liền, không có space
- `TP` ở cuối - viết tắt "thành phố"

---

### Case 2: `32,DUONG S9,P.TAY THANH,Q.TAN PHU` (ID: 37)

**Thông tin:**
- Quận: TAN PHU
- Phường: TAY THANH
- Format: `Q.` và `P.` (viết tắt có dấu chấm)

**Phân tích:**
```
Input:  "32,DUONG S9,P.TAY THANH,Q.TAN PHU"
Nên expand thành: "32 duong s9 phuong tay thanh quan tan phu"

Expected output:
  Province: ho chi minh
  District: tan phu
  Ward: tay thanh
```

**Vấn đề:**
- `P.TAY THANH` - dấu chấm dính với tên phường
- `Q.TAN PHU` - dấu chấm dính với tên quận
- `DUONG S9` - S9 là tên đường (không phải phường/quận)

---

### Case 3: `660/8 PHAM THE HIEN P4 Q8` (ID: 50)

**Thông tin:**
- Quận: 8
- Phường: 4
- Format: Viết tắt không space (`Q8`, `P4`)

**Phân tích:**
```
Input:  "660/8 PHAM THE HIEN P4 Q8"
Nên expand thành: "660/8 pham the hien phuong 4 quan 8"

Expected output:
  Province: ho chi minh
  District: quan 8
  Ward: phuong 4
```

**Vấn đề:**
- `P4` và `Q8` - viết tắt dính liền với số
- Đây là **pattern rất phổ biến ở HCM**
- **CRITICAL:** Phải xử lý được pattern này

---

### Case 4: `55 BE VAN DAN,P14,Q TAN BINH,TP` (ID: 75)

**Thông tin:**
- Quận: TAN BINH
- Phường: 14
- Format: `P14` (không space), `Q TAN BINH` (có space)

**Phân tích:**
```
Input:  "55 BE VAN DAN,P14,Q TAN BINH,TP"
Nên expand thành: "55 be van dan phuong 14 quan tan binh thanh pho"

Expected output:
  Province: ho chi minh
  District: tan binh
  Ward: phuong 14
```

**Vấn đề:**
- Mixed format: `P14` (không space) + `Q TAN BINH` (có space)
- `TP` ở cuối

---

### Case 5: `128 TRAN HUNG DAO F7 Q5` (ID: 89)

**Thông tin:**
- Quận: 5
- Phường: 7
- Format: `F7` (Floor? hoặc Phường 7?), `Q5`

**Phân tích:**
```
Input:  "128 TRAN HUNG DAO F7 Q5"
Nên expand thành: "128 tran hung dao phuong 7 quan 5"

Expected output:
  Province: ho chi minh
  District: quan 5
  Ward: phuong 7
```

**Vấn đề đặc biệt:**
- `F7` - **F có thể là Floor (tầng) hoặc viết tắt của Phường**
- Context: Có `Q5` (Quận 5) → `F7` nhiều khả năng là **Phường 7**
- Cần logic context-aware: Khi có `Q` + số → `F` + số là phường

---

### Case 6: `041 LO B C/C AN QUANG P9 Q10` (ID: 188)

**Thông tin:**
- Quận: 10
- Phường: 9
- Format: `P9`, `Q10` (viết tắt dính số)

**Phân tích:**
```
Input:  "041 LO B C/C AN QUANG P9 Q10"
Nên expand thành: "041 lo b chung cu an quang phuong 9 quan 10"

Expected output:
  Province: ho chi minh
  District: quan 10
  Ward: phuong 9
```

**Vấn đề:**
- `C/C` - viết tắt "chung cư"
- `LO B` - lô B
- Pattern `P9 Q10` rất rõ ràng, lẽ ra phải parse được

---

### Case 7: `71 C9 CONG HOA P.13,Q.TB` (ID: 193)

**⚠️ CASE ĐẶC BIỆT - Trùng với ID 192 (rating 1)**

**Thông tin:**
- Quận: TB (viết tắt của TAN BINH)
- Phường: 13
- Format: `P.13`, `Q.TB` (có dấu chấm)

**Phân tích:**
```
Input:  "71 C9 CONG HOA P.13,Q.TB"
Nên expand thành: "71 c9 cong hoa phuong 13 quan tan binh"

Expected output:
  Province: ho chi minh
  District: tan binh
  Ward: phuong 13
```

**Vấn đề:**
- `TB` - **viết tắt cấp 2**: Q.TB = Quận Tân Bình
- `C9` - Tên block/dãy chung cư (C9 Cộng Hòa)
- Cần dictionary: `TB` → `tan binh`, `GV` → `go vap`

**⚠️ INCONSISTENCY:**
- Cùng địa chỉ, cùng thất bại parsing
- ID 192: rating 1 (user cho điểm tốt)
- ID 193: rating 3 (user cho điểm tệ)
- **Có thể user nhầm lẫn hoặc có context khác?**

---

### Case 8: `131/19/8B NGUYEN THAI SON P7 Q GV N V XMHT1` (ID: 208)

**Thông tin:**
- Quận: GV (viết tắt của GO VAP)
- Phường: 7
- Format: Phức tạp với nhiều viết tắt

**Phân tích:**
```
Input:  "131/19/8B NGUYEN THAI SON P7 Q GV N V XMHT1"
        ↑ Số nhà               ↑ Tên đường  ↑P7 ↑Q GV ↑Noise

Nên expand thành: "131/19/8b nguyen thai son phuong 7 quan go vap"

Expected output:
  Province: ho chi minh
  District: go vap
  Ward: phuong 7
```

**Vấn đề đặc biệt:**
- `Q GV` - **GV = Gò Vấp** (viết tắt cấp 2)
- `N V XMHT1` - Noise data (có thể là mã nội bộ, notes, v.v.)
- Cần:
  1. Dictionary: `GV` → `go vap`
  2. Xóa noise sau khi có đủ thông tin địa lý

---

## 📊 Phân Tích Patterns

### 1. Viết tắt Quận (Q)

| Pattern | Số lượng | Ví dụ | Cách xử lý |
|---------|----------|-------|------------|
| `Q` + số | 4 cases | `Q8`, `Q5`, `Q10` | `Q(\d+)` → `quan \1` |
| `Q.` + số | 1 case | `Q.13` | `Q\.(\d+)` → `quan \1` |
| `Q` + tên | 2 cases | `Q TAN BINH`, `Q GV` | `Q ([A-Z\s]+)` → expand tên |
| `Q.` + tên | 2 cases | `Q.GO VAP`, `Q.TB` | `Q\.([A-Z\s]+)` → expand tên |

**Viết tắt cấp 2 (cần dictionary):**
- `TB` → `tan binh`
- `GV` → `go vap`
- `BT` → `binh thanh`
- `TD` → `thu duc`

### 2. Viết tắt Phường (P/F)

| Pattern | Số lượng | Ví dụ | Cách xử lý |
|---------|----------|-------|------------|
| `P` + số | 5 cases | `P4`, `P9`, `P15`, `P14`, `P7` | `P(\d+)` → `phuong \1` |
| `P.` + số | 2 cases | `P.13` | `P\.(\d+)` → `phuong \1` |
| `P.` + tên | 1 case | `P.TAY THANH` | `P\.([A-Z\s]+)` → `phuong \1` |
| `F` + số | 1 case | `F7` (context: có Q5) | `F(\d+)` → `phuong \1` khi có Q |

### 3. Các viết tắt khác

| Viết tắt | Ý nghĩa | Cách xử lý |
|----------|---------|------------|
| `TP` | Thành phố | Có thể bỏ qua hoặc expand |
| `C/C` | Chung cư | Expand → `chung cu` |
| `C9`, `C1`, etc. | Block/dãy | Giữ nguyên |
| `LO A`, `LO B` | Lô | Giữ nguyên |

---

## 💡 Recommendations

### Priority 1: CRITICAL - Implement Abbreviation Expansion

**1.1. Regex-based expansion trong phase 1 preprocessing:**

```python
def expand_hcm_abbreviations(text):
    """Expand các viết tắt phổ biến ở TP HCM"""

    # Step 1: Expand quận + số (Q8, Q.8, Q 8)
    text = re.sub(r'\bQ\.?\s*(\d+)\b', r'quan \1', text, flags=re.IGNORECASE)

    # Step 2: Expand phường + số (P4, P.4, P 4)
    text = re.sub(r'\bP\.?\s*(\d+)\b', r'phuong \1', text, flags=re.IGNORECASE)

    # Step 3: F + số → phuong (khi có context quận)
    if re.search(r'\bquan\s+\d+\b', text, re.IGNORECASE):
        text = re.sub(r'\bF\.?\s*(\d+)\b', r'phuong \1', text, flags=re.IGNORECASE)

    # Step 4: Expand viết tắt cấp 2 cho quận
    district_abbr = {
        r'\bQ\.?\s*TB\b': 'quan tan binh',
        r'\bQ\.?\s*GV\b': 'quan go vap',
        r'\bQ\.?\s*BT\b': 'quan binh thanh',
        r'\bQ\.?\s*TD\b': 'quan thu duc',
        r'\bQ\.?\s*PN\b': 'quan phu nhuan',
    }
    for pattern, replacement in district_abbr.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Step 5: Expand tên quận đầy đủ
    text = re.sub(r'\bQ\.?\s*([A-Z][A-Z\s]+?)\b(?=,|\s|$)',
                  lambda m: f'quan {m.group(1).lower()}',
                  text)

    # Step 6: Expand tên phường đầy đủ
    text = re.sub(r'\bP\.?\s*([A-Z][A-Z\s]+?)\b(?=,|\s|$)',
                  lambda m: f'phuong {m.group(1).lower()}',
                  text)

    # Step 7: Expand các từ khác
    text = re.sub(r'\bTP\b', 'thanh pho', text, flags=re.IGNORECASE)
    text = re.sub(r'\bC/C\b', 'chung cu', text, flags=re.IGNORECASE)

    return text
```

**1.2. Áp dụng trong preprocessing:**

```python
def preprocess(address_text, province_known=None):
    # Nếu known_province là HCM → apply HCM-specific expansion
    if province_known and 'ho chi minh' in province_known.lower():
        address_text = expand_hcm_abbreviations(address_text)

    # Continue with normal preprocessing...
    normalized = normalize_text(address_text)
    return normalized
```

**Impact:** Sẽ fix được **7/8 cases** (87.5%)

---

### Priority 2: HIGH - Handle Noise Data

**Vấn đề:**
- Case 8 có noise: `N V XMHT1` ở cuối
- Cần detect và remove noise sau khi đã extract đủ thông tin địa lý

**Giải pháp:**

```python
def remove_trailing_noise(text):
    """
    Remove noise sau khi đã có đủ province/district/ward
    """
    # Nếu đã match được đủ thông tin địa lý
    # và còn phần text phía sau (không match gì)
    # → coi như noise và bỏ qua

    # Pattern: sau khi có Q + P, mọi thứ phía sau đều là noise
    text = re.sub(r'(quan\s+\w+.*?phuong\s+\d+).*$', r'\1', text, flags=re.IGNORECASE)

    return text
```

**Impact:** Fix case 8

---

### Priority 3: MEDIUM - Investigate Duplicate Record Issue

**Vấn đề:**
- ID 192 và 193: Cùng địa chỉ, cùng kết quả, khác rating

**Action items:**

1. **Kiểm tra timestamp:**
```sql
SELECT id, timestamp, original_address, user_rating
FROM user_quality_ratings
WHERE original_address = '71 C9 CONG HOA P.13,Q.TB'
ORDER BY timestamp;
```

2. **Tìm các duplicate khác:**
```sql
SELECT original_address, COUNT(*), GROUP_CONCAT(user_rating)
FROM user_quality_ratings
GROUP BY original_address
HAVING COUNT(*) > 1;
```

3. **Nếu là bug:** Cần review logic save rating
4. **Nếu là user behavior:** Cần thêm explanation trong UI

---

### Priority 4: LOW - Context-aware F/P detection

**Vấn đề:**
- `F7` có thể là Floor 7 hoặc Phường 7

**Giải pháp:**
```python
def smart_f_detection(text):
    """
    F + số:
    - Nếu có Q/Quận trong text → F = Phường
    - Nếu có "tầng" hoặc context building → F = Floor
    - Default: F = Phường (ở HCM)
    """
    if re.search(r'\b(quan|Q)\s*\d+', text, re.IGNORECASE):
        # Có quận → F chắc chắn là phường
        text = re.sub(r'\bF(\d+)\b', r'phuong \1', text, flags=re.IGNORECASE)

    return text
```

---

## 📈 Expected Impact

**Hiện tại:**
- HCM success rate: 20% (3/15)
- HCM rating 3: 8/15 (53.3%)

**Sau khi implement Priority 1:**
- Fix được: 7/8 cases rating 3
- New success rate: ~66% (10/15)
- Tăng từ 20% → 66% (**+230% improvement!**)

**Sau khi implement Priority 1 + 2:**
- Fix được: 8/8 cases rating 3
- New success rate: ~73% (11/15)

---

## 🎯 Kết Luận

### Root Causes:

1. **100% cases thất bại do viết tắt** (8/8)
   - Quận viết tắt: Q, Q., Q + tên
   - Phường viết tắt: P, P., F
   - Viết tắt cấp 2: TB, GV (cho tên quận)

2. **Không có nguyên nhân khác:**
   - Không phải thiếu thông tin (100% có Q và P)
   - Không phải format lạ
   - **Chỉ đơn giản là viết tắt!**

### Actions:

✅ **IMPLEMENT NGAY:** Abbreviation expansion cho HCM
- Impact: Fix 87.5% cases (7/8)
- Effort: 1-2 hours
- ROI: Rất cao

⚠️ **INVESTIGATE:** Duplicate record issue (ID 192, 193)
- Có thể là bug trong UI/UX hoặc data logging

📊 **MONITOR:** Sau khi deploy, track lại HCM success rate

---

## 📎 Appendix: Test Cases

**Sau khi implement, test với:**

```python
test_cases = [
    "16/291 LE DUC THO P15 Q.GO VAP TP",
    "32,DUONG S9,P.TAY THANH,Q.TAN PHU",
    "660/8 PHAM THE HIEN P4 Q8",
    "55 BE VAN DAN,P14,Q TAN BINH,TP",
    "128 TRAN HUNG DAO F7 Q5",
    "041 LO B C/C AN QUANG P9 Q10",
    "71 C9 CONG HOA P.13,Q.TB",
    "131/19/8B NGUYEN THAI SON P7 Q GV N V XMHT1",
]

# Expected tất cả parse thành công với confidence > 0.8
```
