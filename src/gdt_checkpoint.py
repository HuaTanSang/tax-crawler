import fcntl
import hashlib
import json
import os
import re
from contextlib import ExitStack
from datetime import UTC, datetime

from gdt_data import SEARCH_TYPES


def cursor(division, search_type, page):
    return {
        "province_code": division["maTinh"],
        "district_code": division["maHuyen"],
        "ward_code": division["maXa"],
        "search_type": search_type,
        "page": page,
    }


class Checkpoint:
    def __init__(self, directory, divisions):
        self.directory = directory
        self.path = directory / "checkpoint.json"
        self.divisions = divisions
        self.positions = {row["maXa"]: index for index, row in enumerate(divisions)}
        self.search_types = tuple(SEARCH_TYPES)
        self.source_hash = hashlib.sha256(
            json.dumps(
                [divisions, self.search_types], sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.files = ExitStack()
        try:
            # Khóa tệp riêng vì checkpoint.json được thay thế sau mỗi trang.
            lock = self.files.enter_context((self.directory / "crawl.lock").open("a+b"))
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(
                    f"Đang có job khác sử dụng {self.directory}."
                ) from error
            if self.path.exists():
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
                self._validate()
                self.output = self.directory / self.state["output"]
                self.file = self.files.enter_context(self.output.open("r+b"))
                offset = self.state["offset"]
                size = self.output.stat().st_size
                if size < offset:
                    raise ValueError(f"{self.output}: output ngắn hơn mốc checkpoint.")
                if offset:
                    self.file.seek(offset - 1)
                    if self.file.read(1) != b"\n":
                        raise ValueError(f"{self.path}: mốc không kết thúc một trang.")
                self.file.seek(offset)
                if size > offset:
                    self.file.truncate()
                    self.file.flush()
                    os.fsync(self.file.fileno())
            else:
                if any(self.directory.glob("*.jsonl")):
                    raise ValueError(
                        f"{self.directory}: có output nhưng thiếu checkpoint."
                    )
                self.output = (
                    self.directory / f"gdt-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.jsonl"
                )
                self.file = self.files.enter_context(self.output.open("x+b"))
                os.fsync(self.file.fileno())
                self._write_state(
                    {
                        "output": self.output.name,
                        "source_hash": self.source_hash,
                        "offset": 0,
                        "next_query": cursor(
                            self.divisions[0], self.search_types[0], 1
                        ),
                    }
                )
        except BaseException:
            self.files.close()
            raise
        return self

    def __exit__(self, *args):
        return self.files.__exit__(*args)

    def _validate(self):
        state = self.state
        if (
            not isinstance(state, dict)
            or set(state) != {"output", "source_hash", "offset", "next_query"}
            or state["source_hash"] != self.source_hash
            or not isinstance(state["output"], str)
            or not re.fullmatch(r"gdt-[0-9]{8}T[0-9]{12}Z\.jsonl", state["output"])
            or type(state["offset"]) is not int
            or state["offset"] < 0
        ):
            raise ValueError(
                f"{self.path}: checkpoint hỏng hoặc danh sách địa bàn đã đổi."
            )
        query = state["next_query"]
        if query is None:
            if not state["offset"]:
                raise ValueError(f"{self.path}: hoàn tất nhưng chưa có dữ liệu.")
            return
        if (
            not isinstance(query, dict)
            or not isinstance(query.get("ward_code"), str)
            or query["ward_code"] not in self.positions
            or query.get("search_type") not in self.search_types
            or type(query.get("page")) is not int
            or query["page"] < 1
            or query
            != cursor(
                self.divisions[self.positions[query["ward_code"]]],
                query["search_type"],
                query["page"],
            )
        ):
            raise ValueError(f"{self.path}: vị trí tiếp tục không hợp lệ.")
        if not state["offset"] and query != cursor(
            self.divisions[0], self.search_types[0], 1
        ):
            raise ValueError(f"{self.path}: thiếu dữ liệu trước vị trí tiếp tục.")

    @property
    def query(self):
        query = self.state["next_query"]
        if query is None:
            return None
        return (
            self.divisions[self.positions[query["ward_code"]]],
            query["search_type"],
            query["page"],
        )

    def _write_state(self, state):
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as target:
            json.dump(state, target, ensure_ascii=False)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, self.path)
        descriptor = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.state = state

    def save(self, parsed):
        division, search_type, page = self.query
        following = parsed["next_page"]
        next_query = None
        if following is not None:
            if type(following) is not int or following != page + 1:
                raise ValueError("Trang tiếp theo không hợp lệ; không ghi dữ liệu.")
            next_query = cursor(division, search_type, following)
        else:
            search_index = self.search_types.index(search_type) + 1
            division_index = self.positions[division["maXa"]]
            if search_index == len(self.search_types):
                search_index = 0
                division_index += 1
            if division_index < len(self.divisions):
                next_query = cursor(
                    self.divisions[division_index], self.search_types[search_index], 1
                )
        item = {
            **self.state["next_query"],
            "province": division["tenTinh"],
            "district": division["tenHuyen"],
            "ward": division["tenXa"],
            "list_name": SEARCH_TYPES[search_type],
            **parsed,
        }
        self.file.write((json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8"))
        self.file.flush()
        os.fsync(self.file.fileno())
        self._write_state(
            {**self.state, "offset": self.file.tell(), "next_query": next_query}
        )
        return item
