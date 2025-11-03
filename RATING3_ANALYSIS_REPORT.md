# Báo Cáo Phân Tích Chi Tiết Cases Rating = 3

**Ngày tạo:** 2025-10-30
**Tổng số records:** 73 cases (32.9% tổng số ratings)

---

## 📊 Tổng Quan Phân Loại

| Nhóm | Số lượng | Tỷ lệ | Mô tả |
|------|----------|-------|-------|
| 1.1 - Viết tắt quá nhiều | 29 | 39.7% | Địa chỉ có quá nhiều viết tắt (TP, Q., P., MT, etc.) |
| 1.4 - Thiếu thông tin địa lý | 19 | 26.0% | Không có tên province/district/ward trong text |
| 2 - Confidence thấp | 10 | 13.7% | Parse được nhưng confidence < 0.6 |
| 3.2 - UX Issue | 5 | 6.8% | Parse đúng (conf ≥ 0.8) nhưng user đánh giá 3 |
| 1.2 - Địa chỉ cơ quan | 5 | 6.8% | Địa chỉ công ty/trường học/cơ quan |
| 1.0 - Khác | 3 | 4.1% | Không parse được, nguyên nhân chưa rõ |
| 3.1 - Parse sai district | 2 | 2.7% | Parse sai district (conf 0.8+) |

---

## 🔍 Phân Tích Chi Tiết Từng Nhóm

### NHÓM 1.1: VIẾT TẮT QUÁ NHIỀU (29 records - 39.7%)

**Đặc điểm:**
- Địa chỉ chứa nhiều viết tắt: TP, TPTH, MT, Q., P., F., TT, BMT, VTAU
- Hệ thống không thể expand các viết tắt này
- Không có province/district đầy đủ trong text

**Ví dụ điển hình:**
```
1. "59 NGUYEN CHICH P NAM NGAN TPTH" (THANH HOA)
   → TPTH = Thành phố Thanh Hóa
   → P = Phường

2. "21 NAM KY KHOI NGHIA P4 MT" (TIEN GIANG)
   → MT = Mỹ Tho
   → P4 = Phường 4

3. "16/291 LE DUC THO P15 Q.GO VAP TP" (HO CHI MINH)
   → Q. = Quận
   → P15 = Phường 15
   → TP = Thành phố

4. "15D1 TONG DUY TAN,P.9, VTAU" (BA RIA VUNG TAU)
   → VTAU = Vũng Tàu

5. "95,TDP 7,P.TAN LOI,TP BMT" (DAK LAK)
   → BMT = Buôn Ma Thuột
```

**💡 Recommendations:**

1. **Tạo abbreviation expansion dictionary:**
   ```python
   CITY_ABBR = {
       'TPTH': 'thanh pho thanh hoa',
       'BMT': 'buon ma thuot',
       'MT': 'my tho',
       'VTAU': 'vung tau',
       'TXHB': 'thi xa hoa binh'
   }

   COMMON_ABBR = {
       r'\bTP\b': 'thanh pho',
       r'\bQ\.': 'quan',
       r'\bP\.': 'phuong',
       r'\bF\.': 'phuong',
       r'\bTT\b': 'thi tran'
   }
   ```

2. **Áp dụng trong phase 1 preprocessing:**
   - Expand các viết tắt phổ biến trước khi normalize
   - Kết hợp với known_province để expand chính xác hơn

3. **Priority: HIGH** - Giải quyết được 39.7% cases rating 3

---

### NHÓM 1.4: THIẾU THÔNG TIN ĐỊA LÝ (19 records - 26.0%)

**Đặc điểm:**
- Chỉ có số nhà, tên đường, tổ, ấp
- Không có tên province/district/ward rõ ràng trong text
- Chỉ dựa vào known_province hint

**Ví dụ điển hình:**
```
1. "660/8 PHAM THE HIEN P4 Q8" (HO CHI MINH)
   → Có P4, Q8 nhưng không match được

2. "90 TO VINH DIEN PHUONG DIEN BIEN" (THANH HOA)
   → Phường Điện Biên ở Thanh Hóa
   → Nhầm lẫn với tỉnh Điện Biên

3. "128 TRAN HUNG DAO F7 Q5" (HO CHI MINH)
   → F7 = Floor 7 hoặc Phường 7?

4. "XA EAKMUT-HUYEN EAKAR" (DAK LAK)
   → Có đầy đủ info nhưng format lạ với dấu gạch ngang

5. "HAI THANH TINH GIA THANH HOA" (THANH HOA)
   → "TINH GIA" có thể là xã
```

**💡 Recommendations:**

1. **Cải thiện xử lý số quận/phường:**
   ```python
   # Khi có known_province = "HO CHI MINH"
   "Q8" → "quan 8"
   "P4" → "phuong 4"
   "F7" → "phuong 7"  # F thường là floor nhưng context HCM → phường
   ```

