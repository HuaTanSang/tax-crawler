import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlencode

import scrapy
from lxml.etree import LxmlError
from scrapy.crawler import CrawlerProcess
from scrapy.utils.defer import maybe_deferred_to_future

from gdt_data import (
    BASE_URL,
    PAGE_URL,
    SEARCH_TYPES,
    InvalidResponseError,
    captcha_details,
    match_locations,
    options,
    parse_results,
    result_url,
)
from gdt_ocr import get_captcha

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"


class GdtSpider(scrapy.Spider):
    name = "gdt"
    allowed_domains = ("www.gdt.gov.vn",)
    custom_settings: ClassVar = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 30,
        "LOG_LEVEL": "INFO",
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/158.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        },
    }

    def __init__(self, divisions, **kwargs):
        super().__init__(**kwargs)
        self.divisions = divisions
        self.credentials = {}
        self.headers = {"Referer": PAGE_URL, "X-Requested-With": "XMLHttpRequest"}

    async def fetch(self, url, headers=None):
        # Dùng downloader của Scrapy để mọi request cùng hưởng cookie và cơ chế retry.
        request = scrapy.Request(
            url, headers=self.headers if headers is None else headers, dont_filter=True
        )
        response = await maybe_deferred_to_future(self.crawler.engine.download(request))
        if response.status != 200:
            raise RuntimeError(
                f"GDT trả HTTP {response.status} cho {url.split('?')[0]}."
            )
        return response

    async def renew_session(self):
        # OCR có thể đọc trống, nên thử tối đa ba ảnh thuộc ba phiên mới.
        for attempt in range(3):
            response = await self.fetch(
                PAGE_URL,
                {
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "no-cache",
                },
            )
            try:
                uid, image_url = captcha_details(response.text)
            except (ValueError, LxmlError):
                (OUTPUT / "last_form.html").write_bytes(response.body)
                raise
            image_response = await self.fetch(
                response.urljoin(image_url),
                {
                    "Referer": PAGE_URL,
                    "Cache-Control": "no-cache",
                },
            )
            if not image_response.body or not image_response.headers.get(
                "Content-Type", b""
            ).lower().startswith(b"image/"):
                raise ValueError("Không tải được ảnh CAPTCHA.")
            image = OUTPUT / "captcha.png"
            image.write_bytes(image_response.body)
            try:
                captcha = get_captcha(image)
            except ValueError as error:
                self.logger.warning("OCR lần %s thất bại: %s", attempt + 1, error)
                continue
            self.credentials = {"uuid": uid, "captcha": captcha}
            # Chỉ thay cặp UUID/CAPTCHA sau khi đã đọc được mã của đúng ảnh.
            self.logger.info("Đã lấy phiên và nhận diện CAPTCHA mới.")
            return
        raise RuntimeError("OCR thất bại sau 3 ảnh CAPTCHA.")

    def resolve_locations(self, body, requested, context):
        # Tệp JSON xác định địa bàn cần lấy, danh sách GDT cung cấp mã truy vấn.
        matched, missing = match_locations(options(body), requested)
        if missing:
            self.logger.error(
                "Địa bàn chưa có mã GDT trong %s: %s", context, ", ".join(missing)
            )
        return matched

    async def result_page(self, province, ward, search_type, page):
        # Một lần tra cứu ban đầu và tối đa ba lần đổi phiên cho cùng trang.
        for attempt in range(4):
            response = await self.fetch(
                result_url(self.credentials, province[0], ward[0], search_type, page)
            )
            try:
                return parse_results(response.text, page)
            except InvalidResponseError as error:
                # Giữ phản hồi để chẩn đoán trước khi lấy CAPTCHA mới và thử lại.
                (OUTPUT / "last_response.html").write_bytes(response.body)
                if attempt == 3:
                    raise RuntimeError("Trang vẫn lỗi sau 3 lần đổi phiên.") from error
                self.logger.warning(
                    "%s / %s / %s / trang %s: %s Lấy phiên mới, thử lại lần %s/3.",
                    province[1],
                    ward[1],
                    search_type,
                    page,
                    error,
                    attempt + 1,
                )
                await self.renew_session()
            except (ValueError, LxmlError):
                # Lỗi cấu trúc dữ liệu cần kiểm tra parser, đổi CAPTCHA sẽ không sửa được.
                (OUTPUT / "last_response.html").write_bytes(response.body)
                raise

    async def start(self):
        # Đi tuần tự để khi đổi phiên, các request tiếp theo dùng ngay mã mới.
        OUTPUT.mkdir(parents=True, exist_ok=True)
        try:
            await self.renew_session()
            response = await self.fetch(BASE_URL + "json_option.jsp?cmd=GET_DS_TINH")
            provinces = self.resolve_locations(
                response.text, self.divisions, "tỉnh/thành"
            )
            for province in provinces:
                query = urlencode(
                    {"cmd": "GET_DS_XA", "maTinh": province[0], "maHuyen": ""}
                )
                response = await self.fetch(BASE_URL + "json_option.jsp?" + query)
                wards = self.resolve_locations(
                    response.text, self.divisions[province[1]], province[1]
                )
                for ward in wards:
                    for search_type in SEARCH_TYPES:
                        page = 1
                        while page is not None:
                            parsed = await self.result_page(
                                province, ward, search_type, page
                            )
                            yield {
                                # Một item xuất ra JSONL tương ứng một trang kết quả.
                                "province_code": province[0],
                                "province": province[1],
                                "ward_code": ward[0],
                                "ward": ward[1],
                                "search_type": search_type,
                                "list_name": SEARCH_TYPES[search_type],
                                "page": page,
                                **parsed,
                            }
                            page = parsed["next_page"]
        except Exception:
            self.logger.exception(
                "Job dừng do lỗi. Các trang đã xuất được giữ trong tệp kết quả."
            )


def main():
    argparse.ArgumentParser(description="Crawl thông tin hộ khoán GDT.").parse_args()
    if shutil.which("tesseract") is None:
        raise SystemExit("Cần cài Tesseract OCR: sudo apt install tesseract-ocr")
    try:
        # Kiểm tra cấu trúc danh sách địa bàn trước khi gửi request lên GDT.
        divisions = json.loads(
            (ROOT / "data" / "administrative_division.json").read_text(encoding="utf-8")
        )
        if (
            not isinstance(divisions, dict)
            or not divisions
            or not all(
                isinstance(name, str)
                and name.strip()
                and isinstance(wards, list)
                and wards
                and all(isinstance(ward, str) and ward.strip() for ward in wards)
                for name, wards in divisions.items()
            )
        ):
            raise ValueError(
                "Tệp địa bàn phải chứa tên tỉnh/thành và danh sách tên xã/phường."
            )
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT / f"gdt-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.jsonl"
    # Tách tệp theo từng lượt chạy để bảo toàn dữ liệu của những lượt trước.
    process = CrawlerProcess(
        {
            "FEEDS": {str(output): {"format": "jsonlines", "encoding": "utf-8"}},
        }
    )
    crawler = process.create_crawler(GdtSpider)
    process.crawl(crawler, divisions=divisions)
    process.start()
    print(f"Tệp dữ liệu: {output}")
    stats = crawler.stats.get_stats()
    # Crawl xong nhưng còn lỗi đối chiếu địa bàn cũng được báo là chưa hoàn tất.
    if stats.get("finish_reason") != "finished" or stats.get("log_count/ERROR", 0):
        raise SystemExit(
            "Job chưa hoàn tất. Xem đường dẫn phản hồi lỗi được ghi trong log."
        )


if __name__ == "__main__":
    main()
