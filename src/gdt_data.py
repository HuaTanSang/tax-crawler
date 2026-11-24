import re
import unicodedata
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


def options(body):
    document = html.fromstring(body.strip() or "<html></html>")
    return [
        (option.get("value"), text(option))
        for option in document.xpath("//option")
        if option.get("value") and "hết" not in text(option).casefold()
    ]


def name_key(name):
    # Chuẩn hóa biến thể tên để đối chiếu, tên gốc vẫn được giữ trong kết quả.
    name = unicodedata.normalize("NFD", name.casefold().replace("đ", "d"))
    name = "".join(
        character for character in name if not unicodedata.combining(character)
    )
    name = re.sub(r"^(tinh|thanh pho|tp\.?)\s+", "", name)
    name = " ".join(name.split())
    return "hue" if name == "thua thien hue" else name


def match_locations(available, requested):
    # Ưu tiên tên nguyên văn và chỉ nhận địa bàn khi tìm được đúng một mã.
    matched = []
    missing = []
    for name in requested:
        candidates = [code for code, label in available if label == name]
        if not candidates:
            candidates = [
                code for code, label in available if name_key(label) == name_key(name)
            ]
        if len(candidates) == 1:
            matched.append((candidates[0], name))
        else:
            missing.append(name)
    return matched, missing


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


def result_url(credentials, province, ward, search_type, page):
    # Quận/Huyện và Kỳ lập bộ để trống theo yêu cầu của luồng tra cứu.
    params = {
        "maTinh": province,
        "maHuyen": "",
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
    empty = document.xpath("//div[@class='message-info']")
    if empty and text(empty[0]) == "Không tìm thấy kết quả":
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
