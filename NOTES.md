# Ghi chú dự án

Cập nhật ngày 24/11/2026 theo trao đổi và mã hiện có trong workspace.

## Luồng người dùng muốn

1. Đọc `data/administrative_division.json`.
2. Duyệt từng tỉnh/thành phố và các xã/phường/đặc khu bên trong.
3. Đối chiếu mã địa bàn với GDT để gửi truy vấn.
4. Script tự tạo phiên GDT, lấy UUID và ảnh CAPTCHA để OCR tự động.
5. Dùng lại CAPTCHA cùng UUID, duyệt 5 danh sách và các trang kết quả.
6. Ghi dữ liệu ra tệp.

Tên tệp đúng là `administrative_division.json`. Người dùng từng gõ
`administrative_devision.json` khi nhắc đến tệp này.

## Dữ liệu địa bàn

`data/administrative_division.json` hiện là một object JSON với 34 tỉnh/thành phố
và 3.321 đơn vị cấp xã. Cấu trúc ví dụ được rút gọn như sau.

```json
{
  "Hà Nội": ["Phường Ba Đình", "Phường Ngọc Hà", "Phường Giảng Võ"]
}
```

Các lần xử lý trước đã chuyển từ tên gọn của xã/phường sang tên đầy đủ có tiền tố.
Tệp này chứa tên địa bàn. Mã GDT cần được đối chiếu từ các endpoint của GDT.
HAR có ví dụ tên `Phương Long Sơn` tại GDT, cho thấy cần kiểm tra sai khác tên.

## Endpoint xác định từ HAR

Trang tra cứu là `https://www.gdt.gov.vn/wps/portal/home/hct`.
Các endpoint bên dưới nằm trên host `https://www.gdt.gov.vn`.

| Chức năng | Endpoint và tham số |
| --- | --- |
| Danh sách tỉnh/thành | `/TTHKApp/jsp/json_option.jsp?cmd=GET_DS_TINH` |
| Danh sách xã/phường | `/TTHKApp/jsp/json_option.jsp?cmd=GET_DS_XA&maTinh=...&maHuyen=` |
| Kết quả | `/TTHKApp/jsp/results.jsp` |

Hai endpoint địa bàn trả các thẻ HTML `option` có mã và tên.
Biểu mẫu có 4 trường bắt buộc gồm Tỉnh/Thành phố, Xã/Phường/Đặc khu,
Tìm theo và Mã xác nhận.
Tham số kết quả gồm `maTinh`, `maHuyen`, `maXa`, `hoTen`, `kyLb`,
`diaChi`, `maSoThue`, `searchType`, `uuid`, `captcha` và `pageNumber`.
Giữ Quận/Huyện và Kỳ lập bộ rỗng theo yêu cầu đã chốt.

| searchType | Tìm theo |
| --- | --- |
| `11` | Danh sách hộ kinh doanh và mức thuế phải nộp |
| `10` | Danh sách hộ kinh doanh không thuộc diện nộp thuế GTGT |
| `12` | Danh sách hộ kinh doanh tạm nghỉ kinh doanh được miễn, giảm thuế |
| `04` | Danh sách hộ kinh doanh nghỉ, bỏ kinh doanh |
| `03` | Danh sách hộ kinh doanh điều chỉnh thông tin và tiền thuế |

Bảng kết quả có class `ta_border`. Tiêu đề có `rowspan` và `colspan`.
Liên kết tiếp theo có ID `nextPage` và dạng `javascript:goToPage(2);`.
Truy vấn trang tiếp theo dùng `pageNumber`.
Kết quả rỗng trong HAR có thông báo `Không tìm thấy kết quả`.

## Trạng thái code hiện tại

