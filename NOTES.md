# Ghi chú dự án

Cập nhật ngày 26/11/2026 theo trao đổi và mã hiện có trong workspace.

## Luồng người dùng muốn

1. Đọc danh sách tên và mã địa bàn đã lưu cục bộ tại `data/ds_full.csv`.
2. Duyệt theo 3 cấp tỉnh/thành phố → quận/huyện → xã/phường/thị trấn.
3. Dùng trực tiếp `maTinh`, `maHuyen`, `maXa` đã lưu để gửi truy vấn,
   không fetch lại danh sách địa bàn hoặc đối chiếu tên qua endpoint khi chạy.
4. Script tự tạo phiên GDT, lấy UUID và ảnh CAPTCHA để OCR tự động.
5. Dùng lại CAPTCHA cùng UUID, duyệt 5 danh sách và các trang kết quả.
6. Chọn một/nhiều tỉnh khi chạy, ghi mỗi tỉnh một tệp và lưu checkpoint riêng.
7. Dừng và chạy lại cùng lệnh để tiếp tục vào đúng tệp của từng tỉnh.

Quyết định ngày 25/11/2026 thay thế luồng 2 cấp và yêu cầu để trống `maHuyen`.
Vẫn để `kyLb` rỗng và không lọc theo mốc 01/07/2025.
Code đã chuyển sang luồng 3 cấp từ CSV cục bộ, chưa kiểm chứng với GDT trực tiếp.

## Dữ liệu địa bàn

### Danh sách 3 cấp đã lưu

Repo `/home/tansang/Documents/Crawl_data_gov` có sẵn các tệp trong `Data/`.
Đã đọc kiểm tra bằng thư viện CSV, chưa truy vấn GDT để kiểm chứng tính hiện hành.

| Tệp | Nội dung đã kiểm tra |
| --- | --- |
| `ds_tinh.csv` | 63 dòng, cột `id`, `title` |
| `ds_huyen_toan_quoc.csv` | 740 dòng, cột `id`, `title` |
| `ds_xa_toan_quoc.csv` | 12.132 dòng, cột `id`, `title` |
| `ds_full.csv` | 12.132 dòng, đủ mã và tên của cả 3 cấp |

`ds_full.csv` có các cột `maXa`, `tenXa`, `maHuyen`, `tenHuyen`, `maTinh`, `tenTinh`.
Tệp này có 63 mã tỉnh, 716 mã huyện và 12.132 mã xã khác nhau, không có dòng thiếu
giá trị trong 6 cột trên. Có thể dùng trực tiếp quan hệ trong tệp để tạo truy vấn.
Số mã huyện trong tệp ghép khác số dòng của danh sách huyện riêng, nên chưa kết luận
tệp ghép bao phủ mọi huyện. Giữ mã dưới dạng chuỗi, bảo toàn số 0 đầu nếu có.

Ví dụ một dòng gồm An Giang (`805`) → Huyện An Phú (`80505`) →
Thị trấn An Phú (`8050509`). Đây là danh sách 3 cấp đã lưu từ repo tham khảo,
chưa xác nhận GDT hiện còn trả kết quả cho mọi mã cũ.
Đã sao chép nguyên bản `Data/ds_full.csv` vào `data/ds_full.csv` của tax-crawler,
đối chiếu byte và SHA-256 trùng khớp
`bddf2821a1548e29c9a4b5cd9dcfb58ea0a0fac55229e9212862801aad82d543`.
Job đọc bản sao này, không phụ thuộc repo tham khảo khi chạy.
Không cần các danh sách mã crawl dựng sẵn vì job đã duyệt đủ 5 `searchType` cho
từng dòng địa bàn. Các danh sách tên/mã riêng lẻ chứa thông tin trùng với tệp ghép
đối với những xã có trong tệp, nên chưa sao chép thêm.

