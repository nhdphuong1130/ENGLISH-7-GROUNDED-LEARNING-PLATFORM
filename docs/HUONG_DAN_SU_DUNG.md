# Hướng Dẫn Sử Dụng Nền Tảng Học Tiếng Anh 7 Grounded Learning

Tài liệu này hướng dẫn chi tiết cách cài đặt, vận hành và sử dụng ứng dụng học tập tiếng Anh 7 có gia sư AI cho học sinh và lập trình viên.

---

## 1. Khởi động Nhanh Hệ thống

### 1.1. Chuẩn bị môi trường
- Cài đặt Docker & Docker Compose.
- Cài đặt Python 3.12 (kèm `uv`).
- Cài đặt Flutter SDK (bản 3.27 trở lên).
- Cài đặt Make (`sudo apt install make` trên Linux).

### 1.2. Khởi chạy cụm dịch vụ
Từ thư mục gốc của dự án:
```bash
# Tạo file môi trường từ mẫu
cp .env.example .env

# Khởi động SQL Server, Neo4j, MinIO, API và Worker
make up

# Kiểm tra trạng thái các container
make ps
```

### 1.3. Nạp dữ liệu sách giáo khoa & Đồ thị tri thức
```bash
make seed
```
Lệnh trên sẽ tự động:
1. Nạp toàn bộ cây nội dung Unit 1 đến Unit 12 vào SQL Server.
2. Xây dựng ontology sư phạm (chủ đề, ngữ pháp, từ vựng, ngữ âm) và sinh vector embedding vào Neo4j.

---

## 2. Hướng dẫn Dành cho Học sinh trên Ứng dụng Di động

### 2.1. Đăng nhập & Đăng ký
- Mở ứng dụng Android hoặc truy cập bản web/PWA bằng Safari, Chrome hay trình
  duyệt hiện đại khác.
- Đăng nhập bằng email/số điện thoại và mật khẩu đã được cấp. Ứng dụng không
  hiển thị hoặc điền sẵn tài khoản, mật khẩu mẫu.
- Ứng dụng tự động ghi nhớ phiên đăng nhập an toàn qua Secure Storage, không cần đăng nhập lại mỗi khi mở app.

### 2.2. Học bài theo SGK (Tab Bài học)
- Danh sách bài học hiển thị đầy đủ 12 Unit học kỳ 1 và học kỳ 2:
  - **Học kỳ 1:** Unit 1 (Hobbies) đến Unit 6 + Review 1, 2.
  - **Học kỳ 2:** Unit 7 (Traffic) đến Unit 12 + Review 3, 4.
- Mỗi bài học chia thành các phần chuẩn SGK: *Getting Started, A Closer Look 1, A Closer Look 2, Communication, Skills 1, Skills 2, Looking Back & Project*.
- **Bài nghe Audio:** Nhấn nút Play/Pause tại các hoạt động có biểu tượng đĩa nghe để nghe giọng đọc bản xứ từ file audio chuẩn của NXB Giáo dục.
- **Bài tập tương tác:**
  - *Bảng phát âm:* Hiển thị từ và âm IPA (`/ə/` và `/ɜː/`) kèm hộp mẹo hướng dẫn phát âm chuẩn.
  - *True / False:* Chọn đúng/sai cho các câu hỏi đọc hiểu và nhận phản hồi giải thích ngay lập tức.
  - *Nối từ vựng / Điền từ:* Luyện tập phản xạ từ vựng trực quan.

### 2.3. Hỏi đáp Gia sư AI (Tab Gia sư)
- Nhập câu hỏi thắc mắc về bài học (ví dụ: *"Khi nào dùng thì hiện tại đơn?", "Cách phát âm đuôi -ed?"*).
- Học sinh có thể chụp ảnh hoặc chọn ảnh bài tập trong sách để gia sư phân tích câu hỏi.
- **Cam kết chống ảo giác:** Gia sư AI chỉ trả lời khi tìm thấy bằng chứng trong sách giáo khoa tiếng Anh 7 và luôn trích dẫn kèm số trang, số Unit cụ thể (`[Unit X, Trang Y]`).

### 2.4. Luyện tập Trắc nghiệm (Tab Kiểm tra)
- Chọn mức độ khó (Dễ / Trung bình / Khó) và thời gian làm bài (15, 45 hoặc 60 phút).
- Làm bài trắc nghiệm với đồng hồ đếm ngược và số lượt nghe bị giới hạn theo quy định bài thi.
- Nộp bài để nhận điểm số ngay lập tức cùng nhận xét đánh giá mức độ hoàn thành.

### 2.5. Hồ sơ Cá nhân (Tab Hồ sơ)
- Xem thông tin tài khoản học sinh.
- Chỉnh sửa họ tên, ngày sinh, trường học, khối lớp và phần giới thiệu bản thân.
- Đổi mật khẩu tài khoản trực tiếp trong ứng dụng.
- Đăng xuất an toàn khi muốn chuyển tài khoản.

