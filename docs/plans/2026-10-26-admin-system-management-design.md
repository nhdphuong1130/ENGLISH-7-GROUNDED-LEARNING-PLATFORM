# Thiết kế quản trị toàn bộ hệ thống

**Ngày:** 2026-10-26  
**Trạng thái:** Đã được xác nhận

## 1. Mục tiêu

Mở rộng vai trò `admin` để quản lý toàn bộ dữ liệu vận hành của English 7 Grounded Learning Platform trên cả ứng dụng Flutter và web. Hai giao diện có đầy đủ chức năng tương đương, dùng chung API, quy tắc nghiệp vụ và cơ chế phân quyền phía backend.

Phạm vi quản trị bao gồm:

- CRUD học viên và trạng thái tài khoản.
- CRUD nội dung học tập, bài kiểm tra, flashcard và luyện nói.
- Quản lý tài liệu sách giáo khoa và trích dẫn nguồn.
- Theo dõi tiến độ, bài làm và toàn bộ lịch sử hội thoại của học viên.
- Nhập/xuất dữ liệu hàng loạt.
- Lưu lịch sử phiên bản nội dung và nhật ký thao tác admin.

Không đưa prompt, lựa chọn model AI, khóa API hoặc cấu hình hạ tầng vào giao diện quản trị.

## 2. Kiến trúc giao diện

Sử dụng một codebase Flutter responsive cho Android, iOS PWA và web. Sau khi đăng nhập, người dùng có vai trò `admin` được chuyển tới khu vực `/admin`.

- Trên web và tablet: dùng thanh điều hướng bên trái, bảng dữ liệu rộng và biểu mẫu nhiều cột.
- Trên điện thoại: dùng điều hướng gọn, danh sách dạng thẻ và biểu mẫu một cột.
- App và web cung cấp đầy đủ chức năng tương đương.
- Các widget, model, validation và API client quản trị được dùng chung; chỉ bố cục thay đổi theo kích thước màn hình.

Các module chính:

1. Dashboard.
2. Học viên.
3. Nội dung học tập.
4. Bài kiểm tra.
5. Flashcard.
6. Luyện nói.
7. Tiến độ.
8. Hội thoại.
9. Nhập/xuất dữ liệu.
10. Nhật ký quản trị.

## 3. Phân quyền và xác thực

Hệ thống giữ một vai trò quản trị duy nhất là `admin`. Mọi API quản trị phải kiểm tra vai trò tại dependency của router; việc ẩn nút trên client không được xem là biện pháp bảo mật.

Admin đăng nhập bằng mật khẩu. Khi đăng nhập trên thiết bị mới, server bắt buộc xác thực OTP trước khi cấp phiên quản trị. Thiết bị tin cậy có thời hạn và admin có thể thu hồi toàn bộ phiên đăng nhập. Mật khẩu cũ không bao giờ được hiển thị hoặc có khả năng khôi phục; admin chỉ được đặt lại mật khẩu.

Học viên không được gọi bất kỳ API quản trị nào, kể cả khi tự tạo HTTP request hoặc sửa trạng thái client.

## 4. Quản lý học viên

Danh sách học viên chỉ hiển thị thông tin cơ bản: họ tên hoặc tài khoản, số điện thoại/email, lớp, trường và trạng thái. Admin bấm vào học viên để xem hồ sơ, tiến độ, bài làm, flashcard cá nhân, luyện nói và lịch sử hội thoại.

Admin được phép:

- Tạo học viên mới.
- Sửa họ tên, số điện thoại/email, lớp và trường.
- Đặt lại mật khẩu mà không xem mật khẩu cũ.
- Khóa hoặc mở khóa tài khoản.
- Lưu trữ tài khoản.
- Xóa vĩnh viễn tài khoản và dữ liệu liên quan.

Khóa hoặc lưu trữ là lựa chọn mặc định, giữ nguyên dữ liệu học tập và ngăn đăng nhập. Xóa vĩnh viễn phải hiển thị số lượng dữ liệu liên quan, yêu cầu nhập lại thông tin xác nhận và ghi audit log đầy đủ.

Lớp và trường chỉ là trường văn bản trong hồ sơ học viên; không tạo module hoặc bảng quản lý trường/lớp riêng.

## 5. Quản lý nội dung

Admin được CRUD các loại nội dung sau:

- Unit và bài học.
- Từ vựng, nghĩa, từ loại, phiên âm và ví dụ.
- Quy tắc ngữ pháp và ví dụ.
- Âm phát âm và nội dung luyện phát âm.
- Câu hỏi, đáp án, lời giải và cấu hình bài kiểm tra.
- Bộ flashcard và thẻ.
- Bài luyện nói, câu mẫu và tiêu chí chấm.
- Tài liệu sách giáo khoa, trang sách và trích dẫn nguồn.

Mọi nội dung học thuật phải giữ yêu cầu grounding bằng Unit và trang sách. Dữ liệu từ vựng, ngữ pháp, chủ đề và phát âm tiếp tục ánh xạ vào ontology hiện có (`Topic`, `GrammarRule`, `Vocabulary`, `PronunciationSound`).

## 6. Quy trình xuất bản và phiên bản

