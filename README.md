# English 7 Grounded Learning Platform

## Chạy lại ứng dụng trên máy đã cài đặt

Tab **Tiến độ** tổng hợp các bài kiểm tra đã nộp: số bài, tỷ lệ câu đúng và lịch sử
kèm thời điểm nộp. Dữ liệu lưu theo tài khoản trên backend và tải lại mỗi khi mở tab;
cũng có thể kéo xuống hoặc bấm làm mới. Bài chưa nộp không được tính.
Các bài đã nộp bằng phiên bản cũ (chưa lưu kết quả) không thể khôi phục lịch sử điểm.

Mở Android emulator trong Android Studio → Device Manager, sau đó chạy tại thư mục repo:

```bash
make run
```

Lệnh này bật API, SQL Server, Neo4j và MinIO, chờ backend healthy rồi mở Flutter trên
emulator đang kết nối. Cần Docker Compose hỗ trợ `up --wait`, Flutter và Python 3
trong PATH (script cũng tìm Flutter tại `$HOME/.local/opt/flutter/bin`).
Giữ terminal đang chạy; nhấn `q` để thoát Flutter, `make down` để dừng backend.
Trong Android Studio có thể chọn cấu hình **Run App (Android)** thay vì **Mobile App (Flutter)**.
Nếu dùng cấu hình Flutter trực tiếp, chạy `make up` trước rồi bấm **Thử lại** trên app.

`make up` chỉ bật backend cơ bản. `make run` và `make up-full` bật cả worker OCR;
lần đầu phải tải Torch, mô hình DocLayout-YOLO và các thư viện PaddleOCR nên cần
mạng ổn định và có thể mất nhiều thời gian. `docker compose up -d` cũng bật toàn
bộ dịch vụ, bao gồm worker.
Timeout tải thư viện vision là 300 giây; nếu mạng ngắt hẳn, build vẫn có thể thất bại.

Kiểm tra script khởi động bằng `make test-launcher`. Có thể chọn thiết bị cụ thể với
`make run DEVICE=emulator-5556`; với điện thoại thật, đặt `API_BASE_URL` thành địa chỉ LAN
của máy chạy backend. Máy cài mới vẫn cần làm các bước cấu hình và nạp dữ liệu bên dưới.

Nền tảng học tiếng Anh lớp 7 có gia sư AI sư phạm chuẩn mực, được tiếp đất (grounded) trực tiếp vào nội dung sách giáo khoa *Tiếng Anh 7 – Global Success* (Tập 1 và Tập 2).

Hệ thống này cho phép:

- Học bài học tương tác chuẩn SGK từ Unit 1 đến Unit 12 và các bài Review 1, 2, 3, 4.
- Nghe bài nghe audio bản ngữ chất lượng cao với trình phát âm thanh tích hợp.
- Làm các bài tập tương tác: bảng phát âm ngữ âm IPA (`/ə/`, `/ɜː/`), đọc hiểu True/False, nối từ vựng, trắc nghiệm.
- Hỏi đáp gia sư AI thông minh với cam kết 100% câu trả lời có trích dẫn xuất xứ sách giáo khoa (`[Unit X, Trang Y]`).
- Tải ảnh bài tập từ camera hoặc thư viện để gia sư AI nhận diện và hướng dẫn giải bài.
- Luyện tập bài thi trắc nghiệm tính giờ với giới hạn số lần nghe audio và chấm điểm tự động.
- Quản lý hồ sơ học sinh cá nhân (thông tin trường lớp, ngày sinh, đổi mật khẩu an toàn).

---

## Kiến trúc Hệ thống

Hệ thống gồm các thành phần chính:

- `sqlserver`: Microsoft SQL Server 2022 lưu trữ dữ liệu người dùng, hồ sơ, bài thi và cấu trúc bài học.
- `neo4j`: Cơ sở dữ liệu đồ thị Neo4j 5.26 lưu trữ Đồ thị Tri thức Sư phạm (Pedagogical Knowledge Graph) và chỉ mục vector kép (Dual Vector Indexing).
- `minio`: Lưu trữ đối tượng tương thích S3 cho các file âm thanh MP3 và hình ảnh bài học.
- `backend`: REST API xây dựng bằng Python 3.12 (FastAPI, SQLAlchemy, FastEmbed, Pytest).
- `worker`: Dịch vụ chạy nền xử lý tác vụ nạp tri thức và lập chỉ mục.
- `mobile`: Ứng dụng di động học sinh viết bằng Flutter / Dart 3.x (hỗ trợ Android & iOS).

