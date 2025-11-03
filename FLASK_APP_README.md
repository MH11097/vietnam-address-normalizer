# Vietnamese Address Parser - Flask Web App

Web interface cho Vietnamese Address Parser, tận dụng logic từ `demo.py` để cung cấp giao diện thân thiện với người dùng.

## 🌟 Features

✅ **Input linh hoạt:**
- Nhập địa chỉ thủ công với form
- Load random sample từ database
- Hỗ trợ province/district hints (optional)

✅ **Hiển thị kết quả chi tiết:**
- Đầy đủ 5 phases của parsing pipeline
- Color-coded confidence scores
- Accordion để collapse/expand từng phase

✅ **Rating System:**
- Đánh giá chất lượng kết quả (1=Tốt, 2=Trung bình, 3=Kém)
- Lưu vào database để phân tích
- Xem statistics tổng hợp tại `/stats`

✅ **Modern UI:**
- Bootstrap 5 responsive design
- Smooth animations
- Mobile-friendly

## 📁 Cấu trúc files

```
/app.py                          # Flask app chính
/templates/
  ├── index.html                 # Trang chủ với form input
  └── stats.html                 # Trang statistics
/static/
  ├── css/style.css              # Custom CSS
  └── js/script.js               # Frontend JavaScript
/requirements.txt                # Python dependencies
```

## 🚀 Cách chạy

### 1. Install dependencies (nếu chưa có Flask)

```bash
pip install Flask==3.0.0 Werkzeug==3.0.1
```

Hoặc:

```bash
pip install -r requirements.txt
```

### 2. Chạy Flask app

```bash
python3 app.py
```

### 3. Truy cập web app

Mở browser và vào: **http://localhost:5000**

## 🎯 Cách sử dụng

### Option 1: Nhập địa chỉ thủ công

1. Chọn tab **"Nhập thủ công"**
2. Nhập địa chỉ vào text area
3. (Optional) Nhập Province/District hints
4. Click **"Parse Address"**
5. Xem kết quả chi tiết với 5 phases
6. Đánh giá chất lượng kết quả (1/2/3)

### Option 2: Load random sample từ DB

1. Chọn tab **"Random từ Database"**
2. Click **"Load Random Sample"**
3. Form sẽ tự động điền địa chỉ từ database
4. Click **"Parse Address"**
5. Xem kết quả và đánh giá

### Xem Statistics

- Truy cập: **http://localhost:5000/stats**
- Hoặc click link "View Statistics" ở footer

## 📊 API Endpoints

### `POST /parse`
Parse một địa chỉ

**Request:**
```json
{
  "address": "NGO394 DOI CAN P.CONG VI BD HN",
  "province": "Hà Nội",
  "district": null,
  "cif_no": "CIF123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "phase1": { ... },
    "phase2": { ... },
    "phase3": { ... },
    "phase4": { ... },
    "phase5": { ... }
  },
  "summary": {
    "ward": "Cống Vị",
    "district": "Ba Đình",
    "province": "Hà Nội",
    "confidence": 0.95
  },
  "metadata": {
    "original_address": "...",
    "total_time_ms": 125.5
  }
}
```

### `GET /random`
Load random address từ database

**Response:**
```json
{
  "success": true,
  "data": {
    "cif_no": "CIF123",
    "address": "123 Doi Can...",
    "province": "Hà Nội",
    "district": "Ba Đình"
  }
}
```

### `POST /submit_rating`
Submit user rating

**Request:**
```json
{
  "rating": 1
}
```

**Response:**
```json
{
  "success": true,
  "record_id": 5,
  "message": "Đã lưu đánh giá thành công!"
}
```

### `GET /stats`
Xem statistics page

## 🎨 Screenshots

### Trang chủ
- Form nhập địa chỉ với 2 tabs
- Modern Bootstrap 5 design

### Trang kết quả
- 5 phases hiển thị trong accordions
- Color-coded confidence scores
- Rating buttons ở cuối

### Trang statistics
- Tổng số ratings
- Phân bố theo rating (1/2/3)
- Average confidence by rating

## 🔧 Customization

### Thay đổi port
Sửa trong `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Thay 5000 → 8080
```

### Thêm custom CSS
Edit file: `static/css/style.css`

### Sửa giao diện
Edit templates: `templates/index.html`, `templates/stats.html`

## 📝 Notes

- Flask app sử dụng session để lưu last parse result cho rating feature
- Secret key trong production nên thay bằng random string
- Database connection được reuse từ `src/utils/db_utils.py`
- Tất cả parsing logic import từ `src/processors/` modules

## 🐛 Troubleshooting

**Lỗi: "ModuleNotFoundError: No module named 'flask'"**
→ Chạy: `pip install Flask==3.0.0`

**Lỗi: "Address 'localhost:5000' already in use"**
→ Port 5000 đang được dùng bởi process khác. Thay đổi port hoặc kill process cũ.

**Lỗi database connection**
→ Kiểm tra file `data/address.db` có tồn tại không.

## 🎉 Enjoy!

Flask app đã sẵn sàng để test! Mở browser và bắt đầu parse addresses!