Nội dung sử dụng vòng đời:

`Bản nháp → Xem trước → Xuất bản → Lưu trữ`

- Học viên chỉ nhìn thấy phiên bản đã xuất bản.
- Admin có thể xem trước dưới góc nhìn học viên trên app và web.
- Mỗi lần xuất bản tạo một phiên bản bất biến.
- Admin có thể so sánh và khôi phục phiên bản cũ; thao tác khôi phục tạo một phiên bản mới thay vì sửa lịch sử.
- Nếu xuất bản thất bại, phiên bản đang phục vụ học viên không thay đổi.

Nội dung đã phát sinh bài làm, tiến độ hoặc tham chiếu chỉ được lưu trữ để bảo toàn lịch sử. Chỉ nội dung chưa từng được sử dụng mới được xóa vĩnh viễn.

## 7. Tiến độ và hội thoại

Màn hình tiến độ bắt đầu bằng danh sách học viên với thông tin tổng quan tối thiểu. Khi chọn một học viên, admin xem chi tiết mức hoàn thành, kết quả kiểm tra, flashcard, luyện nói và các chỉ số liên quan.

Màn hình hội thoại cũng bắt đầu bằng danh sách tài khoản học viên. Khi chọn một học viên, hệ thống hiển thị toàn bộ trao đổi giữa học viên và AI theo thứ tự thời gian, có mốc thời gian nhưng không chia thành các thẻ hội thoại rời rạc theo từng phiên.

Admin có thể tìm kiếm, lọc khoảng thời gian và xuất dữ liệu.

## 8. Nhập và xuất dữ liệu

- CSV và XLSX dùng cho học viên và dữ liệu dạng bảng.
- CSV/XLSX hỗ trợ nhập học viên và nội dung hàng loạt.
- CSV, XLSX, DOCX và PDF dùng cho báo cáo, tiến độ và hội thoại khi phù hợp.

Luồng nhập dữ liệu gồm tải tệp, kiểm tra toàn bộ, xem trước thay đổi, hiển thị lỗi theo từng dòng và xác nhận ghi dữ liệu. Không ghi một phần khi tệp chưa vượt qua validation, trừ khi admin chủ động chọn chế độ bỏ qua dòng lỗi trong một thiết kế sau này.

## 9. Nhật ký quản trị

Audit log là dữ liệu chỉ đọc, ghi lại:

- Admin thực hiện thao tác.
- Loại thao tác và đối tượng.
- Thời gian, IP và nền tảng.
- Dữ liệu trước và sau thay đổi.
- Kết quả thành công hoặc thất bại.
- Request ID để truy vết và chống thao tác lặp.

Không ghi mật khẩu, OTP, access token, refresh token, khóa API hoặc bí mật hệ thống. Audit log không được sửa hoặc xóa từ giao diện quản trị.

## 10. Xử lý lỗi và đồng thời

- Thao tác phá hủy phải có cảnh báo tác động và bước xác nhận rõ ràng.
- Request phá hủy hoặc xuất bản dùng idempotency key để tránh thực hiện hai lần.
- Khi hai thiết bị cùng sửa một bản ghi, backend kiểm tra phiên bản và trả lỗi xung đột thay vì ghi đè im lặng.
- Client hiển thị lỗi theo trường và giữ lại dữ liệu biểu mẫu để admin sửa.
- Tác vụ dài như nhập tệp, xuất báo cáo và tái lập chỉ mục chạy qua job nền, có trạng thái và khả năng thử lại an toàn.

## 11. Kiểm thử và tiêu chí chấp nhận

### Backend

- Mọi API admin trả `403` cho học viên.
- CRUD học viên và nội dung tuân thủ validation và quan hệ dữ liệu.
- Khóa, lưu trữ và xóa vĩnh viễn hoạt động đúng chính sách.
- Xuất bản, lịch sử phiên bản và khôi phục không làm mất phiên bản cũ.
- Audit log đầy đủ và không chứa bí mật.
- Nhập/xuất xử lý đúng dữ liệu hợp lệ, lỗi từng dòng và tệp lớn.

### Flutter app và web

- Cùng một hành vi nghiệp vụ trên màn hình điện thoại, tablet và desktop.
- Điều hướng admin không xuất hiện với học viên.
- Các bảng chuyển thành danh sách/thẻ phù hợp trên màn hình nhỏ.
- Xác nhận thao tác nguy hiểm và xử lý xung đột hiển thị rõ ràng.

### End-to-end

- Đăng nhập admin bằng mật khẩu và OTP trên thiết bị mới.
- Tạo, sửa, khóa, mở khóa và xóa học viên.
- Tạo bản nháp, xem trước, xuất bản và khôi phục nội dung.
- Nhập CSV/XLSX và xuất báo cáo/hội thoại.
- Học viên không thể truy cập API hoặc giao diện quản trị.

## 12. Ngoài phạm vi

- Quản lý prompt hoặc model AI.
- Quản lý khóa API và cấu hình hạ tầng.
- Tạo thêm vai trò Super Admin, Content Admin hoặc Support Admin.
- Xây dựng thực thể trường, lớp hoặc năm học riêng.