Áp dụng cách repo tham khảo dùng mã GDT 3 cấp đã lưu để tạo truy vấn trực tiếp.
Giữ Scrapy và bộ parser đang có, không thêm Selenium, pandas hay bước cắt mã xã
để suy ra tỉnh/huyện. Luồng hiện tại đọc đủ ba mã từ các cột CSV.

### Tệp 2 cấp hiện có trong tax-crawler

`data/administrative_division.json` hiện là một object JSON với 34 tỉnh/thành phố
và 3.321 đơn vị cấp xã. Cấu trúc ví dụ được rút gọn như sau.

```json
{
  "Hà Nội": ["Phường Ba Đình", "Phường Ngọc Hà", "Phường Giảng Võ"]
}
```

Tên tệp đúng là `administrative_division.json`. Người dùng từng gõ
`administrative_devision.json` khi nhắc đến tệp này.
Các lần xử lý trước đã chuyển từ tên gọn của xã/phường sang tên đầy đủ có tiền tố.
Tệp chỉ chứa tên tỉnh và xã, thiếu cấp huyện và mã GDT. Luồng cũ đối chiếu tên với
endpoint GDT. Theo yêu cầu mới, job dùng CSV có đủ mã và quan hệ ở trên.
Tệp JSON này được giữ làm dữ liệu tham khảo.

## Endpoint xác định từ HAR

Trang tra cứu là `https://www.gdt.gov.vn/wps/portal/home/hct`.
Các endpoint bên dưới nằm trên host `https://www.gdt.gov.vn`.

| Chức năng | Endpoint và tham số |
| --- | --- |
| Danh sách tỉnh/thành | `/TTHKApp/jsp/json_option.jsp?cmd=GET_DS_TINH` |
| Danh sách xã/phường | `/TTHKApp/jsp/json_option.jsp?cmd=GET_DS_XA&maTinh=...&maHuyen=` |
| Kết quả | `/TTHKApp/jsp/results.jsp` |

Hai endpoint địa bàn trả các thẻ HTML `option` có mã và tên.
Đây là các endpoint của luồng 2 cấp trước đây, giữ lại làm thông tin tham khảo.
Luồng mới dùng danh sách lưu cục bộ nên không gọi lại các endpoint địa bàn khi chạy.
Tham số kết quả gồm `maTinh`, `maHuyen`, `maXa`, `hoTen`, `kyLb`,
`diaChi`, `maSoThue`, `searchType`, `uuid`, `captcha` và `pageNumber`.
Theo yêu cầu mới, điền mã Quận/Huyện từ dữ liệu cục bộ và giữ Kỳ lập bộ rỗng.

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

- Đã triển khai yêu cầu 3 cấp ngày 25/11/2026. `load_divisions` đọc `data/ds_full.csv`,
  kiểm tra cột, giá trị thiếu, mã trùng và quan hệ mã tỉnh–huyện–xã trước khi truy vấn.
  Hàm tạo URL gửi đủ `maTinh`, `maHuyen`, `maXa`, giữ `kyLb` rỗng.
  Metadata kết quả có thêm `district_code` và `district`.
- `src/gdt_spider.py` dùng Scrapy, xử lý tuần tự địa bàn và từng trang.
- Spider tự tải trang tra cứu, lấy UID từ ảnh `captchaCtn` làm UUID của phiên,
  tải ảnh vào `output/<mã-tỉnh>/captcha.png` rồi gọi `src/gdt_ocr.py` để nhận diện mã.
  Scrapy giữ cookie cho các request trong phiên. HAR được dùng làm mẫu kiểm tra cấu trúc trong
  quá trình phát triển.
- Spider duyệt trực tiếp từng dòng địa bàn trong CSV, không fetch danh mục địa bàn
  hoặc đối chiếu tên. Mã giữ dưới dạng chuỗi và tên giữ theo CSV.
  Đã bỏ bộ đối chiếu tên của luồng 2 cấp.
