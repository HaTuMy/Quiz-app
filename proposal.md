**QUIZ APP proposal**
# Thông tin
- Nhóm
  - Thành viên 1: Nguyễn Quang Mạnh - 22645001 
  - Thành viên 2: Nguyễn Thanh Tường Vy -  22708841
  - Thành viên 3: Lê Hà Tú My - 22648801
  - Thành viên 4: Phạm Thị Ngọc Hương - 20065491
- Git repository: <[HaTuMy/Quiz-app](https://github.com/HaTuMy/Quiz-app)>
# Ý tưởng
## Minimum Viable Product
**User (Học sinh) :**

- Đăng ký, đăng nhập tài khoản
- Học sinh làm bài kiểm tra
- Học sinh xem điểm và đáp án sau khi làm bài 
- Thay đổi mật khẩu cá nhân

**Admin (Giáo viên Admin):**

- Thay đổi mật khẩu cá nhân
- Giáo viên tạo bài kiểm tra, thêm, chỉnh sửa, xóa câu hỏi (CURD)
- Giáo viên xem kết quả bài kiểm tra của học sinh
## Complete Product
**User (Học sinh) :**

- Đăng ký, đăng nhập tài khoản
- Học sinh làm bài kiểm tra
- Học sinh xem điểm và đáp án sau khi làm bài 
- Thay đổi mật khẩu cá nhân
- Xem lại lịch sử làm bài.

**Admin (Giáo viên Admin):**

- Thay đổi mật khẩu cá nhân
- Giáo viên tạo bài kiểm tra, thêm, chỉnh sửa, xóa câu hỏi (CURD)
- Giáo viên xem kết quả bài kiểm tra của học sinh
- Thống kê kết quả làm bài của học sinh
- Cấu hình hệ thống (ví dụ: thời gian làm bài, số lần thi lại)

# Phân Tích & Thiết Kế
## Chức năng
<Liệt kê các chức năng theo từng actors>

**User:**

- **Tài khoản**
- Đăng ký, đăng nhập.
- Thay đổi mật khẩu.
- **Làm bài kiểm tra**
- Xem danh sách bài kiểm tra.
- Bắt đầu bài kiểm tra.
- Trả lời câu hỏi (trắc nghiệm, điền đáp án, kéo thả, v.v.).
- Nộp bài kiểm tra trước thời gian hoặc hệ thống tự động nộp khi hết giờ.
- ` `**Xem kết quả**
- Xem điểm số ngay sau khi nộp bài.
- Xem đáp án đúng của từng câu hỏi (nếu giáo viên cho phép).
- Xem lịch sử các bài kiểm tra đã làm.


**Admin (Giáo viên):**

- **Quản lý bài kiểm tra:**
- Tạo bài kiểm tra mới.
- Chỉnh sửa bài kiểm tra (tên, mô tả, thời gian làm bài).
- Xóa bài kiểm tra.
- Xem danh sách bài kiểm tra đã tạo.
- **Quản lý câu hỏi :**
- Thêm câu hỏi vào bài kiểm tra.
- Chỉnh sửa/xóa câu hỏi.
- **Xem kết quả học sinh :**
- Xem điểm số của từng học sinh.
- Xem chi tiết bài làm của học sinh.
- **Giám sát hoạt động của học sinh:**
- Theo dõi học sinh nào đã làm bài, thời gian làm bài.
- Kiểm tra trạng thái bài kiểm tra (đã nộp, chưa nộp).

## Lược đồ CSDL

![](Aspose.Words.c18847e7-03c1-4fd7-acd2-2295dd702f13.001.png)

## Giao diện 
Liệt kê các giao diện (webpage) dự kiến:

1. **Trang Đăng Ký/Đăng Nhập** 

   2. **Chức năng:** Đăng ký tài khoản mới, đăng nhập vào hệ thống.
   2. **Các trường:** Email, mật khẩu, xác nhận mật khẩu.
   2. **Chức năng phụ:** Quên mật khẩu, thay đổi mật khẩu.
1. **Trang Thay Đổi Mật Khẩu (Change Password)**

   2. **Chức năng:** Cung cấp một giao diện cho người dùng thay đổi mật khẩu.
   2. **Các trường:** Mật khẩu cũ, mật khẩu mới, xác nhận mật khẩu mới.
1. **Trang Danh Sách Bài Kiểm Tra (View Test List)**

   2. **Chức năng:** Hiển thị danh sách các bài kiểm tra mà người dùng có thể làm.
   2. **Các trường:** Tên bài kiểm tra, mô tả, thời gian làm bài, trạng thái (Chưa làm, Đã làm).
1. **Trang Chi Tiết Bài Kiểm Tra (Test Details)**

   2. **Chức năng:** Khi người dùng chọn một bài kiểm tra, hiển thị thông tin chi tiết của bài kiểm tra, như câu hỏi và các lựa chọn trả lời.
   2. **Các trường:** Câu hỏi, các lựa chọn câu trả lời, nút bắt đầu làm bài kiểm tra.
1. **Trang Làm Bài Kiểm Tra (Take the Test)**

   2. **Chức năng:** Giao diện nơi học sinh có thể trả lời các câu hỏi của bài kiểm tra.
   2. **Các trường:** Các câu hỏi trắc nghiệm, điền đáp án, kéo thả, và nút nộp bài.
1. **Trang Nộp Bài Kiểm Tra (Submit Test)**

   2. **Chức năng:** Học sinh có thể nộp bài kiểm tra trước thời gian hoặc hệ thống tự động nộp khi hết giờ.
   2. **Các trường:** Nút nộp bài, cảnh báo về thời gian còn lại.
1. **Trang Kết Quả Bài Kiểm Tra (Test Results)**

   2. **Chức năng:** Hiển thị điểm số ngay sau khi nộp bài.
   2. **Các trường:** Điểm số, đáp án đúng (nếu giáo viên cho phép), các câu trả lời đã chọn của học sinh.
1. **Trang Lịch Sử Bài Kiểm Tra (Test History)**

   2. **Chức năng:** Hiển thị lịch sử các bài kiểm tra mà học sinh đã làm.
   2. **Các trường:** Tên bài kiểm tra, điểm số, thời gian làm bài, trạng thái (Đã làm, Đã nộp).

### Giao diện cho Admin (Giáo viên)
1. **Trang Quản Lý Tài Khoản Người Dùng (Manage User Accounts)**
   1. **Chức năng:** Quản lý tài khoản học sinh và giáo viên.
   1. **Các trường:** Danh sách tài khoản người dùng (học sinh và giáo viên), các thao tác chỉnh sửa, xóa tài khoản.
1. **Trang Quản Lý Bài Kiểm Tra (Manage Tests)**
   1. **Chức năng:** Cho phép giáo viên tạo mới, chỉnh sửa, hoặc xóa bài kiểm tra.
   1. **Các trường:** Tên bài kiểm tra, mô tả, thời gian, các thao tác (Thêm mới, Sửa, Xóa).
1. **Trang Xem Danh Sách Bài Kiểm Tra (View Test List for Admin)**
   1. **Chức năng:** Hiển thị danh sách bài kiểm tra đã được giáo viên tạo.
   1. **Các trường:** Tên bài kiểm tra, mô tả, thời gian làm bài, các thao tác (Sửa, Xóa).
1. **Trang Quản Lý Câu Hỏi (Manage Questions)**
   1. **Chức năng:** Cho phép giáo viên thêm câu hỏi vào bài kiểm tra, chỉnh sửa hoặc xóa câu hỏi.
   1. **Các trường:** Danh sách câu hỏi, các thao tác thêm, chỉnh sửa, xóa câu hỏi.
1. **Trang Xem Kết Quả Học Sinh (View Student Results)**
   1. **Chức năng:** Hiển thị điểm số của từng học sinh và chi tiết bài làm của họ.
   1. **Các trường:** Tên học sinh, điểm số, các câu trả lời, trạng thái bài kiểm tra (đã nộp hay chưa).
1. **Trang Giám Sát Hoạt Động Học Sinh (Monitor Student Activity)**
   1. **Chức năng:** Theo dõi thời gian làm bài, trạng thái bài kiểm tra của học sinh.
   1. **Các trường:** Tên học sinh, thời gian làm bài, trạng thái bài kiểm tra (đã làm, chưa nộp).

# Kế hoạch thực hiện
Liệt kê kế hoạch dự kiến trong 6 tuần

- Tuần 1: Phân tích yêu cầu và thiết kế hệ thống
- Tìm hiểu yêu cầu của dự án và lên ý tưởng về các chức năng của ứng dụng.
- Nghiên cứu các hệ thống Quiz App tương tự để học hỏi và lựa chọn công nghệ phù hợp dựa trên yêu cầu của dự án.
- Phân công công việc cho từng thành viên trong nhóm.
- Tuần 2: Xây dựng backend và cơ sở dữ liệu
- Cài đặt môi trường phát triển, thiết lập repo Git.
- Xây dựng cơ sở dữ liệu
- Viết API cho các chức năng chính: 
  - ` `Đăng ký, đăng nhập (authentication).
  - Quản lý bài kiểm tra (CRUD bài kiểm tra, câu hỏi).
- Thiết kế API rõ ràng, dễ hiểu và dễ sử dụng.
- Áp dụng các biện pháp bảo mật cho API và cơ sở dữ liệu.
- Sử dụng hệ thống quản lý phiên bản (ví dụ: Git) để quản lý mã nguồn hiệu quả.

- Tuần 3: Xây dựng frontend cơ bản
- Thiết lập frontend với React (hoặc framework phù hợp). 
- Xây dựng giao diện đăng nhập, đăng ký, thay đổi mật khẩu.
- Kết nối frontend với backend qua API.
- Hiển thị danh sách bài kiểm tra cho người dùng.
- Tuần 4: Phát triển chức năng làm bài kiểm tra
- Xây dựng giao diện làm bài kiểm tra (câu trắc nghiệm, điền đáp án...).
- Xử lý logic nộp bài kiểm tra, tính điểm.
- Hiển thị kết quả sau khi làm bài.
- Kiểm thử và debug các lỗi cơ bản.
- Đảm bảo tính công bằng và chính xác trong việc chấm điểm.
- Tuần 5: Hoàn thiện chức năng cho Admin
- Xây dựng giao diện quản lý bài kiểm tra cho giáo viên..
- Thêm chức năng xem kết quả của học sinh.
- Thống kê điểm số và trạng thái làm bài.
- Xây dựng hệ thống phân quyền để quản lý quyền truy cập của người dùng.
- Tuần 6: Hoàn thiện, kiểm thử và triển khai
- Kiểm thử toàn bộ hệ thống.
- Triển khai demo và chuẩn bị báo cáo.
# Câu hỏi/ Vấn đề
Liệt kê câu hỏi hoặc vấn đề của nhóm bạn tại đây
