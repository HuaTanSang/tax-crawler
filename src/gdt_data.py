import csv
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from lxml import html

BASE_URL = "https://www.gdt.gov.vn/TTHKApp/jsp/"
PAGE_URL = "https://www.gdt.gov.vn/wps/portal/home/hct"
SEARCH_TYPES = {
    "11": "Danh sách hộ kinh doanh và mức thuế phải nộp",
    "10": "Danh sách hộ kinh doanh không thuộc diện nộp thuế GTGT",
    "12": "Danh sách hộ kinh doanh tạm nghỉ kinh doanh được miễn, giảm thuế",
    "04": "Danh sách hộ kinh doanh nghỉ, bỏ kinh doanh",
    "03": "Danh sách hộ kinh doanh điều chỉnh thông tin và tiền thuế",
}


class InvalidResponseError(ValueError):
    # Nhóm phản hồi có thể thử lại sau khi lấy phiên/CAPTCHA mới.
    pass


def text(element):
    return " ".join(" ".join(element.itertext()).split())


def load_divisions(path):
    # CSV đã lưu đủ quan hệ ba cấp, không cần đối chiếu tên qua GDT.
    fields = {"maTinh", "tenTinh", "maHuyen", "tenHuyen", "maXa", "tenXa"}
    divisions = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if (
            len(reader.fieldnames or []) != len(fields)
            or set(reader.fieldnames or []) != fields
        ):
            raise ValueError(f"{path}: cần đủ 6 cột mã và tên tỉnh, huyện, xã.")
        for number, row in enumerate(reader, 2):
            if set(row) != fields or any(
                not isinstance(value, str) or not value.strip()
                for value in row.values()
            ):
                raise ValueError(f"{path}, dòng {number}: thiếu hoặc thừa dữ liệu.")
            row = {key: value.strip() for key, value in row.items()}
            if not (
                re.fullmatch(r"[0-9]{3}", row["maTinh"])
                and re.fullmatch(r"[0-9]{5}", row["maHuyen"])
                and re.fullmatch(r"[0-9]{7}", row["maXa"])
                and row["maHuyen"].startswith(row["maTinh"])
                and row["maXa"].startswith(row["maHuyen"])
            ):
                raise ValueError(f"{path}, dòng {number}: mã GDT ba cấp không hợp lệ.")
            if row["maXa"] in seen:
                raise ValueError(f"{path}, dòng {number}: trùng mã xã {row['maXa']}.")
            seen.add(row["maXa"])
            divisions.append(row)
    if not divisions:
        raise ValueError(f"{path}: danh sách địa bàn rỗng.")
    return divisions


def captcha_details(body):
    # Trang GDT dùng UID của ảnh CAPTCHA làm UUID trong request tra cứu.
    document = html.fromstring(body)
    if document.xpath("//title[normalize-space()='Request Rejected']"):
        raise ValueError("GDT từ chối request tải trang (Request Rejected).")
    sources = document.xpath("//*[@id='captchaCtn']/@src")
    if len(sources) != 1:
        raise ValueError("Không tìm thấy ảnh CAPTCHA trên trang GDT.")
    query = parse_qs(urlsplit(sources[0]).query)
    if not query.get("uid"):
        raise ValueError("Ảnh CAPTCHA thiếu UID của phiên.")
    return query["uid"][0], sources[0]


def result_url(credentials, province, district, ward, search_type, page):
    # Dùng đủ ba mã địa bàn đã lưu, Kỳ lập bộ vẫn để trống.
    params = {
        "maTinh": province,
        "maHuyen": district,
        "maXa": ward,
        "hoTen": "",
        "kyLb": "",
        "diaChi": "",
        "maSoThue": "",
        "searchType": search_type,
        **credentials,
        "pageNumber": str(page),
    }
    return BASE_URL + "results.jsp?" + urlencode(params)


def parse_results(body, page):
    if not body.strip():
        raise InvalidResponseError(
            "Máy chủ trả về nội dung rỗng. Hãy kiểm tra lại phiên tra cứu, UUID và CAPTCHA."
        )
    document = html.fromstring(body)
    if document.xpath("//title[normalize-space()='Request Rejected']"):
        raise InvalidResponseError("GDT từ chối request tra cứu (Request Rejected).")
    notices = [
        text(element)
        for element in document.xpath(
            "//div[@class='message-info' or @class='message-error']"
        )
    ]
    for notice in notices:
        if "mã xác nhận" in notice.casefold():
            raise InvalidResponseError(f"GDT báo lỗi CAPTCHA: {notice}")
    if "Không tìm thấy kết quả" in notices:
        return {"columns": [], "rows": [], "next_page": None}
    tables = document.xpath(
        "//table[contains(concat(' ', @class, ' '), ' ta_border ')]"
    )
    if len(tables) != 1:
        raise InvalidResponseError(
            "Không có bảng kết quả hợp lệ. Kiểm tra CAPTCHA hoặc phiên."
        )
    table = tables[0]
    header_rows = table.xpath("./tr[th] | ./thead/tr[th]")
    # Trải các ô rowspan/colspan thành lưới để giữ đúng vị trí cột.
    grid = {}
    for row_number, row in enumerate(header_rows):
        column = 0
        for cell in row.xpath("./th"):
            while (row_number, column) in grid:
                column += 1
            width = int(cell.get("colspan", "1"))
            for down in range(int(cell.get("rowspan", "1"))):
                for across in range(width):
                    grid[row_number + down, column + across] = text(cell)
            column += width
    if not grid:
        raise ValueError("Bảng kết quả thiếu tiêu đề.")
    columns = []
    # Ghép nhiều tầng tiêu đề, ví dụ Địa chỉ KD / Cũ và Địa chỉ KD / Mới.
    for column in range(1 + max(column for _, column in grid)):
        labels = []
        for row in range(len(header_rows)):
            label = grid.get((row, column), "")
            if label and (not labels or labels[-1] != label):
                labels.append(label)
        columns.append(" / ".join(labels))
    if len(set(columns)) != len(columns):
        raise ValueError("Tiêu đề cột bị trùng.")
    rows = []
    # Giữ dữ liệu dạng chuỗi để bảo toàn số 0 đầu mã số thuế và cách ghi tiền.
    for row in table.xpath("./tr[td] | ./tbody/tr[td]"):
        values = [text(cell) for cell in row.xpath("./td")]
        if len(values) != len(columns):
            raise ValueError(f"Số ô dữ liệu {len(values)} khác số cột {len(columns)}.")
        rows.append(dict(zip(columns, values, strict=True)))
    following = document.xpath("//*[@id='nextPage']/@href")
    # Kiểm tra trang trả về và lấy số trang tiếp theo từ liên kết JavaScript.
    current = document.xpath("//*[@id='tableNavigator']//span")
    if current:
        if len(current) != 1 or text(current[0]) != f"Trang: {page}":
            raise ValueError("Trang trả về khác trang được yêu cầu.")
    elif page != 1 or following:
        raise ValueError("Thiếu thông tin phân trang.")
    next_page = None
    if following:
        match = re.fullmatch(r"javascript:goToPage\((\d+)\);?", following[0].strip())
        if not match or int(match[1]) != page + 1:
            raise ValueError("Liên kết trang tiếp theo không hợp lệ.")
        next_page = int(match[1])
    return {"columns": columns, "rows": rows, "next_page": next_page}