- `src/gdt_spider.py` dùng Scrapy, xử lý tuần tự địa bàn và từng trang.
- Spider tự tải trang tra cứu, lấy UID từ ảnh `captchaCtn` làm UUID của phiên,
  tải ảnh vào `output/captcha.png` rồi gọi `src/gdt_ocr.py` để nhận diện mã.
  Scrapy giữ cookie cho các request trong phiên. HAR được dùng làm mẫu kiểm tra cấu trúc trong
  quá trình phát triển.
- Spider đã đọc `data/administrative_division.json` làm danh sách cần crawl.
  Danh sách GDT được dùng để đối chiếu mã địa bàn. Kết quả giữ tên trong tệp.
  Bộ đối chiếu ưu tiên tên nguyên văn, sau đó kiểm tra biến thể dấu/chữ hoa/thường,
  tiền tố tỉnh/thành và Huế/Thừa Thiên Huế. Trường hợp thiếu hoặc khớp nhiều mã
  được ghi log lỗi. Job lấy phần khớp được và báo chưa hoàn tất khi còn lỗi.
- Cách chạy hiện tại là `uv run --locked src/gdt_spider.py`.
- Job hiện ghi từng trang vào `output/gdt-<thời điểm chạy>.jsonl`.
  Mỗi lần chạy bắt đầu từ đầu và tạo tệp riêng.
- Bản trước từng dùng SQLite để tiếp tục tiến độ. Sau yêu cầu đơn giản hóa,
  cơ chế đó đã được bỏ khỏi code. Trong `output` hiện có các tệp cũ
  `gdt.sqlite3` và `gdt.jsonl`.
- Tham số CLI cũ như `--province`, `--ward`, `--captcha` và `--request-url`
  đã được bỏ trong bản đơn giản hóa.
- HAR ở thư mục gốc đã được thêm vào `.gitignore` bằng mẫu `*.har`.

## CAPTCHA và lỗi đã gặp

CAPTCHA là ảnh chữ/số. Ban đầu người dùng nhập mã tay, sau đó yêu cầu OCR tự động.
Theo người dùng, mã giữ nguyên khi giữ nguyên
trang. Luồng chạy mới lấy UUID và ảnh trong cùng phiên của Scrapy, rồi dùng lại
phiên đó cho các truy vấn.

Theo yêu cầu mới nhất, đã chuyển hàm OCR người dùng gửi sang đầu vào là tệp ảnh
tải xuống. Giữ resize 390×150, grayscale, dilation kernel 6×6, ngưỡng 150,
median blur 5, lề trắng 30 pixel dưới ảnh và Tesseract `--psm 13`.
Phần chụp màn hình và crop tọa độ được bỏ vì đã có ảnh CAPTCHA riêng.

Job đổi phiên và OCR lại khi phản hồi kết quả rỗng, bị từ chối hoặc thiếu bảng.
Tối đa 3 lần đổi phiên cho một trang, sau đó báo lỗi. Trang đã xuất trong cùng
lượt chạy được giữ lại. Lỗi cấu trúc bảng được báo để kiểm tra.
Chạy lại toàn bộ lệnh vẫn tạo lượt mới từ đầu.

Thư viện Python thêm NumPy, opencv-python-headless và pytesseract.
Tesseract là chương trình hệ thống cần có trong PATH. Môi trường sandbox chưa có
Tesseract và lỗi DNS khi tải thư viện, nên độ chính xác OCR thật chưa được đo.

Người dùng đã chạy được Scrapy 2.13.3 trên máy thật. Lượt chạy lúc 16:41 nhận
HTTP 200 nhưng dừng với `invalid_response`. Database của lượt đó có 0 trang,
còn `output/last_response.html` chỉ gồm 13 lần xuống dòng CRLF, tổng cộng 26 byte.
HAR được ghi khoảng 15:28 cùng ngày. UUID/CAPTCHA cũ là một giả thuyết,
nguyên nhân cụ thể vẫn chưa được xác nhận.

Parser hiện báo riêng trường hợp phản hồi rỗng và giữ phản hồi lỗi để kiểm tra.
HTTP 200 chỉ xác nhận có phản hồi, cần kiểm tra nội dung để xác định crawl thành công.