- Cách chạy hiện tại là `uv run --locked src/gdt_spider.py`.
- Có thể chọn một tỉnh bằng `--province 805`, nhiều tỉnh bằng
  `--province MA_TINH_1 MA_TINH_2`, hoặc không truyền để crawl tất cả.
  Mã tỉnh được kiểm tra qua CSV trước khi gửi request; mã lặp chỉ xử lý một lần.
  Các tỉnh và địa bàn trong tỉnh giữ thứ tự CSV, xử lý tuần tự.
- Job ghi từng trang vào `output/<mã-tỉnh>/gdt-<thời-điểm-bắt-đầu>.jsonl`.
  `checkpoint.json` cùng thư mục ghi tên output, mốc byte đã xác nhận,
  vị trí cần crawl tiếp (mã tỉnh/huyện/xã, search type, trang), và SHA-256 của
  danh sách địa bàn đã lọc theo tỉnh cùng thứ tự các search type.
  Vị trí tiếp theo rỗng nghĩa là tỉnh đã hoàn tất. Trang không có kết quả cũng
  được ghi nhận, hết loại danh sách thì chuyển loại tiếp theo hoặc địa bàn tiếp theo.
- `src/gdt_checkpoint.py` quản lý cả ghi trang và checkpoint, thay cho `FEEDS`.
  Chỉ cập nhật tiến độ sau khi ghi/flush/fsync dữ liệu thành công. Checkpoint
  được ghi vào tệp tạm, fsync rồi thay thế; thư mục cũng được fsync.
  Lỗi ghi làm job dừng, không gửi request sang trang hoặc tỉnh tiếp theo.
- Nhấn Ctrl+C một lần và đợi Scrapy đóng. Chạy lại lấy phiên/UUID/CAPTCHA mới,
  tiếp tục đúng vị trí và đúng tệp timestamp ban đầu của tỉnh. Dữ liệu vượt
  mốc byte đã xác nhận được cắt để tải lại trang chưa xác nhận, tránh ghi lặp trang.
  Nếu output ngắn hơn mốc, thiếu output/checkpoint, checkpoint hỏng hoặc danh sách
  địa bàn của tỉnh đổi thì báo lỗi và giữ dữ liệu để kiểm tra, không tự đoán tiến độ.
  Tỉnh đã hoàn tất vẫn kiểm tra output trước khi bỏ qua, không lấy thêm phiên/kết quả.
- `crawl.lock` riêng theo tỉnh giữ khóa trong lúc xử lý tỉnh đó, tránh hai job cùng
  ghi một tỉnh; không khóa trực tiếp checkpoint vì tệp này được thay thế mỗi trang.
  CAPTCHA và `last_form.html`/`last_response.html` cũng tách vào thư mục tỉnh.
  Muốn crawl mới một tỉnh, dừng job rồi lưu trữ cả thư mục tỉnh ra ngoài `output/`.
  Các output cũ ở thư mục gốc giữ nguyên, không tự nhập vào checkpoint.
- Bản trước từng dùng SQLite để tiếp tục tiến độ. Sau yêu cầu đơn giản hóa,
  cơ chế đó đã được bỏ khỏi code. Trong `output` hiện có các tệp cũ
  `gdt.sqlite3` và `gdt.jsonl`.
- `--province` được thêm lại theo yêu cầu checkpoint từng tỉnh ngày 26/11/2026,
  nhận mã GDT thay vì tên. Các tham số cũ `--ward`, `--captcha` và `--request-url`
  vẫn được bỏ.
- HAR ở thư mục gốc đã được thêm vào `.gitignore` bằng mẫu `*.har`.
- `src/gdt_export.py` (26/11/2026) chuyển JSONL từng thư mục tỉnh thành mỗi
  `searchType` một tệp `<tỉnh>_<list_name>.xlsx` đặt cạnh JSONL, bỏ dấu tiếng Việt
  và dấu câu, từ nối bằng `_`. Theo yêu cầu 26/11/2026 chỉ xuất xlsx (openpyxl,
  write-only); đã bỏ CSV/TSV và `--ext`. Giữ 6 cột metadata địa bàn (không có
  `page`, `list_name`, `search_type`) và cột nguồn theo thứ tự `columns`, ô ghi dạng chuỗi.
  Quá 1.048.576 dòng một sheet thì báo lỗi. Chỉ đọc đến mốc byte của
  checkpoint; cột khác nhau trong cùng `searchType` thì báo lỗi, không để tệp dở.