2. **Sử dụng known_province để tìm district/ward:**
   - Khi parse được "DIEN BIEN" và known_province = "THANH HOA"
   - Tìm trong database: phường Điện Biên thuộc Thanh Hóa

3. **Xử lý format đặc biệt:**
   - Xử lý dấu gạch ngang: "XA-HUYEN" → "xa ... huyen ..."

4. **Priority: MEDIUM-HIGH** - 26% cases, cần logic phức tạp hơn

---

### NHÓM 2: CONFIDENCE THẤP (10 records - 13.7%)

**Đặc điểm:**
- Parse được province nhưng confidence chỉ 0.4
- Không parse được district/ward
- Thường là địa chỉ cơ quan/công ty

**Ví dụ điển hình:**
```
1. "CTY CP YEN SON" (THAI NGUYEN)
   → Parsed: thai nguyen (confidence: 0.4)

2. "CONG TY TNHH KAPS TEX VINA" (PHU THO)
   → Parsed: phu tho (confidence: 0.4)

3. "LU DOAN 454" (HAI DUONG)
   → Parsed: hai duong (confidence: 0.4)

4. "THON 2_EANAM_EAHLEO" (DAK LAK)
   → Parsed: dak lak (confidence: 0.4)
```

**💡 Recommendations:**

1. **Đây là các case khó:**
   - Địa chỉ cơ quan: không có thông tin địa lý chi tiết
   - Chỉ match được province từ hint

2. **Có thể chấp nhận:**
   - Với địa chỉ công ty, chỉ có province là hợp lý
   - Nên hiển thị warning cho user biết là "incomplete address"

3. **Cải thiện UI:**
   - Khi confidence < 0.5, hiển thị: "⚠️ Chỉ tìm được tỉnh/thành phố"
   - User sẽ hiểu và không đánh giá rating 3

4. **Priority: LOW** - Khó cải thiện, nên focus vào UX

---

### NHÓM 3.2: UX ISSUE (5 records - 6.8%)

**⚠️ VẤN ĐỀ NGHIÊM TRỌNG:**
- Parse ĐẶT (confidence 0.8 - 1.0, exact match)
- User vẫn đánh giá rating = 3

**Ví dụ điển hình:**
```
1. "NGHIA TAN GIA NGHIA" (DAK NONG)
   → Parsed: dak nong / gia nghia / nghia tan
   → Confidence: 1.0 (EXACT MATCH!)
   ⚠️ PARSE HOÀN TOÀN ĐÚNG nhưng rating = 3

2. "P. HUU NGHI TXHB" (HOA BINH) [2 records trùng]
   → Parsed: hoa binh / hoa binh / huu nghi
   → Confidence: 0.97 (EXACT MATCH!)
   ⚠️ PARSE HOÀN TOÀN ĐÚNG nhưng rating = 3

3. "TT Z191 CAU DIEN TU LIEM" (HA NOI)
   → Parsed: ha noi / thach that
   → Confidence: 0.8
   ⚠️ SAI: Phải là quận Từ Liêm, không phải huyện Thạch Thất!

4. "HOI BAI-TAN THANH-BA RIA VUNG TAU" (BA RIA VUNG TAU)
   → Parsed: ba ria vung tau / vung tau
   → Confidence: 0.8
   ⚠️ SAI?: Có thể thiếu ward
```

**💡 Recommendations:**

1. **Case "NGHIA TAN GIA NGHIA" và "P. HUU NGHI TXHB":**
   - **Nguyên nhân:** User không hiểu kết quả hoặc UI không rõ
   - **Giải pháp:**
     - Hiển thị rõ ràng hơn: "✅ Ward: Nghĩa Tân, District: Gia Nghĩa, Province: Đắk Nông"
     - Thêm confidence score với icon: "🎯 99.7% chính xác"

2. **Case "TT Z191 CAU DIEN TU LIEM":**
   - **Nguyên nhân:** Parse SAI district
   - "TU LIEM" → nên match quận Từ Liêm, không phải huyện Thạch Thất
   - "CAU DIEN" là tên đường ở Từ Liêm
   - **Giải pháp:** Cải thiện matching logic cho "TU LIEM"

3. **Priority: CRITICAL**
   - 3/5 cases parse ĐÚNG → UX issue
   - 2/5 cases parse SAI → algorithm issue

---

### NHÓM 1.2: ĐỊA CHỈ CƠ QUAN (5 records - 6.8%)

**Đặc điểm:**
- Địa chỉ cơ quan, công ty, trường học
- Không có thông tin địa lý cụ thể

