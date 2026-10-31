# Hướng Dẫn Cài Đặt Từ Git Và Cấu Hình SIM Gateway

Tài liệu này hướng dẫn cài đặt **English 7 Grounded Learning Platform** từ
GitHub và dùng một điện thoại Android có SIM làm cổng gửi SMS OTP thật.

> Không đưa file `.env`, mật khẩu SIM Gateway, API key hoặc thông tin đăng nhập
> thật lên Git. Repository đã cấu hình `.gitignore` để bỏ qua `.env`.

## 1. Mô hình hoạt động

```text
Ứng dụng Flutter
       |
       v
FastAPI trong Docker
       |
       v
Máy tính -- USB/ADB hoặc Wi-Fi LAN --> SMS Gateway trên Android --> Nhà mạng
                                                                  |
                                                                  v
                                                        Số điện thoại nhận OTP
```

Điện thoại chạy SIM Gateway chỉ đóng vai trò gửi SMS bằng SIM đang lắp trong
máy. Số nhận OTP có thể là một điện thoại khác.

## 2. Yêu cầu

### Máy tính

- Git.
- Docker và Docker Compose plugin (`docker compose`).
- GNU Make.
- Python 3.
- Flutter SDK 3.27 trở lên và Android SDK/ADB.

Kiểm tra nhanh:

```bash
git --version
docker --version
docker compose version
make --version
python3 --version
flutter doctor
adb version
```

### Điện thoại làm SIM Gateway