Luồng truy xuất tri thức gia sư (GraphRAG):
1. Học sinh gửi câu hỏi hoặc ảnh chụp bài tập.
2. Backend trích xuất câu hỏi và sinh vector nhúng cục bộ qua `FastEmbed` (`BAAI/bge-small-en-v1.5`, 384 chiều).
3. Thực hiện truy vấn vector kép và duyệt đồ thị tri thức đa bước (multi-hop graph traversal).
4. Hợp nhất điểm số qua thuật toán Reciprocal Rank Fusion (RRF) để chọn đoạn trích SGK chuẩn nhất.
5. Mô hình ngôn ngữ tổng hợp lời giảng sư phạm kèm trích dẫn số trang và Unit gửi về cho học sinh.

### Hội thoại với Gia sư AI

Gia sư trả lời tự nhiên như một người hướng dẫn thân thiện, có thể dùng cách
xưng hô do học sinh yêu cầu, nhưng chỉ giải thích nội dung đã được xác minh từ
*Tiếng Anh 7 Global Success*. Lịch sử hội thoại chỉ giúp hiểu câu hỏi nối tiếp;
nó không bao giờ được xem là bằng chứng. Câu trả lời có căn cứ hiển thị nguồn
theo dạng `[Unit X, Page Y]`, còn câu hỏi ngoài phạm vi nhận lời từ chối cố định
thay vì nội dung suy đoán.

Mỗi tài khoản có tối đa 20 đoạn chat, mỗi đoạn tối đa 50 lượt hỏi–đáp. Chỉ sáu
lượt hoàn tất gần nhất được gửi cho AI và mỗi đoạn chat hết hạn sau 90 ngày.
Trong ứng dụng, học sinh có thể mở lịch sử, tiếp tục, xóa hoặc tạo đoạn chat mới.
Các API lịch sử đều kiểm tra quyền sở hữu theo tài khoản đăng nhập.

---

## Công nghệ Chính

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, FastEmbed, PyJWT, Argon2-cffi.
- **Mobile:** Flutter 3.27+, Dart, HTTP Client, Flutter Secure Storage, Audioplayers.
- **Cơ sở dữ liệu:** Microsoft SQL Server 2022, Neo4j Community 5.26, MinIO S3 Storage.
- **Hạ tầng cục bộ:** Docker & Docker Compose, GNU Make.

---

## Cấu trúc Thư mục

```text
backend/                Mã nguồn Backend API (FastAPI, GraphRAG, 163 unit tests)
mobile/                 Mã nguồn Ứng dụng di động Flutter (33 widget & unit tests)
backups/                Thư mục sao lưu CSDL SQL Server (.bak, .sql)
db_scripts/             Kịch bản SQL khởi tạo lược đồ và seed CSDL
docs/                   Tài liệu thiết kế, hướng dẫn sử dụng và cài đặt
data/                   Dữ liệu siêu dữ liệu bài học và manifest SGK
evaluation/             Bộ dữ liệu đánh giá độ chuẩn xác truy xuất
scripts/                Các kịch bản tự động hóa, build knowledge graph, test queries
docker-compose.yml      Cấu hình cụm Docker Compose cục bộ
Makefile                Bộ lệnh Make điều khiển toàn bộ hệ thống
DESIGN.md               Tài liệu thiết kế kiến trúc và giao diện hệ thống
README.md               Tài liệu giới thiệu và hướng dẫn tổng quan dự án
```

---

## Yêu cầu Trước Khi Chạy

Cần cài sẵn trên máy:

- Docker & Docker Compose plugin (`docker compose`)
- GNU Make (`make`)
- Python 3.12 (khuyến nghị kèm công cụ quản lý gói `uv`)
- Flutter SDK (bản 3.27 trở lên)

Kiểm tra nhanh phiên bản:

```bash
docker --version
docker compose version
make --version
python3 --version
flutter --version
```

---

## Cách Chạy Hệ Thống Khi Mới Kéo Repo Về

### 1. Tạo file môi trường

Sao chép từ file mẫu:

```bash
cp .env.example .env
```

### 2. Khởi động cụm dịch vụ Docker

```bash
make up
```

Kiểm tra trạng thái các container:

```bash
make ps
```

Các cổng dịch vụ mặc định:
- **Backend API:** `http://localhost:8000` (Tài liệu Swagger: `http://localhost:8000/docs`)
- **SQL Server:** `localhost:1433`
- **Neo4j Browser:** `http://localhost:7474`
- **MinIO Console:** `http://localhost:9001`

### 3. Nạp dữ liệu bài học và Xây dựng Đồ thị Tri thức

```bash
make seed
```

Lệnh này sẽ tự động khởi tạo dữ liệu giáo trình 12 Unit vào SQL Server và xây dựng đồ thị vector sư phạm vào Neo4j.

### 4. Khởi chạy ứng dụng di động Flutter

```bash
cd mobile
flutter run
```

---

## Danh Sách Lệnh Makefile Thường Dùng

