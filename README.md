# Tax crawler

Dự án dùng Python 3.12, uv và Scrapy để tra cứu thông tin hộ khoán từ GDT.

## Cài đặt

```sh
uv sync --locked
uv run --locked pre-commit install
```

Lệnh cài hook cần chạy trong một Git repository. Nếu vừa tạo thư mục dự án mới, chạy `git init` trước.
OCR cần chương trình Tesseract trong PATH. Trên Ubuntu/WSL, cài bằng lệnh sau.

```sh
sudo apt install tesseract-ocr
```

## Chạy job

```sh
uv run --locked src/gdt_spider.py
```

Script tự mở một phiên GDT, lấy UUID và lưu ảnh CAPTCHA vào `output/captcha.png`.
Hàm `get_captcha(image_path)` trong `src/gdt_ocr.py` đọc ảnh này bằng OpenCV và
Tesseract. Scrapy giữ cookie, UUID và mã nhận diện được cho các truy vấn cùng phiên.
Job xử lý tuần tự từng trang theo thứ tự địa bàn trong tệp JSON.

Khi nhận phản hồi rỗng, `Request Rejected` hoặc thiếu bảng kết quả, job lưu phản
hồi vào `output/last_response.html`, lấy phiên/ảnh mới, OCR lại và thử đúng trang
đang lỗi. Mỗi trang có tối đa 3 lần đổi phiên. OCR trống được thử lại với tối đa
3 ảnh mới. Lỗi cấu trúc cột hoặc phân trang được báo để kiểm tra dữ liệu.
Lỗi ở bước tải biểu mẫu được lưu riêng vào `output/last_form.html`.

Job đọc địa bàn cần crawl từ `data/administrative_division.json`, đối chiếu mã
tỉnh/xã bằng danh sách GDT, rồi duyệt 5 loại danh sách và các trang kết quả.
Quận/Huyện và Kỳ lập bộ để trống. Tên địa bàn trong kết quả giữ theo tệp của bạn.
Các biến thể dấu, chữ hoa/thường và tên tỉnh như Huế/Thừa Thiên Huế được đối chiếu
khi xác định được một mã duy nhất. Địa bàn thiếu mã hoặc khớp nhiều mã được báo
trong log. Job vẫn lấy phần khớp được và kết thúc với trạng thái chưa hoàn tất.

Kết quả được ghi từng trang vào một tệp `output/gdt-<thời điểm chạy>.jsonl`.
Mỗi dòng JSON chứa mã và tên
địa bàn, loại danh sách, số trang, tiêu đề cột và danh sách bản ghi. Giá trị thuế
và mã số thuế giữ ở dạng chuỗi theo nguồn.

Mỗi lần chạy duyệt từ đầu và tạo một tệp kết quả riêng.
Trong cùng một lần chạy, phục hồi phiên tiếp tục ở trang đang lỗi và giữ dữ liệu
đã xuất trước đó.

## Kiểm tra trước khi commit

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m unittest discover -s tests
uv run --locked pre-commit run --all-files
```

Các hook dùng đúng phiên bản Ruff trong `uv.lock`. Chạy `uv lock` khi thay đổi dependency.
