# Hướng dẫn Expose Flask App ra Internet

## 🎯 Mục đích
Expose Vietnamese Address Parser Flask app ra internet để test/demo mà không cần deploy chính thức.

---

## 📋 So sánh các phương án

| Tiêu chí | ngrok | localtunnel | Cloudflare Tunnel |
|----------|-------|-------------|-------------------|
| **Độ dễ** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Tốc độ setup** | < 2 phút | < 3 phút | ~5 phút |
| **Miễn phí** | Có (giới hạn) | Có | Có (không giới hạn) |
| **Stable URL** | Không (trừ paid) | Có thể request | Có |
| **Bandwidth** | Giới hạn | Không giới hạn | Không giới hạn |
| **Tốc độ** | Nhanh | Trung bình | Rất nhanh |
| **Khuyên dùng** | ✅ Demo nhanh | Test ngắn hạn | Dùng lâu dài |

---

## Option 1: 🚀 ngrok (KHUYÊN DÙNG - ĐƠN GIẢN NHẤT)

### Bước 1: Cài đặt ngrok

**macOS (Homebrew):**
```bash
brew install ngrok/ngrok/ngrok
```

**Windows (Chocolatey):**
```bash
choco install ngrok
```

**Hoặc download trực tiếp:** https://ngrok.com/download

### Bước 2: Đăng ký tài khoản (optional nhưng nên làm)
1. Đăng ký miễn phí tại: https://dashboard.ngrok.com/signup
2. Copy authtoken từ dashboard
3. Kích hoạt:
```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### Bước 3: Chạy app

**Terminal 1 - Chạy Flask app:**
```bash
python app.py
```
App sẽ chạy tại http://localhost:9797

**Terminal 2 - Expose với ngrok:**
```bash
ngrok http 9797
```

### Kết quả:
```
ngrok                                                                    (Ctrl+C to quit)

Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        Asia Pacific (ap)
Latency                       12ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok.io -> http://localhost:9797

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

🎉 **Copy URL `https://abc123.ngrok.io`** và chia sẻ với bất kỳ ai!

### Tính năng nâng cao:

**Custom subdomain (cần paid account):**
```bash
ngrok http 9797 --subdomain=address-parser
# URL: https://address-parser.ngrok.io
```

**Basic auth protection:**
```bash
ngrok http 9797 --basic-auth="username:password"
```

**Web Inspector:**
- Mở http://127.0.0.1:4040 để xem tất cả requests/responses
- Rất hữu ích cho debugging!

---

## Option 2: 🌐 localtunnel

### Bước 1: Cài đặt (cần Node.js)
```bash
npm install -g localtunnel
```

### Bước 2: Chạy app
**Terminal 1 - Flask:**
```bash
python app.py
```

**Terminal 2 - localtunnel:**
```bash
lt --port 9797
```

### Với custom subdomain:
```bash
lt --port 9797 --subdomain address-parser
# URL: https://address-parser.loca.lt
```

### Lưu ý:
- Lần đầu truy cập sẽ có màn hình xác nhận IP
- Click "Continue" để tiếp tục
- URL cố định nếu dùng `--subdomain` (nhưng không đảm bảo 100%)

---

## Option 3: ☁️ Cloudflare Tunnel (Chuyên nghiệp nhất)

### Bước 1: Cài đặt cloudflared

**macOS:**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Windows:**
Download từ: https://github.com/cloudflare/cloudflared/releases

**Linux:**
```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### Bước 2: Login Cloudflare
```bash
cloudflared tunnel login
```
Browser sẽ mở, login vào Cloudflare account (tạo miễn phí nếu chưa có).

### Bước 3: Tạo tunnel
```bash
cloudflared tunnel create address-parser
```

### Bước 4: Chạy tunnel
**Terminal 1 - Flask:**
```bash
python app.py
```

**Terminal 2 - Cloudflare tunnel:**
```bash
cloudflared tunnel --url http://localhost:9797
```

### Kết quả:
```
Your quick tunnel has been created! Visit it at:
https://abc-def-ghi.trycloudflare.com
```

### Permanent tunnel (với config file):
1. Tạo file `cloudflared-config.yml`:
```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /path/to/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: address-parser.yourdomain.com
    service: http://localhost:9797
  - service: http_status:404
