# Hướng dẫn làm việc

## Mục tiêu

Xây dựng job Scrapy lấy thông tin hộ kinh doanh từ
`https://www.gdt.gov.vn/wps/portal/home/hct`.
Trao đổi với người dùng bằng tiếng Việt.

## Yêu cầu đã chốt

- Áp dụng Ponytail full. Ưu tiên thay đổi nhỏ nhất giải quyết đủ yêu cầu, tái sử dụng
  code hiện có và giữ cách chạy đơn giản.
- Dùng Python 3.12, uv, `pyproject.toml`, `uv.lock`, Ruff và pre-commit.
- Theo quyết định ngày 25/11/2026, dùng đơn vị hành chính 3 cấp theo quan hệ
  tỉnh/thành phố → quận/huyện → xã/phường/thị trấn.
- Dùng danh sách tên và mã GDT đã lưu cục bộ để xác định địa bàn cần crawl.
  Nguồn chạy job là `data/ds_full.csv`, được sao chép từ
  `/home/tansang/Documents/Crawl_data_gov/Data/ds_full.csv`,
  gồm `maTinh`, `tenTinh`, `maHuyen`, `tenHuyen`, `maXa`, `tenXa`.
  Job phải chạy độc lập, không phụ thuộc đường dẫn repo tham khảo.
  Không fetch lại danh sách tỉnh/huyện/xã hoặc đối chiếu tên qua endpoint khi chạy.
- Giữ mã địa bàn dưới dạng chuỗi và giữ đúng quan hệ tỉnh–huyện–xã trong dữ liệu.
  `data/administrative_division.json` hiện chỉ có tên và 2 cấp, không còn là
  nguồn xác định địa bàn cho luồng 3 cấp. Không tự suy mã huyện từ tệp này.
- Nếu đơn vị hành chính có trong tệp local nhưng danh sách GDT trả về chưa có
  đơn vị tương ứng, ghi log như hiện tại và tiếp tục crawl các địa bàn khớp được.
  Người dùng đã chốt tạm hoãn việc xử lý các địa bàn này đến khi có yêu cầu tiếp.
- Giữ tiền tố đơn vị hành chính như Phường, Xã, Thị trấn và Đặc khu theo nguồn.
  Tên tỉnh/thành phố dùng tên gọn, ví dụ Hà Nội.
- Duyệt đủ 5 loại danh sách trong “Tìm theo” và toàn bộ các trang kết quả.
- Truy vấn theo đủ `maTinh`, `maHuyen`, `maXa` lấy từ danh sách đã lưu,
  cùng `searchType`, UUID và CAPTCHA của phiên.
- Giữ `kyLb` rỗng. Người dùng đã rút mốc 01/07/2025 khỏi yêu cầu.
  Yêu cầu 3 cấp thay thế quyết định cũ để trống `maHuyen`.
- Script tự lấy UUID và ảnh CAPTCHA từ một phiên GDT mới, OCR ảnh tải xuống
  bằng hàm `get_captcha(image_path)` rồi dùng mã cùng UUID và cookie của phiên đó.
  PNG trong suốt phải được ghép lên nền trắng trước OCR. Chỉ gửi mã OCR có 5 ký tự
  chữ/số. Log chuỗi OCR và giữ thông báo từ chối mã của GDT để chẩn đoán.
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
