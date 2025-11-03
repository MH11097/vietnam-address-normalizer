# Update: Summary Format - 2 Rows INPUT/OUTPUT

## ✨ Tính năng mới

Summary section được format lại thành **2 dòng ngang nhau** để dễ so sánh INPUT vs OUTPUT.

## 📊 Layout Mới

```
┌────────────────────────────────────────────────────────────────────┐
│ Tóm tắt                                                            │
│                                                                    │
│ INPUT:  raw_address            | Ward: ____ | District: Ba Đình | Province: Hà Nội │
│ OUTPUT: remaining_address_part | Ward: Cống Vị | District: Ba Đình | Province: Hà Nội │
│                                                                    │
│ ─────────────────────────────────────────────────────────────────  │
│ Thời gian: 125ms | Confidence: 95% | Match Type: exact            │
└────────────────────────────────────────────────────────────────────┘
```

## 🎨 Color Coding

**Badges có màu khác nhau để phân biệt:**

- **Ward:** `bg-warning text-dark` (⚠️ Màu vàng/cam)
- **District:** `bg-success` (✅ Màu xanh lá)
- **Province:** `bg-primary` (🔵 Màu xanh dương)

## 📋 Dòng INPUT

**Format:**
```
INPUT: raw_address | Ward: known_ward | District: known_district | Province: known_province
```

**Hiển thị:**
- Raw address: Full địa chỉ gốc
- Known Ward: Từ database (thường là `____`)
- Known District: Từ database hoặc `____`
- Known Province: Từ database hoặc `____`

**Ví dụ:**
```
INPUT: CANH SAT PHONG CHAY CHUA CHAY | Ward: ____ | District: Quảng Trị | Province: Quảng Trị
```

## 📋 Dòng OUTPUT

**Format:**
```
OUTPUT: remaining_address | Ward: parsed_ward | District: parsed_district | Province: parsed_province
```

**Hiển thị:**
- Remaining address: Phần còn lại sau khi remove matched components
- Parsed Ward: Kết quả extract
- Parsed District: Kết quả extract
- Parsed Province: Kết quả extract

**Ví dụ:**
```
OUTPUT: CANH SAT PHONG CHAY CHUA | Ward: ____ | District: Quảng Trị | Province: Quảng Trị
```

## 🎯 Examples

### Example 1: Full Match
```
INPUT:  123 DOI CAN P.CONG VI BD HN  | Ward: ____     | District: ____     | Province: Hà Nội
OUTPUT: NGO394                        | Ward: Cống Vị  | District: Ba Đình  | Province: Hà Nội
```
👉 Dễ thấy: Ward và District được parse thành công, Province match với known value

### Example 2: Partial Match
```
INPUT:  UNKNOWN STREET ABC            | Ward: ____  | District: ____      | Province: ____
OUTPUT: UNKNOWN STREET                 | Ward: ____  | District: ____      | Province: ____
```
👉 Dễ thấy: Không parse được gì, OUTPUT giống INPUT

### Example 3: With Known District
```
INPUT:  456 NGUYEN TRAI                | Ward: ____        | District: Thanh Xuân | Province: Hà Nội
OUTPUT: 456                            | Ward: Khương Mai  | District: Thanh Xuân | Province: Hà Nội
```
👉 Dễ thấy: District match với known value, Ward được parse từ address

## 📝 Changes Made

### File: `app.py`

**Added to metadata:**
```python
'metadata': {
    'original_address': address_text,
    'known_ward': None,  # Usually not provided in raw data
    'known_district': district_known,
    'known_province': province_known,
    'remaining_address': formatted_output.get('remaining_1', '') or
                         formatted_output.get('remaining_2', '') or
                         formatted_output.get('remaining_3', ''),
    'total_time_ms': total_time
}
```

### File: `static/js/script.js`

**New Summary format:**

```javascript
<!-- INPUT Row -->
<div class="d-flex align-items-start gap-2 flex-wrap">
    <strong style="min-width: 70px;">INPUT:</strong>
    <span>${escapeHtml(metadata.original_address)}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-warning text-dark">Ward: ${metadata.known_ward || '____'}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-success">District: ${metadata.known_district || '____'}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-primary">Province: ${metadata.known_province || '____'}</span>
</div>

<!-- OUTPUT Row -->
<div class="d-flex align-items-start gap-2 flex-wrap">
    <strong style="min-width: 70px;">OUTPUT:</strong>
    <span>${escapeHtml(metadata.remaining_address || '____')}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-warning text-dark">Ward: ${escapeHtml(summary.ward)}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-success">District: ${escapeHtml(summary.district)}</span>
    <span class="text-muted">|</span>
    <span class="badge bg-primary">Province: ${escapeHtml(summary.province)}</span>
</div>
```

## 🎨 Visual Design

**Alignment:**
- `INPUT:` và `OUTPUT:` có fixed width (70px) để align
- Flexbox với `gap-2` cho spacing đều
- `flex-wrap` để responsive trên mobile

**Typography:**
- Label (INPUT/OUTPUT): Bold
- Address text: Normal weight
- Badges: Bootstrap badges với màu riêng
- Separators: Gray muted

## 📱 Responsive

**Desktop (>768px):**
```
INPUT:  full_address | Ward: ... | District: ... | Province: ...
OUTPUT: remaining    | Ward: ... | District: ... | Province: ...
```

**Mobile (<768px):**
```
INPUT:  address_here
        | Ward: ...
        | District: ...
        | Province: ...
OUTPUT: remaining
        | Ward: ...
        | District: ...
        | Province: ...
```

## ✅ Benefits

✅ **Dễ so sánh:** 2 dòng ngang nhau, cùng format
✅ **Visual clear:** Ward màu vàng, District xanh lá, Province xanh dương
✅ **Complete context:** Thấy rõ input vs output
✅ **Alignment:** Fixed label width giúp dễ đọc
✅ **Remaining visible:** Biết được phần nào chưa parse

## 🧪 Test Cases

### Test 1: Manual input - no hints
```
INPUT:  123 Doi Can Ba Dinh Ha Noi | Ward: ____ | District: ____ | Province: ____
OUTPUT: 123                         | Ward: ____  | District: Ba Đình | Province: Hà Nội
```

### Test 2: Manual input - with province hint
```
INPUT:  456 Unknown Street          | Ward: ____ | District: ____ | Province: Hà Nội
OUTPUT: 456 Unknown Street          | Ward: ____ | District: ____  | Province: Hà Nội
```

### Test 3: Random mode - full hints
```
INPUT:  NGO394 DOI CAN P.CONG VI   | Ward: ____ | District: Ba Đình | Province: Hà Nội
OUTPUT: NGO394                      | Ward: Cống Vị | District: Ba Đình | Province: Hà Nội
```

## 🎯 Key Improvements

1. **Side-by-side comparison** - INPUT và OUTPUT ngang nhau
2. **Color-coded badges** - Ward vàng, District xanh lá, Province xanh dương
3. **Remaining address visible** - Biết được phần nào chưa được parse
4. **Known values shown** - Thấy rõ hints từ database
5. **Consistent formatting** - Cùng structure giúp dễ so sánh

## 🚀 Deploy

```bash
# Hard refresh browser
Ctrl+Shift+R (Windows) hoặc Cmd+Shift+R (Mac)

# Test:
1. Parse một địa chỉ (manual hoặc random)
2. Xem phần Summary
3. ✅ Thấy 2 dòng INPUT/OUTPUT ngang nhau
4. ✅ Ward màu vàng, District xanh lá, Province xanh dương
```

## 🎉 Status

✅ **COMPLETED** - Summary format mới với 2 dòng dễ so sánh!
