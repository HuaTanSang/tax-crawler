# Hướng dẫn làm việc

## Mục tiêu

Xây dựng job Scrapy lấy thông tin hộ kinh doanh từ
`https://www.gdt.gov.vn/wps/portal/home/hct`.
Trao đổi với người dùng bằng tiếng Việt.

## Yêu cầu đã chốt

- Áp dụng Ponytail full. Ưu tiên thay đổi nhỏ nhất giải quyết đủ yêu cầu, tái sử dụng
  code hiện có và giữ cách chạy đơn giản.
- Dùng Python 3.12, uv, `pyproject.toml`, `uv.lock`, Ruff và pre-commit.
- Spider phải duyệt danh sách tỉnh/thành phố và xã/phường/đặc khu trong
  `data/administrative_division.json`. Đây là nguồn xác định địa bàn cần crawl.
- Dùng endpoint GDT để đối chiếu mã tỉnh/xã phục vụ truy vấn. Giữ rõ khác biệt
  giữa tên trong tệp và tên/mã GDT trả về khi đối chiếu.
- Giữ tiền tố đơn vị hành chính như Phường, Xã, Thị trấn và Đặc khu theo nguồn.
  Tên tỉnh/thành phố dùng tên gọn, ví dụ Hà Nội.
- Duyệt đủ 5 loại danh sách trong “Tìm theo” và toàn bộ các trang kết quả.
- Bốn trường bắt buộc trên biểu mẫu là Tỉnh/Thành phố, Xã/Phường/Đặc khu,
  Tìm theo và Mã xác nhận.
- Giữ `maHuyen` và `kyLb` rỗng. Người dùng đã rút mốc 01/07/2025 khỏi yêu cầu.
- Script tự lấy UUID và ảnh CAPTCHA từ một phiên GDT mới, OCR ảnh tải xuống
  bằng hàm `get_captcha(image_path)` rồi dùng mã cùng UUID và cookie của phiên đó.
  Khi phản hồi không hợp lệ, đổi phiên và OCR lại, thử lại đúng trang với giới hạn
  số lần. Giữ các kiểm tra lỗi cấu trúc bảng và phân trang.
  Theo quan sát của người dùng, mã giữ nguyên khi giữ nguyên trang.
- Kiểm tra quan hệ giữa UUID, CAPTCHA và phiên khi xử lý phản hồi rỗng.
  Chỉ kết luận nguyên nhân khi có bằng chứng.

## Cách triển khai

- Giữ Scrapy làm công cụ crawl chính.
- Ưu tiên một lệnh chạy và xử lý CAPTCHA tự động theo yêu cầu mới nhất.
- Giữ kiểm tra dữ liệu đầu vào, lỗi mạng, phản hồi rỗng và cấu trúc bảng.
- Bảo toàn các cột gộp tiêu đề, đặc biệt các cột Cũ/Mới.
- Giữ mã số thuế và giá trị tiền theo dạng chuỗi của nguồn khi xuất dữ liệu.
- Khi sửa logic, kiểm tra các caller và cập nhật test, hướng dẫn liên quan.
- Logic mới đáng kể cần một kiểm tra nhỏ bắt đúng trường hợp lỗi.
- Báo rõ phần đã kiểm tra offline và phần đã kiểm tra trực tiếp với GDT.
- Kết thúc trả lời ngắn gọn, nêu phần chưa kiểm chứng và giới hạn liên quan.

## Lệnh thường dùng

```sh
uv sync --locked
uv run --locked src/gdt_spider.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests
uv run --locked pre-commit run --all-files
```

Xem `NOTES.md` để biết trạng thái thực tế và các việc còn thiếu.
