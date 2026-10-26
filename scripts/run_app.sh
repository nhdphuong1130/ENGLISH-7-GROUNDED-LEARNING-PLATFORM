#!/usr/bin/env bash

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$PATH:$HOME/.local/opt/flutter/bin"
cd "$DIR"

echo "=================================================="
echo " 🚀 English 7 Grounded Learning Platform"
echo "=================================================="

# Start every runtime used by the app, including the image OCR worker.
echo "[1/2] Khởi động backend, OCR và runtime giọng nói..."
if ! docker compose -f docker-compose.yml -f compose.speech.yml up -d --wait --wait-timeout 180 api worker speech-runtime 2>/dev/null; then
    if ! docker compose up -d --wait --wait-timeout 180 api worker; then
        echo "Backend chưa sẵn sàng. Kiểm tra bằng: docker compose logs --tail=60 api sqlserver-init" >&2
        exit 1
    fi
fi
# This initializer exits successfully instead of staying up like an API service.
docker compose run --rm --no-deps minio-init

echo "Cập nhật lược đồ và nạp từ vựng SGK đã kiểm duyệt..."
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m english7.modules.flashcards.seed
setup_android_bridge() {
    local adb_bin
    adb_bin="$(command -v adb || echo "$HOME/Android/Sdk/platform-tools/adb")"
    if [[ -x "$adb_bin" ]]; then
        local physical_device
        physical_device="$("$adb_bin" devices | grep -v "emulator-" | awk 'NR>1 && $2=="device" {print $1}' | head -n 1)"
        if [[ -n "$physical_device" ]]; then
            echo "Phát hiện thiết bị Android: $physical_device. Đang cấu hình cầu nối ADB & SMS Gateway..."
            "$adb_bin" -s "$physical_device" reverse tcp:8000 tcp:8000 2>/dev/null || true
            "$adb_bin" -s "$physical_device" forward tcp:8080 tcp:8080 2>/dev/null || true

            # Khởi động sms_forwarder (port 8088 -> 8080) cho Docker API truy cập
            if ! pgrep -f "scripts/sms_forwarder.py" >/dev/null; then
                nohup python3 "$DIR/scripts/sms_forwarder.py" >/dev/null 2>&1 &
            fi

            # Đảm bảo app SMS Gateway mở sẵn
            if "$adb_bin" -s "$physical_device" shell pm list packages | grep -q "me.capcom.smsgateway"; then
                "$adb_bin" -s "$physical_device" shell monkey -p me.capcom.smsgateway -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
            fi
        fi
    fi
}

setup_android_bridge

if [[ "${1:-}" == "--backend-only" ]]; then
    exit 0
fi

command -v flutter >/dev/null || { echo "Không tìm thấy Flutter trong PATH." >&2; exit 1; }
command -v python3 >/dev/null || { echo "Cần python3 để chọn thiết bị Flutter." >&2; exit 1; }
port="$(docker compose port api 8000 | head -n 1 | awk -F: '{print $NF}')"
[[ "$port" =~ ^[0-9]+$ ]] || { echo "Không xác định được cổng API." >&2; exit 1; }

# 2. Launch Flutter App
echo "[2/2] Launching Flutter Mobile App..."
cd "$DIR/mobile"

device="${1:-android}"
api_host=localhost
if [[ "$device" == android ]]; then
    device="$(flutter devices --machine | python3 -c '
import json, sys
devices = json.load(sys.stdin)
android_devices = [d["id"] for d in devices if d.get("targetPlatform", "").startswith("android")]
physical = [d for d in android_devices if not d.startswith("emulator-")]
if physical:
    print(physical[0])
elif android_devices:
    print(android_devices[0])
else:
    print("")')"
    if [[ -z "$device" ]]; then
        echo "Hãy cắm điện thoại Android hoặc mở Android emulator trong Device Manager rồi chạy lại." >&2
        exit 1
    fi
fi

if [[ "$device" == emulator-* ]]; then
    api_host=10.0.2.2
else
    # Physical device: setup adb reverse for API & forward for SMS Gateway
    ADB_BIN="$(command -v adb || echo "$HOME/Android/Sdk/platform-tools/adb")"
    if [[ -x "$ADB_BIN" ]]; then
        "$ADB_BIN" -s "$device" reverse tcp:8000 tcp:8000 2>/dev/null || true
        "$ADB_BIN" -s "$device" forward tcp:8080 tcp:8080 2>/dev/null || true
    fi
    api_host=127.0.0.1
fi
exec flutter run -d "$device" "--dart-define=API_BASE_URL=${API_BASE_URL:-http://$api_host:$port}"