Lượt chạy tự lấy phiên lúc 17:47 dừng với `invalid_form` sau request đầu tiên.
Log ghi tổng phản hồi khoảng 475 byte và bộ chọn CAPTCHA chưa tìm được ảnh.
Đã bổ sung lưu nguyên nội dung phản hồi ở bước này vào `output/last_form.html`,
kèm HTTP status, URL và số byte trong log. Cần đọc phản hồi thực tế đó để xác định
nguyên nhân. `last_response.html` là phản hồi ở bước tra cứu kết quả.

Người dùng đã cung cấp nội dung `last_form.html` với tiêu đề `Request Rejected`
và thông báo `The requested URL was rejected`. Phía GDT đã từ chối request
trước bước CAPTCHA. Đã cấu hình User-Agent và header điều hướng theo request
trình duyệt thành công trong HAR. Đây là thay đổi cần thử lại trên máy người dùng,
hiệu quả với GDT trực tiếp vẫn chưa xác nhận.

## Kiểm tra và giới hạn

- Bộ test hiện tại có 18 test cho phiên/CAPTCHA, tham số truy vấn, danh sách địa bàn,
  đối chiếu tên/mã, tiêu đề gộp ô, phản hồi rỗng và phân trang.
- Đã kiểm tra 10 phản hồi kết quả trong HAR.
- Đã chạy thử Scrapy offline với dữ liệu HAR cho 5 danh sách, 9 trang và 120 dòng.
  Bài thử giới hạn ở hai trang mỗi danh sách có dữ liệu để mô phỏng trang cuối.
- Luồng tự lấy CAPTCHA đã được thử offline với phản hồi mô phỏng cho trang và
  ảnh, kiểm tra cookie được giữ qua các request và chỉ hỏi mã một lần.
  Bộ đọc UUID cũng đã đối chiếu với HTML trang thực trong HAR.
- Luồng OCR tự động đã kiểm tra qua downloader Scrapy với OCR được mô phỏng.
  Một trang cố ý trả rỗng, sau đó job lấy phiên/ảnh mới và thử lại đúng trang đó.
  Kết quả thử gồm 9 trang, 120 dòng, hai lần OCR và các cookie tương ứng hai phiên.
  Các trang thành công được xuất một lần.
- Sandbox từng lỗi DNS khi kết nối GDT và PyPI. Người dùng mở GDT và chạy
  Scrapy được trên máy của mình. Cần phân biệt hai môi trường khi chẩn đoán.
- Bộ đọc bảng đã kiểm tra offline. Toàn bộ job crawl trực tiếp thành công
  vẫn chưa được xác nhận.
- Bản nhập tay trên máy người dùng đã lưu 725 trang, 10.709 dòng trước khi
  phản hồi rỗng sau khoảng 15 phút. Thời hạn UUID/CAPTCHA là giả thuyết chưa xác nhận.
- Với dữ liệu HAR hiện có, bộ đối chiếu khớp đủ 34 tỉnh/thành.
  An Giang khớp được 35 trong 102 xã/phường của tệp, còn 67 đơn vị chưa có mã
  tương ứng trong danh sách GDT đã ghi lại. Một số ví dụ gồm Phường Long Xuyên,
  Phường Châu Đốc và Xã An Phú.

## Việc cần tiếp tục

- Xác minh mã GDT cho các địa bàn chưa khớp, đặc biệt 67 đơn vị An Giang trong
  đối chiếu với HAR hiện có.
- Kiểm chứng OCR tự động và phục hồi phiên với GDT trực tiếp.
- Kiểm tra lại `src/process_address_unit.py` trước khi tái tạo dữ liệu.
  Default hiện trỏ đến `data/vn_only_simplified_json_generated_data_vn_units.json`
  là một list, trong khi code xử lý hiện yêu cầu object tên tỉnh và danh sách tên xã.
