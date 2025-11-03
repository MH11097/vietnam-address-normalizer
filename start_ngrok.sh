#!/bin/bash

# Script để chạy Flask app và ngrok cùng lúc
# Sử dụng: ./start_ngrok.sh

set -e  # Exit on error

echo "🚀 Starting Vietnamese Address Parser with ngrok..."
echo ""

# Kiểm tra ngrok đã cài chưa
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok chưa được cài đặt!"
    echo ""
    echo "Cài đặt ngrok:"
    echo "  macOS:   brew install ngrok/ngrok/ngrok"
    echo "  Windows: choco install ngrok"
    echo "  Hoặc:    https://ngrok.com/download"
    exit 1
fi

# Kiểm tra Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "❌ Python chưa được cài đặt!"
    exit 1
fi

PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Kiểm tra Flask app tồn tại
if [ ! -f "app.py" ]; then
    echo "❌ Không tìm thấy app.py trong thư mục hiện tại!"
    echo "Vui lòng chạy script từ thư mục gốc của project."
    exit 1
fi

# Kiểm tra port 9797 có đang được dùng không
if lsof -Pi :9797 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Port 9797 đang được sử dụng bởi process khác!"
    echo ""
    read -p "Bạn có muốn kill process đó không? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PID=$(lsof -ti:9797)
        kill -9 $PID
        echo "✅ Đã kill process $PID"
        sleep 1
    else
        echo "❌ Không thể tiếp tục khi port 9797 đang bận."
        exit 1
    fi
fi

# Tạo log directory
mkdir -p logs

echo "📦 Checking dependencies..."
$PYTHON_CMD -c "import flask" 2>/dev/null || {
    echo "❌ Flask chưa được cài đặt!"
    echo "Chạy: pip install -r requirements.txt"
    exit 1
}

# Hỏi người dùng muốn options gì
echo ""
echo "Chọn ngrok options:"
echo "  1) Quick start (random URL)"
echo "  2) Với basic auth (username/password)"
echo "  3) Custom subdomain (cần paid account)"
read -p "Lựa chọn (1-3, mặc định: 1): " choice
choice=${choice:-1}

NGROK_OPTS=""
case $choice in
    2)
        read -p "Username: " username
        read -sp "Password: " password
        echo ""
        NGROK_OPTS="--basic-auth=$username:$password"
        ;;
    3)
        read -p "Subdomain (vd: address-parser): " subdomain
        NGROK_OPTS="--subdomain=$subdomain"
        ;;
esac

echo ""
echo "🌟 Starting Flask app..."

# Chạy Flask app trong background
$PYTHON_CMD app.py > logs/flask.log 2>&1 &
FLASK_PID=$!

# Đợi Flask khởi động
sleep 3

# Kiểm tra Flask có chạy không
if ! ps -p $FLASK_PID > /dev/null; then
    echo "❌ Flask app failed to start. Check logs/flask.log"
    cat logs/flask.log
    exit 1
fi

echo "✅ Flask app running (PID: $FLASK_PID)"
echo "   Local:  http://localhost:9797"
echo ""

# Function để cleanup khi exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $FLASK_PID 2>/dev/null || true
    pkill -f "ngrok http" 2>/dev/null || true
    echo "✅ Cleaned up. Goodbye!"
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

echo "🌐 Starting ngrok tunnel..."
echo ""

# Chạy ngrok
ngrok http 9797 $NGROK_OPTS &
NGROK_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Services are running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Flask App:"
echo "   Local:       http://localhost:9797"
echo ""
echo "🌍 Public URL:"
echo "   Xem terminal ngrok bên dưới hoặc"
echo "   Mở: http://localhost:4040 (ngrok inspector)"
echo ""
echo "📊 Monitoring:"
echo "   Flask logs:  tail -f logs/flask.log"
echo "   Ngrok web:   http://localhost:4040"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Đợi cho đến khi user Ctrl+C
wait $NGROK_PID