## CAPTCHA và lỗi đã gặp

CAPTCHA là ảnh chữ/số. Ban đầu người dùng nhập mã tay, sau đó yêu cầu OCR tự động.
Theo người dùng, mã giữ nguyên khi giữ nguyên
trang. Luồng chạy mới lấy UUID và ảnh trong cùng phiên của Scrapy, rồi dùng lại
phiên đó cho các truy vấn.

Theo yêu cầu mới nhất, đã chuyển hàm OCR người dùng gửi sang đầu vào là tệp ảnh
tải xuống. Giữ resize 390×150, grayscale, dilation kernel 6×6, ngưỡng 150,
median blur 5 và lề trắng 30 pixel dưới ảnh. Ban đầu dùng Tesseract `--psm 13`,
đã đổi sang `--psm 7` sau khi kiểm tra ảnh thực ngày 25/11/2026.
Phần chụp màn hình và crop tọa độ được bỏ vì đã có ảnh CAPTCHA riêng.

Lượt chạy 01:51 ngày 25/11/2026 thất bại ngay trang đầu. `last_response.html`
chứa thông báo `Vui lòng nhập đúng mã xác nhận.` trong `div.message-info`.
Đã xác nhận `captcha.png` là PNG RGBA 130×50, cả ba kênh RGB đều bằng 0,
chữ nằm ở kênh alpha. Code cũ đọc `IMREAD_COLOR` bỏ alpha, tạo ảnh đen toàn bộ
và Tesseract đọc ra `a`. Code mới giữ alpha, ghép lên nền trắng rồi OCR.
Tesseract thật đọc ảnh mẫu được `nc24b`, khớp nội dung ảnh đã xem.
Mẫu được lưu ở `tests/fixtures/captcha_transparent.png` làm kiểm tra hồi quy.
Chỉ mã OCR đủ 5 ký tự chữ/số mới được gửi. Log hiển thị chuỗi OCR, không coi
việc đọc ra chuỗi là GDT đã xác thực thành công. Parser báo riêng thông báo lỗi
CAPTCHA từ máy chủ và giữ cơ chế đổi phiên/thử lại có giới hạn.

Job đổi phiên và OCR lại khi phản hồi kết quả rỗng, bị từ chối hoặc thiếu bảng.
Tối đa 3 lần đổi phiên cho một trang, sau đó báo lỗi. Trang đã xuất và được
checkpoint xác nhận được giữ lại. Lỗi cấu trúc bảng được báo để kiểm tra.
Chạy lại toàn bộ lệnh tiếp tục từ checkpoint riêng của các tỉnh được chọn.

Thư viện Python thêm NumPy, opencv-python-headless và pytesseract.
Tesseract là chương trình hệ thống cần có trong PATH. Các lần kiểm tra trước chưa có
Tesseract và gặp lỗi DNS khi tải thư viện. Lần này đã có thư viện và Tesseract,
đã kiểm tra OCR thật với một ảnh mẫu. Chưa đo độ chính xác trên nhiều CAPTCHA.

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