---

## 3. Quản trị toàn bộ hệ thống trên ứng dụng và web

Admin dùng cùng một giao diện trên Android và web/PWA. Sau khi đăng nhập, hệ
thống tự mở không gian quản trị đáp ứng theo kích thước màn hình.

### 3.1. Đăng nhập admin và xác thực thiết bị mới

1. Nhập email và mật khẩu admin.
2. Nếu đây là thiết bị hoặc trình duyệt mới, hệ thống gửi OTP đến số điện thoại
   quản trị được cấu hình bởi `ENGLISH7_ADMIN_OTP_PHONE`.
3. Nhập mã 6 chữ số trong hộp **Xác thực OTP quản trị**.
4. Thiết bị được tin cậy trong 30 ngày. Mã nhận diện ngẫu nhiên được giữ trong
   vùng lưu trữ bảo mật của ứng dụng; server chỉ lưu bản băm SHA-256.

OTP hết hạn sau 5 phút và thử sai tối đa 5 lần cho mỗi yêu cầu. Xóa dữ liệu
trình duyệt, dùng chế độ riêng tư, cài lại ứng dụng hoặc thu hồi thiết bị tin cậy
sẽ yêu cầu OTP lại. Học sinh đăng nhập như bình thường và không đi qua bước này.

### 3.2. Dashboard và quản lý học viên

- Dashboard chỉ hiển thị số liệu tổng quan: tổng học viên, trạng thái tài khoản,
  bài đã nộp và nội dung nháp.
- Mục **Học viên** hỗ trợ tìm kiếm, lọc và phân trang. Bấm một tài khoản để xem
  chi tiết; từ đó admin có thể tạo/sửa, đặt lại mật khẩu, khóa/mở khóa, lưu trữ,
  khôi phục hoặc xóa có xác nhận.
- Nhập CSV/XLSX luôn chạy kiểm tra thử trước. Chỉ xác nhận nhập thật sau khi xem
  báo cáo dòng hợp lệ và dòng lỗi.
- Danh sách tài khoản có thể xuất CSV hoặc XLSX.

### 3.3. Quản lý nội dung học tập

- Admin quản lý sách, Unit, Section, Activity, quiz, flashcard SGK và nội dung
  luyện nói từ cùng giao diện.
- Nội dung mới hoặc vừa sửa ở trạng thái nháp. Dùng **Xem trước** để kiểm tra
  trích dẫn Unit/trang trước khi **Xuất bản**.
- Mỗi lần thay đổi tạo một revision bất biến để tra cứu lịch sử. Nội dung có thể
  được lưu trữ, khôi phục hoặc xóa an toàn theo trạng thái được phép.
- Nội dung AI phục vụ học tập vẫn phải dựa trên SGK và có trích dẫn
  `[Unit X, Page Y]`; admin không quản lý hay chỉnh sửa mô hình AI.

### 3.4. Tiến độ, hội thoại và nhật ký quản trị

- Mục tiến độ hiển thị danh sách tài khoản ngắn gọn. Bấm học viên để xem chi
  tiết kết quả học tập.
- Mục hội thoại cũng nhóm theo tài khoản. Khi mở một học viên, toàn bộ trao đổi
  với AI được ghép theo thứ tự thời gian và vẫn giữ mốc thời gian từng lượt.
- Có thể xuất lịch sử hội thoại theo tài khoản ở CSV, XLSX hoặc DOCX.
- Mục audit là nhật ký chỉ đọc cho các thao tác quản trị; không cho phép sửa hay
  xóa. Mật khẩu, OTP, token và khóa bí mật luôn được che khỏi nhật ký.

### 3.5. Cài PWA trên iPhone/iPad

1. Mở địa chỉ triển khai `/app/` bằng Safari.
2. Chọn **Chia sẻ** → **Thêm vào Màn hình chính**.
3. Mở biểu tượng English 7 vừa tạo và đăng nhập.

Sau mỗi lần triển khai bản web mới, đóng và mở lại PWA. Nếu giao diện vẫn là bản
cũ, xóa biểu tượng khỏi Màn hình chính, xóa dữ liệu website trong Safari rồi
thêm lại.

---

## 4. Lệnh Quản trị & Sao lưu CSDL Dành cho Kỹ thuật viên

| Tác vụ | Lệnh thực hiện |
|---|---|
| Xem log hệ thống | `make logs` |
| Chạy unit test backend | `make test-backend` |
| Chạy unit test mobile | `make test-mobile` |
| Chạy toàn bộ test | `make test` |
| Kiểm tra tĩnh Flutter | `make analyze` |
| Kiểm tra tài nguyên PWA | `make test-pwa` |
| Build PWA tại `/app/` | `make build-pwa` |
| Sao lưu CSDL ra file | `make backup-db` (Lưu vào thư mục `backups/`) |
| Phục hồi CSDL | `make restore FILE=backups/<ten_file>.bak` |