```

2. Route DNS (trên Cloudflare dashboard)

3. Chạy:
```bash
cloudflared tunnel run address-parser
```

---

## 🔥 Quick Start Script

Tôi đã tạo script `start_ngrok.sh` để bạn chạy nhanh:

```bash
chmod +x start_ngrok.sh
./start_ngrok.sh
```

---

## 🛡️ Security Best Practices

### 1. Tắt Debug Mode trong production
Sửa `app.py` line 299:
```python
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=9797)  # debug=False!
```

### 2. Thay đổi SECRET_KEY
Sửa `app.py` line 21:
```python
import secrets
app.secret_key = secrets.token_hex(32)  # Random key
```

### 3. Rate limiting (optional)
Cài đặt Flask-Limiter:
```bash
pip install Flask-Limiter
```

Thêm vào `app.py`:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)
```

### 4. HTTPS Only
Ngrok/Cloudflare tự động cung cấp HTTPS, nhưng thêm force HTTPS:
```python
from flask_talisman import Talisman
Talisman(app)
```

---

## 🐛 Troubleshooting

### Lỗi "Port 9797 already in use"
```bash
# Tìm process đang dùng port
lsof -i :9797

# Kill process
kill -9 <PID>
```

### Ngrok: "Failed to complete tunnel connection"
- Check firewall/antivirus
- Thử region khác: `ngrok http 9797 --region=us`
- Restart ngrok

### Database locked error
SQLite có thể bị lock khi nhiều requests đồng thời. Consider:
1. Thêm timeout: `sqlite3.connect('db.sqlite', timeout=20)`
2. Hoặc dùng connection pooling

### Slow response từ tunnel
- Ngrok free có latency cao, normal
- Cloudflare nhanh hơn nhiều
- Consider deploy thật nếu cần production speed

---

## 📊 Monitoring & Analytics

### Ngrok Web Inspector
- URL: http://localhost:4040
- Xem tất cả requests, responses, timing
- Replay requests để debug

### Cloudflare Dashboard
- Analytics về traffic
- Security events
- Rate limiting stats

---

## 💰 Chi phí

| Service | Free Tier | Paid (monthly) |
|---------|-----------|----------------|
| **ngrok** | 1 online tunnel, random URL | $8 - custom domains, 3 tunnels |
| **localtunnel** | Unlimited, free | N/A |
| **Cloudflare** | Unlimited bandwidth, tunnels | Free forever |

---

## ✅ Checklist trước khi share URL

- [ ] Đã tắt `debug=True` trong app.py
- [ ] Đã test tất cả features (parse, random, rating, stats)
- [ ] Database có data để test
- [ ] Không có sensitive info trong logs
- [ ] Đã test trên mobile browser
- [ ] Set rate limiting nếu cần
- [ ] Backup database trước khi expose

---

## 🎓 Tips & Tricks

1. **Dùng ngrok cho demo nhanh** (< 1 giờ)
2. **Dùng Cloudflare cho session dài** (nhiều ngày)
3. **Monitor logs trong khi expose:**
   ```bash
   python app.py | tee flask.log
   ```
4. **Test với curl trước:**
   ```bash
   curl https://your-url.ngrok.io/random
   ```
5. **Share URL với context:**
   - "Đây là demo app, có thể chậm"
   - "URL sẽ thay đổi sau X giờ"
   - "Không lưu data quan trọng"

---

## 📞 Cần giúp đỡ?

- ngrok docs: https://ngrok.com/docs
- localtunnel: https://github.com/localtunnel/localtunnel
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/

Happy tunneling! 🚀
