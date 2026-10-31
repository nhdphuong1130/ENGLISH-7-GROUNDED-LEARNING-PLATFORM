#!/usr/bin/env python3
"""
SMS Gateway Tunnel Supervisor
Tự động duy trì cả 2 cầu nối:
1. ADB forward: máy tính port 8085 -> điện thoại port 8080
2. SSH Reverse Tunnel: EC2 port 18080 -> máy tính port 8085
Tự động khôi phục ngay lập tức nếu cáp bị lỏng, đổi mạng 4G/Wi-Fi hoặc ADB khởi động lại.
"""
import os
import subprocess
import sys
import time

KEY_FILE = os.path.expanduser("~/Downloads/english7-key.pem")
SERVER_HOST = "13.229.72.146"
SERVER_USER = "ubuntu"
LOCAL_PORT = 8085
REMOTE_PORT = 18080


def ensure_adb_forward():
    try:
        # 1. Đảm bảo ứng dụng SMS Gateway luôn chạy trên điện thoại
        proc = subprocess.run(
            ["adb", "shell", "ps -A | grep -i gateway"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if "me.capcom.smsgateway" not in proc.stdout:
            subprocess.run(
                ["adb", "shell", "monkey", "-p", "me.capcom.smsgateway", "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True,
                timeout=3,
            )

        # 2. Đảm bảo cổng 8085 luôn forward tới 8080
        res = subprocess.run(
            ["adb", "forward", "--list"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if f"tcp:{LOCAL_PORT}" not in res.stdout:
            subprocess.run(
                ["adb", "forward", f"tcp:{LOCAL_PORT}", "tcp:8080"],
                capture_output=True,
                text=True,
                timeout=3,
            )
    except Exception:
        pass


def main():
    ssh_proc = None
    ssh_cmd = [
        "ssh",
        "-i", KEY_FILE,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-N",
        "-R", f"0.0.0.0:{REMOTE_PORT}:127.0.0.1:{LOCAL_PORT}",
        f"{SERVER_USER}@{SERVER_HOST}",
    ]

    while True:
        ensure_adb_forward()

        # Check SSH process
        if ssh_proc is None or ssh_proc.poll() is not None:
            # Clean up old SSH processes if any
            subprocess.run(
                ["pkill", "-f", f"ssh.*-R.*{REMOTE_PORT}:127.0.0.1:{LOCAL_PORT}"],
                capture_output=True,
            )
            # Clean up remote port on EC2
            subprocess.run(
                [
                    "ssh", "-i", KEY_FILE,
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "ConnectTimeout=5",
                    f"{SERVER_USER}@{SERVER_HOST}",
                    f"sudo fuser -k {REMOTE_PORT}/tcp 2>/dev/null || true",
                ],
                capture_output=True,
            )
            ssh_proc = subprocess.Popen(ssh_cmd)

        time.sleep(2)


if __name__ == "__main__":
    main()
