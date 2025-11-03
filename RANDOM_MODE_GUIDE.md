# Random Mode - User Guide

## ✨ Tính năng mới: Random Mode với Auto-Parse

### 🎯 Mục đích
Giúp người dùng test nhanh nhiều địa chỉ từ database chỉ với 1 click, không cần nhiều thao tác.

### 🚀 Cách sử dụng

#### Option 1: Từ tab Random
1. Click tab **"Random từ Database"**
2. Click button **"Load Random Sample"**
3. ✅ **Auto parse** - Địa chỉ được load và parse tự động
4. Xem kết quả bên phải
5. Đánh giá (1/2/3) nếu muốn
6. Click **"Next Random Address"** để xem địa chỉ tiếp theo
7. Lặp lại bước 5-6 để test nhiều địa chỉ

#### Option 2: Từ kết quả bất kỳ
- Sau khi có kết quả parsing (manual hoặc random)
- Nếu muốn test random, click button **"Load Random Sample"** ở phần Action Buttons
- Tự động chuyển sang Random Mode

### 🎨 UI Changes

#### Random Mode Badge
- Badge màu vàng xuất hiện ở góc trên phải form: **"🔀 Random Mode"**
- Badge có hiệu ứng pulse để dễ nhận biết

#### Form trong Random Mode
- ❌ Address textarea: **Disabled** (read-only, màu xám)
- ❌ Province input: **Disabled**
- ❌ District input: **Disabled**
- ❌ Parse button: **Hidden** (không cần vì đã auto parse)

#### Action Buttons
**Trong Random Mode:**
- 🔵 **"Next Random Address"** (primary, lớn) - Click để load địa chỉ tiếp theo
- ⚪ **"Back to Manual"** (secondary) - Quay lại Manual mode

**Trong Manual Mode:**
- ⚪ **"Parse địa chỉ khác"** - Reload trang
- ⚪ **"Load Random Sample"** - Chuyển sang Random mode

### 🔄 Workflow So sánh

#### Trước (Old):
```
Click "Load Random"
  → Fill form
  → Click "Parse Address"
  → View result
  → (Lặp lại từ đầu)
```

#### Sau (New):
```
Click "Load Random"
  → Auto parse
  → View result + Rate
  → Click "Next Random"
  → Auto parse địa chỉ mới
  → View result + Rate
  → ... (Lặp lại)
```

**Tiết kiệm:** ~3 clicks/địa chỉ → Nhanh hơn 3x!

### 🧪 Test Cases

#### Test 1: Load Random lần đầu
1. Vào tab Random
2. Click "Load Random Sample"
3. ✅ Expect: Form fill + auto parse + badge hiện + inputs disabled

#### Test 2: Next Random
1. Sau khi ở Random mode
2. Click "Next Random Address"
3. ✅ Expect: Load địa chỉ mới + auto parse

#### Test 3: Switch về Manual
1. Từ Random mode
2. Click "Back to Manual" hoặc click tab Manual
3. ✅ Expect: Badge ẩn + inputs enabled + parse button hiện

#### Test 4: Rating vẫn hoạt động
1. Ở Random mode
2. Đánh giá kết quả (1/2/3)
3. ✅ Expect: Rating saved vào database

#### Test 5: Mobile responsive
1. Resize browser xuống mobile size
2. Test Random mode
3. ✅ Expect: Layout stack vertically, buttons responsive

### 🛠️ Technical Details

#### JavaScript Functions
- `isRandomMode` (global flag) - Track current mode
- `setFormMode(mode)` - Enable/disable inputs + show/hide badge
- `parseAddress(address, province, district)` - Extracted helper
- `handleLoadRandom()` - Modified to auto parse
- `handleNextRandom()` - Wrapper for handleLoadRandom
- `displayResult()` - Conditional buttons based on mode

#### HTML Elements
- `#randomModeBadge` - Badge element (initially hidden)
- `#parseBtn` - Parse button (hide in random mode)
- `.random-mode-badge` - CSS class for badge styling

#### CSS Classes
- `.random-mode-badge` - Gradient yellow badge with pulse animation
- `textarea:disabled, input:disabled` - Grayed out disabled inputs

### 📊 Benefits

✅ **UX tốt hơn:**
- Chỉ 1 click để next
- Rõ ràng đang ở mode nào (badge)
- Không thể edit nhầm trong random mode

✅ **Nhanh hơn:**
- Auto parse ngay lập tức
- Không cần fill form thủ công
- Rapid iteration qua nhiều địa chỉ

✅ **Dễ test hơn:**
- Rapid testing của nhiều địa chỉ
- Thu thập ratings nhanh hơn
- Build ground truth dataset hiệu quả

### 🐛 Troubleshooting

**Vấn đề:** Badge không hiện khi click Load Random
- **Fix:** Kiểm tra browser console có lỗi không
- Refresh page và thử lại

**Vấn đề:** Parse button vẫn hiện trong Random mode
- **Fix:** Clear browser cache và reload

**Vấn đề:** Next Random không load địa chỉ mới
- **Fix:** Kiểm tra Flask app đang chạy
- Kiểm tra database có data không

**Vấn đề:** Form vẫn editable trong Random mode
- **Fix:** Check JavaScript console
- Đảm bảo `setFormMode('random')` được gọi

### 🎉 Enjoy!

Random mode giờ đã siêu nhanh! Bạn có thể test hàng trăm địa chỉ trong vài phút để build ground truth dataset cho model improvement.

Happy testing! 🚀
