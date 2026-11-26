import argparse
import json
import os
import re
import unicodedata
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
# Giới hạn dòng mỗi sheet của Excel, tính cả dòng tiêu đề.
EXCEL_ROWS = 1_048_576
META = (
    "province_code",
    "district_code",
    "ward_code",
    "province",
    "district",
    "ward",
)


def file_stem(*parts):
    # Bỏ dấu tiếng Việt và dấu câu, nối các từ bằng dấu gạch dưới.
    text = unicodedata.normalize("NFD", " ".join(parts)).replace("đ", "d")
    text = "".join(
        char for char in text.replace("Đ", "D") if not unicodedata.combining(char)
    )
    return "_".join(re.findall(r"\w+", text))


def pages(directory):
    checkpoint = directory / "checkpoint.json"
    state = {}
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
    for path in sorted(directory.glob("*.jsonl")):
        # Chỉ đọc phần checkpoint đã xác nhận vì job crawl có thể đang ghi tiếp.
        limit = state["offset"] if state.get("output") == path.name else None
        read = 0
        with path.open("rb") as source:
            for number, line in enumerate(source, 1):
                if limit is not None and read >= limit:
                    break
                read += len(line)
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"{path}:{number}: dòng JSON không hợp lệ."
                    ) from error


def export(directory):
    outputs = {}
    try:
        for item in pages(directory):
            if not item["rows"]:
                continue
            fields = [*META, *item["columns"]]
            output = outputs.get(item["search_type"])
            if output is None:
                workbook = Workbook(write_only=True)
                sheet = workbook.create_sheet()
                sheet.append(fields)
                stem = file_stem(item["province"], item["list_name"])
                output = outputs[item["search_type"]] = {
                    "path": directory / f"{stem}.xlsx",
                    "workbook": workbook,
                    "sheet": sheet,
                    "fields": fields,
                    "rows": 0,
                }
            elif fields != output["fields"]:
                raise ValueError(
                    f"{directory}: searchType {item['search_type']} xã "
                    f"{item['ward_code']} trang {item['page']} có cột khác trang trước."
                )
            output["rows"] += len(item["rows"])
            if output["rows"] >= EXCEL_ROWS:
                raise ValueError(f"{output['path']}: vượt giới hạn dòng của Excel.")
            meta = [item[key] for key in META]
            for row in item["rows"]:
                # Giá trị ghi dạng chuỗi nên mã số thuế giữ số 0 ở đầu.
                output["sheet"].append([*meta, *(row[key] for key in item["columns"])])
    except BaseException:
        # Đóng sheet ghi dở để openpyxl kết thúc luồng ghi, không để lỗi khi dọn.
        for output in outputs.values():
            output["sheet"].close()
        raise
    for output in outputs.values():
        temporary = output["path"].with_name(output["path"].name + ".tmp")
        try:
            output["workbook"].save(temporary)
            os.replace(temporary, output["path"])
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    return [(output["path"], output["rows"]) for output in outputs.values()]


def main():
    parser = argparse.ArgumentParser(
        description="Chuyển JSONL của từng tỉnh thành mỗi searchType một tệp xlsx."
    )
    parser.add_argument(
        "directories",
        nargs="*",
        type=Path,
        metavar="THU_MUC_TINH",
        help="Thư mục tỉnh, ví dụ output/805; mặc định là mọi thư mục trong output/.",
    )
    args = parser.parse_args()
    directories = args.directories or sorted(
        path for path in OUTPUT.glob("*/") if any(path.glob("*.jsonl"))
    )
    if not directories:
        raise SystemExit(f"Không có thư mục tỉnh nào chứa JSONL trong {OUTPUT}.")
    failed = False
    for directory in directories:
        if not any(directory.glob("*.jsonl")):
            print(f"{directory}: không có tệp JSONL.")
            failed = True
            continue
        try:
            for path, rows in export(directory):
                print(f"{path}: {rows} dòng")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{directory}: lỗi {error!r}")
            failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
