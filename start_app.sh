#!/bin/bash
# start_with_logs.sh

# Tạo thư mục logs nếu chưa có
mkdir -p logs

LOG_DIR="logs"
PYTHON_LOG="$LOG_DIR/python_app.log"
TUNNEL_LOG="$LOG_DIR/localtunnel.log"
COMBINED_LOG="$LOG_DIR/combined.log"

echo "🚀 Starting applications with logging..."
echo "📝 Logs directory: $LOG_DIR"
echo ""

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$COMBINED_LOG"
}

# Function to run Python app with restart and logging
run_python_app() {
    while true; do
        log_message "📱 Starting Python app..."
        python3 app.py >> "$PYTHON_LOG" 2>&1
        EXIT_CODE=$?
        log_message "⚠️  Python app stopped with exit code: $EXIT_CODE. Restarting in 3 seconds..."
        sleep 3
    done
}

# Function to run LocalTunnel with restart and logging
run_localtunnel() {
    # Wait for Python app to start
    sleep 5
    while true; do
        log_message "🌐 Starting LocalTunnel..."
        npx localtunnel --port 9797 --subdomain bidv-address-parser >> "$TUNNEL_LOG" 2>&1
        EXIT_CODE=$?
        log_message "⚠️  LocalTunnel stopped with exit code: $EXIT_CODE. Restarting in 3 seconds..."
        sleep 3
    done
}

# Cleanup function
cleanup() {
    echo ""
    log_message "🛑 Stopping all applications..."
    pkill -P $$
    log_message "✅ All services stopped"
    exit 0
}

trap cleanup INT TERM

# Clear old logs (optional)
> "$PYTHON_LOG"
> "$TUNNEL_LOG"
> "$COMBINED_LOG"

log_message "=========================================="
log_message "Starting BIDV Address Parser Services"
log_message "=========================================="

# Run both in background
run_python_app &
run_localtunnel &

echo "✅ Both services are running with auto-restart!"
echo ""
echo "📱 Python app: http://localhost:9797"
echo "🌐 Public URL: https://bidv-address-parser.loca.lt"
echo ""
echo "📝 Log files:"
echo "   - Python app: $PYTHON_LOG"
echo "   - LocalTunnel: $TUNNEL_LOG"
echo "   - Combined: $COMBINED_LOG"
echo ""
echo "💡 View logs in real-time:"
echo "   tail -f $PYTHON_LOG"
echo "   tail -f $TUNNEL_LOG"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running
wait
