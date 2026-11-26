import argparse
import csv
import shutil
from pathlib import Path
from typing import ClassVar

import scrapy
from lxml.etree import LxmlError
from scrapy.crawler import CrawlerProcess
from scrapy.utils.defer import maybe_deferred_to_future

from gdt_checkpoint import Checkpoint
from gdt_data import (
    PAGE_URL,
    InvalidResponseError,
    captcha_details,
    load_divisions,
    parse_results,
    result_url,
    select_provinces,
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

    def __init__(self, provinces, **kwargs):
        super().__init__(**kwargs)
        self.provinces = provinces
        self.completed = False
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
                (self.directory / "last_form.html").write_bytes(response.body)
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
            image = self.directory / "captcha.png"
            image.write_bytes(image_response.body)
            try:
                captcha = get_captcha(image)
            except ValueError as error:
                self.logger.warning("OCR lần %s thất bại: %s", attempt + 1, error)
                continue
            self.credentials = {"uuid": uid, "captcha": captcha}
            # Chỉ thay cặp UUID/CAPTCHA sau khi đã đọc được mã của đúng ảnh.
            self.logger.info("Đã lấy phiên mới; mã OCR: %s.", captcha)
            return
        raise RuntimeError("OCR thất bại sau 3 ảnh CAPTCHA.")

    async def result_page(self, division, search_type, page):
        # Một lần tra cứu ban đầu và tối đa 10 lần đổi phiên cho cùng trang.
        for attempt in range(11):
            response = await self.fetch(
                result_url(
                    self.credentials,
                    division["maTinh"],
                    division["maHuyen"],
                    division["maXa"],
                    search_type,
                    page,
                )
            )
            try:
                return parse_results(response.text, page)
            except InvalidResponseError as error:
                # Giữ phản hồi để chẩn đoán trước khi lấy CAPTCHA mới và thử lại.
                (self.directory / "last_response.html").write_bytes(response.body)
                if attempt == 10:
                    raise RuntimeError("Trang vẫn lỗi sau 3 lần đổi phiên.") from error
                self.logger.warning(
                    "%s / %s / %s / %s / trang %s: %s Lấy phiên mới, thử lại lần %s/3.",
                    division["tenTinh"],
                    division["tenHuyen"],
                    division["tenXa"],
                    search_type,
                    page,
                    error,
                    attempt + 1,
                )
                await self.renew_session()
            except (ValueError, LxmlError):
                # Lỗi cấu trúc dữ liệu cần kiểm tra parser, đổi CAPTCHA sẽ không sửa được.
                (self.directory / "last_response.html").write_bytes(response.body)
                raise

    async def start(self):
        # Đi tuần tự để khi đổi phiên, các request tiếp theo dùng ngay mã mới.
        try:
            for province, divisions in self.provinces.items():
                self.directory = OUTPUT / province
                with Checkpoint(self.directory, divisions) as checkpoint:
                    self.logger.info("Tệp dữ liệu: %s", checkpoint.output)
                    if checkpoint.query is None:
                        self.logger.info("Tỉnh %s đã hoàn tất; bỏ qua.", province)
                        continue
                    if shutil.which("tesseract") is None:
                        raise RuntimeError(
                            "Cần cài Tesseract OCR: sudo apt install tesseract-ocr"
                        )
                    self.logger.info("Tiếp tục từ %s", checkpoint.state["next_query"])
                    await self.renew_session()
                    while checkpoint.query is not None:
                        division, search_type, page = checkpoint.query
                        parsed = await self.result_page(division, search_type, page)
                        yield checkpoint.save(parsed)
            self.completed = True
        except Exception:
            self.logger.exception(
                "Job dừng do lỗi. Chạy lại cùng lệnh để tiếp tục checkpoint từng tỉnh."
            )


def main():
    parser = argparse.ArgumentParser(description="Crawl thông tin hộ khoán GDT.")
    parser.add_argument(
        "--province",
        nargs="+",
        action="extend",
        metavar="MA_TINH",
        help="Mã GDT của các tỉnh cần crawl; mặc định là tất cả tỉnh trong CSV.",
    )
    args = parser.parse_args()
    try:
        # Kiểm tra cấu trúc danh sách địa bàn trước khi gửi request lên GDT.
        divisions = load_divisions(ROOT / "data" / "ds_full.csv")
        provinces = select_provinces(divisions, args.province)
    except (OSError, ValueError, csv.Error) as error:
        raise SystemExit(str(error)) from error
    process = CrawlerProcess()
    crawler = process.create_crawler(GdtSpider)
    process.crawl(crawler, provinces=provinces)
    process.start()
    stats = crawler.stats.get_stats()
    # Chỉ báo hoàn tất khi Scrapy chạy hết và không có lỗi được ghi nhận.
    if (
        crawler.spider is None
        or not crawler.spider.completed
        or stats.get("finish_reason") != "finished"
        or stats.get("log_count/ERROR", 0)
    ):
        raise SystemExit(
            "Job chưa hoàn tất. Chạy lại cùng lệnh để tiếp tục checkpoint từng tỉnh."
        )
    print("Đã hoàn tất tất cả tỉnh được chọn.")


if __name__ == "__main__":
    main()