**Ví dụ điển hình:**
```
1. "BAN DAN VAN TINH UY" (HA TINH)
   → Ban Dân Vận Tỉnh Ủy

2. "SO 2 NGO 149 TO 20A QUAN HOA" (HA NOI)
   → "SO 2" = Số 2 (địa chỉ)
   → "QUAN HOA" = Quận Hòa? hay phường Quan Hòa?

3. "TRUONG CAO DANG XAY DUNG CT DO THI" (HA NOI)
   → Trường Cao đẳng

4. "P2009 CT2 CHUNG CU BAN CO YEU CHINH PHU..." (HA NOI)
   → Chung cư Ban Cờ
```

**💡 Recommendations:**

1. **Phân loại địa chỉ cơ quan:**
   - Detect keywords: "BAN", "SO", "TRUONG", "CHUNG CU"
   - Flag là "organization address"

2. **Xử lý riêng:**
   - "QUAN HOA" → phường Quan Hoa (Cầu Giấy, Hà Nội)
   - Cần context-aware parsing

3. **Priority: MEDIUM** - 6.8% cases, cần thêm rules

---

### NHÓM 3.1: PARSE SAI DISTRICT (2 records - 2.7%)

**Đặc điểm:**
- Parse được với confidence cao (0.8+)
- Nhưng district KHÔNG KHỚP với known_district

**Ví dụ điển hình:**
```
1. "TRUONG TH TRAN THOI 3 HUYEN CAI NUOC" (CA MAU)
   Known district: THANH PHO CA MAU
   Parsed district: ca mau (không đúng!)
   → Sai: Phải là "huyen cai nuoc", không phải "ca mau"

2. "TRUONG TIEU HOC THI TRAN THOI BINH A HUYEN TB TINH CA MAU" (CA MAU)
   Known district: THANH PHO CA MAU
   Parsed district: ca mau (không đúng!)
   → Sai: Text có "HUYEN" rõ ràng nhưng parse nhầm
```

**💡 Recommendations:**

1. **Bug trong extraction logic:**
   - Text có "HUYEN CAI NUOC" hoặc "HUYEN TB"
   - Nhưng parse thành "ca mau" (tên tỉnh/thành phố)

2. **Giải pháp:**
   - Ưu tiên match "HUYEN + tên" trước khi match tỉnh
   - Khi có cả province và district cùng tên (Cà Mau), phải phân biệt

3. **Priority: HIGH** - Bug cần fix

---

### NHÓM 1.0: KHÁC (3 records - 4.1%)

**Đặc điểm:**
- Không parse được gì
- Không thuộc các nhóm trên

**Ví dụ:**
```
1. "P302T3 CT18 KDT VIET HUNG, GIANG BIEN" (HA NOI / QUAN LONG BIEN)
   → Format chung cư phức tạp

2. "160 YEN BAI PHUONG 4" (BA RIA VUNG TAU / THANH PHO VUNG TAU)
   → "YEN BAI" là tên tỉnh nhưng ở đây là tên đường

3. "THON TU DO, TINH AN DONG" (QUANG NGAI / THANH PHO QUANG NGAI)
   → Có "TINH" nhầm với từ "tỉnh"
```

**💡 Recommendations:**
- Case-by-case analysis
- Cần thêm nhiều special rules

---

## 📋 Tổng Kết và Action Items

### Priority 1 (CRITICAL):
1. **Fix nhóm 3.1** (Parse sai district với Cà Mau) → 2 records
2. **Review nhóm 3.2** (UX issues với high confidence) → 5 records
   - Fix "TU LIEM" matching bug
   - Improve result display UI

### Priority 2 (HIGH):
3. **Nhóm 1.1** (Viết tắt quá nhiều) → 29 records (39.7%)
   - Implement abbreviation expansion
   - Biggest impact on success rate

### Priority 3 (MEDIUM):
4. **Nhóm 1.4** (Thiếu thông tin địa lý) → 19 records (26%)
   - Improve district/ward inference from province hint
   - Better handling of Q8, P4, etc.

5. **Nhóm 1.2** (Địa chỉ cơ quan) → 5 records
   - Add organization address detection
   - Special handling for QUAN HOA, etc.

### Priority 4 (LOW):
6. **Nhóm 2** (Confidence thấp) → 10 records
   - Mainly UI improvement
   - Show warnings for incomplete addresses

---

## 📊 Kết Luận

**Nếu giải quyết được các nhóm priority 1-2:**
- Có thể cải thiện: 29 + 19 + 5 + 2 = **55 records (75.3%)**
- Rating 3 sẽ giảm từ 73 → ~18 records
- Success rate tổng thể tăng đáng kể

**Root causes chính:**
1. **Không xử lý viết tắt** (39.7%)
2. **Không infer district/ward từ province** (26%)
3. **UX không rõ ràng** (6.8%)
4. **Bugs trong matching logic** (2.7%)