| Lệnh | Ý nghĩa |
|---|---|
| `make run` | Bật backend, chờ healthy và mở app trên emulator |
| `make up` | Bật backend cơ bản ở chế độ chạy nền, chờ healthy |
| `make up-full` | Bật toàn bộ dịch vụ, bao gồm worker OCR |
| `make speech-setup` | Cài runtime giọng nói và tải mô hình miễn phí một lần |
| `make speech-up` | Bật VieNeu-TTS và nhận dạng giọng nói CPU |
| `make speech-down` | Dừng riêng dịch vụ giọng nói |
| `make seed-flashcards` | Nạp từ SGK có trích dẫn đã kiểm duyệt, không tạo trùng |
| `make down` | Dừng và dọn dẹp các container |
| `make ps` | Liệt kê trạng thái các container đang chạy |
| `make logs` | Xem live log từ tất cả các container |
| `make restart` | Khởi động lại toàn bộ dịch vụ |
| `make test` | Chạy toàn bộ kiểm thử backend (`pytest`) và mobile (`flutter test`) |
| `make test-backend` | Chạy unit/API test backend |
| `make test-mobile` | Chạy unit và widget test mobile |
| `make test-speech` | Kiểm thử runtime âm thanh, không cần tải mô hình |
| `make test-learning-live` | Kiểm tra lưu/đọc trên SQL Server và rollback dữ liệu kiểm thử |
| `make analyze` | Chạy phân tích cú pháp tĩnh Flutter (yêu cầu 0 lỗi, 0 cảnh báo) |
| `make seed` | Nạp dữ liệu SGK và lập chỉ mục đồ thị tri thức |
| `make backup-db` | Sao lưu CSDL SQL Server ra thư mục `backups/` |
| `make restore FILE=backups/<file>.bak` | Khôi phục CSDL từ bản sao lưu |
| `make clean` | Dọn dẹp các file cache `__pycache__`, `.pytest_cache`, `build` |

---

## Flashcard và luyện nói

Trong app, mở tab **Luyện tập** → chọn **Flashcard** hoặc **Luyện nói**.
Học sinh có thể dùng bộ SGK chỉ đọc hoặc tạo bộ cá nhân riêng tư, thêm/sửa/xóa từ,
sao chép từ SGK, đánh dấu từ khó và ôn theo lịch. Nhập từ tiếng Anh trước khi xem
đáp án; câu trả lời sai không được tăng mức ghi nhớ. Tab **Tiến độ** hiển thị số
thẻ đã ôn, thẻ đến hạn và lịch sử luyện nói bên cạnh kết quả kiểm tra.

`make up` và `make run` tự chạy migration, sau đó nạp những từ có bằng chứng trong
đoạn SGK đã kiểm duyệt và xuất bản. Không sinh số trang giả; bộ từ có thể chưa đủ
12 Unit nếu dữ liệu nguồn chưa đủ điều kiện. Dữ liệu cá nhân cũ được giữ nguyên.

Luyện nói dùng dịch vụ CPU riêng, không yêu cầu API trả phí:

```bash
make speech-setup   # lần đầu: cài thư viện và tải mô hình, cần Internet
make speech-up      # bật dịch vụ giọng nói
make run            # mở app trên emulator đã bật
```

Học sinh chọn giọng phản hồi tiếng Việt, thu tối đa 15 giây, nghe lại rồi chủ động
gửi. Hệ thống trả **bản chép lời và mức khớp từ**, không phải điểm phát âm âm vị.
VieNeu đọc phản hồi tiếng Việt; không dùng giọng này làm mẫu phát âm tiếng Anh.
Chỉ hiện audio mẫu tiếng Anh khi có nguồn đã kiểm duyệt. Bản thu không được lưu
dài hạn; lịch sử lưu câu mẫu, bản chép lời và nhận xét. Dịch vụ giọng nói tắt thì
flashcard và các chức năng học khác vẫn dùng được.

`make down` dừng cả các container giọng nói nếu đang bật, không xóa volume dữ liệu
hay model cache. Chi tiết cài đặt và giới hạn: [speech runtime](docs/speech-runtime.md).

## Tài Khoản Mẫu Đăng Nhập Mặc Định

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Học sinh mẫu | `student@example.com` | `password` |
| Quản trị viên | `admin@example.com` | `password` |

---

## Tài Liệu Tham Khảo Thêm

- [Tài liệu Thiết kế Hệ thống](DESIGN.md)
- [Hướng dẫn Sử dụng Chi tiết](docs/HUONG_DAN_SU_DUNG.md)
- [Đặc tả Cấu trúc Dự án](docs/project-structure.md)
- [Danh mục Thư viện Phụ thuộc](docs/dependencies.md)
- [Hướng dẫn Cài đặt Linux](docs/setup-linux.md)
- [Hướng dẫn Cài đặt Windows](docs/setup-windows.md)
- [Hướng dẫn Android Studio](docs/android-studio.md)
- [Hướng dẫn Cài đặt từ Git và Cấu hình SIM Gateway](docs/HUONG_DAN_CAI_DAT_GIT_SIM_GATEWAY.md)
