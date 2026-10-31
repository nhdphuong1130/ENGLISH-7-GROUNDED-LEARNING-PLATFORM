#!/usr/bin/env bash
# ==============================================================================
# Script kết nối cầu nối SMS Gateway từ điện thoại Android cắm cáp tới AWS EC2
# ==============================================================================
set -euo pipefail

KEY_FILE="${1:-$HOME/Downloads/english7-key.pem}"
SERVER_HOST="${2:-13.229.72.146}"
SERVER_USER="${3:-ubuntu}"
LOCAL_PORT=8085
REMOTE_PORT=18080

echo "=== Cầu nối SMS OTP Gateway tới AWS EC2 ($SERVER_HOST) ==="

if [[ ! -f "$KEY_FILE" ]]; then
    echo "❌ Lỗi: Không tìm thấy SSH key: $KEY_FILE"
    echo "Sử dụng: $0 [đường_dẫn_key_pem] [ip_server]"
    exit 1
fi

chmod 400 "$KEY_FILE" 2>/dev/null || true

# 1. Kiểm tra thiết bị Android
ADB_BIN="$(command -v adb || echo "$HOME/Android/Sdk/platform-tools/adb")"
if ! command -v "$ADB_BIN" >/dev/null 2>&1; then
    echo "❌ Lỗi: Không tìm thấy adb trong hệ thống."
    exit 1
fi

DEVICE="$("$ADB_BIN" devices | grep -v "emulator-" | awk 'NR>1 && $2=="device" {print $1}' | head -n 1)"
if [[ -z "$DEVICE" ]]; then
    echo "❌ Lỗi: Không tìm thấy điện thoại Android nào được kết nối qua USB (adb devices)."
    echo "Hãy cắm cáp USB, bật USB Debugging và thử lại."
    exit 1
fi

echo "📱 Đã kết nối điện thoại: $DEVICE"

# Mở ứng dụng SMS Gateway nếu có
if "$ADB_BIN" -s "$DEVICE" shell pm list packages | grep -q "me.capcom.smsgateway"; then
    "$ADB_BIN" -s "$DEVICE" shell monkey -p me.capcom.smsgateway -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
    echo "✅ Đã kích hoạt ứng dụng SMS Gateway trên điện thoại"
fi

# Thiết lập forward cổng từ máy tính đến Gateway trên điện thoại (8085 -> 8080)
"$ADB_BIN" -s "$DEVICE" forward "tcp:$LOCAL_PORT" tcp:8080
echo "✅ Đã forward cổng adb: $LOCAL_PORT -> 8080"

# Watchdog tự động khôi phục adb forward khi điện thoại đổi mạng (Wi-Fi <-> 4G) hoặc cắm lại cáp
(
    while true; do
        if ! "$ADB_BIN" forward --list 2>/dev/null | grep -q "tcp:$LOCAL_PORT"; then
            "$ADB_BIN" -s "$DEVICE" forward "tcp:$LOCAL_PORT" tcp:8080 2>/dev/null || true
        fi
        sleep 2
    done
) &
WATCHDOG_PID=$!
trap 'kill $WATCHDOG_PID 2>/dev/null || true' EXIT INT TERM

# Dọn dẹp tiến trình tunnel cũ nếu có
pkill -f "ssh.*-R.*18080:127.0.0.1:$LOCAL_PORT" || true

echo "🚀 Đang thiết lập SSH Reverse Tunnel tới $SERVER_HOST..."
echo "👉 EC2 ($REMOTE_PORT) <---> Máy tính ($LOCAL_PORT) <---> Điện thoại (8080)"
echo "Nhấn Ctrl+C để dừng cầu nối."

exec ssh -i "$KEY_FILE" \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -N -R "0.0.0.0:$REMOTE_PORT:127.0.0.1:$LOCAL_PORT" \
    "$SERVER_USER@$SERVER_HOST"
