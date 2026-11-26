# Tax crawler

This script uses Scrapy to collect household business information from [GDT](https://www.gdt.gov.vn/wps/portal/home/hct). It uses administrative divisions from before 01/07/2025 (1 July 2025).

## Prerequisites

- Windows: use WSL with Ubuntu and follow the instructions below. On macOS and Ubuntu, go straight to installation.

## Installation

### 1. Install Git, curl and Tesseract OCR

Tesseract is a system program that reads CAPTCHA images. Install it separately from the Python dependencies.
Follow the instructions for your operating system.

**Ubuntu / WSL (Ubuntu):**

```sh
sudo apt update
sudo apt install -y git curl ca-certificates tesseract-ocr
```

**macOS:** if you don't have [Homebrew](https://brew.sh/), install it with the command below, then follow
the **Next steps** shown at the end of the installation to add `brew` to your PATH:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install the tools:

```sh
brew install git curl tesseract
```

The Tesseract installation commands follow the [official documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).
Check that the tools are installed:

```sh
git --version
curl --version
tesseract --version
```

### 2. Install uv and Python 3.12

The remaining steps apply to Ubuntu, WSL/Ubuntu and macOS.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) with the standalone installer:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"
uv --version
```

Use uv to [install Python 3.12](https://docs.astral.sh/uv/guides/install-python/):

```sh
uv python install 3.12
```

### 3. Clone the repository and install dependencies

```sh
git clone https://github.com/HuaTanSang/tax-crawler.git
cd tax-crawler
uv sync --locked
uv run --locked python --version
```

### 4. Install the pre-commit hook

Run this once in the cloned repository to enable automatic checks before each commit:

```sh
uv run --locked pre-commit install
```

## Run the job

From the `tax-crawler` directory, run:

```sh
uv run --locked src/gdt_spider.py
```

To crawl one province, pass its GDT code from `data/ds_full.csv`. For example,
An Giang is `805`:

```sh
uv run --locked src/gdt_spider.py --province 805
```

Use `--province CODE1 CODE2` to select several provinces. Repeated codes are
processed once; unknown codes are rejected before any requests. Without this
option, the job crawls all provinces. Provinces and their divisions are processed
sequentially in CSV order, including all five search types and every result page.

Each province has its own directory:

```text
output/<province-code>/
  gdt-<first-start-timestamp>.jsonl
  checkpoint.json
  crawl.lock
  captcha.png
  last_form.html       # saved when the lookup form is invalid
  last_response.html   # saved when a result page is invalid
```

Each JSONL line contains one result page. The job saves the complete page to disk
before updating the checkpoint, including pages with no results. The checkpoint
records the next division/search type/page, the output filename, the confirmed
byte length, and a fingerprint of that province's ordered division list and
search types.

Press **Ctrl+C once** and wait for Scrapy to close. Run the same command later to
resume each selected province using a fresh session and CAPTCHA. The job appends
to the original timestamped file; it does not create another file on resume.
You can select a different province while another is paused. Completed provinces
are checked and skipped without fetching another session or result page.

After an abrupt stop, bytes beyond the confirmed checkpoint length are discarded
and the unconfirmed page is fetched again. This prevents duplicate pages caused
by resuming. An output shorter than the confirmed length, a missing output or
checkpoint, a malformed checkpoint, or a changed division list stops the job and
preserves the files for inspection. Keep the output and checkpoint together and
do not edit the division list while resuming. A file lock prevents two jobs from
writing the same province at once; the lock is released when the process ends.

To start a fresh crawl for a province, stop any job using it, move its entire
directory outside `output/` to keep the previous data, then run the command again.
Older output files in the root of `output/` are preserved and are not imported
into checkpoints. Resume protection does not remove duplicates already present
in GDT data or guarantee a fixed snapshot when GDT changes its results.

## Export to Excel

Convert the JSONL of each province directory into one `.xlsx` file per search type:

```sh
uv run --locked src/gdt_export.py output/805
```

Without a directory, every directory in `output/` that contains JSONL is exported.
Files are written next to the JSONL and named `<province>_<list name>.xlsx`, with
Vietnamese diacritics and punctuation removed and words joined by underscores, for
example `An_Giang_Danh_sach_ho_kinh_doanh_va_muc_thue_phai_nop.xlsx`. Running again
replaces them.

Each row is one household with the location metadata (`province_code`,
`district_code`, `ward_code`, `province`, `district`, `ward`)
followed by the source columns, including merged headers such as
`Địa chỉ KD / Cũ`. Cells are written as text, so tax codes keep leading zeros and
amounts stay as in the source. Only bytes confirmed by `checkpoint.json` are read,
so it is safe to export while a crawl is running. Pages without rows produce no
lines. A page whose columns differ from earlier pages of the same search type, or
a list longer than Excel's 1,048,576 rows, stops the export for that province
without leaving partial files.