- Checkpoint từng tỉnh ngày 26/11/2026: 18 test offline đạt, bao gồm chọn tỉnh,
  ghi/đọc tiếp qua 5 loại danh sách và hai xã trùng tên khác huyện, các điểm ngắt
  khi ghi output hoặc thay checkpoint, output ngắn/thiếu, checkpoint hỏng,
  danh sách địa bàn đổi, khóa cùng tỉnh, lỗi ghi không chuyển trang, và đường dẫn
  CAPTCHA/phản hồi lỗi tách riêng theo tỉnh.
  Bài thử tiến trình Scrapy thật dùng hàm lấy phiên và kết quả mô phỏng: gửi SIGINT,
  chạy riêng tỉnh khác rồi tiếp tục tỉnh đầu vào đúng tệp timestamp ban đầu,
  kiểm tra 20 trang duy nhất ở tỉnh đầu và giữ nguyên tệp tỉnh còn lại.
  Chạy lại tất cả tỉnh đã hoàn tất không lấy phiên/kết quả; mã tỉnh sai không gửi
  request và output cũ ở thư mục gốc không bị thay đổi.
  Đã kiểm tra loader/chọn tỉnh với CSV thật: 12.132 địa bàn, 63 tỉnh;
  riêng An Giang (`805`) có 158 địa bàn. Chưa kiểm chứng checkpoint với GDT trực tiếp.
  Chống trùng áp dụng cho trang do dừng/chạy lại, không loại trùng của nguồn
  hoặc bảo đảm ảnh chụp dữ liệu cố định khi GDT cập nhật giữa các lần chạy.
- Đã chạy đạt 21 test sau khi sửa xử lý PNG trong suốt và thông báo lỗi CAPTCHA.
  Test kiểm tra ảnh RGBA/RGB/grayscale thật, từ chối chuỗi OCR sai độ dài,
  và giữ thông báo GDT báo sai mã xác nhận. Phần gọi Tesseract trong unit test
  được mô phỏng; OCR bằng chương trình Tesseract thật được kiểm tra riêng trên ảnh mẫu.
  Các test còn kiểm tra phiên/CAPTCHA,
  tham số truy vấn 3 cấp, đọc CSV địa bàn, tiêu đề gộp ô, phản hồi rỗng và phân trang.
- Đã đọc toàn bộ `data/ds_full.csv` bằng loader mới, kiểm tra 12.132 mã xã duy nhất,
  quan hệ mã tỉnh–huyện–xã hợp lệ và tên/mã nhất quán trong bản sao.
- Test luồng 3 cấp dùng hai xã trùng tên thuộc hai huyện khác nhau, đủ 5 loại
  danh sách và có phân trang. Tất cả request tra cứu dùng mã cục bộ, không có
  request tải danh mục địa bàn. Test phục hồi phiên giữ nguyên cả ba mã khi thử lại.
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
- Trong luồng 2 cấp trước đây, với dữ liệu HAR, bộ đối chiếu khớp đủ 34 tỉnh/thành.
  An Giang khớp được 35 trong 102 xã/phường của tệp, còn 67 đơn vị chưa có mã
  tương ứng trong danh sách GDT đã ghi lại. Một số ví dụ gồm Phường Long Xuyên,
  Phường Châu Đốc và Xã An Phú.

- Export (trước khi chuyển sang xlsx): 3 test offline trong `tests/test_export.py`. Chạy thật với
  `output/805` (crawl chưa xong, dừng ở huyện `80517`): 5 tệp, 140.545 / 99.084 /
  20.466 / 12.246 / 1.149 dòng, khớp số dòng đếm trực tiếp từ JSONL.

## Việc cần tiếp tục

- Kiểm chứng truy vấn bằng mã GDT 3 cấp cũ với GDT trực tiếp. Chưa kết luận
  mọi địa bàn trong CSV vẫn còn dữ liệu trên máy chủ.
- Theo quyết định ngày 25/11/2026, các đơn vị hành chính có trong tệp local
  2 cấp nhưng GDT chưa trả về đơn vị tương ứng đã được ghi log ở luồng cũ.
  Việc đối chiếu bổ sung mã cho các địa bàn này tiếp tục tạm hoãn đến khi người dùng
  yêu cầu. Luồng CSV hiện tại không đối chiếu danh sách 2 cấp này.
- Kiểm chứng OCR tự động và phục hồi phiên với GDT trực tiếp.