- Điện thoại Android có SIM đang hoạt động và còn khả năng gửi SMS.
- Cáp USB truyền dữ liệu nếu sử dụng phương án USB/ADB.
- Ứng dụng [SMS Gateway for Android](https://github.com/capcom6/android-sms-gateway)
  có package `me.capcom.smsgateway`.
- Quyền gửi SMS và quyền chạy nền cho ứng dụng Gateway.

Nhà mạng có thể tính cước cho mỗi SMS. Nên thử với một số điện thoại trước khi
gửi nhiều lần.

## 3. Lấy mã nguồn từ GitHub

```bash
git clone https://github.com/nhdphuong1130/Nhom3_SMS_OTP.git
cd Nhom3_SMS_OTP
```

Nếu đã clone dự án, cập nhật nhánh chính bằng:

```bash
git switch main
git pull --ff-only origin main
```

## 4. Tạo cấu hình cục bộ

Sao chép file mẫu:

```bash
cp .env.example .env
```

Đổi các mật khẩu mẫu và JWT secret trong `.env`. Với SIM Gateway, cấu hình:

```dotenv
ENGLISH7_SMS_GATEWAY_URL=http://127.0.0.1:8080
ENGLISH7_SMS_GATEWAY_USERNAME=sms
ENGLISH7_SMS_GATEWAY_PASSWORD=mat_khau_gateway_cua_ban
```

`ENGLISH7_SMS_GATEWAY_USERNAME` và `ENGLISH7_SMS_GATEWAY_PASSWORD` phải giống
chính xác thông tin Basic Auth hiển thị trong ứng dụng SMS Gateway.

Kiểm tra `.env` không bị Git theo dõi:

```bash
git status --short --ignored .env
```

Kết quả mong đợi bắt đầu bằng `!! .env`.

## 5. Cấu hình ứng dụng SMS Gateway trên Android

1. Cài APK từ trang Releases của dự án SMS Gateway for Android.
2. Mở ứng dụng và cấp quyền gửi SMS khi Android yêu cầu.
3. Chọn chế độ **Local Server**.
4. Giữ cổng mặc định là `8080`.
5. Ghi lại Username và Password của Basic Authentication.
6. Bật Local Server và chuyển trạng thái từ **Offline** sang **Online**.
7. Trong cài đặt pin của Android, chọn không tối ưu pin cho SMS Gateway để
   dịch vụ không bị dừng khi tắt màn hình.

Có thể mở `http://<IP-điện-thoại>:8080/docs` trong cùng mạng LAN để kiểm tra
Swagger của Gateway. Không công khai cổng `8080` ra Internet.

## 6. Kết nối bằng USB/ADB — khuyến nghị khi demo

### 6.1. Chuẩn bị điện thoại

1. Bật **Tùy chọn nhà phát triển**.
2. Bật **Gỡ lỗi USB**.
3. Cắm cáp USB truyền dữ liệu vào máy tính.
4. Chấp nhận hộp thoại cho phép gỡ lỗi trên điện thoại.
5. Mở SMS Gateway và bảo đảm Local Server đang Online.

Kiểm tra thiết bị:

```bash
adb devices
```

Trạng thái phải là `device`, không phải `unauthorized` hoặc `offline`.

### 6.2. Khởi chạy tự động

Từ thư mục gốc của dự án:

```bash
make run
```

Script `scripts/run_app.sh` sẽ tự động:

- khởi động Backend và các dịch vụ Docker;
- tạo `adb reverse` cho API ở cổng `8000`;
- tạo `adb forward` từ máy tính cổng `8080` đến Gateway trên điện thoại;
- chạy `scripts/sms_forwarder.py` để Docker truy cập Gateway qua cổng `8088`;
- mở ứng dụng Flutter trên thiết bị Android.

Luồng kết nối trong chế độ này:

```text
Backend Docker -> host.docker.internal:8088 -> 127.0.0.1:8080
                -> ADB forward -> SMS Gateway trên điện thoại
```

Giữ cáp USB trong suốt phiên demo. Nếu rút cáp, SMS đã được Gateway tiếp nhận
vẫn có thể được gửi, nhưng các yêu cầu OTP mới qua cầu nối ADB sẽ thất bại.

## 7. Kết nối qua Wi-Fi LAN — dùng được khi rút cáp

Điện thoại Gateway và máy tính phải ở cùng mạng Wi-Fi.

1. Mở SMS Gateway và lấy địa chỉ Local IP, ví dụ `192.168.1.50`.
2. Thay URL trong `.env`:

   ```dotenv
   ENGLISH7_SMS_GATEWAY_URL=http://192.168.1.50:8080
   ```

3. Khởi động lại Backend để nạp cấu hình mới:

   ```bash
   docker compose up -d --force-recreate api
   ```

4. Giữ Local Server trên điện thoại ở trạng thái Online.

Với phương án này, có thể rút cáp USB mà Backend vẫn gửi OTP qua Wi-Fi. Điện
thoại Gateway vẫn cần bật, có kết nối Wi-Fi, có SIM và được phép gửi SMS.

Nếu điện thoại đổi IP sau khi kết nối lại Wi-Fi, cập nhật URL trong `.env` rồi
khởi động lại container `api`. Có thể đặt DHCP reservation trên router để IP
điện thoại ổn định hơn.

## 8. Kết nối EC2 với điện thoại làm SMS Gateway

EC2 không thể truy cập trực tiếp `127.0.0.1` hoặc IP Wi-Fi nội bộ của điện thoại. Có hai cách kết nối:

### 8.1. Phương án 1: Dùng SSH Reverse Tunnel (Khuyên dùng khi cắm cáp vào máy tính)

Trên server EC2, file `.env` đã được cấu hình sẵn:
```dotenv
ENGLISH7_SMS_GATEWAY_URL=http://host.docker.internal:18080
ENGLISH7_SMS_GATEWAY_USERNAME=sms
ENGLISH7_SMS_GATEWAY_PASSWORD=mat_khau_gateway_cua_ban
```

Từ máy tính đã cắm cáp USB vào điện thoại Android, chỉ cần chạy script:
```bash
bash scripts/sms_tunnel_ec2.sh
```
Script sẽ tự động:
1. Phát hiện điện thoại Android qua ADB;
2. Kích hoạt ứng dụng SMS Gateway;
3. Forward cổng ADB `8085 -> 8080`;
4. Thiết lập SSH Reverse Tunnel: cổng `18080` trên EC2 sẽ chuyển tiếp về SMS Gateway trên điện thoại.

### 8.2. Phương án 2: Kết nối EC2 qua Cloudflare Tunnel (Dùng độc lập không cần máy tính)

Trên điện thoại, dùng Termux và Cloudflare Tunnel để chuyển tiếp HTTPS
tới Local Server của SMS Gateway:

```bash
pkg update
pkg install cloudflared
cloudflared tunnel --url http://127.0.0.1:8080
```

Cloudflared sẽ hiển thị một URL `https://...trycloudflare.com`. Cập nhật URL
đó trên server, giữ nguyên Username/Password Basic Auth đang cấu hình trong
SMS Gateway, rồi khởi động lại API.

Quick Tunnel đổi URL sau mỗi lần chạy. Triển khai lâu dài nên dùng
Named Tunnel với hostname cố định. Không công khai trực tiếp cổng HTTP
`8080` và không tắt Basic Auth.

## 9. Khởi động hệ thống thủ công

Nếu không dùng `make run`, thực hiện:

```bash
make up
make seed
cd mobile
flutter run
```

Khi chạy Flutter trên điện thoại thật, cần bảo đảm thiết bị truy cập được API.
`make run` đã tự cấu hình cầu nối ADB, nên đây là cách đơn giản hơn khi demo.

## 10. Kiểm tra gửi OTP

1. Mở màn hình đăng ký hoặc quên mật khẩu trên ứng dụng Flutter.
2. Nhập số điện thoại nhận, ví dụ `09xxxxxxxx`.
3. Chọn **Gửi mã OTP qua SMS**.
4. Kiểm tra trạng thái gửi trong ứng dụng SMS Gateway.
5. Kiểm tra SMS trên điện thoại nhận và nhập mã sáu chữ số vào ứng dụng.

Backend tự chuẩn hóa số Việt Nam từ `09xxxxxxxx` sang `+849xxxxxxxx`, sau đó
Gateway gửi SMS bằng SIM vật lý. OTP có hiệu lực trong 5 phút và bị xóa sau khi
xác thực thành công.

Theo dõi log Backend:

```bash
docker compose logs -f api
```

Chỉ dùng log để chẩn đoán trong môi trường phát triển; không chia sẻ log có số
điện thoại hoặc OTP.

## 11. Xử lý lỗi thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `adb devices` báo `unauthorized` | Chưa cấp quyền gỡ lỗi USB | Rút/cắm lại cáp và chọn **Allow** trên điện thoại |
| Không thấy thiết bị | Cáp chỉ hỗ trợ sạc hoặc thiếu ADB | Đổi cáp/cổng USB, cài Android Platform Tools |
| Gateway báo Offline | Local Server chưa chạy | Mở ứng dụng và chuyển sang Online |
| Backend không kết nối Gateway | Sai URL, cổng hoặc cầu nối ADB | Chạy lại `make run`; kiểm tra cổng `8080` và `8088` |
| Trả về Dev mode thay vì gửi SMS | Thiếu mật khẩu Gateway hoặc container chưa nạp `.env` | Kiểm tra ba biến `ENGLISH7_SMS_GATEWAY_*`, sau đó tạo lại container API |
| Gateway trả `401 Unauthorized` | Username/password không khớp | Chép lại Basic Auth từ ứng dụng Gateway |
| Đã rút USB và không gửi được | Cấu hình vẫn dùng `127.0.0.1` qua ADB | Chuyển sang IP LAN của điện thoại theo mục 7 |
| Gateway nhận yêu cầu nhưng SMS không đi | Thiếu quyền SMS, SIM hết tiền hoặc mất sóng | Cấp lại quyền, kiểm tra SIM, sóng và cước nhà mạng |
| Gửi nhầm SIM trên máy hai SIM | Chưa chọn SIM mặc định | Chọn SIM gửi SMS mặc định trong Android/Gateway |

## 12. Dừng hệ thống

Nhấn `q` để dừng phiên `flutter run`, sau đó:

```bash
make down
```

Nếu không còn sử dụng USB debugging, có thể tắt tùy chọn này trên điện thoại để
giảm rủi ro bảo mật.

## 13. Tài liệu tham khảo

- [SMS Gateway for Android — mã nguồn và bản phát hành](https://github.com/capcom6/android-sms-gateway)
- [Hướng dẫn Local Server chính thức](https://docs.sms-gate.app/getting-started/local-server/)
- [Hướng dẫn cài đặt Linux](setup-linux.md)
- [Hướng dẫn cài đặt Windows](setup-windows.md)
- [Hướng dẫn Android Studio](android-studio.md)
